"""ChatGPT-facing experiment tool contracts and owner-scoped service facade."""
from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import and_, or_, select

from .service import ExperimentService, GatewayError, Principal, digest
from .store import control, runs
from .admission import evaluate_admission, load_local_cpu_policy, plan_for_workload
from .artifacts import ArtifactStore, inspect_artifact_storage
from .health import heartbeat_age, heartbeat_is_fresh
from .provider_selection import (
    gpu_requirements as _gpu_requirements,
    plan_for_selected_gpu,
    select_registered_candidate,
)

TERMINAL = {"succeeded", "failed", "cancelled", "expired"}
STATUS_LOG_LIMIT = 4096
STATE_SUMMARY = {
    "awaiting_approval": "実行計画は準備できました。承認が必要です。",
    "authorized": "登録済みlocal CPU policyでこのsmoke planは事前許可されています。",
    "approved": "実行計画は承認済みで、workerの受付を待っています。",
    "queued": "実験をキューに登録しました。",
    "submitting": "workerが実行環境を開始しています。",
    "submit_unknown": "開始結果を確認できません。再送せず、既存の実行を照合しています。",
    "running": "実験を実行中です。",
    "succeeded": "実験が終了しました。結果を取得できます。",
    "failed": "実験が失敗しました。結果と実行状態を確認してください。",
    "cancelled": "実験を停止しました。",
    "expired": "実行前に承認または価格情報の期限が切れました。",
}


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictInput):
    pass


class PrepareInput(StrictInput):
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    workload: str = Field(min_length=1, max_length=100)
    parameters: dict = Field(default_factory=dict)
    runtime_seconds: int = Field(default=300, ge=1, le=3600)
    max_cost_usd: str = Field(default="0.00", pattern=r"^(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,6})?$")
    resource_policy: Literal["free_first"] = "free_first"
    requires_gpu: bool | None = None
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")


class RunInput(StrictInput):
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class ArtifactInput(RunInput):
    artifact_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    offset: int = Field(default=0, ge=0)
    length: int = Field(default=18 * 1024, ge=1, le=24 * 1024)


class SubmitInput(RunInput):
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ListInput(StrictInput):
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = Field(default=None, max_length=512)
    workload: str | None = Field(default=None, min_length=1, max_length=100)
    repository: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    state: Literal[
        "awaiting_approval", "approved", "authorized", "queued", "submitting", "submit_unknown",
        "running", "succeeded", "failed", "cancelled", "expired",
    ] | None = None
    created_after: int | None = Field(default=None, ge=0)
    created_before: int | None = Field(default=None, ge=0)


def _envelope(*, status: str, summary: str, machine_state: dict,
              next_actions: list[str], blocker: str | None = None, **extra) -> dict:
    return {"schema_version": 2, "status": status, "human_summary": summary,
            "machine_state": machine_state, "next_allowed_actions": next_actions,
            "blocking_reason": blocker, **extra}


