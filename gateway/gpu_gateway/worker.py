from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import time
import uuid
from urllib.parse import quote
from decimal import Decimal

from jsonschema import SchemaError as InvalidSchema
from sqlalchemy import and_, or_, select, update

from .artifacts import (ArtifactStore, MAX_ARTIFACTS_PER_RUN,
                        MAX_RUN_ARTIFACT_BYTES, inspect_artifact_storage)
from .backends import Backend, Observation, build_backends
from .config import Settings, load_workloads
from .registry import (candidate_plan_requires_paid_authorization, default_registry,
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

logger = logging.getLogger(__name__)
# Keep the historical module constant for callers while sharing its source.
WORKER_HEARTBEAT_STALE_SECONDS = HEARTBEAT_STALE_SECONDS
ARTIFACT_TTL_SECONDS = 30 * 24 * 3600
ARTIFACT_PRUNE_INTERVAL_SECONDS = 3600
PROVIDER_EVIDENCE_POLL_INTERVAL_SECONDS = 60


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

    def finish(self, job: dict, state: str, result=None, error=""):
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
                paid_required = candidate_plan_requires_paid_authorization(plan)
                if not supports_candidate_execution(registration, backend, plan):
                    refusal = self._missing_backend_result(job, cleanup_pending=False)
                    failure = ("paid_execution_contract_unavailable" if paid_required else
                               "candidate_backend_contract_unavailable")
                    refusal["failure_code"] = failure
                    self.finish(job, "failed", refusal, error=failure)
                    return True
                if paid_required:
                    try:
                        paid_authorized = backend.validate_paid_authorization(job) is True
                    except Exception:
                        paid_authorized = False
                    if not paid_authorized:
                        refusal = self._missing_backend_result(job, cleanup_pending=False)
                        refusal["failure_code"] = "paid_authorization_invalid"
                        self.finish(job, "failed", refusal, error="paid_authorization_invalid")
                        return True
            if plan["provider"] == "local_cpu":
                storage = inspect_artifact_storage(
                    self.settings.artifact_dir, self.settings.artifact_min_free_bytes)
                if not storage["available"]:
                    self.finish(job, "failed", error="ARTIFACT_STORAGE_UNAVAILABLE")
                    return True
            attempt = int(job.get("attempt") or 0) + 1
            intent = {"provider": plan["provider"], "owner": job["owner"], "run_id": job["id"],
                      "attempt": attempt, "plan_fingerprint": job["fingerprint"],
                      "phase": "dispatching", "created_at": now}
            if not self.update(job, attempt=attempt, submission_intent=intent):
                logger.info("Lease lost before submission intent for run %s", job["id"])
                return True
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
                if plan.get("selection_binding") is not None:
                    handle = backend.start_candidate_bound(job)
                else:
                    handle = backend.start(job)
                if not isinstance(handle, dict) or not handle:
                    raise ValueError("Missing durable provider handle")
                json.dumps(handle, allow_nan=False)
            except Exception:
                # Some failures occur AFTER provider acceptance. No automatic retry.
                self.update(job, state="submit_unknown", error="submission_outcome_unknown", lease_until=now + 5)
                logger.warning("Submission outcome unknown for run %s", job["id"])
                return True
            # Persist a returned handle even if this worker lost its lease. This is
            # evidence of an already-started job, NOT authority to start another.
            persisted_intent = intent | {"phase": "handle_persisted"}
            with self.store.transaction() as c:
                c.execute(update(runs).where(runs.c.id == job["id"], runs.c.handle.is_(None)).values(
                    handle=handle, submission_intent=persisted_intent))
            self.update(job, state="running", lease_until=now + 1, error="")
            return True
        try:
            handle = job["handle"]
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
                handle = backend.reconcile(job)
                observed_at = int(self.clock())
                if handle is None:
                    self.update(job, state="submit_unknown", error="operator_reconciliation_required",
                                lease_until=now + 30, last_observed_at=observed_at)
                    return True
                intent = job.get("submission_intent")
                if isinstance(intent, dict):
                    intent = intent | {"phase": "handle_persisted"}
                # Preserve newly discovered provider identity even if this
                # reconciliation call outlived its lease. The lease-fenced
                # state transition below decides whether this worker may act.
                with self.store.transaction() as connection:
                    connection.execute(update(runs).where(
                        runs.c.id == job["id"], runs.c.handle.is_(None)
                    ).values(handle=handle, submission_intent=intent))
                if not self.update(job, state="running", error="", last_observed_at=observed_at):
                    return True
            latest = self.store.read(job["id"])
            lifecycle_backend = all(callable(getattr(backend, name, None))
                                    for name in ("capture", "cleanup", "is_clean"))
            if lifecycle_backend and latest.get("result") is not None and latest.get("cleanup_state") == "pending":
                backend.cleanup(handle)
                if not backend.is_clean(handle):
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
                self.finish(job, intended, saved, error=failure_error)
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
                    backend.cleanup(handle)
                    if not backend.is_clean(handle):
                        raise RuntimeError("cleanup receipt not confirmed")
                    result = dict(observation_result)
                    result["cleanup_state"] = "complete"
                    self.finish(job, state, result, error=terminal_error)
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
