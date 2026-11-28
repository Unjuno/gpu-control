"""Stateless registered-provider protocol for the Modal adapter.

Sites/D1 owns plans, authorization and durable run state.  This module accepts
only reviewed fixed-provider manifests and returns an opaque handle that Sites
persists.  It deliberately has no database or arbitrary execution API.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping

from workload_registry import WORKLOADS, KAGGLE_WORKLOAD, HF_WORKLOAD, MODAL_GPU_WORKLOAD
from canonical_json import canonical_json_bytes


MODAL_GPU_PROVIDER_USAGE_LIMIT_USD = "30.00"
MODAL_GPU_PROVIDER_USAGE_LIMIT_CENTS = 3000
REPOSITORY = WORKLOADS["kaggle_training"]["repository"]
SOURCE_SHA = WORKLOADS["kaggle_training"]["source_sha"]
GPU_CONTROL_REPOSITORY = WORKLOADS["modal_gpu_canary"]["repository"]
MODAL_GPU_SOURCE_SHA = WORKLOADS["modal_gpu_canary"]["source_sha"]
MODAL_GPU_IMAGE_DIGEST = WORKLOADS["modal_gpu_canary"]["adapter_manifest"]["image_digest"]
KAGGLE_IMAGE = WORKLOADS["kaggle_training"]["adapter_manifest"]["image_digest"]
HF_IMAGE = WORKLOADS["huggingface_evaluation"]["adapter_manifest"]["image_digest"]
HF_REVISION = WORKLOADS["huggingface_evaluation"]["source_revision"]
KAGGLE_RESOURCE = WORKLOADS["kaggle_training"]["adapter_manifest"]["provider_resource_id"]
HF_RESOURCE = WORKLOADS["huggingface_evaluation"]["adapter_manifest"]["provider_resource_id"]

_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_ARTIFACT_PATH = re.compile(r"^runs/[0-9a-f]{32}/orbitune-output\.zip$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
HF_ARTIFACT_REPOSITORY = WORKLOADS["huggingface_evaluation"]["artifact_repository"]


class AdapterError(RuntimeError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def provider_submission_failure_state(failure_stage: str, error_code: str) -> str:
    """Classify only proven pre-submit failures as terminal.

    Once a provider submission request may have reached its service, a lost
    response is not evidence that no resource exists. Keep the run recoverable
    unless the adapter returned a stable error known to occur before submit.
    """
    if failure_stage not in {"provider_submission", "submission_persistence", "worker_spawn"}:
        return "failed"
    definitive = {
        "provider_not_configured",
        "provider_evidence_expired_or_exhausted",
        "kaggle_token_not_configured",
        "kaggle_quota_unavailable",
        "kaggle_quota_invalid",
        "kaggle_quota_insufficient",
        "kaggle_latest_snapshot_failed",
        "kaggle_latest_snapshot_invalid",
    }
    return "failed" if error_code in definitive else "uncertain"


def uncertain_submission_response(run_id: str, provider: str) -> dict[str, Any]:
    return _envelope(
        status="pending",
        summary="provider受付結果が未確定です。同じrunの状態照会で受付記録を照合します。",
        state={"run_id": run_id, "state": "uncertain", "provider": provider,
               "submission_attempted": True, "provider_resource_created": "unknown",
               "cleanup_state": "unknown"},
        next_actions=["experiment_status"], blocker="SUBMISSION_OUTCOME_UNCONFIRMED",
    )


def canonical(value: Any) -> bytes:
    try:
        return canonical_json_bytes(value)
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
                arguments["parameters"] or not 1 <= arguments["runtime_seconds"] <= WORKLOADS["kaggle_training"]["runtime_seconds"]):
            raise AdapterError("invalid_arguments")
    elif workload == HF_WORKLOAD:
        parameters = arguments["parameters"]
        if (arguments["repository"] != REPOSITORY or arguments["commit"] != SOURCE_SHA or
                "provider_evidence" in arguments or
                arguments["max_cost_usd"] not in {"0", "0.0", "0.00", "0.000", "0.0000", "0.00000", "0.000000"} or
                not 1 <= arguments["runtime_seconds"] <= WORKLOADS["huggingface_evaluation"]["runtime_seconds"] or
                set(parameters) != {"artifact_repo_id", "artifact_revision", "artifact_path", "artifact_sha256"} or
                not isinstance(parameters["artifact_repo_id"], str) or _REPO.fullmatch(parameters["artifact_repo_id"]) is None or
                parameters["artifact_repo_id"] != HF_ARTIFACT_REPOSITORY or
                not isinstance(parameters["artifact_revision"], str) or re.fullmatch(r"[0-9a-f]{40}", parameters["artifact_revision"]) is None or
                not isinstance(parameters["artifact_path"], str) or _ARTIFACT_PATH.fullmatch(parameters["artifact_path"]) is None or
                not isinstance(parameters["artifact_sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", parameters["artifact_sha256"]) is None):
            raise AdapterError("invalid_arguments")
    elif workload == MODAL_GPU_WORKLOAD:
        evidence = arguments.get("provider_evidence")
        if (arguments["repository"] != GPU_CONTROL_REPOSITORY or
                arguments["commit"] != MODAL_GPU_SOURCE_SHA or
                arguments["max_cost_usd"] != WORKLOADS["modal_gpu_canary"]["cost_ceiling_usd"] or arguments["parameters"] or
                arguments["runtime_seconds"] != WORKLOADS["modal_gpu_canary"]["runtime_seconds"] or
                not isinstance(evidence, dict) or
                set(evidence) != {"schema_version", "workspace", "environment", "usage_limit_usd",
                                  "credits_used_usd", "charges_usd", "gpu", "hourly_price_usd",
                                  "price_source", "verified_at", "expires_at", "evidence_id"} or
                evidence["schema_version"] != 1 or evidence["workspace"] != "unjuno" or
                evidence["environment"] != "main" or
                evidence["usage_limit_usd"] != MODAL_GPU_PROVIDER_USAGE_LIMIT_USD or
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
    for item in WORKLOADS.values():
        if item["id"] == workload and isinstance(item.get("adapter_manifest"), dict):
            return dict(item["adapter_manifest"])
    raise AdapterError("workload_not_registered", 404)


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
            ((plan.get("provider") == "modal_gpu" and (plan.get("max_cost_usd") != WORKLOADS["modal_gpu_canary"]["cost_ceiling_usd"] or
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
                round((float(evidence["credits_used_usd"]) + float(evidence["charges_usd"]) + 0.01) * 100) >
                MODAL_GPU_PROVIDER_USAGE_LIMIT_CENTS):
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
    artifact_store: Any = None
    owner_training: Mapping[str, Any] | None = None

    def capabilities(self) -> dict[str, Any]:
        owner_training = dict(self.owner_training or {
            "profile_configured": False, "admission_enabled": False,
            "ready": False, "blocker": "OWNER_TRAINING_PROFILE_NOT_CONFIGURED",
        })
        return _envelope(
            status="ok", summary="KaggleとHugging Faceの登録済み無料経路を確認しました。",
            state={"providers": [
                {"id": "kaggle", "configured": self.kaggle is not None, "paid_fallback": False},
                {"id": "huggingface_space", "configured": self.huggingface is not None, "paid_fallback": False},
                {"id": "modal_gpu", "configured": self.modal_gpu is not None, "paid_fallback": False},
            ], "workloads": [KAGGLE_WORKLOAD, HF_WORKLOAD, MODAL_GPU_WORKLOAD],
                "owner_selected_training": owner_training},
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

    def reconcile_submission(self, run: Mapping[str, Any]) -> dict[str, Any] | None:
        """Recover a provider handle after an ambiguous submission response.

        Backends must use an idempotent provider-side identity or a durable
        pre-submit journal. This method never calls ``start`` and therefore
        cannot silently create a second provider job.
        """
        provider = run.get("plan", {}).get("provider")
        backend = (self.kaggle if provider == "kaggle" else
                   self.huggingface if provider == "huggingface_space" else
                   self.modal_gpu if provider == "modal_gpu" else None)
        reconcile = getattr(backend, "reconcile", None)
        if not callable(reconcile):
            return None
        handle = reconcile(run)
        if handle is None:
            return None
        if (not isinstance(handle, dict) or handle.get("provider") != provider or
                handle.get("run_id") != run.get("id") or
                handle.get("plan_fingerprint") != run.get("fingerprint")):
            raise AdapterError("provider_reconciliation_handle_invalid", 502)
        return _envelope(
            status="pending", summary="provider受付を同じrunへ復旧しました。",
            state={"run_id": run["id"], "state": "running", "provider": provider,
                   "provider_handle": handle},
            next_actions=["experiment_status", "experiment_cancel"],
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
        if provider == "kaggle" and "runtime_seconds" in arguments:
            runtime_seconds = arguments["runtime_seconds"]
            if type(runtime_seconds) is not int or not 1 <= runtime_seconds <= WORKLOADS["kaggle_training"]["runtime_seconds"]:
                raise AdapterError("provider_handle_mismatch", 409)
            recorded_runtime = handle.get("runtime_seconds")
            if recorded_runtime is not None and recorded_runtime != runtime_seconds:
                raise AdapterError("provider_handle_mismatch", 409)
            handle = {**handle, "runtime_seconds": runtime_seconds}
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
        stalled = (state == "running" and result is not None and
                   result.get("lifecycle_condition") == "provider_deadline_exceeded")
        if state != "running":
            backend.cleanup(handle)
            if not backend.is_clean(handle):
                raise AdapterError("cleanup_not_confirmed", 503)
            if result is not None:
                result = {**result, "cleanup_state": "confirmed"}
        status = ("blocked" if stalled else "ok" if state == "succeeded" else
                  "error" if state in {"failed", "cancelled"} else "pending")
        actions = ["experiment_result"] if state == "succeeded" else ["experiment_status"] if state == "running" else []
        return _envelope(status=status, summary="provider状態を確認しました。",
            state={"run_id": arguments["run_id"], "state": state, "provider": provider,
                   "provider_handle": handle,
                   **({"cleanup_state": "confirmed"} if state != "running" else {}),
                   **({"result": result} if result is not None else {})},
            next_actions=actions,
            **({"blocker": "PROVIDER_DEADLINE_EXCEEDED_CLEANUP_UNCONFIRMED"} if stalled else {}),
            **({"result": result} if tool == "experiment_result" and result is not None else {}))

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
            if self.artifact_store is None:
                return _envelope(status="blocked", summary="外部artifact取得経路が設定されていません。",
                    state={}, next_actions=["experiment_result"], blocker="ARTIFACT_RETRIEVAL_UNAVAILABLE")
            if (not isinstance(arguments, dict) or set(arguments) != {
                    "run_id", "artifact_id", "offset", "length", "provider_handle", "external_artifact"} or
                    arguments["artifact_id"] != "orbitune-output.zip" or
                    not isinstance(arguments["run_id"], str) or _RUN_ID.fullmatch(arguments["run_id"]) is None or
                    not isinstance(arguments["provider_handle"], dict) or
                    arguments["provider_handle"].get("run_id") != arguments["run_id"]):
                raise AdapterError("invalid_arguments")
            reference = arguments["external_artifact"]
            if not isinstance(reference, dict) or reference.get("run_id") != arguments["run_id"]:
                raise AdapterError("artifact_reference_mismatch", 409)
            chunk = self.artifact_store.read(
                reference, offset=arguments["offset"], max_bytes=arguments["length"])
            return _envelope(status="ok", summary="外部artifactを固定revisionから再取得し検証しました。",
                state={"run_id": arguments["run_id"], **chunk}, next_actions=[])
        raise AdapterError("tool_not_supported", 404)
