from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import pytest

from gpu_gateway.config import Settings
from gpu_gateway.huggingface_artifacts import HuggingFaceArtifactStore


@dataclass
class RepoInfo:
    private: bool
    sha: str = "c" * 40


@dataclass
class CommitInfo:
    oid: str


class FakeApi:
    def __init__(self, *, private=True, existing=False):
        self.private = private
        self.existing = existing
        self.calls = []
        self.uploaded = b""

    def repo_info(self, **kwargs):
        self.calls.append(("repo_info", kwargs))
        return RepoInfo(private=self.private)

    def file_exists(self, **kwargs):
        self.calls.append(("file_exists", kwargs))
        return self.existing

    def upload_file(self, **kwargs):
        self.calls.append(("upload_file", kwargs))
        self.uploaded = Path(kwargs["path_or_fileobj"]).read_bytes()
        return CommitInfo(oid="c" * 40)


def settings():
    return Settings(
        hf_token="hf_secret_test_value",
        hf_artifact_repositories=("owner/private-artifacts",),
    )


def test_publish_uploads_only_to_allowlisted_private_repo_and_verifies_exact_revision(tmp_path):
    artifact = tmp_path / "checkpoint.pt"
    artifact.write_bytes(b"checkpoint-bytes")
    api = FakeApi()
    downloads = []

    def download(**kwargs):
        downloads.append(kwargs)
        restored = tmp_path / "downloaded.pt"
        restored.write_bytes(api.uploaded)
        return str(restored)

    store = HuggingFaceArtifactStore(settings(), api=api, downloader=download)
    reference = store.publish(
        artifact,
        repo_id="owner/private-artifacts",
        path_in_repo="runs/run-1/checkpoint.pt",
        run_id="run-1",
        source_sha="a" * 40,
    )

    checksum = hashlib.sha256(b"checkpoint-bytes").hexdigest()
    assert reference == {
        "service": "huggingface_hub",
        "repo_id": "owner/private-artifacts",
        "repo_type": "model",
        "path_in_repo": "runs/run-1/checkpoint.pt",
        "revision": "c" * 40,
        "sha256": checksum,
        "size_bytes": len(b"checkpoint-bytes"),
        "run_id": "run-1",
        "source_sha": "a" * 40,
        "private": True,
    }
    assert downloads == [{
        "repo_id": "owner/private-artifacts",
        "filename": "runs/run-1/checkpoint.pt",
        "repo_type": "model",
        "revision": "c" * 40,
        "token": "hf_secret_test_value",
    }]
    assert "hf_secret_test_value" not in repr(reference)


def test_publish_rejects_public_or_unallowlisted_repository_before_upload(tmp_path):
    artifact = tmp_path / "checkpoint.pt"
    artifact.write_bytes(b"checkpoint")

    for repo_id, private in (("other/repo", True), ("owner/private-artifacts", False)):
        api = FakeApi(private=private)
        store = HuggingFaceArtifactStore(settings(), api=api, downloader=lambda **_: "unused")
        with pytest.raises(ValueError):
            store.publish(
                artifact, repo_id=repo_id, path_in_repo="runs/run/checkpoint.pt",
                run_id="run", source_sha="a" * 40,
            )
        assert all(name != "upload_file" for name, _kwargs in api.calls)


def test_publish_detects_redownload_checksum_mismatch(tmp_path):
    artifact = tmp_path / "checkpoint.pt"
    artifact.write_bytes(b"checkpoint")
    corrupted = tmp_path / "corrupted.pt"
    corrupted.write_bytes(b"corrupted")
    store = HuggingFaceArtifactStore(
        settings(), api=FakeApi(), downloader=lambda **_: str(corrupted),
    )

    with pytest.raises(RuntimeError, match="checksum"):
        store.publish(
            artifact, repo_id="owner/private-artifacts",
            path_in_repo="runs/run/checkpoint.pt", run_id="run", source_sha="a" * 40,
        )


def test_publish_reuses_matching_existing_path_without_duplicate_upload(tmp_path):
    artifact = tmp_path / "bundle.zip"
    artifact.write_bytes(b"same-content")
    restored = tmp_path / "existing.zip"
    restored.write_bytes(b"same-content")
    api = FakeApi(existing=True)
    store = HuggingFaceArtifactStore(
        settings(), api=api, downloader=lambda **_: str(restored),
    )

    reference = store.publish(
        artifact, repo_id="owner/private-artifacts",
        path_in_repo="runs/run/bundle.zip", run_id="run", source_sha="a" * 40,
    )

    assert reference["revision"] == "c" * 40
    assert all(name != "upload_file" for name, _kwargs in api.calls)


def test_publish_refuses_to_overwrite_existing_path_with_different_content(tmp_path):
    artifact = tmp_path / "bundle.zip"
    artifact.write_bytes(b"new")
    restored = tmp_path / "existing.zip"
    restored.write_bytes(b"old")
    api = FakeApi(existing=True)
    store = HuggingFaceArtifactStore(
        settings(), api=api, downloader=lambda **_: str(restored),
    )

    with pytest.raises(RuntimeError, match="immutable artifact path"):
        store.publish(
            artifact, repo_id="owner/private-artifacts",
            path_in_repo="runs/run/bundle.zip", run_id="run", source_sha="a" * 40,
        )
    assert all(name != "upload_file" for name, _kwargs in api.calls)


def test_publish_rejects_paths_tokens_and_unbounded_artifacts(tmp_path):
    artifact = tmp_path / "checkpoint.pt"
    artifact.write_bytes(b"12345")
    store = HuggingFaceArtifactStore(
        settings(), api=FakeApi(), downloader=lambda **_: str(artifact), max_bytes=4,
    )

    with pytest.raises(ValueError):
        store.publish(
            artifact, repo_id="owner/private-artifacts", path_in_repo="../token.txt",
            run_id="run", source_sha="a" * 40,
        )
    with pytest.raises(ValueError, match="size"):
        store.publish(
            artifact, repo_id="owner/private-artifacts", path_in_repo="runs/run/checkpoint.pt",
            run_id="run", source_sha="a" * 40,
        )
