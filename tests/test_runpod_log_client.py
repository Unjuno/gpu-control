from __future__ import annotations

import json

import pytest

from gpu_control.providers.runpod_v2 import RUNPOD_V2_BASE_URL, RunPodV2Error, RunPodV2HttpClient


RESULT = "GPU_CONTROL_RESULT_JSON_V1:cmVzdWx0"
COMPLETION = "GPU_CONTROL_COMPLETION_JSON_V2:Y29tcGxldGlvbg=="


class StreamResponse:
    def __init__(self, lines: list[bytes], *, status: int = 200) -> None:
        self.status = status
        self.lines = lines

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.lines)


def event(line: str, source: str = "container") -> bytes:
    payload = json.dumps({"source": source, "line": line, "ts": "2026-08-28T00:00:00Z"})
    return f"data: {payload}\n".encode("utf-8")


def test_log_reader_uses_fixed_sse_endpoint_and_stops_after_both_markers() -> None:
    calls = []

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        calls.append((request, timeout))
        return StreamResponse([
            event("ordinary"),
            event("ignored", source="system"),
            event(RESULT),
            event(COMPLETION),
            event("must-not-be-needed"),
        ])

    client = RunPodV2HttpClient("secret", timeout=4.0, opener=opener)
    lines = client.read_container_log_lines("pod-123")

    assert lines == ("ordinary", RESULT, COMPLETION)
    request, timeout = calls[0]
    assert request.full_url == f"{RUNPOD_V2_BASE_URL}/pods/pod-123/logs?source=container&tail=5000"
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.get_header("Accept") == "text/event-stream"
    assert timeout == 4.0


def test_log_reader_fails_closed_on_oversized_stream() -> None:
    def opener(request, timeout):  # type: ignore[no-untyped-def]
        return StreamResponse([event("x" * 1024)])

    client = RunPodV2HttpClient("secret", opener=opener)
    with pytest.raises(RunPodV2Error, match="bounded byte limit"):
        client.read_container_log_lines("pod-123", max_bytes=100)


def test_log_reader_fails_closed_on_malformed_sse_json() -> None:
    def opener(request, timeout):  # type: ignore[no-untyped-def]
        return StreamResponse([b"data: not-json\n"])

    client = RunPodV2HttpClient("secret", opener=opener)
    with pytest.raises(RunPodV2Error, match="valid JSON"):
        client.read_container_log_lines("pod-123")
