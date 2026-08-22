from __future__ import annotations

from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

import gpu_control.source as source_module
from gpu_control.source import SourceVerificationError, verify_public_github_source
from gpu_control.validation import build_request


VALID_SHA = "0123456789abcdef0123456789abcdef01234567"


class FakeResponse(BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def make_request():
    return build_request(
        target_repo="example/model",
        target_sha=VALID_SHA,
        dockerfile_path="containers/Dockerfile",
        gpu_profile="cheap-24gb",
        max_runtime_minutes=5,
        max_cost_usd="0.05",
    )


def response(payload: object) -> FakeResponse:
    return FakeResponse(json.dumps(payload).encode("utf-8"))


def test_verifies_public_repository_exact_commit_and_dockerfile(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_urls: list[str] = []
    seen_auth: list[str | None] = []

    def fake_urlopen(request, timeout: float):  # type: ignore[no-untyped-def]
        seen_urls.append(request.full_url)
        seen_auth.append(request.get_header("Authorization"))
        if request.full_url.endswith("/repos/example/model"):
            return response({"full_name": "example/model", "private": False})
        if f"/commits/{VALID_SHA}" in request.full_url:
            return response({"sha": VALID_SHA})
        if f"/contents/containers/Dockerfile?ref={VALID_SHA}" in request.full_url:
            return response({"type": "file"})
        raise AssertionError(request.full_url)

    monkeypatch.setattr(source_module, "urlopen", fake_urlopen)

    result = verify_public_github_source(make_request(), token="test-token")

    assert result.repository == "example/model"
    assert result.commit_sha == VALID_SHA
    assert result.dockerfile_path == "containers/Dockerfile"
    assert result.repository_public is True
    assert result.commit_verified is True
    assert result.dockerfile_verified is True
    assert len(seen_urls) == 3
    assert seen_auth == ["Bearer test-token"] * 3


def test_rejects_private_repository_even_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        source_module,
        "urlopen",
        lambda request, timeout: response({"full_name": "example/model", "private": True}),
    )

    with pytest.raises(SourceVerificationError, match="must be public"):
        verify_public_github_source(make_request(), token="test-token")


def test_rejects_commit_identity_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):  # type: ignore[no-untyped-def]
        if request.full_url.endswith("/repos/example/model"):
            return response({"full_name": "example/model", "private": False})
        return response({"sha": "f" * 40})

    monkeypatch.setattr(source_module, "urlopen", fake_urlopen)

    with pytest.raises(SourceVerificationError, match="exact requested commit"):
        verify_public_github_source(make_request())


def test_rejects_missing_source_object(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):  # type: ignore[no-untyped-def]
        raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr(source_module, "urlopen", fake_urlopen)

    with pytest.raises(SourceVerificationError, match="not found"):
        verify_public_github_source(make_request())


def test_rejects_non_file_dockerfile_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):  # type: ignore[no-untyped-def]
        if request.full_url.endswith("/repos/example/model"):
            return response({"full_name": "example/model", "private": False})
        if f"/commits/{VALID_SHA}" in request.full_url:
            return response({"sha": VALID_SHA})
        return response({"type": "dir"})

    monkeypatch.setattr(source_module, "urlopen", fake_urlopen)

    with pytest.raises(SourceVerificationError, match="does not resolve to a file"):
        verify_public_github_source(make_request())