def _cursor_encode(owner: str, created_at: int, run_id: str) -> str:
    raw = json.dumps({"owner": owner, "created_at": created_at, "id": run_id},
                     separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _cursor_decode(value: str, owner: str) -> tuple[int, str]:
    try:
        if not isinstance(value, str) or len(value) > 512:
            raise ValueError()
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        data = json.loads(raw)
        if (not isinstance(data, dict) or set(data) != {"owner", "created_at", "id"} or
                data["owner"] != owner or type(data["created_at"]) is not int or
                not isinstance(data["id"], str) or not data["id"]):
            raise ValueError()
        return data["created_at"], data["id"]
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
        raise GatewayError("invalid_cursor", "The experiment list cursor is invalid", 400) from None


def _list(service: ExperimentService, principal: Principal, request: ListInput) -> dict:
    principal.require("experiments:read")
    if request.created_after is not None and request.created_before is not None and request.created_after > request.created_before:
        raise GatewayError("invalid_arguments", "created_after must not be later than created_before")
    predicates = [runs.c.owner == principal.owner]
    if request.state:
        predicates.append(runs.c.state == request.state)
    if request.created_after is not None:
        predicates.append(runs.c.created_at >= request.created_after)
    if request.created_before is not None:
        predicates.append(runs.c.created_at <= request.created_before)
    if request.workload:
        predicates.append(runs.c.plan["workload"].as_string() == request.workload)
    if request.repository:
        predicates.append(runs.c.plan["repository"].as_string() == request.repository)
    if request.cursor:
        created_at, run_id = _cursor_decode(request.cursor, principal.owner)
        predicates.append(or_(runs.c.created_at < created_at,
                              and_(runs.c.created_at == created_at, runs.c.id < run_id)))
    with service.store.engine.connect() as connection:
        rows = connection.execute(
            select(runs).where(*predicates).order_by(runs.c.created_at.desc(), runs.c.id.desc())
            .limit(request.limit + 1)
        ).mappings().all()
    has_more = len(rows) > request.limit
    page = rows[:request.limit]
    values = [{"run_id": row["id"], "state": row["state"], "created_at": row["created_at"],
               "last_observed_at": row["last_observed_at"],
               "workload": row["plan"].get("workload"),
               "repository": row["plan"].get("repository"),
               "source_sha": row["plan"].get("source_sha"),
               "provider": row["plan"].get("provider"),
               "cleanup_state": row["cleanup_state"]}
              for row in page]
    next_cursor = _cursor_encode(principal.owner, page[-1]["created_at"], page[-1]["id"]) if has_more and page else None
    return _envelope(status="ok", summary=f"{len(values)}件の実験を取得しました。",
                     machine_state={"count": len(values)}, next_actions=[],
                     experiments=values, next_cursor=next_cursor,
                     worker_last_seen_at=service.list(principal)["worker_last_seen_at"])


def _capabilities(service: ExperimentService, principal: Principal) -> dict:
    """Describe workload-level readiness without treating configuration as capacity."""
    data = service.integrations(principal)
    now = int(service.clock())
    control_store_available = True
    try:
        with service.store.engine.connect() as connection:
            row = connection.execute(select(
                control.c.worker_seen_at, control.c.supervisor_seen_at,
                control.c.active_count,
            ).where(control.c.id == 1)).mappings().first()
    except Exception:
        # Keep capabilities read-only and fail closed, while distinguishing a
        # control-store outage from an online store with stopped workers.
        control_store_available = False
        row = None
    if row is None:
        # A reachable database without the singleton control row is not a
        # healthy admission store either.
        control_store_available = False

    worker_seen_at = row["worker_seen_at"] if row else 0
    supervisor_seen_at = row["supervisor_seen_at"] if row else 0
    worker_age = heartbeat_age(now, worker_seen_at)
    supervisor_age = heartbeat_age(now, supervisor_seen_at)
    worker_ready = heartbeat_is_fresh(now, worker_seen_at)
    supervisor_ready = heartbeat_is_fresh(now, supervisor_seen_at)
    active_count = row["active_count"] if row else None
    capacity_available = (
        control_store_available
        and type(active_count) is int
        and active_count >= 0
        and active_count < service.settings.max_inflight
    )

    local_policy = None
    local_policy_error = None
    try:
        local_policy = load_local_cpu_policy()
    except (OSError, ValueError, TypeError):
        local_policy_error = "LOCAL_CPU_POLICY_INVALID"

    enabled_providers = {provider["id"] for provider in data["providers"]
                         if provider["enabled"]}
    artifact_storage = inspect_artifact_storage(
        service.settings.artifact_dir, service.settings.artifact_min_free_bytes)
    resources = []
    for workload_info in data["workloads"]:
        name = workload_info["id"]
        workload = service.workloads[name]
        provider = workload.provider
        registration = service.registry.get(provider)
        provider_enabled = provider in enabled_providers
        blockers: list[str] = []
        if provider == "demo":
            availability = "simulation_only"
            provider_availability = "UNKNOWN"
            cost_classification = "LOCAL"
            additional_cost = "0"
            approval_mode = "none"
        elif provider == "local_cpu":
            cost_classification = "LOCAL"
            additional_cost = "0"
            approval_mode = "operator_local_policy"
            if not control_store_available:
                blockers.append("CONTROL_STORE_UNAVAILABLE")
            if not workload.source_repository or not workload.source_sha:
                blockers.append("SOURCE_IDENTITY_UNCONFIGURED")
            if local_policy_error:
                blockers.append(local_policy_error)
            elif local_policy is not None:
                try:
                    probe = plan_for_workload(
                        workload_name=name,
                        workload_manifest=workload.model_dump(mode="json"),
                        repository=workload.source_repository,
                        source_sha=workload.source_sha,
                        parameters={}, runtime_seconds=1,
                        max_cost_usd="0", now=now, policy=local_policy,
                    )
                    decision = evaluate_admission(probe, local_policy, now)
                    if not decision.allowed:
                        blockers.append(decision.blocking_reason or "LOCAL_CPU_POLICY_INVALID")
                except (KeyError, ValueError, TypeError):
                    blockers.append("LOCAL_CPU_POLICY_INVALID")
            if not provider_enabled:
                blockers.append("LOCAL_CPU_BACKEND_DISABLED")
            if not artifact_storage["available"]:
                blockers.append("ARTIFACT_STORAGE_UNAVAILABLE")
            if not worker_ready:
                blockers.append("WORKER_OFFLINE")
            if not supervisor_ready:
                blockers.append("RECOVERY_SUPERVISOR_OFFLINE")
            if not capacity_available:
                blockers.append("CONCURRENCY_UNAVAILABLE")
            availability = "queue_ready" if not blockers else "blocked"
            provider_availability = "AVAILABLE" if availability == "queue_ready" else "UNAVAILABLE"
        else:
            approval_mode = "browser"
            provider_availability = "UNAVAILABLE" if not provider_enabled else "UNKNOWN"
            additional_cost = None
            cost_classification = "UNKNOWN"
            quote_current = (workload.quoted_usd_per_hour is not None and
                             bool(workload.quote_reference) and
                             workload.quote_expires_at > now)
            if quote_current:
                cost_classification = "PAID"
                additional_cost = str(
                    workload.quoted_usd_per_hour * Decimal(workload.max_runtime_seconds) /
                    Decimal(3600)
                )
            if not provider_enabled:
                blockers.append("PROVIDER_DISABLED")
                availability = "blocked"
            else:
                blockers.append("PROVIDER_LIVE_ACCEPTANCE_REQUIRED")
                availability = "configured_unverified"

        candidate_selection = None
        if workload.requires_gpu:
            requirements, decision, missing_requirements, evidence_status, inventory_complete = select_registered_candidate(
                service.store, service.settings, name=name, workload=workload,
                now=now, max_cost_usd=workload.max_cost_usd,
            )
            cpu_alternatives = sorted(
                candidate_name for candidate_name, candidate_workload
                in service.workloads.items()
                if not candidate_workload.requires_gpu and
                candidate_workload.provider == "local_cpu"
            )
            alternatives = ([{"kind": "local_cpu_workload", "workload": item}
                             for item in cpu_alternatives] +
                            [{"kind": "paid_gpu_path",
                              "status": "unavailable_until_live_acceptance"}])
            if requirements is None:
                candidate_selection = {
                    "status": "not_evaluated",
                    "blocking_reason": "WORKLOAD_REQUIREMENTS_INCOMPLETE",
                    "missing_workload_requirements": missing_requirements,
                    "provider_evidence": "NOT_AVAILABLE",
                    "alternatives": alternatives,
                }
            else:
                decision_status = (
                    "candidate_selected" if decision is not None and decision.selected is not None else
                    "not_evaluated" if not inventory_complete else "blocked"
                )
                candidate_selection = {
                    "status": decision_status,
                    "blocking_reason": (None if decision is None or decision.blocking_reason is None else
                                        decision.blocking_reason.value),
                    "missing_workload_requirements": [],
                    "provider_evidence": evidence_status,
                    "workload_fingerprint": requirements.fingerprint(),
                    "selector_result": None if decision is None else decision.to_dict(),
                    "alternatives": alternatives,
                }

        resources.append({
            "workload": name,
            "provider": provider,
            "execution": registration.execution if registration else "unsupported",
            "availability": availability,
            # `availability` above is the Gateway submission state. Keep live
            # provider/resource evidence separate so configured-but-unverified
            # providers are never presented as available inventory.
            "provider_availability": provider_availability,
            "submission_available": availability == "queue_ready",
            "simulation": provider == "demo",
            "execution_capacity": "UNVERIFIED",
            "blocking_reasons": blockers,
            "source_repository": workload.source_repository or None,
            "source_sha": workload.source_sha or None,
            "requires_gpu": workload.requires_gpu,
            "gpu_model": workload.gpu if workload.requires_gpu else None,
            "gpu_vram_mib": None,
            "cpu_cores": workload.cpu,
            "memory_mib": workload.memory_mib,
            "max_runtime_seconds": workload.max_runtime_seconds,
            "max_cost_usd": "0" if provider in {"local_cpu", "demo"} else str(workload.max_cost_usd),
            "cost_classification": cost_classification,
            "additional_provider_cost_usd_at_max_runtime": additional_cost,
            "quote_reference": workload.quote_reference or None,
            "quote_expires_at": workload.quote_expires_at or None,
            "cost_scope": "Provider charge only; host, electricity and Gateway costs are excluded.",
            "quota_status": ("NOT_APPLICABLE_SIMULATION" if provider == "demo" else
                             "LOCAL_CAPACITY_UNVERIFIED" if provider == "local_cpu" else "UNKNOWN"),
            "configured_run_concurrency": service.settings.max_inflight,
            "approval_mode": approval_mode,
            "human_approval_required": approval_mode == "browser",
            "parameter_schema": workload.parameter_schema,
            **({"candidate_selection": candidate_selection}
               if candidate_selection is not None else {}),
        })

    submission_available = any(resource["submission_available"] for resource in resources)
    return _envelope(
        status="ok" if submission_available else "blocked",
        summary=("現在受付可能な登録workloadを確認しました。" if submission_available else
                 "現在受付可能な実験環境はありません。blockerを確認してください。"),
        machine_state={
            "providers": data["providers"],
            "resources": resources,
            "control_store": {"available": control_store_available},
            "artifact_storage": artifact_storage,
            "worker": {"last_seen_at": worker_seen_at, "age_seconds": worker_age,
                       "ready": worker_ready},
            "recovery_supervisor": {"last_seen_at": supervisor_seen_at,
                                    "age_seconds": supervisor_age,
                                    "ready": supervisor_ready},
            "capacity": {"active_runs": active_count,
                         "max_concurrent_runs": service.settings.max_inflight,
                         "available": capacity_available},
        },
        next_actions=["experiment_prepare"] if submission_available else ["retry_later"],
        blocker=None if submission_available else "NO_QUEUEABLE_RESOURCE",
    )


def invoke(service: ExperimentService, principal: Principal, name: str, arguments: dict) -> dict:
    """Invoke canonical ChatGPT-facing tools without bypassing existing service gates."""
    try:
        if name == "experiment_capabilities":
            EmptyInput.model_validate(arguments)
            return _capabilities(service, principal)

        if name == "experiment_prepare":
            request = PrepareInput.model_validate(arguments)
            principal.require("experiments:run")
            request_payload = request.model_dump(mode="json")
            request_hash = digest(request_payload)
            existing = service.existing_prepare(principal, request_payload)
            if existing is not None:
                state = existing["state"]
                response_status = ("ok" if state in {"authorized", "succeeded"} else
                                   "error" if state in {"failed", "cancelled", "expired"} else
                                   "pending")
                next_actions = (
                    ["approve_exact_plan_in_browser"] if state == "awaiting_approval" else
                    ["experiment_submit"] if state == "authorized" else
                    ["experiment_result"] if state == "succeeded" else
                    ["experiment_status"]
                )
                blocker = "APPROVAL_REQUIRED" if state == "awaiting_approval" else None
                machine_state = {
                    "run_id": existing["id"], "state": state,
                    "plan_fingerprint": existing["fingerprint"],
                }
                binding = existing.get("plan", {}).get("selection_binding")
                if isinstance(binding, dict):
                    machine_state["selection_binding"] = binding
                return _envelope(
                    status=response_status,
                    summary=STATE_SUMMARY.get(state, "既存の実験状態を確認しました。"),
                    machine_state=machine_state,
                    next_actions=next_actions,
                    blocker=blocker,
                )
            workload = service.workloads.get(request.workload)
            if workload is None:
                return _envelope(status="blocked", summary="このworkloadはoperator registryに登録されていません。",
                                 machine_state={}, next_actions=["choose_registered_workload"],
                                 blocker="WORKLOAD_NOT_REGISTERED")
            if workload.provider == "demo":
                return _envelope(status="blocked", summary="このworkloadはsimulation専用で、実験として実行できません。",
                                 machine_state={"simulation": True}, next_actions=["choose_registered_workload"],
                                 blocker="SIMULATION_ONLY")
            if (not workload.source_repository or not workload.source_sha or
                    request.repository != workload.source_repository or request.commit != workload.source_sha):
                return _envelope(status="blocked", summary="要求されたrepository/commitが登録workloadのsource identityと一致しません。",
                                 machine_state={"expected_repository": workload.source_repository or None,
                                                "expected_source_sha": workload.source_sha or None},
                                 next_actions=["use_registered_source_identity"],
                                 blocker="SOURCE_IDENTITY_MISMATCH")
            if request.requires_gpu is not None and request.requires_gpu != workload.requires_gpu:
                return _envelope(status="blocked", summary="要求されたGPU要件がoperator登録workloadの要件と一致しません。",
                                 machine_state={"requires_gpu": workload.requires_gpu}, next_actions=["choose_registered_workload"],
                                 blocker="DEVICE_REQUIREMENT_MISMATCH")
            if workload.requires_gpu:
                if request.runtime_seconds > workload.max_runtime_seconds:
                    return _envelope(status="blocked", summary="runtimeがoperator登録上限を超えています。",
                                     machine_state={"max_runtime_seconds": workload.max_runtime_seconds},
                                     next_actions=["experiment_capabilities"], blocker="RUNTIME_LIMIT")
                if Decimal(request.max_cost_usd) > workload.max_cost_usd:
                    return _envelope(status="blocked", summary="cost ceilingがoperator登録上限を超えています。",
                                     machine_state={"max_cost_usd": str(workload.max_cost_usd)},
                                     next_actions=["experiment_capabilities"], blocker="COST_LIMIT")
                requirements, decision, missing, evidence_status, _complete = select_registered_candidate(
                    service.store, service.settings, name=request.workload,
                    workload=workload, now=int(service.clock()),
                    max_cost_usd=Decimal(request.max_cost_usd),
                )
                if requirements is None:
                    return _envelope(
                        status="blocked",
                        summary="GPU workloadの実行条件が未登録か不完全です。",
                        machine_state={"requires_gpu": True, "provider": workload.provider,
                                       "missing_workload_requirements": missing,
                                       "provider_evidence": evidence_status},
                        next_actions=["experiment_capabilities"],
                        blocker="WORKLOAD_REQUIREMENTS_INCOMPLETE",
                    )
                if decision is None or decision.selected is None:
                    blocker = ("PROVIDER_EVIDENCE_UNAVAILABLE" if decision is None or
                               decision.blocking_reason is None else decision.blocking_reason.value)
                    return _envelope(
                        status="blocked",
                        summary="現在の署名済みprovider evidenceでは、このGPU要求を安全に満たせません。",
                        machine_state={"requires_gpu": True, "provider": workload.provider,
                                       "provider_evidence": evidence_status,
                                       "selector_result": None if decision is None else decision.to_dict()},
                        next_actions=["experiment_capabilities"], blocker=blocker,
                    )
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", workload.image_digest):
                    return _envelope(
                        status="blocked",
                        summary="GPU workloadは固定image digestなしでは承認planを作成できません。",
                        machine_state={"requires_gpu": True, "provider": workload.provider},
                        next_actions=["update_registered_workload"],
                        blocker="IMMUTABLE_IMAGE_REQUIRED",
                    )
                gpu_plan = plan_for_selected_gpu(
                    name=request.workload, workload=workload,
                    requirements=requirements, evidence=decision.selected,
                    repository=request.repository, source_sha=request.commit,
                    parameters=request.parameters, runtime_seconds=request.runtime_seconds,
                    max_cost_usd=request.max_cost_usd,
                )
                prepared = service.prepare_bound_gpu(
                    principal, gpu_plan, request.idempotency_key,
                    request_hash=request_hash)
                return _envelope(
                    status="pending", summary=STATE_SUMMARY[prepared["state"]],
                    machine_state={"run_id": prepared["id"], "state": prepared["state"],
                                   "plan_fingerprint": prepared["fingerprint"],
                                   "selection_binding": gpu_plan.selection_binding.model_dump(mode="json")},
                    next_actions=["approve_exact_plan_in_browser"],
                    blocker="APPROVAL_REQUIRED",
                )
            if workload.provider != "local_cpu":
                return _envelope(status="blocked", summary="現在、free_firstで実行できるCPU backendが有効ではありません。",
                                 machine_state={"provider": workload.provider},
                                 next_actions=["retry_later", "experiment_capabilities"],
                                 blocker="LOCAL_CPU_BACKEND_UNAVAILABLE")
            try:
                policy = load_local_cpu_policy()
                plan = plan_for_workload(workload_name=request.workload,
                    workload_manifest=workload.model_dump(mode="json"),
                    repository=request.repository, source_sha=request.commit,
                    parameters=request.parameters, runtime_seconds=request.runtime_seconds,
                    max_cost_usd=request.max_cost_usd, now=int(service.clock()), policy=policy)
                decision = evaluate_admission(plan, policy, int(service.clock()))
            except (OSError, ValueError, TypeError):
                return _envelope(status="blocked", summary="local CPU policyを安全に読み取れませんでした。",
                                 machine_state={}, next_actions=["retry_later"],
                                 blocker="LOCAL_CPU_POLICY_INVALID")
            if not decision.allowed:
                return _envelope(status="blocked", summary="operatorのlocal CPU admission policyがこのplanを許可しません。",
                                 machine_state={"policy_version": policy.get("version"),
                                                "policy_digest": decision.policy_digest,
                                                "valid_until": decision.valid_until},
                                 next_actions=["experiment_capabilities"],
                                 blocker=decision.blocking_reason)
            registration = service.registry.get("local_cpu")
            if registration is None or not registration.enabled(service.settings):
                return _envelope(status="blocked", summary="local CPU worker backendが登録・有効化されていません。",
                                 machine_state={"policy_digest": decision.policy_digest},
                                 next_actions=["retry_later"], blocker="LOCAL_CPU_BACKEND_UNAVAILABLE")
            artifact_storage = inspect_artifact_storage(
                service.settings.artifact_dir, service.settings.artifact_min_free_bytes)
            if not artifact_storage["available"]:
                return _envelope(status="blocked", summary="local CPU実験の成果物ストレージを利用できません。",
                                 machine_state={"artifact_storage": artifact_storage},
                                 next_actions=["retry_later", "experiment_capabilities"],
                                 blocker="ARTIFACT_STORAGE_UNAVAILABLE")
            prepared = service.prepare_local(
                principal, plan, request.idempotency_key, policy, decision,
                request_hash=request_hash)
            return _envelope(status="ok", summary=STATE_SUMMARY[prepared["state"]],
                             machine_state={"run_id": prepared["id"], "state": prepared["state"],
                                            "plan_fingerprint": prepared["fingerprint"],
                                            "policy_digest": decision.policy_digest,
                                            "valid_until": decision.valid_until},
                             next_actions=["experiment_submit"])

        if name == "experiment_submit":
            request = SubmitInput.model_validate(arguments)
            principal.require("experiments:run")
            stored = service.get(principal, request.run_id)
            if stored["fingerprint"] != request.plan_fingerprint:
                raise GatewayError("plan_changed", "The supplied fingerprint does not match the stored plan", 409)
            result = service.submit(principal, request.run_id)
            state = result["state"]
            return _envelope(status="pending", summary=STATE_SUMMARY.get(state, "実験状態を確認しました。"),
                             machine_state={"run_id": result["id"], "state": state,
                                            "plan_fingerprint": result["fingerprint"]},
                             next_actions=["experiment_status"],
                             blocker="APPROVAL_REQUIRED" if state == "awaiting_approval" else None)

        if name == "experiment_artifact":
            request = ArtifactInput.model_validate(arguments)
            principal.require("experiments:read")
            run = service.get(principal, request.run_id)
            if run["state"] not in TERMINAL:
                return _envelope(status="pending", summary="成果物は実験とcleanupが完了してから取得できます。",
                                 machine_state={"run_id": request.run_id},
                                 next_actions=["experiment_status"], blocker="ARTIFACT_NOT_READY")
            stored = service.store.read(request.run_id)
            if stored is None or stored["cleanup_state"] not in {"complete", "not_required"}:
                raise GatewayError("artifact_unavailable", "Experiment cleanup is not confirmed", 409)
            result = run.get("result")
            manifests = result.get("artifacts", []) if isinstance(result, dict) else []
            manifest = next((item for item in manifests
                             if isinstance(item, dict) and item.get("artifact_id") == request.artifact_id), None)
            if manifest is None:
                raise GatewayError("not_found", "Artifact not found", 404)
            now = int(service.clock())
            expiry = manifest.get("expires_at")
            if type(expiry) is int and expiry <= now:
                raise GatewayError("artifact_expired", "Artifact retention period has expired", 410)
            try:
                chunk = ArtifactStore(service.settings.artifact_dir).get(
                    principal.owner, request.run_id, request.artifact_id,
                    offset=request.offset, length=request.length,
                    expected_sha256=manifest["sha256"], expected_size=manifest["size_bytes"])
            except (OSError, ValueError, KeyError):
                raise GatewayError("artifact_unavailable", "Artifact is missing or failed integrity verification", 410) from None
            next_offset = request.offset + len(chunk)
            return _envelope(status="ok", summary="成果物の一部を取得しました。",
                             machine_state={"run_id": request.run_id, "artifact_id": request.artifact_id,
                                            "offset": request.offset, "next_offset": next_offset,
                                            "complete": next_offset >= manifest["size_bytes"],
                                            "sha256": manifest["sha256"], "size_bytes": manifest["size_bytes"],
                                            "media_type": manifest["media_type"],
                                            "data_base64": base64.b64encode(chunk).decode("ascii")},
                             next_actions=[])

        if name in {"experiment_status", "experiment_result", "experiment_cancel"}:
            request = RunInput.model_validate(arguments)
            if name == "experiment_cancel":
                result = service.cancel(principal, request.run_id)
            else:
                result = service.get(principal, request.run_id)
            state = result["state"]
            cleanup = (service.store.read(request.run_id) or {}).get("cleanup_state", "unknown")
            if name == "experiment_result" and state not in TERMINAL:
                return _envelope(status="pending", summary="実験はまだ終了していません。",
                                 machine_state={"run_id": result["id"], "state": state,
                                                "cleanup_state": cleanup,
                                                "last_observed_at": result.get("last_observed_at")},
                                 next_actions=["experiment_status"], blocker=None)
            stored_result = result.get("result")
            result_omitted = (isinstance(stored_result, dict) and
                              stored_result.get("result_omitted") is True)
            payload = {"run_id": result["id"], "state": state,
                       "plan_fingerprint": result["fingerprint"],
                       "last_observed_at": result.get("last_observed_at"),
                       "cleanup_state": cleanup,
                       "result": (stored_result if name == "experiment_result" and not result_omitted else None),
                       "error_code": (result.get("error") or
                                      (stored_result.get("failure_code") if isinstance(stored_result, dict) else None) or
                                      ("result_size_limit" if result_omitted else None))}
            if result_omitted:
                payload["result_omitted"] = True
            if name == "experiment_status":
                result_data = result.get("result")
                raw_logs = result_data.get("logs") if isinstance(result_data, dict) else None
                if isinstance(raw_logs, str):
                    payload["logs"] = raw_logs[-STATUS_LOG_LIMIT:]
                    payload["logs_truncated"] = len(raw_logs) > STATUS_LOG_LIMIT
                status = "ok" if state in TERMINAL else "pending"
                actions = [] if state in TERMINAL else ["experiment_status", "experiment_cancel"]
            elif name == "experiment_cancel":
                status, actions = "pending", ["experiment_status"] if state not in TERMINAL else []
            else:
                if result_omitted:
                    return _envelope(
                        status="blocked",
                        summary="実験は完了しましたが、結果データはサイズ上限により取得できません。",
                        machine_state=payload,
                        next_actions=[],
                        blocker="RESULT_OMITTED",
                    )
                status = "error" if state != "succeeded" else "ok"
                actions = []
                if (result.get("result") or {}).get("simulation") is True:
                    return _envelope(status="blocked", summary="このrunはsimulationです。実計算の成功には数えられません。",
                                     machine_state=payload, next_actions=[], blocker="SIMULATION_RESULT")
            summary = ("実験は完了しましたが、結果データはサイズ上限により省略されました。"
                       if name == "experiment_status" and result_omitted else
                       STATE_SUMMARY.get(state, "実験状態を確認しました。"))
            return _envelope(status=status, summary=summary,
                             machine_state=payload, next_actions=actions,
                             blocker=payload["error_code"] if state == "failed" else None)

        if name == "experiment_list":
            request = ListInput.model_validate(arguments)
            return _list(service, principal, request)
        raise GatewayError("unknown_tool", "Unknown ChatGPT experiment tool", 404)
    except ValidationError:
        raise GatewayError("invalid_arguments", "Tool arguments do not match the schema", 400) from None
