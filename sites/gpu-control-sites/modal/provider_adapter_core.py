"""Stateless registered-provider protocol for the Modal adapter.

Sites/D1 owns plans, authorization and durable run state.  This module accepts
only the two reviewed free-provider manifests and returns an opaque handle that
Sites persists.  It deliberately has no database or arbitrary execution API.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping


KAGGLE_WORKLOAD = "orbitune-kaggle-100-step-v1"
HF_WORKLOAD = "orbitune-zero-gpu-eval-v1"
REPOSITORY = "Unjuno/orbitune"
SOURCE_SHA = "44a1b806160ab5bc721a370d034a6dfcb28f27a8"
KAGGLE_IMAGE = "sha256:3f764ee4d610edfbe6b07769538ffbae8413b9df47c05af783245d65c7c21bed"
HF_IMAGE = "sha256:f0c1b097b3ed4a7cc356d77f1d9b8fbaffc8445b9168f02dba2a713741be6537"
HF_REVISION = "ce27a09881be902b2de3f6b1ce28c48355bd56df"
KAGGLE_RESOURCE = "UnjunoOrg/orbitune-100-step"
HF_RESOURCE = "Unjuno/gpu-control-orbitune-zero-gpu"

_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_ARTIFACT_PATH = re.compile(r"^runs/[0-9a-f]{32}/orbitune-output\.zip$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class AdapterError(RuntimeError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise AdapterError("invalid_arguments") from exc


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _envelope(*, status: str, summary: str, state: Mapping[str, Any],
              next_actions: list[str], blocker: str | None = None,
              **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": 2, "status": status, "human_summary": summary,
        "machine_state": dict(state), "next_allowed_actions": next_actions,
        "blocking_reason": blocker, **extra,
    }


def _validate_prepare(arguments: object) -> dict[str, Any]:
    required = {"workload", "repository", "commit", "parameters",
                "runtime_seconds", "max_cost_usd", "idempotency_key"}
    if not isinstance(arguments, dict) or set(arguments) != required:
        raise AdapterError("invalid_arguments")
    if (arguments["repository"] != REPOSITORY or arguments["commit"] != SOURCE_SHA or
            not isinstance(arguments["idempotency_key"], str) or
            _IDEMPOTENCY.fullmatch(arguments["idempotency_key"]) is None or
            arguments["max_cost_usd"] not in {"0", "0.0", "0.00", "0.000", "0.0000", "0.00000", "0.000000"} or
            type(arguments["runtime_seconds"]) is not int or
            not isinstance(arguments["parameters"], dict)):
        raise AdapterError("invalid_arguments")
    workload = arguments["workload"]
    if workload == KAGGLE_WORKLOAD:
        if arguments["parameters"] or not 1 <= arguments["runtime_seconds"] <= 1800:
            raise AdapterError("invalid_arguments")
    elif workload == HF_WORKLOAD:
        parameters = arguments["parameters"]
        if (not 1 <= arguments["runtime_seconds"] <= 60 or
                set(parameters) != {"artifact_repo_id", "artifact_revision", "artifact_path", "artifact_sha256"} or
                not isinstance(parameters["artifact_repo_id"], str) or _REPO.fullmatch(parameters["artifact_repo_id"]) is None or
                parameters["artifact_repo_id"] != "Unjuno/gpu-control-orbitune-artifacts" or
                not isinstance(parameters["artifact_revision"], str) or re.fullmatch(r"[0-9a-f]{40}", parameters["artifact_revision"]) is None or
                not isinstance(parameters["artifact_path"], str) or _ARTIFACT_PATH.fullmatch(parameters["artifact_path"]) is None or
                not isinstance(parameters["artifact_sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", parameters["artifact_sha256"]) is None):
            raise AdapterError("invalid_arguments")
    else:
        raise AdapterError("workload_not_registered", 404)
    return arguments


def _manifest(workload: str) -> dict[str, Any]:
    if workload == KAGGLE_WORKLOAD:
        return {
            "provider": "kaggle", "image_digest": KAGGLE_IMAGE,
            "source_repository": REPOSITORY, "source_sha": SOURCE_SHA,
            "provider_resource_id": KAGGLE_RESOURCE, "gpu": "NvidiaTeslaT4",
        }
    return {
        "provider": "huggingface_space", "image_digest": HF_IMAGE,
        "source_repository": REPOSITORY, "source_sha": SOURCE_SHA,
        "source_revision": HF_REVISION, "provider_resource_id": HF_RESOURCE,
        "gpu": "zero-gpu-large",
    }


def prepare(owner: str, arguments: object) -> dict[str, Any]:
    args = _validate_prepare(arguments)
    manifest = _manifest(args["workload"])
    plan = {
        "schema_version": 2, "workload": args["workload"],
        "provider": manifest["provider"], "repository": REPOSITORY,
        "source_sha": SOURCE_SHA, "parameters": args["parameters"],
        "runtime_seconds": args["runtime_seconds"], "max_cost_usd": "0",
        "known_cost_usd": "0", "cost_classification": "FREE_QUOTA",
        "paid_fallback_allowed": False, "image_digest": manifest["image_digest"],
        "workload_manifest": manifest,
        "owner_binding_sha256": hashlib.sha256(owner.encode("utf-8")).hexdigest(),
    }
    fingerprint = _fingerprint(plan)
    run_id = hashlib.sha256(canonical({
        "version": 1, "owner": owner, "idempotency_key": args["idempotency_key"],
        "plan_fingerprint": fingerprint,
    })).hexdigest()[:32]
    return _envelope(
        status="ok", summary="無料枠だけを使う登録済み実験planを準備しました。",
        state={"run_id": run_id, "state": "prepared", "plan_fingerprint": fingerprint},
        next_actions=["experiment_submit"], approved_plan=plan,
    )


def _validated_run(owner: str, arguments: object, now: int) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise AdapterError("invalid_arguments")
    required = {"run_id", "plan_fingerprint", "approved_plan", "authorization"}
    if set(arguments) != required:
        raise AdapterError("invalid_arguments")
    run_id, fingerprint = arguments["run_id"], arguments["plan_fingerprint"]
    plan, authorization = arguments["approved_plan"], arguments["authorization"]
    expected_keys = {"schema_version", "workload", "provider", "repository", "source_sha",
                     "parameters", "runtime_seconds", "max_cost_usd", "known_cost_usd",
                     "cost_classification", "paid_fallback_allowed", "image_digest",
                     "workload_manifest", "owner_binding_sha256"}
    if (not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None or
            not isinstance(fingerprint, str) or _FINGERPRINT.fullmatch(fingerprint) is None or
            not isinstance(plan, dict) or set(plan) != expected_keys or _fingerprint(plan) != fingerprint or
            plan.get("workload") not in {KAGGLE_WORKLOAD, HF_WORKLOAD} or
            plan.get("repository") != REPOSITORY or plan.get("source_sha") != SOURCE_SHA or
            plan.get("workload_manifest") != _manifest(plan.get("workload")) or
            plan.get("provider") != plan["workload_manifest"]["provider"] or
            plan.get("image_digest") != plan["workload_manifest"]["image_digest"] or
            plan.get("schema_version") != 2 or plan.get("max_cost_usd") != "0" or
            plan.get("known_cost_usd") != "0" or plan.get("paid_fallback_allowed") is not False or
            plan.get("cost_classification") != "FREE_QUOTA" or
            plan.get("owner_binding_sha256") != hashlib.sha256(owner.encode("utf-8")).hexdigest() or
            not isinstance(authorization, dict) or
            set(authorization) != {"authorization_id", "source", "authorized_at", "expires_at"} or
            not isinstance(authorization["authorization_id"], str) or
            re.fullmatch(r"[0-9a-f]{32}", authorization["authorization_id"]) is None or
            authorization["source"] != "chatgpt_mcp_write_confirmation" or
            type(authorization["authorized_at"]) is not int or
            type(authorization["expires_at"]) is not int or
            authorization["authorized_at"] > now or authorization["expires_at"] < now or
            authorization["expires_at"] - authorization["authorized_at"] > 600):
        raise AdapterError("plan_or_authorization_invalid", 409)
    try:
        _validate_prepare({
            "workload": plan["workload"], "repository": plan["repository"],
            "commit": plan["source_sha"], "parameters": plan["parameters"],
            "runtime_seconds": plan["runtime_seconds"], "max_cost_usd": plan["max_cost_usd"],
            "idempotency_key": "adapter-validation",
        })
    except AdapterError as exc:
        raise AdapterError("plan_or_authorization_invalid", 409) from exc
    return {
        "id": run_id, "fingerprint": fingerprint, "plan": plan,
        "registered_workload_manifest": plan["workload_manifest"], "started_at": now,
    }


@dataclass
class ProviderAdapter:
    kaggle: Any
    huggingface: Any
    clock: Any = time.time

    def capabilities(self) -> dict[str, Any]:
        return _envelope(
            status="ok", summary="KaggleとHugging Faceの登録済み無料経路を確認しました。",
            state={"providers": [
                {"id": "kaggle", "configured": self.kaggle is not None, "paid_fallback": False},
                {"id": "huggingface_space", "configured": self.huggingface is not None, "paid_fallback": False},
            ], "workloads": [KAGGLE_WORKLOAD, HF_WORKLOAD]},
            next_actions=["experiment_prepare"],
        )

    def submit(self, owner: str, arguments: object) -> dict[str, Any]:
        now = int(self.clock())
        run = _validated_run(owner, arguments, now)
        provider = run["plan"]["provider"]
        backend = self.kaggle if provider == "kaggle" else self.huggingface
        if backend is None:
            raise AdapterError("provider_not_configured", 503)
        handle = None
        if provider == "kaggle":
            handle = backend.reconcile(run)
        if handle is None:
            handle = backend.start(run)
        if not isinstance(handle, dict):
            raise AdapterError("provider_invalid_handle", 502)
        return _envelope(
            status="pending", summary="登録済み無料providerへ投入しました。",
            state={"run_id": run["id"], "state": "running", "provider": provider,
                   "provider_handle": handle}, next_actions=["experiment_status", "experiment_cancel"],
        )

    def observe(self, tool: str, arguments: object) -> dict[str, Any]:
        if (not isinstance(arguments, dict) or not isinstance(arguments.get("run_id"), str) or
                _RUN_ID.fullmatch(arguments["run_id"]) is None or
                not isinstance(arguments.get("provider_handle"), dict)):
            raise AdapterError("invalid_arguments")
        handle = arguments["provider_handle"]
        provider = handle.get("provider")
        backend = self.kaggle if provider == "kaggle" else self.huggingface if provider == "huggingface_space" else None
        if backend is None:
            raise AdapterError("provider_not_configured", 503)
        if handle.get("run_id") != arguments["run_id"]:
            raise AdapterError("provider_handle_mismatch", 409)
        if tool == "experiment_cancel":
            if provider == "kaggle":
                return _envelope(status="blocked", summary="Kaggleは信頼できる取消APIを提供していません。",
                    state={"run_id": arguments["run_id"], "state": "running", "provider_handle": handle},
                    next_actions=["experiment_status"], blocker="CANCELLATION_UNSUPPORTED")
            backend.cancel(handle)
            return _envelope(status="pending", summary="取消を要求しました。",
                state={"run_id": arguments["run_id"], "state": "running", "provider_handle": handle},
                next_actions=["experiment_status"])
        observation = backend.capture(handle)
        state = observation.state
        result = observation.result if isinstance(observation.result, dict) else None
        if state != "running":
            backend.cleanup(handle)
            if not backend.is_clean(handle):
                raise AdapterError("cleanup_not_confirmed", 503)
            if result is not None:
                result = {**result, "cleanup_state": "confirmed"}
        status = "ok" if state == "succeeded" else "error" if state in {"failed", "cancelled"} else "pending"
        actions = ["experiment_result"] if state == "succeeded" else ["experiment_status"] if state == "running" else []
        return _envelope(status=status, summary="provider状態を確認しました。",
            state={"run_id": arguments["run_id"], "state": state, "provider": provider,
                   "provider_handle": handle, **({"result": result} if result is not None else {})},
            next_actions=actions, **({"result": result} if tool == "experiment_result" and result is not None else {}))

    def invoke(self, owner: str, tool: str, arguments: object) -> dict[str, Any]:
        if tool == "experiment_capabilities":
            if arguments != {}:
                raise AdapterError("invalid_arguments")
            return self.capabilities()
        if tool == "experiment_prepare":
            return prepare(owner, arguments)
        if tool == "experiment_submit":
            return self.submit(owner, arguments)
        if tool in {"experiment_status", "experiment_result", "experiment_cancel"}:
            return self.observe(tool, arguments)
        if tool == "experiment_list":
            return _envelope(status="ok", summary="永続run一覧はSites D1が管理します。",
                state={"count": 0}, next_actions=[], experiments=[])
        if tool == "experiment_artifact":
            return _envelope(status="blocked", summary="外部artifactは不変参照として結果に含まれます。",
                state={}, next_actions=["experiment_result"], blocker="INLINE_ARTIFACT_UNAVAILABLE")
        raise AdapterError("tool_not_supported", 404)
