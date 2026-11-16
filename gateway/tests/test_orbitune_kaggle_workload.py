from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from gpu_gateway.config import Workload
from gpu_gateway.orbitune_workload import stage_orbitune_checkout


def _git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(directory), *args), check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def fake_checkout(tmp_path: Path) -> tuple[Path, str]:
    checkout = tmp_path / "orbitune"
    (checkout / "orbitune").mkdir(parents=True)
    (checkout / "orbitune" / "__init__.py").write_text("VERSION = 'test'\n", encoding="utf-8")
    (checkout / "README.md").write_text("not copied\n", encoding="utf-8")
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "test@example.invalid")
    _git(checkout, "config", "user.name", "Test")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "fixture")
    return checkout, _git(checkout, "rev-parse", "HEAD")


def test_kaggle_and_space_workloads_use_provider_specific_resource_identity():
    common = {
        "source_repository": "Unjuno/orbitune",
        "source_sha": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "runtime_requirements": ("cuda",),
    }
    kaggle = Workload.model_validate(common | {
        "provider": "kaggle",
        "provider_resource_id": "owner/orbitune-100-step",
        "gpu": "NvidiaTeslaT4",
    })
    space = Workload.model_validate(common | {
        "provider": "huggingface_space",
        "provider_resource_id": "owner/approved-zero-gpu",
        "max_runtime_seconds": 60,
    })

    assert kaggle.provider_data_center_id is None
    assert space.provider_data_center_id is None


def test_stage_builder_copies_only_exact_clean_orbitune_package_and_registered_entrypoint(tmp_path):
    checkout, sha = fake_checkout(tmp_path)
    stage = tmp_path / "stage"

    provenance = stage_orbitune_checkout(checkout, stage, expected_sha=sha)

    assert provenance["source_repository"] == "Unjuno/orbitune"
    assert provenance["source_sha"] == sha
    assert (stage / "orbitune" / "__init__.py").is_file()
    assert (stage / "train.py").is_file()
    assert not (stage / "README.md").exists()
    assert json.loads((stage / "gpu-control-provenance.json").read_text()) == provenance


def test_stage_builder_rejects_wrong_dirty_or_symlinked_checkout(tmp_path):
    checkout, sha = fake_checkout(tmp_path)
    with pytest.raises(ValueError, match="SHA"):
        stage_orbitune_checkout(checkout, tmp_path / "wrong", expected_sha="0" * 40)

    (checkout / "orbitune" / "dirty.py").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clean"):
        stage_orbitune_checkout(checkout, tmp_path / "dirty", expected_sha=sha)
