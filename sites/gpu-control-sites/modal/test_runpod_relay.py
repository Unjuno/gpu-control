import io
import json
import urllib.error

import pytest

import runpod_relay


def test_upstream_path_is_endpoint_and_operation_scoped():
    assert runpod_relay.upstream_path("endpoint_abc", "run", None) == "/v2/endpoint_abc/run"
    assert runpod_relay.upstream_path("endpoint_abc", "status", "job_abc") == "/v2/endpoint_abc/status/job_abc"
    with pytest.raises(ValueError):
        runpod_relay.upstream_path("endpoint_abc", "account", None)
    with pytest.raises(ValueError):
        runpod_relay.upstream_path("../account", "run", None)


def test_relay_rejects_redirect_without_following(monkeypatch):
    class Redirect:
        status = 302
        def read(self, _size): return b""
        def close(self): pass
    class Opener:
        def open(self, _request, timeout):
            assert timeout == 35
            raise urllib.error.HTTPError("https://api.runpod.ai", 302, "redirect", {}, Redirect())
    monkeypatch.setattr(runpod_relay.urllib.request, "build_opener", lambda *_args: Opener())
    with pytest.raises(ValueError, match="redirect_rejected"):
        runpod_relay.relay("GET", "/v2/endpoint_abc/status/job_abc", "Bearer secret", b"")


def test_relay_returns_only_bounded_json(monkeypatch):
    class Response:
        status = 200
        def read(self, _size): return json.dumps({"id": "job_abc", "status": "IN_QUEUE"}).encode()
        def close(self): pass
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://api.runpod.ai/v2/endpoint_abc/run"
            assert request.get_header("Authorization") == "Bearer secret"
            return Response()
    monkeypatch.setattr(runpod_relay.urllib.request, "build_opener", lambda *_args: Opener())
    status, body, headers = runpod_relay.relay("POST", "/v2/endpoint_abc/run", "Bearer secret", b"{}")
    assert status == 200
    assert json.loads(body) == {"id": "job_abc", "status": "IN_QUEUE"}
    assert headers == {"content-type": "application/json"}
