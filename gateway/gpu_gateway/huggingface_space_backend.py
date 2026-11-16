"""Approved Gradio ZeroGPU Space backend for bounded evaluation only."""
from __future__ import annotations

import importlib
import json
import re
from typing import Any, Callable, Mapping

from .backends import Observation
from .config import Settings


_RESOURCE_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUEST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}-[0-9a-f]{12}$")


class ZeroGpuQuotaError(RuntimeError):
    pass


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
        if (not isinstance(run_id, str) or
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id) is None or
                not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None):
            raise ValueError("Hugging Face Space run identity is invalid")
        if type(runtime) is not int or not 1 <= runtime <= 60:
            raise ValueError("Hugging Face Space evaluation must be at most 60 seconds")
        if not isinstance(parameters, dict):
            raise ValueError("Hugging Face Space parameters must be an object")
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
                remaining < runtime or overquota not in {None, 0, 0.0}):
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

    def start(self, run: dict) -> dict:
        if not self.settings.enable_huggingface_space:
            raise RuntimeError("Hugging Face Space submission is disabled")
        if not self.settings.hf_token:
            raise RuntimeError("Hugging Face worker token is not configured")
        space_id, request_id, source_sha, parameters, runtime = self._identity(run)
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
        handle = {"provider": "huggingface_space", "space_id": space_id,
                  "request_id": request_id, "source_sha": source_sha}
        if response["state"] not in {"queued", "running"}:
            handle["observation"] = response
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
        handle = {"provider": "huggingface_space", "space_id": space_id,
                  "request_id": request_id, "source_sha": source_sha,
                  "observation": response}
        return handle

    def inspect(self, handle: dict) -> Observation:
        request_id = handle.get("request_id")
        if not isinstance(request_id, str) or _REQUEST_RE.fullmatch(request_id) is None:
            raise ValueError("Hugging Face Space handle is invalid")
        response = handle.get("observation")
        if response is None:
            response = self._response(
                self._client(handle["space_id"]).predict(request_id, api_name="/status"),
                request_id,
            )
        state = response["state"]
        if state in {"queued", "running"}:
            return Observation("running")
        result = {
            "provider": "huggingface_space",
            "space_id": handle["space_id"],
            "request_id": request_id,
            "source_sha": handle["source_sha"],
            "metrics": response.get("result", {}),
            "cleanup_state": "not_required",
        }
        return Observation(state, result)

    def capture(self, handle: dict) -> Observation:
        return self.inspect(handle)

    def validate_candidate_observation(self, run: dict, observation: Observation) -> bool:
        if observation.state == "running" or not isinstance(observation.result, Mapping):
            return False
        space_id, request_id, source_sha, _parameters, _runtime = self._identity(run)
        return (observation.result.get("provider") == "huggingface_space" and
                observation.result.get("space_id") == space_id and
                observation.result.get("request_id") == request_id and
                observation.result.get("source_sha") == source_sha)

    def cleanup(self, handle: dict) -> None:
        if self.inspect(handle).state == "running":
            raise RuntimeError("Hugging Face evaluation is not terminal")

    def is_clean(self, handle: dict) -> bool:
        return self.inspect(handle).state != "running"

    def cancel(self, handle: dict) -> None:
        request_id = handle["request_id"]
        response = self._client(handle["space_id"]).predict(request_id, api_name="/cancel")
        self._response(response, request_id)
