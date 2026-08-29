from __future__ import annotations

import json

import pytest

from gpu_control.providers.runpod_v2 import RUNPOD_V2_BASE_URL, RunPodV2Error, RunPodV2HttpClient


class FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def read(self) -> bytes:
        return self._raw


def test_list_pods_uses_fixed_v2_full_account_endpoint_without_filters() -> None:
    calls = []

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        calls.append((request, timeout))
        return FakeResponse(
            200,
            {
                "pods": [
                    {"id": "pod-1", "name": "gpu-control-example", "status": "RUNNING"}
                ]
            },
        )

    client = RunPodV2HttpClient("secret-token", timeout=3.0, opener=opener)
    payload = client.list_pods()

    assert payload["pods"][0]["id"] == "pod-1"
    assert len(calls) == 1
    request, timeout = calls[0]
    assert request.full_url == f"{RUNPOD_V2_BASE_URL}/pods"
    assert request.get_method() == "GET"
    assert request.data is None
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert timeout == 3.0


def test_list_pods_rejects_missing_v2_pods_envelope() -> None:
    def opener(request, timeout):  # type: ignore[no-untyped-def]
        return FakeResponse(200, {"items": []})

    client = RunPodV2HttpClient("secret-token", opener=opener)
    with pytest.raises(RunPodV2Error, match="missing pods"):
        client.list_pods()
