"""ChatGPT-facing experiment tool contracts and owner-scoped service facade."""
from __future__ import annotations

import base64
import binascii
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import and_, or_, select

from .service import ExperimentService, GatewayError, Prepare, Principal
from .store import runs
from .admission import evaluate_admission, load_local_cpu_policy, plan_for_workload

TERMINAL = {"succeeded", "failed", "cancelled", "expired"}
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


def invoke(service: ExperimentService, principal: Principal, name: str, arguments: dict) -> dict:
    """Invoke canonical ChatGPT-facing tools without bypassing existing service gates."""
    try:
        if name == "experiment_capabilities":
            EmptyInput.model_validate(arguments)
            data = service.integrations(principal)
            worker = service.list(principal)["worker_last_seen_at"]
            enabled_providers = {provider["id"] for provider in data["providers"] if provider["enabled"]}
            runnable = [w for w in data["workloads"] if w["provider"] == "local_cpu" and
                        w["provider"] in enabled_providers and
                        w["source_repository"] and w["source_sha"]]
            return _envelope(
                status="ok" if runnable else "blocked",
                summary=("登録済みの実行環境を確認しました。" if runnable else
                         "実行環境の登録がありません。現在登録されているdemoはsimulation専用です。"),
                machine_state={"providers": data["providers"], "workloads": data["workloads"],
                               "worker_last_seen_at": worker},
                next_actions=["experiment_prepare"] if runnable else ["retry_later"],
                blocker=None if runnable else "NO_EXECUTABLE_WORKLOAD",
            )

        if name == "experiment_prepare":
            request = PrepareInput.model_validate(arguments)
            principal.require("experiments:run")
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
                return _envelope(status="blocked", summary="GPU必須workloadをCPUへfallbackすることはできません。対応するGPU実行経路がありません。",
                                 machine_state={"requires_gpu": True, "provider": workload.provider},
                                 next_actions=["experiment_capabilities"], blocker="GPU_BACKEND_UNAVAILABLE")
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
            prepared = service.prepare_local(principal, plan, request.idempotency_key, policy, decision)
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
                                                "cleanup_state": cleanup},
                                 next_actions=["experiment_status"], blocker=None)
            payload = {"run_id": result["id"], "state": state,
                       "plan_fingerprint": result["fingerprint"],
                       "cleanup_state": cleanup,
                       "result": result.get("result") if name == "experiment_result" else None,
                       "error_code": result.get("error") or None}
            if name == "experiment_status":
                status = "ok" if state in TERMINAL else "pending"
                actions = [] if state in TERMINAL else ["experiment_status", "experiment_cancel"]
            elif name == "experiment_cancel":
                status, actions = "pending", ["experiment_status"] if state not in TERMINAL else []
            else:
                status = "error" if state != "succeeded" else "ok"
                actions = []
                if (result.get("result") or {}).get("simulation") is True:
                    return _envelope(status="blocked", summary="このrunはsimulationです。実計算の成功には数えられません。",
                                     machine_state=payload, next_actions=[], blocker="SIMULATION_RESULT")
            return _envelope(status=status, summary=STATE_SUMMARY.get(state, "実験状態を確認しました。"),
                             machine_state=payload, next_actions=actions,
                             blocker=payload["error_code"] if state == "failed" else None)

        if name == "experiment_list":
            request = ListInput.model_validate(arguments)
            return _list(service, principal, request)
        raise GatewayError("unknown_tool", "Unknown ChatGPT experiment tool", 404)
    except ValidationError:
        raise GatewayError("invalid_arguments", "Tool arguments do not match the schema", 400) from None
