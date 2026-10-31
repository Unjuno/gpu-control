from __future__ import annotations

import argparse
import json
import logging
import os
import re
import secrets
import time
import uuid
from urllib.parse import quote
from decimal import Decimal

from jsonschema import SchemaError as InvalidSchema
from sqlalchemy import String, and_, cast, or_, select, update

from .artifacts import (ArtifactStore, MAX_ARTIFACTS_PER_RUN,
                        MAX_RUN_ARTIFACT_BYTES, inspect_artifact_storage)
from .backends import Backend, Observation, ProviderAccountLeaseRequest, build_backends
from .config import Settings, load_workloads
from .registry import (candidate_plan_authorization_kind, default_registry,
                       supports_candidate_execution)
from .service import TERMINAL, digest
from .store import Store, control, runs
from .admission import (evaluate_admission, load_local_cpu_policy,
                        matches_registered_local_workload)
from .contracts import (PlanV2, ResultV2, plan_fingerprint,
                        validate_candidate_gpu_success, validate_result_binding)
from .candidate_receipts import verify_candidate_receipt
from .health import HEARTBEAT_STALE_SECONDS, heartbeat_is_stale
from .provider_evidence import build_signed_observation
from .runpod_inventory import (
    OBSERVATION_TTL_SECONDS,
    SOURCE as RUNPOD_EVIDENCE_SOURCE,
    collect_runpod_inventory,
    default_client as runpod_evidence_client,
)
from gpu_control.providers.runpod_current_pricing import RUNPOD_GRAPHQL_SPEC_REVISION
from .provider_selection import current_bound_candidate
from .provider_account_scope import derive_provider_account_scope

logger = logging.getLogger(__name__)
# Keep the historical module constant for callers while sharing its source.
WORKER_HEARTBEAT_STALE_SECONDS = HEARTBEAT_STALE_SECONDS
ARTIFACT_TTL_SECONDS = 30 * 24 * 3600
ARTIFACT_PRUNE_INTERVAL_SECONDS = 3600
PROVIDER_EVIDENCE_POLL_INTERVAL_SECONDS = 60


def _unset_json_value(column):
    """Match both SQL NULL and JSON null on SQLite and PostgreSQL."""
    return or_(column.is_(None), cast(column, String) == "null")


