from __future__ import annotations

import ast
import base64
import io
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

from gpu_gateway.config import Workload
from gpu_gateway.orbitune_workload import (
    stage_orbitune_checkout, stage_orbitune_zero_gpu_space,
    staged_space_payload_digest,
)
from gpu_gateway.huggingface_space_backend import space_contract_digest


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
    (checkout / "orbitune" / "model.py").write_text("MODEL = 'test'\n", encoding="utf-8")
    (checkout / "orbitune" / "tokenizer").mkdir()
    (checkout / "orbitune" / "tokenizer" / "__init__.py").write_text("", encoding="utf-8")
    (checkout / "orbitune" / "tokenizer" / "vocab.py").write_text(
        "VOCAB = 'test'\n", encoding="utf-8")
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
        "source_revision": "c" * 40,
        "max_runtime_seconds": 60,
    })

    assert kaggle.provider_data_center_id is None
    assert space.provider_data_center_id is None


def test_deploy_registry_is_runnable_and_pins_live_private_resources():
    registry_path = Path(__file__).parents[1] / "deploy" / "workloads.json"
    registry = {
        name: Workload.model_validate(value)
        for name, value in json.loads(registry_path.read_text(encoding="utf-8")).items()
    }
    kaggle = registry["orbitune-kaggle-100-step-v1"]
    space = registry["orbitune-zero-gpu-eval-v1"]

    assert kaggle.provider_resource_id == "UnjunoOrg/orbitune-100-step"
    assert kaggle.image_digest == "sha256:3f764ee4d610edfbe6b07769538ffbae8413b9df47c05af783245d65c7c21bed"
    assert space.provider_resource_id == "Unjuno/gpu-control-orbitune-zero-gpu"
    assert space.source_revision == "2e9df7dcd8815cf3059ae94ce6504315e63a85ab"
    assert space.image_digest == space_contract_digest(
        space.provider_resource_id, space.source_revision,
    )


def test_stage_builder_copies_only_exact_clean_orbitune_package_and_registered_entrypoint(tmp_path):
    checkout, sha = fake_checkout(tmp_path)
    stage = tmp_path / "stage"

    provenance = stage_orbitune_checkout(checkout, stage, expected_sha=sha)

    assert provenance["source_repository"] == "Unjuno/orbitune"
    assert provenance["source_sha"] == sha
    assert (stage / "orbitune" / "__init__.py").is_file()
    assert (stage / "train.py").is_file()
    rendered = (stage / "train.py").read_text(encoding="utf-8")
    assert "__GPU_CONTROL_ORBITUNE_BUNDLE_B64__" not in rendered
    assert "__GPU_CONTROL_ORBITUNE_BUNDLE_SHA256__" not in rendered
    assert "_ORBITUNE_BUNDLE_B64" in rendered
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(rendered).body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"_ORBITUNE_BUNDLE_B64", "_ORBITUNE_BUNDLE_SHA256"}
    }
    bundle = base64.b64decode(assignments["_ORBITUNE_BUNDLE_B64"], validate=True)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        assert "orbitune/model.py" in archive.namelist()
        assert "orbitune/tokenizer/vocab.py" in archive.namelist()
        assert all(not name.startswith("/") and ".." not in Path(name).parts
                   for name in archive.namelist())
    assert not (stage / "README.md").exists()
    assert json.loads((stage / "gpu-control-provenance.json").read_text()) == provenance


def test_stage_builder_rejects_wrong_dirty_or_symlinked_checkout(tmp_path):
    checkout, sha = fake_checkout(tmp_path)
    with pytest.raises(ValueError, match="SHA"):
        stage_orbitune_checkout(checkout, tmp_path / "wrong", expected_sha="0" * 40)

    (checkout / "orbitune" / "dirty.py").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clean"):
        stage_orbitune_checkout(checkout, tmp_path / "dirty", expected_sha=sha)


def test_zero_gpu_space_stage_is_reviewable_deterministic_and_upload_ready(tmp_path):
    checkout, sha = fake_checkout(tmp_path)
    first = tmp_path / "space-a"
    second = tmp_path / "space-b"

    first_provenance = stage_orbitune_zero_gpu_space(checkout, first, expected_sha=sha)
    second_provenance = stage_orbitune_zero_gpu_space(checkout, second, expected_sha=sha)

    assert first_provenance == second_provenance
    assert first_provenance["source_sha"] == sha
    assert first_provenance["space_payload_digest"] == staged_space_payload_digest(first)
    assert (first / "orbitune" / "model.py").is_file()
    assert (first / "app.py").is_file()
    assert (first / "README.md").is_file()
    assert (first / "requirements.txt").is_file()
    assert not (first / ".git").exists()
    assert not (first / "gpu-control-provenance.json").exists()


def test_zero_gpu_space_stage_rejects_dirty_checkout_and_existing_target(tmp_path):
    checkout, sha = fake_checkout(tmp_path)
    target = tmp_path / "space"
    target.mkdir()
    with pytest.raises(ValueError, match="must not already exist"):
        stage_orbitune_zero_gpu_space(checkout, target, expected_sha=sha)

    (checkout / "orbitune" / "dirty.py").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clean"):
        stage_orbitune_zero_gpu_space(checkout, tmp_path / "dirty-space", expected_sha=sha)


def test_stage_builders_reject_symlinked_package_entries(tmp_path):
    checkout, _sha = fake_checkout(tmp_path)
    linked = checkout / "orbitune" / "linked.py"
    linked.symlink_to(checkout / "README.md")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "tracked symlink fixture")
    sha = _git(checkout, "rev-parse", "HEAD")

    for builder, name in (
        (stage_orbitune_checkout, "kaggle-symlink"),
        (stage_orbitune_zero_gpu_space, "space-symlink"),
    ):
        with pytest.raises(ValueError, match="symlink"):
            builder(checkout, tmp_path / name, expected_sha=sha)


def test_stage_builders_reject_ignored_untracked_package_files(tmp_path):
    checkout, _sha = fake_checkout(tmp_path)
    (checkout / ".gitignore").write_text("orbitune/ignored-secret.py\n", encoding="utf-8")
    _git(checkout, "add", ".gitignore")
    _git(checkout, "commit", "-qm", "ignore fixture")
    (checkout / "orbitune" / "ignored-secret.py").write_text("SECRET = 1\n", encoding="utf-8")
    sha = _git(checkout, "rev-parse", "HEAD")
    assert _git(checkout, "status", "--porcelain", "--untracked-files=all") == ""

    for builder, name in (
        (stage_orbitune_checkout, "kaggle-ignored"),
        (stage_orbitune_zero_gpu_space, "space-ignored"),
    ):
        with pytest.raises(ValueError, match="exactly tracked"):
            builder(checkout, tmp_path / name, expected_sha=sha)


def test_space_payload_digest_rejects_unhashed_root_content(tmp_path):
    checkout, sha = fake_checkout(tmp_path)
    target = tmp_path / "space"
    stage_orbitune_zero_gpu_space(checkout, target, expected_sha=sha)
    original = staged_space_payload_digest(target)

    (target / ".env").write_text("TOKEN=secret\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected root entries"):
        staged_space_payload_digest(target)
    assert original.startswith("sha256:")
