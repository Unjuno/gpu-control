from pathlib import Path
import hashlib
from types import SimpleNamespace

import pytest

from provider_runtime import Observation, ProviderSettings, bounded_text
from provider_runtime.huggingface_artifacts import HuggingFaceArtifactStore


def test_contracts_are_bounded_and_reject_unknown_states() -> None:
    assert bounded_text([b"abc", "def"], 4) == ("abcd", True)
    assert Observation("succeeded", {"ok": True}).state == "succeeded"
    with pytest.raises(ValueError, match="unsupported state"):
        Observation("unknown")


def test_provider_settings_accept_only_fixed_secret_bearing_boundaries(tmp_path: Path) -> None:
    settings = ProviderSettings(
        enable_kaggle=True,
        kaggle_api_token="kaggle-token",
        kaggle_username="UnjunoOrg",
        kaggle_staging_root=str(tmp_path / "stage"),
        kaggle_source_cache_root=str(tmp_path / "cache"),
        enable_huggingface_space=True,
        hf_space_read_token="hf-read",
        hf_artifact_write_token="hf-write",
        hf_artifact_repositories=("Unjuno/private-artifacts",),
        hf_space_allowlist=("Unjuno/private-zero-gpu",),
    )
    settings.validate()


def test_provider_settings_redacts_and_separates_secrets() -> None:
    settings = ProviderSettings(
        kaggle_api_token="kaggle-secret",
        hf_space_read_token="hf-secret",
        hf_artifact_write_token="hf-secret",
        hf_artifact_repositories=("Unjuno/artifacts",),
    )
    rendered = repr(settings)
    assert "kaggle-secret" not in rendered
    assert "hf-secret" not in rendered
    with pytest.raises(ValueError, match="must be distinct"):
        settings.validate()


@pytest.mark.parametrize("change", [
    {"kaggle_staging_root": "relative"},
    {"kaggle_api_token": "token with spaces"},
    {"hf_artifact_repositories": ("not-a-resource",)},
    {"hf_space_allowlist": ()},
])
def test_provider_settings_fail_closed(tmp_path: Path, change: dict) -> None:
    values = dict(
        enable_kaggle=True, kaggle_api_token="kaggle-token", kaggle_username="UnjunoOrg",
        kaggle_staging_root=str(tmp_path / "stage"), kaggle_source_cache_root=str(tmp_path / "cache"),
        enable_huggingface_space=True, hf_space_read_token="hf-read",
        hf_artifact_repositories=("Unjuno/private-artifacts",),
        hf_space_allowlist=("Unjuno/private-zero-gpu",),
    )
    values.update(change)
    with pytest.raises(ValueError):
        ProviderSettings(**values).validate()


def test_private_artifact_read_verifies_full_file_before_returning_chunk(tmp_path: Path) -> None:
    payload = b"verified-private-artifact"
    artifact = tmp_path / "orbitune-output.zip"
    artifact.write_bytes(payload)
    revision = "a" * 40
    run_id = "b" * 32
    settings = ProviderSettings(
        hf_artifact_write_token="hf-write",
        hf_artifact_repositories=("Unjuno/private-artifacts",),
    )
    api = SimpleNamespace(repo_info=lambda **_kwargs: SimpleNamespace(private=True, sha=revision))
    store = HuggingFaceArtifactStore(
        settings, api=api, downloader=lambda **_kwargs: str(artifact), max_bytes=1024)
    reference = {
        "service": "huggingface_hub", "repo_id": "Unjuno/private-artifacts",
        "repo_type": "model", "path_in_repo": f"runs/{run_id}/orbitune-output.zip",
        "revision": revision, "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload), "run_id": run_id, "source_sha": "c" * 40,
        "private": True,
    }

    chunk = store.read(reference, offset=9, max_bytes=7)

    assert chunk["artifact_id"] == "orbitune-output.zip"
    assert chunk["next_offset"] == 16
    assert chunk["eof"] is False
    assert chunk["sha256"] == reference["sha256"]
    assert chunk["full_file_verified"] is True
    assert chunk["verification_method"] == "exact_revision_size_and_sha256"
    broken = {**reference, "sha256": "d" * 64}
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        store.read(broken, offset=0, max_bytes=7)
