from __future__ import annotations

from dataclasses import dataclass

import pytest

from gpu_gateway.config import Settings
from gpu_gateway.huggingface_space_backend import HuggingFaceSpaceBackend, ZeroGpuQuotaError
from gpu_gateway.registry import default_registry


@dataclass
class Quota:
    base: float = 300
    remaining: float = 120
    resets_at: object = None
    overquota_used: float = 0


class FakeApi:
    def __init__(self, quota):
        self.quota = quota
        self.calls = []

    def get_zero_gpu_quota(self, **kwargs):
        self.calls.append(kwargs)
        return self.quota


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def predict(self, *args, api_name):
        self.calls.append((args, api_name))
        if not self.responses:
            raise AssertionError("unexpected Space call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def settings():
    return Settings(
        enable_huggingface_space=True,
        hf_token="hf_read_token",
        hf_space_allowlist=("owner/approved-zero-gpu",),
    )


def run():
    return {
        "id": "run-1",
        "fingerprint": "f" * 64,
        "plan": {
            "runtime_seconds": 30,
            "parameters": {"prompt": "evaluate this checkpoint"},
            "workload_manifest": {
                "provider": "huggingface_space",
                "provider_resource_id": "owner/approved-zero-gpu",
                "source_sha": "a" * 40,
            },
        },
    }


def test_start_checks_free_quota_and_returns_bounded_durable_request_handle():
    client = FakeClient([{"request_id": "run-1-" + "f" * 12, "state": "running"}])
    backend = HuggingFaceSpaceBackend(
        settings(), api=FakeApi(Quota()), client_factory=lambda _space, _token: client,
    )

    handle = backend.start(run())

    assert handle == {
        "provider": "huggingface_space",
        "space_id": "owner/approved-zero-gpu",
        "request_id": "run-1-" + "f" * 12,
        "source_sha": "a" * 40,
    }
    request = client.calls[0]
    assert request[1] == "/evaluate"
    assert request[0][0] == "run-1-" + "f" * 12
    assert "hf_read_token" not in repr(request)


@pytest.mark.parametrize("quota", [Quota(remaining=29), Quota(remaining=120, overquota_used=1), None])
def test_start_fails_closed_before_space_call_when_free_quota_is_unsafe(quota):
    client = FakeClient([])
    backend = HuggingFaceSpaceBackend(
        settings(), api=FakeApi(quota), client_factory=lambda _space, _token: client,
    )

    with pytest.raises(ZeroGpuQuotaError):
        backend.start(run())
    assert client.calls == []


def test_reconcile_never_restarts_and_uses_deterministic_status_endpoint():
    client = FakeClient([{
        "request_id": "run-1-" + "f" * 12,
        "state": "succeeded",
        "result": {"score": 0.75},
    }])
    backend = HuggingFaceSpaceBackend(
        settings(), api=FakeApi(Quota()), client_factory=lambda _space, _token: client,
    )

    handle = backend.reconcile(run())
    observation = backend.inspect(handle)

    assert client.calls == [(("run-1-" + "f" * 12,), "/status")]
    assert observation.state == "succeeded"
    assert observation.result["metrics"] == {"score": 0.75}


def test_space_must_be_allowlisted_and_registry_does_not_enable_paid_jobs():
    value = run()
    value["plan"]["workload_manifest"]["provider_resource_id"] = "other/unapproved"
    backend = HuggingFaceSpaceBackend(
        settings(), api=FakeApi(Quota()), client_factory=lambda _space, _token: FakeClient([]),
    )
    with pytest.raises(ValueError):
        backend.start(value)

    registry = default_registry()
    assert "huggingface_space" in registry
    assert "huggingface_jobs" not in registry
    assert registry["huggingface_space"].supports_paid_execution is False
