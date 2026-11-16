"""Approved Gradio ZeroGPU Space backend for bounded evaluation only."""
from __future__ import annotations

import importlib
import hashlib
import json
import math
import re
from typing import Any, Callable, Mapping

from .backends import Observation
from .config import Settings


_RESOURCE_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUEST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}-[0-9a-f]{12}$")


class ZeroGpuQuotaError(RuntimeError):
    pass


def space_contract_digest(space_id: str, revision: str) -> str:
    value = f"gpu-control/huggingface-space-contract/v1\0{space_id}\0{revision}\0/evaluate\0/status\0/cancel"
    return "sha256:" + hashlib.sha256(value.encode("ascii")).hexdigest()


class HuggingFaceSpaceBackend:
    """Call one reviewed idempotent Space contract without paid fallback.

    Approved Spaces must expose `/evaluate`, `/status`, and `/cancel`.  The
    deterministic request id lets reconciliation query status without invoking
    evaluation again after an ambiguous network outcome.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        api: Any = None,
        client_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self.settings = settings
        if api is None:
            hub = importlib.import_module("huggingface_hub")
            api = hub.HfApi(token=settings.hf_token)
        self.api = api
        if client_factory is None:
            gradio = importlib.import_module("gradio_client")
            client_factory = lambda space, token: gradio.Client(space, hf_token=token)
        self.client_factory = client_factory

    def _identity(self, run: Mapping[str, Any]) -> tuple[str, str, str, dict[str, Any], int]:
        try:
            plan = run["plan"]
            manifest = (plan.get("workload_manifest") or
                        run["registered_workload_manifest"])
            space_id = manifest["provider_resource_id"]
            source_sha = manifest["source_sha"]
            space_revision = manifest["source_revision"]
            image_digest = manifest["image_digest"]
            parameters = plan["parameters"]
            runtime = plan["runtime_seconds"]
            fingerprint = run["fingerprint"]
            run_id = run["id"]
        except (KeyError, TypeError) as exc:
            raise ValueError("Hugging Face Space plan is incomplete") from exc
        if (manifest.get("provider") != "huggingface_space" or
                not isinstance(space_id, str) or _RESOURCE_RE.fullmatch(space_id) is None or
                space_id not in self.settings.hf_space_allowlist):
            raise ValueError("Hugging Face Space is not allowlisted")
        if not isinstance(source_sha, str) or _SHA_RE.fullmatch(source_sha) is None:
            raise ValueError("Hugging Face Space source SHA is invalid")
        if not isinstance(space_revision, str) or _SHA_RE.fullmatch(space_revision) is None:
            raise ValueError("Hugging Face Space revision is invalid")
        if image_digest != space_contract_digest(space_id, space_revision):
            raise ValueError("Hugging Face Space contract digest is invalid")
        if (not isinstance(run_id, str) or
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id) is None or
                not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None):
            raise ValueError("Hugging Face Space run identity is invalid")
        if type(runtime) is not int or not 1 <= runtime <= 60:
            raise ValueError("Hugging Face Space evaluation must be at most 60 seconds")
        if not isinstance(parameters, dict):
            raise ValueError("Hugging Face Space parameters must be an object")
        if set(parameters) != {"artifact_repo_id", "artifact_revision", "artifact_path", "artifact_sha256"}:
            raise ValueError("Hugging Face Space artifact reference is incomplete")
        if (parameters.get("artifact_repo_id") not in self.settings.hf_artifact_repositories or
                not isinstance(parameters.get("artifact_revision"), str) or
                _SHA_RE.fullmatch(parameters["artifact_revision"]) is None or
                not isinstance(parameters.get("artifact_path"), str) or
                re.fullmatch(r"runs/[0-9a-f]{32}/orbitune-output\.zip", parameters["artifact_path"]) is None or
                not isinstance(parameters.get("artifact_sha256"), str) or
                re.fullmatch(r"[0-9a-f]{64}", parameters["artifact_sha256"]) is None):
            raise ValueError("Hugging Face Space artifact reference is not allowlisted or immutable")
        encoded = json.dumps(parameters, allow_nan=False, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 16 * 1024:
            raise ValueError("Hugging Face Space parameters exceed the request bound")
        return space_id, f"{run_id}-{fingerprint[:12]}", source_sha, parameters, runtime

    def quota_snapshot(self) -> Any:
        try:
            return self.api.get_zero_gpu_quota(token=self.settings.hf_token)
        except Exception as exc:
            raise ZeroGpuQuotaError("Hugging Face ZeroGPU quota is unavailable") from exc

    def _quota(self, runtime: int) -> None:
        try:
            quota = self.quota_snapshot()
            remaining = getattr(quota, "remaining", None)
            overquota = getattr(quota, "overquota_used", None)
        except Exception as exc:
            raise ZeroGpuQuotaError("Hugging Face ZeroGPU quota is unavailable") from exc
        if (not isinstance(remaining, (int, float)) or isinstance(remaining, bool) or
                not math.isfinite(remaining) or remaining < runtime or
                not isinstance(overquota, (int, float)) or isinstance(overquota, bool) or
                not math.isfinite(overquota) or overquota != 0):
            raise ZeroGpuQuotaError("free Hugging Face ZeroGPU quota is unsafe or insufficient")

    @staticmethod
    def _response(value: object, request_id: str) -> dict[str, Any]:
        if not isinstance(value, dict) or value.get("request_id") != request_id:
            raise RuntimeError("Hugging Face Space response is not bound to the request")
        state = value.get("state")
        if state not in {"queued", "running", "succeeded", "failed", "cancelled"}:
            raise RuntimeError("Hugging Face Space returned an invalid state")
        if len(json.dumps(value, allow_nan=False).encode("utf-8")) > 64 * 1024:
            raise RuntimeError("Hugging Face Space response exceeds the result bound")
        return value

    def _client(self, space_id: str) -> Any:
        return self.client_factory(space_id, self.settings.hf_token)

    def verify_space(self, space_id: str, revision: str) -> None:
        try:
            info = self.api.space_info(repo_id=space_id, token=self.settings.hf_token)
        except Exception as exc:
            raise RuntimeError("approved Hugging Face Space is unavailable") from exc
        if getattr(info, "sha", None) != revision or getattr(info, "sdk", None) != "gradio":
            raise RuntimeError("approved Hugging Face Space revision or SDK changed")

    def verify_contract(self, space_id: str) -> None:
        try:
            info = self._client(space_id).view_api(print_info=False, return_format="dict")
        except Exception as exc:
            raise RuntimeError("approved Hugging Face Space API is unavailable") from exc
        named = info.get("named_endpoints") if isinstance(info, Mapping) else None
        expected = {"/evaluate": 3, "/status": 1, "/cancel": 1}
        if not isinstance(named, Mapping) or set(named) != set(expected):
            raise RuntimeError("approved Hugging Face Space endpoint set changed")
        for endpoint, count in expected.items():
            parameters = named[endpoint].get("parameters") if isinstance(named[endpoint], Mapping) else None
            if not isinstance(parameters, list) or len(parameters) != count:
                raise RuntimeError("approved Hugging Face Space parameter contract changed")

    def verified_space_ids(self, workloads: Mapping[str, Any]) -> set[str]:
        verified: set[str] = set()
        for workload in workloads.values():
            if getattr(workload, "provider", None) != "huggingface_space":
                continue
            space_id = getattr(workload, "provider_resource_id", None)
            revision = getattr(workload, "source_revision", None)
            if not isinstance(space_id, str) or not isinstance(revision, str):
                raise RuntimeError("registered Hugging Face Space identity is incomplete")
            self.verify_space(space_id, revision)
            self.verify_contract(space_id)
            verified.add(space_id)
        return verified

    def start(self, run: dict) -> dict:
        if not self.settings.enable_huggingface_space:
            raise RuntimeError("Hugging Face Space submission is disabled")
        if not self.settings.hf_token:
            raise RuntimeError("Hugging Face worker token is not configured")
        space_id, request_id, source_sha, parameters, runtime = self._identity(run)
        manifest = run["plan"].get("workload_manifest") or run["registered_workload_manifest"]
        self.verify_space(space_id, manifest["source_revision"])
        self.verify_contract(space_id)
        self._quota(runtime)
        response = self._response(
            self._client(space_id).predict(
                request_id,
                json.dumps(parameters, allow_nan=False, sort_keys=True, separators=(",", ":")),
                source_sha,
                api_name="/evaluate",
            ),
            request_id,
        )
        handle = self._handle(run, space_id, request_id, source_sha)
        handle["space_revision"] = manifest["source_revision"]
        if response["state"] not in {"queued", "running"}:
            handle["observation"] = response
        return handle

    @staticmethod
    def _handle(run: Mapping[str, Any], space_id: str, request_id: str,
                source_sha: str) -> dict[str, Any]:
        plan = run.get("plan")
        if not isinstance(plan, Mapping):
            raise ValueError("Hugging Face run plan is unavailable")
        handle = {
            "provider": "huggingface_space", "space_id": space_id,
            "request_id": request_id, "source_sha": source_sha,
            "run_id": run.get("id"), "plan_fingerprint": run.get("fingerprint"),
            "image_digest": plan.get("image_digest"), "started_at": run.get("started_at"),
        }
        if (not isinstance(handle["run_id"], str) or
                not isinstance(handle["plan_fingerprint"], str) or
                not isinstance(handle["image_digest"], str) or
                type(handle["started_at"]) is not int):
            raise ValueError("Hugging Face run identity is incomplete")
        return handle

    def start_candidate_bound(self, run: dict) -> dict:
        space_id, _request_id, _source_sha, _parameters, _runtime = self._identity(run)
        binding = run.get("plan", {}).get("selection_binding")
        if not isinstance(binding, Mapping) or binding.get("resource_id") != space_id:
            raise ValueError("Hugging Face candidate binding does not match the approved Space")
        return self.start(run)

    def reconcile(self, run: dict) -> dict | None:
        space_id, request_id, source_sha, _parameters, _runtime = self._identity(run)
        response = self._response(
            self._client(space_id).predict(request_id, api_name="/status"), request_id,
        )
        handle = self._handle(run, space_id, request_id, source_sha)
        manifest = run["plan"].get("workload_manifest") or run["registered_workload_manifest"]
        self.verify_space(space_id, manifest["source_revision"])
        self.verify_contract(space_id)
        handle["space_revision"] = manifest["source_revision"]
        handle["observation"] = response
        return handle

    def inspect(self, handle: dict) -> Observation:
        request_id = handle.get("request_id")
        if not isinstance(request_id, str) or _REQUEST_RE.fullmatch(request_id) is None:
            raise ValueError("Hugging Face Space handle is invalid")
        self.verify_space(handle["space_id"], handle["space_revision"])
        response = handle.get("observation")
        if response is None:
            response = self._response(
                self._client(handle["space_id"]).predict(request_id, api_name="/status"),
                request_id,
            )
        state = response["state"]
        if state in {"queued", "running"}:
            return Observation("running")
        handle["observation"] = response
        raw = response.get("result")
        if state == "succeeded":
            if not isinstance(raw, Mapping):
                raise RuntimeError("Hugging Face Space result is invalid")
            required = (raw.get("device"), raw.get("runtime_seconds"), raw.get("score"))
            if (raw.get("gpu_used") is not True or raw.get("exit_code") != 0 or
                    not isinstance(raw.get("checksum"), str) or
                    re.fullmatch(r"[0-9a-f]{64}", raw["checksum"]) is None or
                    not isinstance(raw.get("device"), str) or not raw["device"].strip() or
                    any(not isinstance(value, (int, float)) or isinstance(value, bool) or
                        not math.isfinite(value) for value in required[1:])):
                raise RuntimeError("Hugging Face Space did not return verified GPU evidence")
            elapsed = float(raw["runtime_seconds"])
            result = {
                "schema_version": 2, "run_id": handle["run_id"],
                "source_sha": handle["source_sha"],
                "plan_fingerprint": handle["plan_fingerprint"],
                "provider": "huggingface_space", "image_digest": handle["image_digest"],
                "simulation": False, "gpu_used": True, "device": raw["device"],
                "exit_code": 0, "started_at": handle["started_at"],
                "finished_at": handle["started_at"] + max(1, math.ceil(elapsed)),
                "runtime_seconds": elapsed, "metrics": {"score": float(raw["score"])},
                "checks": ["approved_space_contract", "zero_gpu_quota_checked"],
                "checksum": raw["checksum"], "artifacts": [], "external_artifacts": [],
                "known_cost_usd": "0", "cost_classification": "FREE_QUOTA",
                "cleanup_state": "pending",
            }
        else:
            result = {"provider": "huggingface_space", "space_id": handle["space_id"],
                      "request_id": request_id, "source_sha": handle["source_sha"],
                      "failure_code": f"space_{state}", "cleanup_state": "pending"}
        return Observation(state, result)

    def capture(self, handle: dict) -> Observation:
        return self.inspect(handle)

    def validate_candidate_observation(self, run: dict, observation: Observation) -> bool:
        if observation.state == "running" or not isinstance(observation.result, Mapping):
            return False
        space_id, request_id, source_sha, _parameters, _runtime = self._identity(run)
        return (observation.result.get("provider") == "huggingface_space" and
                observation.result.get("source_sha") == source_sha and
                observation.result.get("gpu_used") is True and
                observation.result.get("exit_code") == 0)

    def candidate_receipt_claims(self, handle: dict, observation: Observation) -> dict[str, Any]:
        response = handle.get("observation")
        if (observation.state != "succeeded" or not isinstance(observation.result, Mapping) or
                not isinstance(response, Mapping) or response.get("state") != "succeeded"):
            raise ValueError("Hugging Face receipt requires an authenticated terminal response")
        projection = {
            "space_id": handle["space_id"], "request_id": handle["request_id"],
            "state": response["state"], "source_sha": handle["source_sha"],
            "device_model": observation.result.get("device"),
            "checksum": observation.result.get("checksum"),
        }
        return {
            "provider_execution_id": handle["request_id"],
            "device_id": f'huggingface:{handle["request_id"]}:{observation.result.get("device")}',
            "evidence_source": "huggingface_space.gradio.status",
            "provider_object_projection": projection,
        }

    def cleanup(self, handle: dict) -> None:
        if self.inspect(handle).state == "running":
            raise RuntimeError("Hugging Face evaluation is not terminal")

    def is_clean(self, handle: dict) -> bool:
        return self.inspect(handle).state != "running"

    def cancel(self, handle: dict) -> None:
        request_id = handle["request_id"]
        response = self._client(handle["space_id"]).predict(request_id, api_name="/cancel")
        self._response(response, request_id)
