from urllib.request import Request

import pytest

import gpu_control.http_security as http_security
from gpu_control.providers.runpod_v2 import RunPodV2Error, RunPodV2HttpClient


def test_bounded_read_stops_after_limit_plus_one() -> None:
    class Response:
        headers = {}

        def __init__(self) -> None:
            self.requested = []

        def read(self, size: int) -> bytes:
            self.requested.append(size)
            return b"x" * size

    response = Response()
    with pytest.raises(ValueError, match="byte limit"):
        http_security.read_bounded(response, max_bytes=16)
    assert response.requested == [17]


def test_bounded_read_rejects_oversized_content_length_without_reading() -> None:
    class Response:
        headers = {"Content-Length": "17"}
        reads = 0

        def read(self, _size: int) -> bytes:
            self.reads += 1
            return b""

    response = Response()
    with pytest.raises(ValueError, match="byte limit"):
        http_security.read_bounded(response, max_bytes=16)
    assert response.reads == 0


def test_safe_opener_installs_redirect_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = []
    sentinel = object()

    class Opener:
        def open(self, request: Request, *, timeout: float):
            return sentinel

    def build(*handlers):
        seen.extend(handlers)
        return Opener()

    monkeypatch.setattr(http_security, "build_opener", build)
    assert http_security.open_no_redirect(Request("https://example.test"), timeout=2) is sentinel
    assert any(isinstance(item, http_security.NoRedirectHandler) for item in seen)


def test_runpod_api_rejects_oversized_response_before_reading_body() -> None:
    class Response:
        status = 200
        headers = {"Content-Length": str(2 * 1024 * 1024 + 1)}
        reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self, _size: int) -> bytes:
            self.reads += 1
            return b""

    response = Response()
    client = RunPodV2HttpClient("token", opener=lambda *_args, **_kwargs: response)
    with pytest.raises(RunPodV2Error, match="byte limit"):
        client._request("GET", "/pods", expected_status=200)
    assert response.reads == 0
