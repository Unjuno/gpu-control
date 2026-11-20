from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from gpu_gateway import huggingface_space_backend as space_module
from gpu_gateway.config import Settings
from gpu_gateway.huggingface_space_backend import (
    HuggingFaceSpaceBackend, ZeroGpuQuotaError, space_contract_digest,
)
from gpu_gateway.registry import default_registry


@dataclass
class Quota:
    base: float = 300
    remaining: float = 120
    resets_at: object = None
    overquota_used: float = 0


@dataclass
class SpaceInfo:
    sha: str = "e" * 40
    sdk: str = "gradio"
    private: bool = True


class FakeApi:
    def __init__(self, quota, space_info=None):
        self.quota = quota
        self.space_info_value = space_info or SpaceInfo()
        self.calls = []

    def get_zero_gpu_quota(self, **kwargs):
        self.calls.append(kwargs)
        return self.quota

    def space_info(self, **kwargs):
        self.calls.append(kwargs)
        return self.space_info_value


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

    def view_api(self, **_kwargs):
        return {"named_endpoints": {
            "/evaluate": {
                "parameters": [
                    {"label": "request_id", "component": "Textbox"},
                    {"label": "parameters_json", "component": "Textbox"},
                    {"label": "source_sha", "component": "Textbox"},
                ],
                "returns": [{"label": "result", "component": "Json"}],
            },
            "/status": {
                "parameters": [{"label": "request_id", "component": "Textbox"}],
                "returns": [{"label": "result", "component": "Json"}],
            },
            "/cancel": {
                "parameters": [{"label": "request_id", "component": "Textbox"}],
                "returns": [{"label": "result", "component": "Json"}],
            },
        }, "unnamed_endpoints": {}}


def settings():
    return Settings(
        enable_huggingface_space=True,
        hf_space_read_token="hf_read_token",
        hf_artifact_repositories=("owner/private-artifacts",),
        hf_space_allowlist=("owner/approved-zero-gpu",),
    )


def test_default_gradio_client_uses_supported_private_token_contract(monkeypatch):
    captured = {}

    def client(src, **kwargs):
        captured["src"] = src
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        space_module.importlib, "import_module",
        lambda name: SimpleNamespace(Client=client) if name == "gradio_client" else None,
    )
    backend = HuggingFaceSpaceBackend(settings(), api=FakeApi(Quota()))

    backend._client("owner/approved-zero-gpu")

    assert captured == {
        "src": "owner/approved-zero-gpu",
        "token": "hf_read_token",
        "verbose": False,
        "analytics_enabled": False,
        "download_files": False,
    }
    assert "hf_token" not in captured


def run():
    digest = space_contract_digest("owner/approved-zero-gpu", "e" * 40)
    return {
        "id": "run-1",
        "fingerprint": "f" * 64,
        "started_at": 1000,
        "plan": {
            "runtime_seconds": 30,
            "image_digest": digest,
            "parameters": {
                "artifact_repo_id": "owner/private-artifacts",
                "artifact_revision": "d" * 40,
                "artifact_path": "runs/" + "1" * 32 + "/orbitune-output.zip",
                "artifact_sha256": "c" * 64,
            },
            "workload_manifest": {
                "provider": "huggingface_space",
                "provider_resource_id": "owner/approved-zero-gpu",
                "source_sha": "a" * 40,
                "source_revision": "e" * 40,
                "image_digest": digest,
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
        "run_id": "run-1", "plan_fingerprint": "f" * 64,
        "image_digest": space_contract_digest("owner/approved-zero-gpu", "e" * 40), "started_at": 1000,
        "space_revision": "e" * 40,
    }
    request = client.calls[0]
    assert request[1] == "/evaluate"
    assert request[0][0] == "run-1-" + "f" * 12
    assert "hf_read_token" not in repr(request)


@pytest.mark.parametrize("quota", [
    Quota(remaining=29), Quota(remaining=120, overquota_used=1),
    Quota(remaining=float("nan")), Quota(remaining=float("inf")),
    Quota(remaining=120, overquota_used=None), None,
])
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
        "result": {"score": 0.75, "device": "NVIDIA A10G", "gpu_used": True,
                   "exit_code": 0, "checksum": "c" * 64, "runtime_seconds": 4.5},
    }])
    backend = HuggingFaceSpaceBackend(
        settings(), api=FakeApi(Quota()), client_factory=lambda _space, _token: client,
    )

    handle = backend.reconcile(run())
    observation = backend.inspect(handle)

    assert client.calls == [(("run-1-" + "f" * 12,), "/status")]
    assert observation.state == "succeeded"
    assert observation.result["metrics"] == {"score": 0.75}
    assert observation.result["device"] == "NVIDIA A10G"
    assert observation.result["gpu_used"] is True


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


def test_space_endpoint_contract_must_be_exact_before_evaluation():
    client = FakeClient([])
    contract = FakeClient([]).view_api()
    contract["named_endpoints"]["/unexpected"] = {"parameters": [], "returns": []}
    del contract["named_endpoints"]["/cancel"]
    client.view_api = lambda **_kwargs: contract
    backend = HuggingFaceSpaceBackend(
        settings(), api=FakeApi(Quota()), client_factory=lambda _space, _token: client,
    )

    with pytest.raises(RuntimeError, match="endpoint set changed"):
        backend.start(run())
    assert client.calls == []


def test_space_parameter_contract_must_be_exact_before_any_remote_operation():
    client = FakeClient([])
    contract = client.view_api()
    contract["named_endpoints"]["/evaluate"]["parameters"][1]["label"] = "payload"
    client.view_api = lambda **_kwargs: contract
    backend = HuggingFaceSpaceBackend(
        settings(), api=FakeApi(Quota()), client_factory=lambda _space, _token: client,
    )

    with pytest.raises(RuntimeError, match="parameter contract changed"):
        backend.reconcile(run())
    assert client.calls == []


def test_cancel_verifies_revision_and_contract_before_call():
    client = FakeClient([])
    backend = HuggingFaceSpaceBackend(
        settings(), api=FakeApi(Quota(), SpaceInfo(sha="0" * 40)),
        client_factory=lambda _space, _token: client,
    )
    handle = {
        "space_id": "owner/approved-zero-gpu",
        "space_revision": "e" * 40,
        "request_id": "run-1-" + "f" * 12,
    }

    with pytest.raises(RuntimeError, match="revision"):
        backend.cancel(handle)
    assert client.calls == []


def test_public_space_is_rejected_before_evaluation():
    client = FakeClient([])
    backend = HuggingFaceSpaceBackend(
        settings(),
        api=FakeApi(Quota(), SpaceInfo(private=False)),
        client_factory=lambda _space, _token: client,
    )

    with pytest.raises(RuntimeError, match="private visibility changed"):
        backend.start(run())
    assert client.calls == []
