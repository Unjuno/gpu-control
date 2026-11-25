"""Fixed Modal GPU canary backend for the Sites provider adapter.

The backend can only address the separately deployed, reviewed T4 canary.
Callers cannot choose an app, function, image, GPU type, code, command, URL,
or environment variable.  The opaque Modal call id is persisted by Sites.
"""
from __future__ import annotations

import re
import time
from types import SimpleNamespace
from typing import Any

import modal

from provider_adapter_core import (
    AdapterError, MODAL_GPU_IMAGE_DIGEST, MODAL_GPU_SOURCE_SHA, MODAL_GPU_WORKLOAD,
)


APP_NAME = "gpu-control-modal-gpu-canary"
FUNCTION_NAME = "run_canary"
CALL_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


class ModalGpuBackend:
    provider = "modal_gpu"

    def __init__(self, function_lookup=None, call_lookup=None, submission_store=None):
        self._function_lookup = function_lookup or (
            lambda: modal.Function.from_name(APP_NAME, FUNCTION_NAME, environment_name="main"))
        self._call_lookup = call_lookup or modal.FunctionCall.from_id
        self._submission_store = submission_store

    def reconcile(self, run: dict[str, Any]) -> dict[str, Any] | None:
        """Recover a call handle persisted immediately after ``spawn`` returns."""
        if self._submission_store is None:
            return None
        run_id = run.get("id")
        fingerprint = run.get("fingerprint")
        owner_binding = run.get("plan", {}).get("owner_binding_sha256")
        record = self._submission_store.get(run_id)
        if (not isinstance(record, dict) or record.get("provider") != self.provider or
                record.get("run_id") != run_id or record.get("plan_fingerprint") != fingerprint or
                record.get("owner_binding_sha256") != owner_binding):
            return None
        handle = record.get("provider_handle")
        if (not isinstance(handle, dict) or handle.get("provider") != self.provider or
                handle.get("run_id") != run_id or handle.get("plan_fingerprint") != fingerprint):
            return None
        return handle

    def _call(self, handle: dict[str, Any]):
        call_id = handle.get("function_call_id")
        if not isinstance(call_id, str) or CALL_ID.fullmatch(call_id) is None:
            raise AdapterError("provider_handle_mismatch", 409)
        return self._call_lookup(call_id)

    def start(self, run: dict[str, Any]) -> dict[str, Any]:
        function = self._function_lookup()
        call = function.spawn(run["id"], MODAL_GPU_SOURCE_SHA, run["fingerprint"])
        call_id = getattr(call, "object_id", None)
        if not isinstance(call_id, str) or CALL_ID.fullmatch(call_id) is None:
            raise AdapterError("provider_invalid_handle", 502)
        handle = {
            "provider": self.provider,
            "run_id": run["id"],
            "plan_fingerprint": run["fingerprint"],
            "function_call_id": call_id,
            "app": APP_NAME,
            "function": FUNCTION_NAME,
        }
        if self._submission_store is not None:
            record = self._submission_store.get(run["id"])
            owner_binding = run.get("plan", {}).get("owner_binding_sha256")
            if (not isinstance(record, dict) or record.get("provider") != self.provider or
                    record.get("run_id") != run["id"] or
                    record.get("plan_fingerprint") != run["fingerprint"] or
                    record.get("owner_binding_sha256") != owner_binding):
                raise AdapterError("submission_identity_conflict", 409)
            self._submission_store.put(run["id"], {**record, "state": "running",
                "provider_handle": handle, "provider_accepted_at": int(time.time())})
        return handle

    def capture(self, handle: dict[str, Any]):
        try:
            result = self._call(handle).get(timeout=0)
        except modal.exception.OutputExpiredError as exc:
            raise AdapterError("provider_result_expired", 502) from exc
        except modal.exception.TimeoutError as exc:
            if type(exc) is not modal.exception.TimeoutError:
                raise AdapterError("provider_execution_failed", 502) from exc
            return SimpleNamespace(state="running", result=None)
        except modal.exception.InputCancellation:
            handle["terminal"] = "cancelled"
            return SimpleNamespace(state="cancelled", result=None)
        if (not isinstance(result, dict) or result.get("schema_version") != 1 or
                result.get("provider") != self.provider or result.get("workload") != MODAL_GPU_WORKLOAD or
                result.get("run_id") != handle.get("run_id") or
                result.get("source_sha") != MODAL_GPU_SOURCE_SHA or
                result.get("image_digest") != MODAL_GPU_IMAGE_DIGEST or
                result.get("plan_fingerprint") != handle.get("plan_fingerprint") or
                result.get("status") != "passed" or result.get("gpu_used") is not True or
                not isinstance(result.get("checksum"), str) or
                re.fullmatch(r"[0-9a-f]{64}", result["checksum"]) is None):
            raise AdapterError("provider_result_invalid", 502)
        handle["terminal"] = "succeeded"
        return SimpleNamespace(state="succeeded", result=result)

    def cancel(self, handle: dict[str, Any]) -> None:
        self._call(handle).cancel(terminate_containers=True)
        handle["cancel_requested"] = True

    def cleanup(self, handle: dict[str, Any]) -> None:
        # Modal Function calls are finite and the canary is single-use.  A
        # successful result proves the function returned and its container is
        # no longer reusable. Cancellation is provider-owned and idempotent.
        if handle.get("terminal") not in {"succeeded", "cancelled"}:
            raise AdapterError("cleanup_not_confirmed", 503)

    def is_clean(self, handle: dict[str, Any]) -> bool:
        return handle.get("terminal") in {"succeeded", "cancelled"}

