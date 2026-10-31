from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from jsonschema import Draft202012Validator, ValidationError as SchemaError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, insert, select, update

from .config import Settings, Workload
from .store import Store, control, runs
from .registry import default_registry, candidate_plan_requires_paid_authorization
from .contracts import (PlanV2, ResultV2, plan_fingerprint, plan_payload,
                        validate_candidate_gpu_success, validate_result_binding)
from .candidate_receipts import verify_candidate_receipt
from .admission import (evaluate_admission, load_local_cpu_policy,
                        matches_registered_local_workload)
from .provider_selection import current_bound_candidate

TERMINAL = {"succeeded", "failed", "cancelled", "expired"}


class GatewayError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


@dataclass(frozen=True)
class Principal:
    owner: str
    scopes: frozenset[str]
    browser: bool = False

    def require(self, scope: str):
        if scope not in self.scopes:
            raise GatewayError("insufficient_scope", f"Required scope: {scope}", 403)


class Prepare(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    workload: str = Field(min_length=1, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)
    runtime_seconds: int = Field(default=60, ge=1, le=3600)
    max_cost_usd: str = Field(default="0.10", pattern=r"^(0|[1-9][0-9]{0,2})(\.[0-9]{1,6})?$")
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")


class RunID(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def public_run(row: dict) -> dict:
    # Never expose provider credentials, internal handles or exception messages.
    fields = ("id", "state", "created_at", "fingerprint", "plan", "result",
              "error", "cancel_requested", "approved_until", "last_observed_at")
    return {key: row.get(key) for key in fields}


class ExperimentService:
    def __init__(self, store: Store, settings: Settings, workloads: dict[str, Workload], clock: Callable[[], float] = time.time, *, registry=None):
        self.store, self.settings, self.workloads, self.clock = store, settings, workloads, clock
        self.registry = default_registry() if registry is None else registry

    def integrations(self, principal: Principal) -> dict:
        principal.require("experiments:read")
        return {"providers": [{"id": entry.name, "enabled": bool(entry.enabled(self.settings)),
                               "execution": entry.execution, "note": entry.note}
                              for entry in self.registry.values()],
                "workloads": [{"id": name, "provider": w.provider,
                               "max_runtime_seconds": w.max_runtime_seconds,
                               "parameter_schema": w.parameter_schema,
                               "source_repository": w.source_repository or None,
                               "source_sha": w.source_sha or None,
                               "requires_gpu": w.requires_gpu,
                               "gpu": w.gpu if w.requires_gpu else None}
                              for name, w in self.workloads.items()]}

    def owned(self, principal: Principal, run_id: str) -> dict:
        row = self.store.read(run_id)
        if not row or row["owner"] != principal.owner:
            raise GatewayError("not_found", "Experiment not found", 404)
        return row

    def _public_run(self, row: dict) -> dict:
        """Re-verify persisted candidate GPU success evidence on every read."""
        public = public_run(row)
        plan_data, result_data = row.get("plan"), row.get("result")
        if (row.get("state") != "succeeded" or not isinstance(plan_data, dict) or
                plan_data.get("selection_binding") is None):
            return public
        try:
            plan = PlanV2.model_validate_json(json.dumps(plan_data, allow_nan=False))
            if not isinstance(result_data, dict):
                raise ValueError("candidate result is missing")
            core = {key: value for key, value in result_data.items()
                    if key in ResultV2.model_fields}
            result = ResultV2.model_validate_json(json.dumps(core, allow_nan=False))
            fingerprint = plan_fingerprint(plan)
            if row.get("fingerprint") != fingerprint:
                raise ValueError("candidate plan fingerprint changed")
            validate_result_binding(plan, fingerprint, result)
            validate_candidate_gpu_success(result)
            verify_candidate_receipt(
                result_data.get("candidate_receipt"),
                self.settings.candidate_receipt_trusted_keys,
                now=int(self.clock()), plan=plan, fingerprint=fingerprint,
                run_id=row["id"], result=result_data, require_current=False,
            )
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            public.update(state="failed", error="result_integrity_failed",
                          result={"failure_code": "result_integrity_failed"})
        return public

    def prepare(self, principal: Principal, request: Prepare) -> dict:
        principal.require("experiments:run")
        w = self.workloads.get(request.workload)
        if w is None or w.provider not in self.registry:
            raise GatewayError("unknown_workload", "Use an operator-registered workload")
        try:
            Draft202012Validator(w.parameter_schema).validate(request.parameters)
            digest(request.parameters)
        except (SchemaError, ValueError, TypeError):
            raise GatewayError("invalid_parameters", "Parameters do not match the registered schema")
        cap = Decimal(request.max_cost_usd)
        if not Decimal("0") < cap <= min(w.max_cost_usd, self.settings.max_job_cost_usd):
            raise GatewayError("cost_limit", "Cost ceiling exceeds operator policy or is zero")
        if request.runtime_seconds > w.max_runtime_seconds:
            raise GatewayError("runtime_limit", "Runtime exceeds registered workload policy")
        now = int(self.clock())
        if w.provider != "demo":
            if w.quoted_usd_per_hour is None or not w.quote_reference or w.quote_expires_at <= now:
                raise GatewayError("quote_required", "An operator-verified current all-in compute quote is required")
            estimate = w.quoted_usd_per_hour * Decimal(request.runtime_seconds) / Decimal(3600)
            if estimate > cap:
                raise GatewayError("cost_limit", "Quoted compute cost exceeds the requested ceiling")
        else:
            estimate = Decimal(0)
        plan = {"schema_version": 1, "workload": request.workload,
                "workload_manifest": w.model_dump(mode="json"), "parameters": request.parameters,
                "runtime_seconds": request.runtime_seconds, "max_cost_usd": request.max_cost_usd,
                "estimated_compute_usd": str(estimate), "provider": w.provider}
        request_hash = digest(request.model_dump())
        with self.store.transaction() as connection:
            self.store.lock_control(connection)
            old = connection.execute(select(runs).where(runs.c.owner == principal.owner, runs.c.idempotency_key == request.idempotency_key)).mappings().first()
            if old:
                if old["request_hash"] != request_hash:
                    raise GatewayError("idempotency_conflict", "Use a new idempotency key for different inputs", 409)
                return self._public_run(dict(old))
            count = connection.execute(select(func.count()).select_from(runs).where(runs.c.owner == principal.owner, runs.c.state.not_in(list(TERMINAL)))).scalar_one()
            if count >= self.settings.max_open_requests:
                raise GatewayError("request_limit", "Too many unfinished experiments", 429)
            run_id = uuid.uuid4().hex
            connection.execute(insert(runs).values(id=run_id, owner=principal.owner,
                idempotency_key=request.idempotency_key, request_hash=request_hash,
                fingerprint=digest(plan), plan=plan, state="awaiting_approval", created_at=now))
        return self._public_run(self.owned(principal, run_id))

    def existing_prepare(self, principal: Principal, request_payload: dict) -> dict | None:
        """Return an owner-scoped idempotent prepare before volatile admission checks.

        Candidate inventory, quotes, and local policy may expire between a request
        and its transport retry. A retry with the same intent must resolve to its
        already-persisted run instead of selecting a new resource or failing before
        the idempotency record is consulted.
        """
        principal.require("experiments:run")
        if not isinstance(request_payload, dict):
            raise GatewayError("invalid_request", "Prepare request is invalid")
        key = request_payload.get("idempotency_key")
        if not isinstance(key, str):
            raise GatewayError("invalid_request", "Prepare idempotency key is invalid")
        request_hash = digest(request_payload)
        with self.store.engine.connect() as connection:
            row = connection.execute(select(runs).where(
                runs.c.owner == principal.owner,
                runs.c.idempotency_key == key,
            )).mappings().first()
        if row is None:
            return None
        if row["request_hash"] != request_hash and not self._matches_prepared_request(
                row.get("plan"), request_payload):
            raise GatewayError(
                "idempotency_conflict",
                "Use a new idempotency key for different inputs", 409,
            )
        return self._public_run(dict(row))

    @staticmethod
    def _matches_prepared_request(plan: Any, request_payload: dict) -> bool:
        """Recognize pre-upgrade plan-hash rows without trusting volatile evidence."""
        if not isinstance(plan, dict) or plan.get("schema_version") != 2:
            return False
        try:
            if (plan.get("repository") != request_payload.get("repository") or
                    plan.get("source_sha") != request_payload.get("commit") or
                    plan.get("workload") != request_payload.get("workload") or
                    plan.get("parameters") != request_payload.get("parameters") or
                    plan.get("runtime_seconds") != request_payload.get("runtime_seconds") or
                    Decimal(str(plan.get("max_cost_usd"))) !=
                    Decimal(str(request_payload.get("max_cost_usd")))):
                return False
        except (ArithmeticError, TypeError, ValueError):
            return False
        requested_gpu = request_payload.get("requires_gpu")
        if requested_gpu is None:
            return True
        requirement = plan.get("device_requirement")
        return (isinstance(requirement, dict) and
                (requirement.get("accelerator_kind") == "gpu") is requested_gpu)

    def prepare_bound_gpu(self, principal: Principal, plan: PlanV2,
                          idempotency_key: str, request_hash: str | None = None) -> dict:
        """Persist an exact selected GPU plan after one last evidence check."""
        principal.require("experiments:run")
        if not isinstance(plan, PlanV2) or plan.selection_binding is None:
            raise GatewayError("invalid_plan", "A candidate-bound GPU plan is required")
        workload = self.workloads.get(plan.workload)
        if workload is None or not workload.requires_gpu or workload.provider != plan.provider:
            raise GatewayError("plan_changed", "The registered GPU workload changed", 409)
        try:
            Draft202012Validator(workload.parameter_schema).validate(plan.parameters)
            digest(plan.parameters)
        except (SchemaError, ValueError, TypeError):
            raise GatewayError("invalid_parameters", "Parameters do not match the registered schema") from None
        if (plan.runtime_seconds > workload.max_runtime_seconds or
                plan.max_cost_usd < 0 or plan.max_cost_usd > workload.max_cost_usd):
            raise GatewayError("plan_changed", "Runtime or cost exceeds registered workload policy", 409)
        now = int(self.clock())
        current = current_bound_candidate(
            self.store, self.settings, self.workloads, plan, now=now)
        if current.selected is None:
            raise GatewayError("provider_evidence_stale",
                               "The exact selected GPU resource is no longer admissible", 409)
        payload = plan_payload(plan)
        request_hash = request_hash or digest({"plan": payload, "idempotency_key": idempotency_key})
        fingerprint = plan_fingerprint(plan)
        with self.store.transaction() as connection:
            self.store.lock_control(connection)
            old = connection.execute(select(runs).where(
                runs.c.owner == principal.owner,
                runs.c.idempotency_key == idempotency_key,
            )).mappings().first()
            if old:
                if old["request_hash"] != request_hash:
                    raise GatewayError("idempotency_conflict", "Use a new idempotency key for different inputs", 409)
                return self._public_run(dict(old))
            count = connection.execute(select(func.count()).select_from(runs).where(
                runs.c.owner == principal.owner, runs.c.state.not_in(list(TERMINAL)),
            )).scalar_one()
            if count >= self.settings.max_open_requests:
                raise GatewayError("request_limit", "Too many unfinished experiments", 429)
            run_id = uuid.uuid4().hex
            connection.execute(insert(runs).values(
                id=run_id, owner=principal.owner,
                idempotency_key=idempotency_key, request_hash=request_hash,
                fingerprint=fingerprint, plan=payload,
                state="awaiting_approval", created_at=now,
            ))
        return self._public_run(self.owned(principal, run_id))

    def prepare_local(self, principal: Principal, plan: PlanV2, idempotency_key: str,
                      policy: dict, decision, request_hash: str | None = None) -> dict:
        """Persist an operator-preauthorized local plan as distinct from Web approval."""
        principal.require("experiments:run")
        workload = self.workloads.get(plan.workload)
        if workload is None or workload.provider != "local_cpu":
            raise GatewayError("unknown_workload", "Use an operator-registered local CPU workload")
        if not matches_registered_local_workload(plan, self.workloads):
            raise GatewayError("plan_changed", "Plan source or registered workload changed", 409)
        try:
            Draft202012Validator(workload.parameter_schema).validate(plan.parameters)
            digest(plan.parameters)
        except (SchemaError, ValueError, TypeError):
            raise GatewayError("invalid_parameters", "Parameters do not match the registered schema") from None
        current = evaluate_admission(plan, policy, int(self.clock()))
        if (not current.allowed or not decision.allowed or current.policy_digest != decision.policy_digest or
                plan.authorization_policy_version != policy.get("version")):
            raise GatewayError("admission_denied", current.blocking_reason or "Admission decision changed", 409)
        fingerprint = plan_fingerprint(plan)
        payload = plan_payload(plan)
        request_hash = request_hash or digest({"plan": payload, "idempotency_key": idempotency_key})
        now = int(self.clock())
        with self.store.transaction() as connection:
            self.store.lock_control(connection)
            old = connection.execute(select(runs).where(
                runs.c.owner == principal.owner, runs.c.idempotency_key == idempotency_key
            )).mappings().first()
            if old:
                if old["request_hash"] != request_hash:
                    raise GatewayError("idempotency_conflict", "Use a new idempotency key for different inputs", 409)
                return self._public_run(dict(old))
            count = connection.execute(select(func.count()).select_from(runs).where(
                runs.c.owner == principal.owner, runs.c.state.not_in(list(TERMINAL))
            )).scalar_one()
            if count >= self.settings.max_open_requests:
                raise GatewayError("request_limit", "Too many unfinished experiments", 429)
            run_id = uuid.uuid4().hex
            connection.execute(insert(runs).values(
                id=run_id, owner=principal.owner, idempotency_key=idempotency_key,
                request_hash=request_hash, fingerprint=fingerprint,
                plan=payload, state="authorized", created_at=now,
                approved_until=current.valid_until or 0,
                admission={"mode": "local_policy", "policy_version": plan.authorization_policy_version,
                           "policy_digest": current.policy_digest, "valid_until": current.valid_until},
            ))
        return self._public_run(self.owned(principal, run_id))

    def approve(self, principal: Principal, run_id: str, fingerprint: str) -> dict:
        principal.require("experiments:run")
        if not principal.browser:
            raise GatewayError("browser_approval_required", "Approve the exact plan in the authenticated Web UI", 403)
        with self.store.transaction() as connection:
            self.store.lock_control(connection)
            row = connection.execute(select(runs).where(runs.c.id == run_id, runs.c.owner == principal.owner)).mappings().first()
            if row is None:
                raise GatewayError("not_found", "Experiment not found", 404)
            if fingerprint != row["fingerprint"] or digest(row["plan"]) != fingerprint:
                raise GatewayError("plan_changed", "Approval does not match the exact plan", 409)
            if row["state"] not in {"awaiting_approval", "approved"}:
                raise GatewayError("invalid_state", "This experiment cannot be approved", 409)
            connection.execute(update(runs).where(runs.c.id == run_id).values(state="approved", approval_id=uuid.uuid4().hex, approved_until=int(self.clock()) + self.settings.approval_ttl_seconds))
        return self._public_run(self.owned(principal, run_id))

    def submit(self, principal: Principal, run_id: str) -> dict:
        principal.require("experiments:run")
        with self.store.transaction() as connection:
            admission = self.store.lock_control(connection)
            row = connection.execute(select(runs).where(runs.c.id == run_id, runs.c.owner == principal.owner)).mappings().first()
            if row is None:
                raise GatewayError("not_found", "Experiment not found", 404)
            if row["state"] in {"queued", "submitting", "submit_unknown", "running"} | TERMINAL:
                return self._public_run(dict(row))
            if isinstance(row["plan"], dict) and row["plan"].get("selection_binding") is not None:
                try:
                    candidate_plan = PlanV2.model_validate_json(
                        json.dumps(row["plan"], allow_nan=False))
                    if plan_fingerprint(candidate_plan) != row["fingerprint"]:
                        raise ValueError("stored plan fingerprint changed")
                    revalidation = current_bound_candidate(
                        self.store, self.settings, self.workloads,
                        candidate_plan, now=int(self.clock()),
                        connection=connection, lock_observation=True,
                    )
                except (ValueError, TypeError, KeyError, OverflowError):
                    revalidation = None
                if revalidation is None or revalidation.selected is None:
                    raise GatewayError(
                        "provider_evidence_stale",
                        "The exact approved GPU resource or its evidence changed", 409,
                    )
            local_admission = row["admission"]
            if local_admission is not None:
                plan = None
                try:
                    policy = load_local_cpu_policy()
                    plan = PlanV2.model_validate_json(json.dumps(row["plan"], allow_nan=False))
                    decision = evaluate_admission(plan, policy, int(self.clock()))
                except (OSError, ValueError, TypeError):
                    decision = None
                if (local_admission.get("mode") != "local_policy" or decision is None or
                        not matches_registered_local_workload(plan, self.workloads) or
                        not decision.allowed or decision.policy_digest != local_admission.get("policy_digest") or
                        decision.valid_until != local_admission.get("valid_until") or
                        digest(row["plan"]) != row["fingerprint"]):
                    raise GatewayError("admission_revoked", "Current local CPU policy no longer authorizes this plan", 409)
                if row["state"] != "authorized" or row["approved_until"] <= int(self.clock()):
                    raise GatewayError("admission_expired", "Local CPU authorization has expired", 409)
            elif row["state"] != "approved" or row["approved_until"] <= int(self.clock()):
                raise GatewayError("approval_required", "Current Web approval of this exact plan is required", 409)
            p = row["plan"]["provider"]
            registration = self.registry.get(p)
            if registration is None:
                raise GatewayError("provider_unavailable", "Provider backend is not registered", 409)
            if not registration.enabled(self.settings):
                raise GatewayError("provider_disabled", "This provider is not enabled on the gateway", 409)
            if (isinstance(row["plan"], dict) and
                    row["plan"].get("selection_binding") is not None and
                    not registration.supports_candidate_binding):
                raise GatewayError(
                    "gpu_backend_unavailable",
                    "Provider backend has not passed candidate-bound execution acceptance", 409,
                )
            if (isinstance(row["plan"], dict) and
                    row["plan"].get("selection_binding") is not None and
                    candidate_plan_requires_paid_authorization(row["plan"]) and
                    not registration.supports_paid_execution):
                raise GatewayError(
                    "paid_authorization_required",
                    "Provider registration has not passed separately authorized paid execution acceptance", 409,
                )
            if admission["active_count"] >= self.settings.max_inflight:
                raise GatewayError("concurrency_limit", "An experiment is already in flight", 409)
            connection.execute(update(control).where(control.c.id == 1).values(active_count=control.c.active_count + 1))
            connection.execute(update(runs).where(runs.c.id == run_id).values(state="queued", slot_reserved=True))
        return self._public_run(self.owned(principal, run_id))

    def cancel(self, principal: Principal, run_id: str) -> dict:
        principal.require("experiments:cancel")
        with self.store.transaction() as connection:
            self.store.lock_control(connection)
            row = connection.execute(select(runs).where(runs.c.id == run_id, runs.c.owner == principal.owner)).mappings().first()
            if row is None:
                raise GatewayError("not_found", "Experiment not found", 404)
            if row["state"] in TERMINAL:
                return self._public_run(dict(row))
            if row["state"] in {"awaiting_approval", "approved", "authorized", "queued"}:
                if row["slot_reserved"]:
                    connection.execute(update(control).where(control.c.id == 1).values(active_count=control.c.active_count - 1))
                connection.execute(update(runs).where(runs.c.id == run_id).values(state="cancelled", slot_reserved=False, cancel_requested=True))
            else:
                connection.execute(update(runs).where(runs.c.id == run_id).values(cancel_requested=True))
        return self._public_run(self.owned(principal, run_id))

    def get(self, principal: Principal, run_id: str) -> dict:
        principal.require("experiments:read")
        return self._public_run(self.owned(principal, run_id))

    def list(self, principal: Principal) -> dict:
        principal.require("experiments:read")
        with self.store.engine.connect() as connection:
            rows = connection.execute(select(runs).where(runs.c.owner == principal.owner).order_by(runs.c.created_at.desc(), runs.c.id).limit(50)).mappings()
            heartbeat = connection.execute(select(control.c.worker_seen_at).where(control.c.id == 1)).scalar_one()
            experiments = []
            for row in rows:
                verified = self._public_run(dict(row))
                experiments.append({"id": row["id"], "state": verified["state"],
                                    "created_at": row["created_at"], "error": verified["error"],
                                    "last_observed_at": row["last_observed_at"],
                                    "workload": row["plan"]["workload"],
                                    "provider": row["plan"]["provider"]})
            return {"experiments": experiments, "worker_last_seen_at": heartbeat}

    def invoke(self, principal: Principal, name: str, arguments: dict) -> dict:
        try:
            if name == "integrations_list":
                if arguments: raise ValueError()
                return self.integrations(principal)
            if name == "experiments_list":
                if arguments: raise ValueError()
                return self.list(principal)
            if name == "experiments_prepare":
                return self.prepare(principal, Prepare.model_validate(arguments))
            identifier = RunID.model_validate(arguments).run_id
            function = {"experiments_get": self.get, "experiments_submit": self.submit, "experiments_cancel": self.cancel}.get(name)
            if function is None:
                raise GatewayError("unknown_tool", "Unknown tool")
            return function(principal, identifier)
        except (ValidationError, ValueError, TypeError):
            raise GatewayError("invalid_arguments", "Tool arguments do not match the schema")
