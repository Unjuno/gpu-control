from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace

import pytest

try:
    import modal
except ImportError:
    # This backend unit suite exercises only injected lookups and exception
    # handling; the real Modal SDK is intentionally not a CI dependency.
    modal = ModuleType("modal")
    modal.exception = SimpleNamespace(
        TimeoutError=type("TimeoutError", (Exception,), {}),
        OutputExpiredError=type("OutputExpiredError", (Exception,), {}),
        InputCancellation=type("InputCancellation", (Exception,), {}),
    )
    modal.Function = SimpleNamespace()
    modal.FunctionCall = SimpleNamespace()
    sys.modules["modal"] = modal

from modal_gpu_backend import ModalGpuBackend
from provider_adapter_core import MODAL_GPU_IMAGE_DIGEST, MODAL_GPU_SOURCE_SHA, MODAL_GPU_WORKLOAD


RUN_ID = "a" * 32
FINGERPRINT = "b" * 64
CALL_ID = "fc-test_call_1234"


class FakeCall:
    object_id = CALL_ID

    def __init__(self, result=None, pending=False):
        self.result = result
        self.pending = pending
        self.cancelled = False

    def get(self, timeout=0):
        assert timeout == 0
        if self.pending:
            raise modal.exception.TimeoutError
        return self.result

    def cancel(self, terminate_containers=False):
        assert terminate_containers is True
        self.cancelled = True


class FakeFunction:
    def __init__(self, call):
        self.call = call
        self.arguments = None

    def spawn(self, *arguments):
        self.arguments = arguments
        return self.call


def run():
    return {"id": RUN_ID, "fingerprint": FINGERPRINT}


class FakeSubmissionStore(dict):
    def put(self, key, value):
        self[key] = value


def result(**overrides):
    return {
        "schema_version": 1, "provider": "modal_gpu", "workload": MODAL_GPU_WORKLOAD,
        "run_id": RUN_ID, "source_sha": MODAL_GPU_SOURCE_SHA,
        "image_digest": MODAL_GPU_IMAGE_DIGEST,
        "plan_fingerprint": FINGERPRINT, "status": "passed", "gpu_used": True,
        "checksum": "c" * 64, **overrides,
    }


def test_backend_spawns_only_fixed_function_and_validates_gpu_result():
    call = FakeCall(result())
    function = FakeFunction(call)
    backend = ModalGpuBackend(function_lookup=lambda: function, call_lookup=lambda _call_id: call)
    handle = backend.start(run())
    assert function.arguments == (RUN_ID, MODAL_GPU_SOURCE_SHA, FINGERPRINT)
    assert handle == {
        "provider": "modal_gpu", "run_id": RUN_ID, "plan_fingerprint": FINGERPRINT,
        "function_call_id": CALL_ID, "app": "gpu-control-modal-gpu-canary", "function": "run_canary",
    }
    observed = backend.capture(handle)
    assert observed.state == "succeeded"
    assert observed.result["gpu_used"] is True
    backend.cleanup(handle)
    assert backend.is_clean(handle) is True


def test_backend_persists_and_reconciles_modal_call_handle_by_owner_bound_run():
    call = FakeCall(pending=True)
    function = FakeFunction(call)
    owner_binding = "d" * 64
    store = FakeSubmissionStore({RUN_ID: {
        "state": "running", "provider": "modal_gpu", "run_id": RUN_ID,
        "plan_fingerprint": FINGERPRINT, "owner_binding_sha256": owner_binding,
    }})
    run_value = {**run(), "plan": {"provider": "modal_gpu", "owner_binding_sha256": owner_binding}}
    backend = ModalGpuBackend(function_lookup=lambda: function, call_lookup=lambda _call_id: call,
                              submission_store=store)

    handle = backend.start(run_value)

    assert function.arguments == (RUN_ID, MODAL_GPU_SOURCE_SHA, FINGERPRINT)
    assert store[RUN_ID]["provider_handle"] == handle
    assert backend.reconcile(run_value) == handle

    other_owner = {**run_value, "plan": {"provider": "modal_gpu", "owner_binding_sha256": "e" * 64}}
    assert backend.reconcile(other_owner) is None


def test_backend_treats_zero_timeout_as_running_and_rejects_mismatched_result():
    pending = FakeCall(pending=True)
    backend = ModalGpuBackend(function_lookup=lambda: FakeFunction(pending), call_lookup=lambda _call_id: pending)
    handle = backend.start(run())
    assert backend.capture(handle).state == "running"

    invalid = FakeCall(result(run_id="d" * 32))
    backend = ModalGpuBackend(function_lookup=lambda: FakeFunction(invalid), call_lookup=lambda _call_id: invalid)
    handle = backend.start(run())
    with pytest.raises(Exception, match="provider_result_invalid"):
        backend.capture(handle)


def test_backend_cancel_is_bounded_and_marks_cleanup_confirmed():
    call = FakeCall(result())
    backend = ModalGpuBackend(function_lookup=lambda: FakeFunction(call), call_lookup=lambda _call_id: call)
    handle = backend.start(run())
    backend.cancel(handle)
    assert handle["cancel_requested"] is True
    assert backend.is_clean(handle) is False
    call.get = lambda timeout=0: (_ for _ in ()).throw(modal.exception.InputCancellation())
    observed = backend.capture(handle)
    assert observed.state == "cancelled"
    backend.cleanup(handle)
    assert call.cancelled is True
    assert backend.is_clean(handle) is True

