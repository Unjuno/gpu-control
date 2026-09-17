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
from .registry import default_registry

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
    return {key: row.get(key) for key in ("id", "state", "created_at", "fingerprint", "plan", "result", "error", "cancel_requested", "approved_until")}


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
                               "parameter_schema": w.parameter_schema} for name, w in self.workloads.items()]}

    def owned(self, principal: Principal, run_id: str) -> dict:
        row = self.store.read(run_id)
        if not row or row["owner"] != principal.owner:
            raise GatewayError("not_found", "Experiment not found", 404)
        return row

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
                return public_run(dict(old))
            count = connection.execute(select(func.count()).select_from(runs).where(runs.c.owner == principal.owner, runs.c.state.not_in(list(TERMINAL)))).scalar_one()
            if count >= self.settings.max_open_requests:
                raise GatewayError("request_limit", "Too many unfinished experiments", 429)
            run_id = uuid.uuid4().hex
            connection.execute(insert(runs).values(id=run_id, owner=principal.owner,
                idempotency_key=request.idempotency_key, request_hash=request_hash,
                fingerprint=digest(plan), plan=plan, state="awaiting_approval", created_at=now))
        return public_run(self.owned(principal, run_id))

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
        return public_run(self.owned(principal, run_id))

    def submit(self, principal: Principal, run_id: str) -> dict:
        principal.require("experiments:run")
        with self.store.transaction() as connection:
            admission = self.store.lock_control(connection)
            row = connection.execute(select(runs).where(runs.c.id == run_id, runs.c.owner == principal.owner)).mappings().first()
            if row is None:
                raise GatewayError("not_found", "Experiment not found", 404)
            if row["state"] in {"queued", "submitting", "submit_unknown", "running"} | TERMINAL:
                return public_run(dict(row))
            if row["state"] != "approved" or row["approved_until"] <= int(self.clock()):
                raise GatewayError("approval_required", "Current Web approval of this exact plan is required", 409)
            p = row["plan"]["provider"]
            registration = self.registry.get(p)
            if registration is None:
                raise GatewayError("provider_unavailable", "Provider backend is not registered", 409)
            if not registration.enabled(self.settings):
                raise GatewayError("provider_disabled", "This provider is not enabled on the gateway", 409)
            if admission["active_count"] >= self.settings.max_inflight:
                raise GatewayError("concurrency_limit", "An experiment is already in flight", 409)
            connection.execute(update(control).where(control.c.id == 1).values(active_count=control.c.active_count + 1))
            connection.execute(update(runs).where(runs.c.id == run_id).values(state="queued", slot_reserved=True))
        return public_run(self.owned(principal, run_id))

    def cancel(self, principal: Principal, run_id: str) -> dict:
        principal.require("experiments:cancel")
        with self.store.transaction() as connection:
            self.store.lock_control(connection)
            row = connection.execute(select(runs).where(runs.c.id == run_id, runs.c.owner == principal.owner)).mappings().first()
            if row is None:
                raise GatewayError("not_found", "Experiment not found", 404)
            if row["state"] in TERMINAL:
                return public_run(dict(row))
            if row["state"] in {"awaiting_approval", "approved", "queued"}:
                if row["slot_reserved"]:
                    connection.execute(update(control).where(control.c.id == 1).values(active_count=control.c.active_count - 1))
                connection.execute(update(runs).where(runs.c.id == run_id).values(state="cancelled", slot_reserved=False, cancel_requested=True))
            else:
                connection.execute(update(runs).where(runs.c.id == run_id).values(cancel_requested=True))
        return public_run(self.owned(principal, run_id))

    def get(self, principal: Principal, run_id: str) -> dict:
        principal.require("experiments:read")
        return public_run(self.owned(principal, run_id))

    def list(self, principal: Principal) -> dict:
        principal.require("experiments:read")
        with self.store.engine.connect() as connection:
            rows = connection.execute(select(runs).where(runs.c.owner == principal.owner).order_by(runs.c.created_at.desc(), runs.c.id).limit(50)).mappings()
            heartbeat = connection.execute(select(control.c.worker_seen_at).where(control.c.id == 1)).scalar_one()
            return {"experiments": [{"id": row["id"], "state": row["state"],
                                     "created_at": row["created_at"], "error": row["error"],
                                     "workload": row["plan"]["workload"], "provider": row["plan"]["provider"]}
                                    for row in rows], "worker_last_seen_at": heartbeat}

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
