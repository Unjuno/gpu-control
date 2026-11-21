"""Stateless registered-provider protocol for the Modal adapter.

Sites/D1 owns plans, authorization and durable run state.  This module accepts
only reviewed fixed-provider manifests and returns an opaque handle that Sites
persists.  It deliberately has no database or arbitrary execution API.
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
MODAL_GPU_WORKLOAD = "modal-gpu-vector-add-v1"
REPOSITORY = "Unjuno/orbitune"
SOURCE_SHA = "44a1b806160ab5bc721a370d034a6dfcb28f27a8"
GPU_CONTROL_REPOSITORY = "Unjuno/gpu-control"
MODAL_GPU_SOURCE_SHA = "58a24082b73238b982e64a17b7d0624fc2594bab"
MODAL_GPU_IMAGE_DIGEST = "sha256:b0840d8b2a13e573141e158c50f1f8375a7eb853529172effea49cacfc10c919"
KAGGLE_IMAGE = "sha256:3f764ee4d610edfbe6b07769538ffbae8413b9df47c05af783245d65c7c21bed"
HF_IMAGE = "sha256:5d0757c0c6d35514bdd26618a11e028b635d766612c18404551007b2c168ac68"
HF_REVISION = "2e9df7dcd8815cf3059ae94ce6504315e63a85ab"
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
    if not isinstance(arguments, dict) or frozenset(arguments) not in {frozenset(required), frozenset(required | {"provider_evidence"})}:
        raise AdapterError("invalid_arguments")
    if (not isinstance(arguments["idempotency_key"], str) or
            _IDEMPOTENCY.fullmatch(arguments["idempotency_key"]) is None or
            type(arguments["runtime_seconds"]) is not int or
            not isinstance(arguments["parameters"], dict)):
        raise AdapterError("invalid_arguments")
    workload = arguments["workload"]
    if workload == KAGGLE_WORKLOAD:
        if (arguments["repository"] != REPOSITORY or arguments["commit"] != SOURCE_SHA or
                "provider_evidence" in arguments or
                arguments["max_cost_usd"] not in {"0", "0.0", "0.00", "0.000", "0.0000", "0.00000", "0.000000"} or
                arguments["parameters"] or not 1 <= arguments["runtime_seconds"] <= 1800):
            raise AdapterError("invalid_arguments")
    elif workload == HF_WORKLOAD:
        parameters = arguments["parameters"]
        if (arguments["repository"] != REPOSITORY or arguments["commit"] != SOURCE_SHA or
                "provider_evidence" in arguments or
                arguments["max_cost_usd"] not in {"0", "0.0", "0.00", "0.000", "0.0000", "0.00000", "0.000000"} or
                not 1 <= arguments["runtime_seconds"] <= 60 or
                set(parameters) != {"artifact_repo_id", "artifact_revision", "artifact_path", "artifact_sha256"} or
                not isinstance(parameters["artifact_repo_id"], str) or _REPO.fullmatch(parameters["artifact_repo_id"]) is None or
                parameters["artifact_repo_id"] != "Unjuno/gpu-control-orbitune-artifacts" or
                not isinstance(parameters["artifact_revision"], str) or re.fullmatch(r"[0-9a-f]{40}", parameters["artifact_revision"]) is None or
                not isinstance(parameters["artifact_path"], str) or _ARTIFACT_PATH.fullmatch(parameters["artifact_path"]) is None or
                not isinstance(parameters["artifact_sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", parameters["artifact_sha256"]) is None):
            raise AdapterError("invalid_arguments")
    elif workload == MODAL_GPU_WORKLOAD:
        evidence = arguments.get("provider_evidence")
        if (arguments["repository"] != GPU_CONTROL_REPOSITORY or
                arguments["commit"] != MODAL_GPU_SOURCE_SHA or
                arguments["max_cost_usd"] != "0.01" or arguments["parameters"] or
                arguments["runtime_seconds"] != 30 or
                not isinstance(evidence, dict) or
                set(evidence) != {"schema_version", "workspace", "environment", "usage_limit_usd",
                                  "credits_used_usd", "charges_usd", "gpu", "hourly_price_usd",
                                  "price_source", "verified_at", "expires_at", "evidence_id"} or
                evidence["schema_version"] != 1 or evidence["workspace"] != "unjuno" or
                evidence["environment"] != "main" or evidence["usage_limit_usd"] != "1.00" or
                not isinstance(evidence["credits_used_usd"], str) or
                re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{2}", evidence["credits_used_usd"]) is None or
                not isinstance(evidence["charges_usd"], str) or
                re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{2}", evidence["charges_usd"]) is None or
                evidence["gpu"] != "T4" or not isinstance(evidence["hourly_price_usd"], str) or
                re.fullmatch(r"0\.[0-9]{6}", evidence["hourly_price_usd"]) is None or
                float(evidence["hourly_price_usd"]) <= 0 or evidence["price_source"] != "https://modal.com/pricing" or
                type(evidence["verified_at"]) is not int or type(evidence["expires_at"]) is not int or
                evidence["verified_at"] < 0 or evidence["expires_at"] <= evidence["verified_at"] or
                evidence["expires_at"] - evidence["verified_at"] > 3600 or
                not isinstance(evidence["evidence_id"], str) or
                re.fullmatch(r"[0-9a-f]{64}", evidence["evidence_id"]) is None):
            raise AdapterError("invalid_arguments")
        evidence_body = {key: value for key, value in evidence.items() if key != "evidence_id"}
        if hashlib.sha256(canonical(evidence_body)).hexdigest() != evidence["evidence_id"]:
            raise AdapterError("invalid_arguments")
    else:
        raise AdapterError("workload_not_registered", 404)
    return arguments


def _manifest(workload: str) -> dict[str, Any]:
    if workload == KAGGLE_WORKLOAD:
        return {
            "provider": "kaggle", "image_digest": KAGGLE_IMAGE,
            "source_repository": REPOSITORY, "source_sha": SOURCE_SHA,
            "provider_resource_id": KAGGLE_RESOURCE, "gpu": "NvidiaTeslaT4", "gpu_count": 2,
        }
    if workload == HF_WORKLOAD:
        return {
        "provider": "huggingface_space", "image_digest": HF_IMAGE,
        "source_repository": REPOSITORY, "source_sha": SOURCE_SHA,
        "source_revision": HF_REVISION, "provider_resource_id": HF_RESOURCE,
        "gpu": "zero-gpu-large",
        }
    return {
        "provider": "modal_gpu", "source_repository": GPU_CONTROL_REPOSITORY,
        "source_sha": MODAL_GPU_SOURCE_SHA, "provider_resource_id": "gpu-control-modal-gpu-canary/run_canary",
        "image_digest": MODAL_GPU_IMAGE_DIGEST, "gpu": "T4", "gpu_count": 1,
        "network": "blocked", "max_runtime_seconds": 30,
    }


def prepare(owner: str, arguments: object) -> dict[str, Any]:
    args = _validate_prepare(arguments)
    manifest = _manifest(args["workload"])
    plan = {
        "schema_version": 2, "workload": args["workload"],
        "provider": manifest["provider"], "repository": args["repository"],
        "source_sha": args["commit"], "parameters": args["parameters"],
        "runtime_seconds": args["runtime_seconds"], "max_cost_usd": args["max_cost_usd"],
        "known_cost_usd": "0" if manifest["provider"] != "modal_gpu" else None,
        "cost_classification": "FREE_QUOTA" if manifest["provider"] != "modal_gpu" else "PAID_BOUNDED",
        "paid_fallback_allowed": False, "image_digest": manifest.get("image_digest"),
        "provider_evidence": args.get("provider_evidence"),
        "workload_manifest": manifest,
        "owner_binding_sha256": hashlib.sha256(owner.encode("utf-8")).hexdigest(),
    }
    fingerprint = _fingerprint(plan)
    run_id = hashlib.sha256(canonical({
        "version": 1, "owner": owner, "idempotency_key": args["idempotency_key"],
        "plan_fingerprint": fingerprint,
    })).hexdigest()[:32]
    return _envelope(
        status="ok", summary=("上限付きModal GPU実験planを準備しました。" if manifest["provider"] == "modal_gpu"
                              else "無料枠だけを使う登録済み実験planを準備しました。"),
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
                     "provider_evidence", "workload_manifest", "owner_binding_sha256"}
    if (not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None or
            not isinstance(fingerprint, str) or _FINGERPRINT.fullmatch(fingerprint) is None or
            not isinstance(plan, dict) or set(plan) != expected_keys or _fingerprint(plan) != fingerprint or
            plan.get("workload") not in {KAGGLE_WORKLOAD, HF_WORKLOAD, MODAL_GPU_WORKLOAD} or
            plan.get("workload_manifest") != _manifest(plan.get("workload")) or
            plan.get("provider") != plan["workload_manifest"]["provider"] or
            plan.get("image_digest") != plan["workload_manifest"].get("image_digest") or
            plan.get("schema_version") != 2 or plan.get("paid_fallback_allowed") is not False or
            ((plan.get("provider") == "modal_gpu" and (plan.get("max_cost_usd") != "0.01" or
              plan.get("known_cost_usd") is not None or plan.get("cost_classification") != "PAID_BOUNDED")) or
             (plan.get("provider") != "modal_gpu" and (plan.get("max_cost_usd") != "0" or
              plan.get("known_cost_usd") != "0" or plan.get("cost_classification") != "FREE_QUOTA"))) or
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
            **({"provider_evidence": plan["provider_evidence"]} if plan["provider"] == "modal_gpu" else {}),
            "idempotency_key": "adapter-validation",
        })
    except AdapterError as exc:
        raise AdapterError("plan_or_authorization_invalid", 409) from exc
    if plan["provider"] == "modal_gpu":
        evidence = plan["provider_evidence"]
        if (evidence["verified_at"] > now or evidence["expires_at"] < now or
                round((float(evidence["credits_used_usd"]) + float(evidence["charges_usd"]) + 0.01) * 100) > 100):
            raise AdapterError("provider_evidence_expired_or_exhausted", 409)
    return {
        "id": run_id, "fingerprint": fingerprint, "plan": plan,
        "registered_workload_manifest": plan["workload_manifest"], "started_at": now,
    }


@dataclass
class ProviderAdapter:
    kaggle: Any
    huggingface: Any
    modal_gpu: Any = None
    clock: Any = time.time

    def capabilities(self) -> dict[str, Any]:
        return _envelope(
            status="ok", summary="KaggleとHugging Faceの登録済み無料経路を確認しました。",
            state={"providers": [
                {"id": "kaggle", "configured": self.kaggle is not None, "paid_fallback": False},
                {"id": "huggingface_space", "configured": self.huggingface is not None, "paid_fallback": False},
                {"id": "modal_gpu", "configured": self.modal_gpu is not None, "paid_fallback": False},
            ], "workloads": [KAGGLE_WORKLOAD, HF_WORKLOAD, MODAL_GPU_WORKLOAD]},
            next_actions=["experiment_prepare"],
        )

    def validate_submission(self, owner: str, arguments: object) -> dict[str, Any]:
        """Validate a submission without contacting an external provider."""
        now = int(self.clock())
        return _validated_run(owner, arguments, now)

    def submit_validated(self, run: Mapping[str, Any]) -> dict[str, Any]:
        """Perform the slow provider operation for an already validated run.

        The hosted adapter invokes this method in a durable background Modal
        Function.  Keeping validation separate lets the HTTP request return a
        bounded queued handle before Kaggle or Hugging Face CLI work begins.
        """
        provider = run["plan"]["provider"]
        backend = (self.kaggle if provider == "kaggle" else self.huggingface
                   if provider == "huggingface_space" else self.modal_gpu if provider == "modal_gpu" else None)
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

    def submit(self, owner: str, arguments: object) -> dict[str, Any]:
        return self.submit_validated(self.validate_submission(owner, arguments))

    def observe(self, tool: str, arguments: object) -> dict[str, Any]:
        if (not isinstance(arguments, dict) or not isinstance(arguments.get("run_id"), str) or
                _RUN_ID.fullmatch(arguments["run_id"]) is None or
                not isinstance(arguments.get("provider_handle"), dict)):
            raise AdapterError("invalid_arguments")
        handle = arguments["provider_handle"]
        provider = handle.get("provider")
        backend = (self.kaggle if provider == "kaggle" else self.huggingface
                   if provider == "huggingface_space" else self.modal_gpu if provider == "modal_gpu" else None)
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
                   "provider_handle": handle,
                   **({"cleanup_state": "confirmed"} if state != "running" else {}),
                   **({"result": result} if result is not None else {})},
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