class Worker:
    """Short recoverable ticks, executed OUTSIDE the Vercel request lifecycle.

    A stale submitting job is reconciled, never blindly retried. Unknown submissions
    keep their admission slot until an operator/provider supplies reliable evidence.
    """
    def __init__(self, store: Store, settings: Settings, backends: dict[str, Backend], clock=time.time, *, registry=None, role="worker"):
        if role not in {"worker", "supervisor"}:
            raise ValueError("unsupported worker role")
        self.store, self.settings, self.backends, self.clock = store, settings, backends, clock
        self.registry = default_registry() if registry is None else registry
        self.role = role
        self.last_artifact_prune_at = 0
        self.last_provider_evidence_attempt_at = 0

    def _maybe_collect_runpod_evidence(self, now: int) -> None:
        """Poll catalog only from an explicitly enabled, idle normal worker."""
        if (self.role != "worker" or not self.settings.enable_runpod_evidence or
                not self.settings.runpod_api_key or
                now - self.last_provider_evidence_attempt_at < PROVIDER_EVIDENCE_POLL_INTERVAL_SECONDS):
            return
        try:
            workloads = load_workloads()
            if not any(workload.provider == "runpod" and workload.provider_resource_id and
                       workload.provider_data_center_id for workload in workloads.values()):
                return
            self.last_provider_evidence_attempt_at = now
            payload = collect_runpod_inventory(
                workloads, runpod_evidence_client(self.settings.runpod_api_key),
                observed_at=now, expires_at=now + OBSERVATION_TTL_SECONDS,
            )
            stored = self.store.read_provider_observation("runpod")
            version = (stored["version"] if stored else 0) + 1
            self.persist_provider_observation(
                provider="runpod", source=RUNPOD_EVIDENCE_SOURCE,
                source_revision=RUNPOD_GRAPHQL_SPEC_REVISION,
                version=version, expires_at=now + OBSERVATION_TTL_SECONDS,
                payload=payload, observed_at=now,
            )
        except Exception:
            # Provider polling is advisory and must never interrupt queue work.
            # Avoid exception text because HTTP/provider errors may include data.
            logger.warning("RunPod capability observation was not updated")

    def persist_provider_observation(self, *, provider: str, source: str,
                                     source_revision: str, version: int,
                                     expires_at: int, payload: dict,
                                     observed_at: int | None = None) -> bool:
        """Sign and persist one bounded read-only provider observation.

        Only the normal worker role can publish observations. Recovery supervisor
        ticks intentionally have no provider collection authority.
        """
        if self.role != "worker":
            raise RuntimeError("provider observations may only be published by the worker")
        private_key = self.settings.provider_evidence_signing_key_pem
        key_id = self.settings.provider_evidence_signing_key_id
        trusted_keys = self.settings.provider_evidence_trusted_keys
        if private_key is None or not key_id:
            raise RuntimeError("provider evidence signing is not configured")
        observed_at = int(self.clock()) if observed_at is None else observed_at
        envelope = build_signed_observation(
            provider=provider,
            source=source,
            source_revision=source_revision,
            version=version,
            observed_at=observed_at,
            expires_at=expires_at,
            payload=payload,
            key_id=key_id,
            private_key_pem=private_key,
        )
        return self.store.write_provider_observation(
            envelope, trusted_keys, now=observed_at)

    def _maybe_prune_artifacts(self, now: int) -> None:
        if (not self.settings.artifact_dir or
                now - self.last_artifact_prune_at < ARTIFACT_PRUNE_INTERVAL_SECONDS):
            return
        self.last_artifact_prune_at = now
        try:
            with self.store.engine.connect() as connection:
                rows = [dict(row) for row in connection.execute(
                    select(runs.c.id, runs.c.owner, runs.c.state, runs.c.result)).mappings()]
            removed = ArtifactStore(self.settings.artifact_dir).prune(rows, now=now)
            if removed["expired_files"] or removed["orphan_files"]:
                logger.info("Artifact retention removed expired=%d orphan=%d bytes=%d",
                            removed["expired_files"], removed["orphan_files"], removed["bytes_removed"])
        except Exception:
            # Retention maintenance must not stop queue processing. Retry on the
            # next interval; artifact reads still enforce expiry and digest.
            logger.exception("Artifact retention maintenance failed")

    @staticmethod
    def _current_local_registry_status(plan: PlanV2) -> tuple[bool, str | None]:
        configured = bool(os.environ.get("GATEWAY_WORKLOADS_JSON") or
                          os.environ.get("GATEWAY_WORKLOADS_FILE"))
        if not configured:
            return False, "local_workload_registry_unavailable"
        try:
            current_workloads = load_workloads()
        except (OSError, InvalidSchema, ValueError, TypeError, RecursionError):
            return False, "local_workload_registry_unavailable"
        if not matches_registered_local_workload(plan, current_workloads):
            return False, "local_workload_changed_before_start"
        return True, None

    def _persist_artifacts(self, job: dict, observation: Observation) -> dict | None:
        result = observation.result
        if result is None:
            if observation.artifacts:
                raise ValueError("artifacts require a result manifest")
            return None
        if not isinstance(result, dict) or result.get("artifacts") not in (None, []):
            raise ValueError("backend artifact metadata must be generated by the gateway")
        if len(observation.artifacts) > MAX_ARTIFACTS_PER_RUN:
            raise ValueError("artifact count limit exceeded")
        if any(not isinstance(item.data, bytes) for item in observation.artifacts):
            raise ValueError("artifact payload must be bytes")
        if sum(len(item.data) for item in observation.artifacts) > MAX_RUN_ARTIFACT_BYTES:
            raise ValueError("artifact total size limit exceeded")
        artifact_ids = [item.artifact_id for item in observation.artifacts]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("artifact IDs must be unique within a run")
        if not observation.artifacts:
            return result | {"artifacts": []}
        if not self.settings.artifact_dir:
            raise ValueError("artifact storage is not configured")
        now = int(self.clock())
        artifact_store = ArtifactStore(self.settings.artifact_dir)
        metadata = [artifact_store.put(
            job["owner"], job["id"], item.artifact_id, item.data,
            media_type=item.media_type, expires_at=now + ARTIFACT_TTL_SECONDS,
        ) for item in observation.artifacts]
        return result | {"artifacts": metadata}

    @staticmethod
    def _missing_backend_result(job: dict, *, cleanup_pending: bool) -> dict:
        """Persist an explicit failure envelope so lifecycle cleanup can recover."""
        plan = job["plan"]
        cleanup_state = "pending" if cleanup_pending else "not_required"
        if plan.get("schema_version") != 2:
            return {"failure_code": "missing_backend_result", "cleanup_state": cleanup_state}
        return {
            "schema_version": 2,
            "run_id": job["id"],
            "source_sha": plan["source_sha"],
            "plan_fingerprint": job["fingerprint"],
            "provider": plan["provider"],
            "image_digest": plan.get("image_digest"),
            "simulation": False,
            "gpu_used": None,
            "device": None,
            "exit_code": None,
            "started_at": None,
            "finished_at": None,
            "runtime_seconds": None,
            "metrics": {},
            "checks": [],
            "checksum": None,
            "artifacts": [],
            "known_cost_usd": None,
            "cost_classification": "UNKNOWN",
            "cleanup_state": cleanup_state,
            "failure_code": "missing_backend_result",
        }

    def claim(self):
        now = int(self.clock())
        token = uuid.uuid4().hex
        with self.store.transaction() as c:
            control_row = self.store.lock_control(c)
            heartbeat_column = control.c.supervisor_seen_at if self.role == "supervisor" else control.c.worker_seen_at
            c.execute(update(control).where(control.c.id == 1).values({heartbeat_column.key: now}))
            states = ["submitting", "submit_unknown", "running"]
            if self.role == "worker":
                states.insert(0, "queued")
            eligible = runs.c.lease_until <= now
            if self.role == "supervisor" and heartbeat_is_stale(now, control_row["worker_seen_at"]):
                # A dead worker may leave a 120-second submission lease. Once its
                # heartbeat is stale, recovery may inspect that intent early, but
                # it still never calls start() for a non-queued job.
                eligible = or_(eligible, runs.c.state == "submitting")
            row = c.execute(select(runs).where(
                runs.c.state.in_(states),
                eligible,
            ).order_by(runs.c.lease_until, runs.c.created_at).limit(1).with_for_update()).mappings().first()
            if row is None:
                return None
            job = dict(row)
            changes = {"lease_until": now + 120, "lease_token": token}
            if job["state"] == "queued":
                changes.update(state="submitting", started_at=now)
            elif job["state"] == "submitting":
                changes["state"] = "submit_unknown"
            c.execute(update(runs).where(runs.c.id == job["id"]).values(**changes))
            job.update(changes)
            job["was_queued"] = row["state"] == "queued"
            return job

    def update(self, job: dict, **values):
        with self.store.transaction() as c:
            return c.execute(update(runs).where(runs.c.id == job["id"], runs.c.lease_token == job["lease_token"]).values(**values)).rowcount == 1

    def _terminal_record(self, job: dict, state: str, result=None, error=""):
        if state not in TERMINAL:
            raise ValueError("Invalid terminal state")
        record_version = 1
        if isinstance(job.get("plan"), dict) and job["plan"].get("schema_version") == 2:
            record_version = 2
            if result is not None:
                allowed_extra = {"logs", "logs_truncated", "failure_code", "candidate_receipt"}
                try:
                    if not isinstance(result, dict):
                        raise ValueError("result must be an object")
                    core = {key: value for key, value in result.items() if key in ResultV2.model_fields}
                    extras = {key: value for key, value in result.items() if key not in ResultV2.model_fields}
                    if set(extras) - allowed_extra:
                        raise ValueError("unexpected result fields")
                    validated_plan = PlanV2.model_validate_json(json.dumps(job["plan"], allow_nan=False))
                    validated_result = ResultV2.model_validate_json(json.dumps(core, allow_nan=False))
                    validate_result_binding(validated_plan, job["fingerprint"], validated_result)
                    if state == "succeeded" and (validated_result.exit_code != 0 or validated_result.simulation or
                                                   validated_result.provider == "local_cpu" and validated_result.gpu_used is not False):
                        raise ValueError("terminal result does not prove local CPU success")
                    if state == "succeeded" and validated_plan.selection_binding is not None:
                        validate_candidate_gpu_success(validated_result)
                    result = validated_result.model_dump(mode="json") | extras
                except (ValueError, TypeError, json.JSONDecodeError):
                    state, error = "failed", "result_integrity_failed"
                    result = {"failure_code": "result_integrity_failed"}
        if result is not None:
            raw = json.dumps(result, allow_nan=False).encode()
            if len(raw) > self.settings.max_output_bytes * 3:
                result = {"result_omitted": True, "reason": "result_size_limit"}
        return state, result, error, record_version

    def finish(self, job: dict, state: str, result=None, error=""):
        state, result, error, record_version = self._terminal_record(job, state, result, error)
        with self.store.transaction() as c:
            self.store.lock_control(c)
            row = c.execute(select(runs).where(runs.c.id == job["id"])).mappings().one()
            if row["lease_token"] != job["lease_token"] or row["state"] in TERMINAL:
                return
            if row["slot_reserved"]:
                c.execute(update(control).where(control.c.id == 1).values(active_count=control.c.active_count - 1))
            cleanup_state = ((result or {}).get("cleanup_state", "unknown") if isinstance(result, dict)
                             else "unknown")
            if cleanup_state not in {"not_required", "pending", "complete", "unknown"}:
                cleanup_state = "unknown"
            c.execute(update(runs).where(runs.c.id == job["id"]).values(
                state=state, result=result, error=error, slot_reserved=False,
                lease_until=0, lease_token="", finished_at=int(self.clock()),
                cleanup_state=cleanup_state, record_version=record_version))

    def _provider_lease_cleanup_context(self, job: dict, backend, handle: dict):
        intent = job.get("submission_intent")
        if not isinstance(intent, dict) or "account_scope" not in intent:
            return None
        if intent.get("provider") != "runpod" or job.get("plan", {}).get("provider") != "runpod":
            raise RuntimeError("provider account lease identity mismatch")
        provider_job_id = getattr(backend, "provider_job_id", None)
        if not callable(provider_job_id):
            raise RuntimeError("provider adapter cannot identify the leased resource")
        resource_id = provider_job_id(handle)
        if not isinstance(resource_id, str) or not resource_id or len(resource_id) > 512:
            raise RuntimeError("provider adapter returned an invalid resource identity")
        now = int(self.clock())
        lease = self.store.read_provider_account_lease_for_run(
            run_id=job["id"], owner=job["owner"], plan_fingerprint=job["fingerprint"],
            run_lease_token=job["lease_token"], now=now, provider="runpod",
        )
        if lease is None or lease.account_scope != intent.get("account_scope") or lease.provider_job_id != resource_id:
            raise RuntimeError("provider account lease does not match the cleanup resource")
        if lease.state == "active":
            changed = self.store.transition_provider_account_lease_for_run(
                account_scope=lease.account_scope, run_id=job["id"], owner=job["owner"],
                plan_fingerprint=job["fingerprint"], lease_token=lease.lease_token,
                run_lease_token=job["lease_token"],
                core_plan_fingerprint=lease.core_plan_fingerprint,
                authorization_id=lease.authorization_id, expected_state="active",
                new_state="cleanup_pending", now=now, provider_job_id=resource_id,
            )
            if not changed:
                raise RuntimeError("provider lease changed before cleanup")
            lease = lease.__class__(**(lease.__dict__ | {"state": "cleanup_pending"}))
        if lease.state != "cleanup_pending":
            raise RuntimeError("provider account lease is not ready for cleanup")
        return lease, resource_id

    def finish_after_provider_cleanup(self, job: dict, state: str, result: dict,
                                     error: str, lease_context) -> bool:
        if lease_context is None:
            self.finish(job, state, result, error)
            return True
        lease, resource_id = lease_context
        state, result, error, record_version = self._terminal_record(
            job, state, result, error)
        return self.store.finish_run_after_provider_cleanup(
            account_scope=lease.account_scope, run_id=job["id"], owner=job["owner"],
            plan_fingerprint=job["fingerprint"], lease_token=lease.lease_token,
            run_lease_token=job["lease_token"],
            core_plan_fingerprint=lease.core_plan_fingerprint,
            authorization_id=lease.authorization_id, provider_job_id=resource_id,
            cleanup_confirmed=True, state=state, result=result, error=error,
            record_version=record_version, now=int(self.clock()), provider="runpod",
        )

    def _reserve_runpod_account_lease(self, job: dict, backend, *, attempt: int, now: int):
        """Prepare and atomically persist the exact RunPod allocation challenge."""
        if not all(callable(getattr(backend, name, None)) for name in (
                "prepare_provider_account_lease", "start_candidate_bound_with_account_lease",
                "reconcile_candidate_bound_with_account_lease", "provider_job_id")):
            return None
        credential = self.settings.runpod_api_key
        account_scope_id = self.settings.runpod_account_scope_id
        try:
            hmac_key = self.settings.provider_account_scope_hmac_key
            request = backend.prepare_provider_account_lease(job)
        except Exception:
            return None
        if (not credential or not account_scope_id or hmac_key is None or
                not isinstance(request, ProviderAccountLeaseRequest) or
                not isinstance(request.core_plan_fingerprint, str) or
                re.fullmatch(r"[0-9a-f]{64}", request.core_plan_fingerprint) is None or
                not isinstance(request.authorization_id, str) or
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", request.authorization_id) is None or
                not isinstance(request.request_challenge, dict)):
            return None
        try:
            scope = derive_provider_account_scope("runpod", account_scope_id, hmac_key)
        except (TypeError, ValueError):
            return None
        return self.store.reserve_provider_account_lease_with_submission_intent(
            provider="runpod", account_scope=scope, run_id=job["id"], owner=job["owner"],
            plan_fingerprint=job["fingerprint"],
            core_plan_fingerprint=request.core_plan_fingerprint,
            authorization_id=request.authorization_id, run_lease_token=job["lease_token"],
            attempt=attempt, request_challenge=request.request_challenge, now=now,
        )

    def _load_runpod_account_lease(self, job: dict, backend, *, now: int):
        intent = job.get("submission_intent")
        if (not isinstance(intent, dict) or intent.get("provider") != "runpod" or
                "account_scope" not in intent):
            return None
        if not callable(getattr(backend, "reconcile_candidate_bound_with_account_lease", None)):
            return None
        return self.store.read_provider_account_lease_for_run(
            run_id=job["id"], owner=job["owner"], plan_fingerprint=job["fingerprint"],
            run_lease_token=job["lease_token"], now=now, provider="runpod",
        )

    def _activate_runpod_lease_for_handle(self, job: dict, backend, handle: dict, *, now: int) -> bool:
        intent = job.get("submission_intent")
        if not isinstance(intent, dict) or "account_scope" not in intent:
            return True
        lease = self._load_runpod_account_lease(job, backend, now=now)
        if lease is None:
            return False
        try:
            resource_id = backend.provider_job_id(handle)
        except Exception:
            return False
        if not isinstance(resource_id, str) or not resource_id or len(resource_id) > 512:
            return False
        if lease.state in {"active", "cleanup_pending"}:
            return lease.provider_job_id == resource_id
        if lease.state not in {"submitting", "uncertain"}:
            return False
        return self.store.transition_provider_account_lease_for_run(
            account_scope=lease.account_scope, run_id=job["id"], owner=job["owner"],
            plan_fingerprint=job["fingerprint"], lease_token=lease.lease_token,
            run_lease_token=job["lease_token"],
            core_plan_fingerprint=lease.core_plan_fingerprint,
            authorization_id=lease.authorization_id, expected_state=lease.state,
            new_state="active", provider_job_id=resource_id, now=now, provider="runpod",
        )

    def tick(self) -> bool:
        now = int(self.clock())
        self._maybe_prune_artifacts(now)
        job = self.claim()
        if job is None:
            self._maybe_collect_runpod_evidence(int(self.clock()))
            return False
        now = int(self.clock())
        plan = job["plan"]
        backend = self.backends.get(plan["provider"])
        if backend is None:
            if job["was_queued"]:
                self.finish(job, "failed", error="provider_not_configured")
            else:
                self.update(job, error="provider_not_configured", lease_until=now + 30)
            return True
        if job["was_queued"]:
            registration = self.registry.get(plan["provider"])
            enabled = registration is not None and registration.enabled(self.settings)
            if not enabled:
                self.finish(job, "failed", error="new_submissions_disabled")
                return True
            local_admission = job.get("admission")
            if local_admission is not None:
                validated_plan = None
                policy_valid = False
                try:
                    validated_plan = PlanV2.model_validate_json(json.dumps(plan, allow_nan=False))
                    policy = load_local_cpu_policy()
                    decision = evaluate_admission(validated_plan, policy, now)
                    policy_valid = (local_admission.get("mode") == "local_policy" and
                                    decision.allowed and
                                    decision.policy_digest == local_admission.get("policy_digest") and
                                    decision.valid_until == local_admission.get("valid_until") and
                                    plan_fingerprint(validated_plan) == job["fingerprint"] and
                                    job["approved_until"] > now)
                except (OSError, ValueError, TypeError):
                    policy_valid = False
                registry_valid, registry_error = (
                    self._current_local_registry_status(validated_plan)
                    if validated_plan is not None else
                    (False, "local_workload_registry_unavailable")
                )
                valid = policy_valid and registry_valid
                if not valid:
                    reason = (registry_error if policy_valid else
                              "local_policy_revoked_before_start")
                    refusal = self._missing_backend_result(job, cleanup_pending=False)
                    refusal["failure_code"] = reason
                    self.finish(job, "expired", refusal, error=reason)
                    return True
            else:
                if plan.get("schema_version") == 2:
                    try:
                        bound_plan = PlanV2.model_validate_json(json.dumps(plan, allow_nan=False))
                        binding_valid = (bound_plan.selection_binding is not None and
                                         plan_fingerprint(bound_plan) == job["fingerprint"] and
                                         job["approved_until"] > now and
                                         Decimal(plan["max_cost_usd"]) <= self.settings.max_job_cost_usd)
                        current = (current_bound_candidate(
                            self.store, self.settings, load_workloads(), bound_plan, now=now,
                        ) if binding_valid else None)
                        binding_valid = binding_valid and current is not None and current.selected is not None
                    except (OSError, ValueError, TypeError, KeyError, OverflowError):
                        binding_valid = False
                    if not binding_valid:
                        refusal = self._missing_backend_result(job, cleanup_pending=False)
                        refusal["failure_code"] = "provider_evidence_stale"
                        self.finish(job, "expired", refusal, error="provider_evidence_stale")
                        return True
                else:
                    manifest = plan["workload_manifest"]
                    if digest(plan) != job["fingerprint"]:
                        self.finish(job, "failed", error="plan_integrity_failed")
                        return True
                    if job["approved_until"] <= now:
                        self.finish(job, "expired", error="approval_expired_before_submission")
                        return True
                    if Decimal(plan["max_cost_usd"]) > self.settings.max_job_cost_usd:
                        self.finish(job, "failed", error="current_operator_cost_limit")
                        return True
                    if plan["provider"] != "demo":
                        if manifest["quote_expires_at"] <= now:
                            self.finish(job, "expired", error="quote_expired_before_submission")
                            return True
                        quote = Decimal(manifest["quoted_usd_per_hour"])
                        if quote * Decimal(plan["runtime_seconds"]) / Decimal(3600) > Decimal(plan["max_cost_usd"]):
                            self.finish(job, "failed", error="cost_limit")
                            return True
            if plan.get("selection_binding") is not None:
                registration = self.registry.get(plan["provider"])
                authorization_kind = candidate_plan_authorization_kind(plan)
                paid_required = authorization_kind == "paid"
                if not supports_candidate_execution(registration, backend, plan):
                    refusal = self._missing_backend_result(job, cleanup_pending=False)
                    failure = {
                        "paid": "paid_execution_contract_unavailable",
                        "credit": "credit_execution_contract_unavailable",
                    }.get(authorization_kind, "candidate_backend_contract_unavailable")
                    refusal["failure_code"] = failure
                    self.finish(job, "failed", refusal, error=failure)
                    return True
                if plan["provider"] == "runpod" and authorization_kind in {"paid", "credit"}:
                    refusal = self._missing_backend_result(job, cleanup_pending=False)
                    refusal["failure_code"] = "runpod_authorization_persistence_unavailable"
                    self.finish(job, "failed", refusal,
                                error="runpod_authorization_persistence_unavailable")
                    return True
                if authorization_kind in {"paid", "credit"}:
                    try:
                        validator = (backend.validate_paid_authorization if authorization_kind == "paid" else
                                     backend.validate_credit_authorization)
                        authorized = validator(job) is True
                    except Exception:
                        authorized = False
                    if not authorized:
                        refusal = self._missing_backend_result(job, cleanup_pending=False)
                        failure = ("paid_authorization_invalid" if paid_required else
                                   "credit_authorization_invalid")
                        refusal["failure_code"] = failure
                        self.finish(job, "failed", refusal, error=failure)
                        return True
            if plan["provider"] == "local_cpu":
                storage = inspect_artifact_storage(
                    self.settings.artifact_dir, self.settings.artifact_min_free_bytes)
                if not storage["available"]:
                    self.finish(job, "failed", error="ARTIFACT_STORAGE_UNAVAILABLE")
                    return True
            attempt = int(job.get("attempt") or 0) + 1
            runpod_candidate = (plan["provider"] == "runpod" and
                                plan.get("selection_binding") is not None)
            provider_lease = None
            if runpod_candidate:
                provider_lease = self._reserve_runpod_account_lease(
                    job, backend, attempt=attempt, now=now,
                )
                if provider_lease is None:
                    latest = self.store.read(job["id"])
                    if latest and latest.get("cancel_requested") is True:
                        self.finish(job, "cancelled", error="cancelled_before_submission")
                        return True
                    refusal = self._missing_backend_result(job, cleanup_pending=False)
                    refusal["failure_code"] = "provider_account_lease_unavailable"
                    self.finish(job, "failed", refusal, error="provider_account_lease_unavailable")
                    return True
                job["attempt"] = attempt
                job["submission_intent"] = self.store.read(job["id"])["submission_intent"]
                intent = job["submission_intent"]
                moved = self.store.transition_provider_account_lease_for_run(
                    account_scope=provider_lease.account_scope, run_id=job["id"],
                    owner=job["owner"], plan_fingerprint=job["fingerprint"],
                    lease_token=provider_lease.lease_token, run_lease_token=job["lease_token"],
                    core_plan_fingerprint=provider_lease.core_plan_fingerprint,
                    authorization_id=provider_lease.authorization_id,
                    expected_state="reserved", new_state="submitting", now=now,
                )
                if not moved:
                    latest = self.store.read(job["id"])
                    if latest and latest.get("cancel_requested") is True:
                        self.store.transition_provider_account_lease_for_run(
                            account_scope=provider_lease.account_scope, run_id=job["id"],
                            owner=job["owner"], plan_fingerprint=job["fingerprint"],
                            lease_token=provider_lease.lease_token,
                            run_lease_token=job["lease_token"],
                            core_plan_fingerprint=provider_lease.core_plan_fingerprint,
                            authorization_id=provider_lease.authorization_id,
                            expected_state="reserved", new_state="released", now=now,
                        )
                        self.finish(job, "cancelled", error="cancelled_before_submission")
                        return True
                    self.update(job, error="provider_account_lease_claim_lost", lease_until=now + 30)
                    return True
            else:
                intent = {"provider": plan["provider"], "owner": job["owner"], "run_id": job["id"],
                          "attempt": attempt, "plan_fingerprint": job["fingerprint"],
                          "phase": "dispatching", "created_at": now}
                if not self.store.begin_submission(
                        run_id=job["id"], owner=job["owner"],
                        plan_fingerprint=job["fingerprint"],
                        run_lease_token=job["lease_token"], attempt=attempt, intent=intent):
                    latest = self.store.read(job["id"])
                    if latest and latest.get("cancel_requested") is True:
                        self.finish(job, "cancelled", error="cancelled_before_submission")
                        return True
                    logger.info("Lease lost before submission intent for run %s", job["id"])
                    return True
                # Revalidate cancellation, approval expiry, and the worker lease
                # after persisting intent. This is the provider-dispatch
                # linearization point for runs without an account-wide lease.
                if not self.store.confirm_submission_dispatch(
                        run_id=job["id"], owner=job["owner"],
                        plan_fingerprint=job["fingerprint"],
                        run_lease_token=job["lease_token"], attempt=attempt, now=now,
                        clock=self.clock):
                    latest = self.store.read(job["id"])
                    if latest and latest.get("cancel_requested") is True:
                        self.finish(job, "cancelled", error="cancelled_before_submission")
                        return True
                    if latest and latest.get("approved_until", 0) <= int(self.clock()):
                        self.finish(job, "expired", error="approval_expired_before_submission")
                        return True
                    self.update(job, state="submit_unknown",
                                error="submission_dispatch_claim_lost", lease_until=now + 5)
                    return True
            try:
                if provider_lease is not None:
                    handle = backend.start_candidate_bound_with_account_lease(
                        job, provider_lease.request_challenge,
                    )
                elif plan.get("selection_binding") is not None:
                    handle = backend.start_candidate_bound(job)
                else:
                    handle = backend.start(job)
                if not isinstance(handle, dict) or not handle:
                    raise ValueError("Missing durable provider handle")
                json.dumps(handle, allow_nan=False)
            except Exception:
                # Some failures occur AFTER provider acceptance. No automatic retry.
                if provider_lease is not None:
                    self.store.transition_provider_account_lease_for_run(
                        account_scope=provider_lease.account_scope, run_id=job["id"],
                        owner=job["owner"], plan_fingerprint=job["fingerprint"],
                        lease_token=provider_lease.lease_token, run_lease_token=job["lease_token"],
                        core_plan_fingerprint=provider_lease.core_plan_fingerprint,
                        authorization_id=provider_lease.authorization_id,
                        expected_state="submitting", new_state="uncertain", now=now,
                    )
                self.update(job, state="submit_unknown", error="submission_outcome_unknown", lease_until=now + 5)
                logger.warning("Submission outcome unknown for run %s", job["id"])
                return True
            if provider_lease is not None:
                try:
                    provider_job_id = backend.provider_job_id(handle)
                except Exception:
                    provider_job_id = None
                if not isinstance(provider_job_id, str) or not provider_job_id or len(provider_job_id) > 512:
                    self.store.transition_provider_account_lease_for_run(
                        account_scope=provider_lease.account_scope, run_id=job["id"],
                        owner=job["owner"], plan_fingerprint=job["fingerprint"],
                        lease_token=provider_lease.lease_token, run_lease_token=job["lease_token"],
                        core_plan_fingerprint=provider_lease.core_plan_fingerprint,
                        authorization_id=provider_lease.authorization_id,
                        expected_state="submitting", new_state="uncertain", now=now,
                    )
                    self.update(job, state="submit_unknown", error="provider_resource_identity_unavailable",
                                lease_until=now + 5)
                    return True
                if not self.store.transition_provider_account_lease_for_run(
                        account_scope=provider_lease.account_scope, run_id=job["id"],
                        owner=job["owner"], plan_fingerprint=job["fingerprint"],
                        lease_token=provider_lease.lease_token, run_lease_token=job["lease_token"],
                        core_plan_fingerprint=provider_lease.core_plan_fingerprint,
                        authorization_id=provider_lease.authorization_id,
                        expected_state="submitting", new_state="active",
                        provider_job_id=provider_job_id, now=now):
                    persisted_intent = intent | {"phase": "handle_persisted"}
                    with self.store.transaction() as connection:
                        connection.execute(update(runs).where(
                            runs.c.id == job["id"],
                            _unset_json_value(runs.c.handle),
                        ).values(handle=handle, submission_intent=persisted_intent))
                    self.update(job, state="submit_unknown",
                                error="provider_account_lease_transition_pending", lease_until=now + 5)
                    return True
            # Persist a returned handle even if this worker lost its lease. This is
            # evidence of an already-started job, NOT authority to start another.
            persisted_intent = intent | {"phase": "handle_persisted"}
            with self.store.transaction() as c:
                persisted = c.execute(update(runs).where(
                    runs.c.id == job["id"],
                    _unset_json_value(runs.c.handle),
                ).values(
                    handle=handle, submission_intent=persisted_intent))
                if persisted.rowcount != 1:
                    raise RuntimeError("provider handle was not durably persisted")
            self.update(job, state="running", lease_until=now + 1, error="")
            return True
        try:
            handle = job["handle"]
            account_lease_intent = (isinstance(job.get("submission_intent"), dict) and
                                    "account_scope" in job["submission_intent"])
            lease_activated = False
            if handle is None:
                intent = job.get("submission_intent")
                if intent is not None and (
                    not isinstance(intent, dict) or intent.get("provider") != plan["provider"] or
                    intent.get("owner") != job["owner"] or intent.get("run_id") != job["id"] or
                    intent.get("plan_fingerprint") != job["fingerprint"] or
                    type(intent.get("attempt")) is not int or intent["attempt"] < 1 or
                    intent.get("phase") not in {"dispatching", "provider_call_started", "handle_persisted"}
                ):
                    self.update(job, state="submit_unknown", error="submission_intent_mismatch",
                                lease_until=now + 30)
                    return True
                if account_lease_intent:
                    lease = self._load_runpod_account_lease(job, backend, now=int(self.clock()))
                    if lease is None:
                        self.update(job, state="submit_unknown", error="provider_account_lease_unavailable",
                                    lease_until=now + 30)
                        return True
                    try:
                        handle = backend.reconcile_candidate_bound_with_account_lease(
                            job, lease.request_challenge,
                        )
                    except Exception:
                        if lease.state == "submitting":
                            self.store.transition_provider_account_lease_for_run(
                                account_scope=lease.account_scope, run_id=job["id"],
                                owner=job["owner"], plan_fingerprint=job["fingerprint"],
                                lease_token=lease.lease_token, run_lease_token=job["lease_token"],
                                core_plan_fingerprint=lease.core_plan_fingerprint,
                                authorization_id=lease.authorization_id,
                                expected_state="submitting", new_state="uncertain",
                                now=int(self.clock()), provider="runpod",
                            )
                        raise
                    if handle is None and lease.state == "submitting":
                        self.store.transition_provider_account_lease_for_run(
                            account_scope=lease.account_scope, run_id=job["id"],
                            owner=job["owner"], plan_fingerprint=job["fingerprint"],
                            lease_token=lease.lease_token, run_lease_token=job["lease_token"],
                            core_plan_fingerprint=lease.core_plan_fingerprint,
                            authorization_id=lease.authorization_id,
                            expected_state="submitting", new_state="uncertain",
                            now=int(self.clock()), provider="runpod",
                        )
                else:
                    handle = backend.reconcile(job)
                observed_at = int(self.clock())
                if handle is None:
                    self.update(job, state="submit_unknown", error="operator_reconciliation_required",
                                lease_until=now + 30, last_observed_at=observed_at)
                    return True
                if account_lease_intent:
                    if not self._activate_runpod_lease_for_handle(
                            job, backend, handle, now=int(self.clock())):
                        self.update(job, state="submit_unknown",
                                    error="provider_account_lease_handle_mismatch",
                                    lease_until=now + 30)
                        return True
                    lease_activated = True
                intent = job.get("submission_intent")
                if isinstance(intent, dict):
                    intent = intent | {"phase": "handle_persisted"}
                # Preserve newly discovered provider identity even if this
                # reconciliation call outlived its lease. The lease-fenced
                # state transition below decides whether this worker may act.
                with self.store.transaction() as connection:
                    connection.execute(update(runs).where(
                        runs.c.id == job["id"],
                        _unset_json_value(runs.c.handle),
                    ).values(handle=handle, submission_intent=intent))
                if not self.update(job, state="running", error="", last_observed_at=observed_at):
                    return True
            if account_lease_intent and not lease_activated:
                if not self._activate_runpod_lease_for_handle(job, backend, handle, now=int(self.clock())):
                    self.update(job, state="submit_unknown", error="provider_account_lease_handle_mismatch",
                                lease_until=now + 30)
                    return True
            latest = self.store.read(job["id"])
            lifecycle_backend = all(callable(getattr(backend, name, None))
                                    for name in ("capture", "cleanup", "is_clean"))
            if lifecycle_backend and latest.get("result") is not None and latest.get("cleanup_state") == "pending":
                lease_context = self._provider_lease_cleanup_context(job, backend, handle)
                backend.cleanup(handle)
                if backend.is_clean(handle) is not True:
                    raise RuntimeError("cleanup receipt not confirmed")
                saved = dict(latest["result"])
                saved["cleanup_state"] = "complete"
                intended = (latest.get("error", "").removeprefix("cleanup_pending:")
                            if isinstance(latest.get("error"), str) else "")
                if intended not in TERMINAL:
                    intended = "cancelled" if latest["cancel_requested"] else "failed" if saved.get("exit_code") else "succeeded"
                failure_error = (saved.get("failure_code", "")
                                 if intended == "failed" and isinstance(saved.get("failure_code"), str)
                                 else "")
                if not self.finish_after_provider_cleanup(job, intended, saved, failure_error, lease_context):
                    raise RuntimeError("provider lease and run cleanup commit failed")
                return True
            overdue = now > job["started_at"] + plan["runtime_seconds"] + 60
            cancelling = latest["cancel_requested"] or overdue
            if cancelling:
                backend.cancel(handle)
            observation = backend.capture(handle) if lifecycle_backend else backend.inspect(handle)
            observed_at = int(self.clock())
            if observation.state == "running":
                self.update(job, state="running", lease_until=now + 3,
                            error="cancellation_pending" if cancelling else "",
                            last_observed_at=observed_at)
            else:
                if plan.get("selection_binding") is not None:
                    try:
                        verified = backend.validate_candidate_observation(job, observation) is True
                        verified_receipt = None
                        if verified and observation.state == "succeeded":
                            validated_plan = PlanV2.model_validate_json(json.dumps(plan, allow_nan=False))
                            verified_receipt = verify_candidate_receipt(
                                observation.candidate_receipt,
                                self.settings.candidate_receipt_trusted_keys,
                                now=int(self.clock()), plan=validated_plan,
                                fingerprint=job["fingerprint"], run_id=job["id"],
                                result=observation.result,
                            )
                    except Exception:
                        verified = False
                    if not verified:
                        result = self._missing_backend_result(job, cleanup_pending=True)
                        result["failure_code"] = "candidate_result_evidence_invalid"
                        observation = Observation("failed", result)
                    elif verified_receipt is not None:
                        result = dict(observation.result)
                        checks = result.get("checks", [])
                        if not isinstance(checks, list):
                            checks = []
                        result["checks"] = list(dict.fromkeys(
                            checks + ["candidate_resource_verified", "device_identity_verified"]))
                        result["candidate_receipt"] = verified_receipt
                        observation = Observation("succeeded", result, observation.artifacts,
                                                  verified_receipt)
                state = "cancelled" if cancelling else observation.state
                terminal_error = ""
                if observation.result is None:
                    # No manifest means attached payloads cannot be trusted or
                    # published. Still record a bound failure before cleanup so
                    # recovery retains both the handle and admission slot.
                    observation_result = self._missing_backend_result(
                        job, cleanup_pending=lifecycle_backend)
                    if state == "succeeded":
                        state = "failed"
                else:
                    try:
                        observation_result = self._persist_artifacts(job, observation)
                    except Exception:
                        # A full/unavailable artifact volume must not pin a
                        # terminal container and admission slot forever. Do not
                        # publish partial artifact metadata or report success.
                        logger.exception("Artifact persistence failed for run %s", job["id"])
                        if isinstance(observation.result, dict):
                            observation_result = observation.result | {
                                "artifacts": [],
                                "failure_code": "artifact_persistence_failed",
                            }
                        else:
                            observation_result = self._missing_backend_result(
                                job, cleanup_pending=lifecycle_backend,
                            ) | {"failure_code": "artifact_persistence_failed"}
                        state = "failed"
                        terminal_error = "artifact_persistence_failed"
                if lifecycle_backend and observation_result is not None:
                    # Persist the terminal evidence before deleting the container.
                    if not self.update(job, result=observation_result, cleanup_state="pending",
                                       lease_until=now + 1, error="cleanup_pending:" + state,
                                       last_observed_at=observed_at):
                        raise RuntimeError("worker lease lost before result persistence")
                    lease_context = self._provider_lease_cleanup_context(job, backend, handle)
                    backend.cleanup(handle)
                    if backend.is_clean(handle) is not True:
                        raise RuntimeError("cleanup receipt not confirmed")
                    result = dict(observation_result)
                    result["cleanup_state"] = "complete"
                    if not self.finish_after_provider_cleanup(
                            job, state, result, terminal_error, lease_context):
                        raise RuntimeError("provider lease and run cleanup commit failed")
                else:
                    if not self.update(job, last_observed_at=observed_at):
                        return True
                    self.finish(job, state, observation_result, error=terminal_error)
        except Exception:
            # Observability failure does not prove completion and must not free a slot.
            latest = self.store.read(job["id"])
            # Once terminal evidence has been persisted, preserve the intended
            # terminal state across cleanup failures. Timeout-triggered
            # cancellation does not set cancel_requested in the database, so
            # recovery cannot safely infer "cancelled" from that flag alone.
            cleanup_intent = (latest.get("error") if latest and
                              latest.get("cleanup_state") == "pending" and
                              isinstance(latest.get("result"), dict) and
                              isinstance(latest.get("error"), str) and
                              latest["error"].startswith("cleanup_pending:") else None)
            self.update(job, error=cleanup_intent or "provider_observation_or_cleanup_failed",
                        lease_until=now + 10)
            logger.exception("Observation/recovery needed for run %s", job["id"])
        return True


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--init-db", action="store_true")
    mode.add_argument("--check-db", action="store_true",
                      help="report schema migration status without modifying the database")
    mode.add_argument("--bootstrap-auth", action="store_true")
    mode.add_argument("--supervise", action="store_true",
                      help="run recovery-only ticks; never claim newly queued jobs")
    parser.add_argument("--bootstrap-auth-ttl", type=int, default=3600)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=3)
    args = parser.parse_args()
    settings = Settings.from_env()
    store = Store(settings.database_url)
    if args.check_db:
        from .migrations import migration_status
        status = migration_status(store.engine)
        print(json.dumps(status, sort_keys=True, allow_nan=False))
        store.engine.dispose()
        if not status["supported"]:
            raise SystemExit(1)
        return
    if args.init_db:
        store.initialize()
        return
    if args.bootstrap_auth:
        if settings.issuer:
            parser.error("bootstrap-auth is only available for built-in OAuth mode")
        if not 60 <= args.bootstrap_auth_ttl <= 86400:
            parser.error("bootstrap-auth-ttl must be between 60 and 86400 seconds")
        store.initialize()
        from .local_oauth import LocalOAuth
        oauth = LocalOAuth(settings, store)
        if oauth.configured():
            parser.error("owner authentication is already configured")
        token = secrets.token_urlsafe(32)
        oauth.seed_bootstrap(token, ttl_seconds=args.bootstrap_auth_ttl)
        print(settings.public_url.rstrip("/") + "/auth/setup?token=" + quote(token, safe=""))
        return
    if args.poll_seconds < 0.5:
        parser.error("poll-seconds must be at least 0.5")
    worker = Worker(store, settings, build_backends(settings),
                    role="supervisor" if args.supervise else "worker")
    while True:
        worker.tick()
        if args.once:
            break
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
