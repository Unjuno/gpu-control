from pathlib import Path

import pytest

from provider_runtime import Observation, ProviderSettings, bounded_text


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
