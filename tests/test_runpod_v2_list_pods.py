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

    def read(self, size: int = -1) -> bytes:
        return self._raw if size < 0 else self._raw[:size]


def test_list_pods_follows_v2_cursor_pages_and_normalizes_full_account_inventory() -> None:
    calls = []
    pages = [
        {
            "pods": [{"id": "pod-1", "name": "gpu-control-example", "status": "RUNNING"}],
            "pagination": {"nextCursor": "opaque-page-2", "hasNextPage": True},
        },
        {
            "pods": [{"id": "pod-2", "name": "other", "status": "TERMINATED"}],
            "pagination": {"nextCursor": None, "hasNextPage": False},
        },
    ]

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        calls.append((request, timeout))
        return FakeResponse(200, pages[len(calls) - 1])

    client = RunPodV2HttpClient("secret-token", timeout=3.0, opener=opener)
    payload = client.list_pods()

    assert [pod["id"] for pod in payload["pods"]] == ["pod-1", "pod-2"]
    assert len(calls) == 2
    first, first_timeout = calls[0]
    second, second_timeout = calls[1]
    assert first.full_url == f"{RUNPOD_V2_BASE_URL}/pods?limit=256"
    assert second.full_url == f"{RUNPOD_V2_BASE_URL}/pods?limit=255&cursor=opaque-page-2"
    for request, timeout in ((first, first_timeout), (second, second_timeout)):
        assert request.get_method() == "GET"
        assert request.data is None
        assert request.get_header("Authorization") == "Bearer secret-token"
        assert timeout == 3.0


def test_list_pods_rejects_missing_v2_pods_envelope() -> None:
    def opener(request, timeout):  # type: ignore[no-untyped-def]
        return FakeResponse(200, {"items": [], "pagination": {"nextCursor": None, "hasNextPage": False}})

    client = RunPodV2HttpClient("secret-token", opener=opener)
    with pytest.raises(RunPodV2Error, match="missing pods"):
        client.list_pods()


def test_list_pods_rejects_missing_pagination_metadata() -> None:
    def opener(request, timeout):  # type: ignore[no-untyped-def]
        return FakeResponse(200, {"pods": []})

    client = RunPodV2HttpClient("secret-token", opener=opener)
    with pytest.raises(RunPodV2Error, match="missing pagination metadata"):
        client.list_pods()


def test_list_pods_rejects_duplicate_ids() -> None:
    responses = [
        {"pods": [{"id": "pod-1"}], "pagination": {"nextCursor": "same", "hasNextPage": True}},
        {"pods": [{"id": "pod-1"}], "pagination": {"nextCursor": "same", "hasNextPage": True}},
    ]

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        return FakeResponse(200, responses.pop(0))

    client = RunPodV2HttpClient("secret-token", opener=opener)
    with pytest.raises(RunPodV2Error, match="duplicate Pod ids"):
        client.list_pods()


def test_list_pods_rejects_cursor_cycles() -> None:
    responses = [
        {"pods": [{"id": "pod-1"}], "pagination": {"nextCursor": "same", "hasNextPage": True}},
        {"pods": [{"id": "pod-2"}], "pagination": {"nextCursor": "same", "hasNextPage": True}},
    ]

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        return FakeResponse(200, responses.pop(0))

    client = RunPodV2HttpClient("secret-token", opener=opener)
    with pytest.raises(RunPodV2Error, match="cursor repeated"):
        client.list_pods()


def test_list_pods_fails_closed_when_inventory_exceeds_evidence_bound() -> None:
    oversized_page = {
        "pods": [{"id": f"pod-{index}"} for index in range(256)],
        "pagination": {"nextCursor": "more", "hasNextPage": True},
    }

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        return FakeResponse(200, oversized_page)

    client = RunPodV2HttpClient("secret-token", opener=opener)
    with pytest.raises(RunPodV2Error, match="exceeds bounded Pod count"):
        client.list_pods()


def test_list_pods_fails_closed_when_empty_pages_advance_cursor_without_bound() -> None:
    calls = []

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        calls.append(request)
        return FakeResponse(
            200,
            {
                "pods": [],
                "pagination": {"nextCursor": f"page-{len(calls) + 1}", "hasNextPage": True},
            },
        )

    client = RunPodV2HttpClient("secret-token", opener=opener)
    with pytest.raises(RunPodV2Error, match="exceeds bounded page count"):
        client.list_pods()
    assert len(calls) == 32
