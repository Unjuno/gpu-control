import hashlib
import json
import os
import sys

import pytest

import custom_training_job
from custom_training_job import checkpoint_manifest, metrics_manifest, run_custom_training
from test_custom_training_source import git, make_repo


def test_pinned_source_runs_and_returns_checkpoint_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(custom_training_job, "probe_gpu", lambda profile, **kwargs: {
        "name": "NVIDIA L4", "capability": [8, 9], "cuda": "12.8"})
    monkeypatch.setattr(custom_training_job, "install_locked_dependencies",
                        lambda *_args, **_kwargs: sys.executable)
    monkeypatch.setattr(custom_training_job, "gpu_activity_probe", lambda: True)
    repo, _ = make_repo(tmp_path)
    (repo / "train.py").write_text(
        "import os, pathlib\n"
        "(pathlib.Path(os.environ['GPU_CONTROL_CHECKPOINT_DIR']) / 'checkpoint.pt').write_bytes(b'weights')\n"
        "(pathlib.Path(os.environ['GPU_CONTROL_CHECKPOINT_DIR']) / 'metrics.json').write_text('{\\\"loss\\\":1.25,\\\"step\\\":10}')\n"
    )
    git(repo, "add", "train.py")
    (repo / ".gpu-control").mkdir()
    (repo / ".gpu-control" / "experiment.json").write_text(json.dumps({"entrypoint": "train.py"}))
    (repo / "requirements.lock").write_text("torch==2.0.0\n")
    git(repo, "add", ".gpu-control/experiment.json", "requirements.lock")
    git(repo, "commit", "-m", "training")
    sha = git(repo, "rev-parse", "HEAD")
    (repo / "train.py").write_text("raise Exception('dirty worktree')")
    result = run_custom_training(repo, sha, "train.py", 5, tmp_path / "checkpoints",
        expected_manifest_sha256=hashlib.sha256((repo / ".gpu-control/experiment.json").read_bytes()).hexdigest(),
        dependencies_lock="requirements.lock",
        expected_lock_sha256=hashlib.sha256((repo / "requirements.lock").read_bytes()).hexdigest(),
        run_id="a" * 32, gpu_profile="L4", drop_privileges=False)
    assert result["state"] == "succeeded" and result["source_sha"] == sha
    assert result["run_id"] == "a" * 32 and result["gpu_used"] is True
    assert result["checkpoint"] == {"filename": "checkpoint.pt", "size_bytes": 7,
                                    "sha256": hashlib.sha256(b"weights").hexdigest()}
    assert result["metrics"]["values"] == {"loss": 1.25, "step": 10}
    assert result["metrics"]["sha256"] == hashlib.sha256(b'{"loss":1.25,"step":10}').hexdigest()
    assert result["gpu"]["name"]


def test_checkpoint_symlink_is_not_followed(tmp_path):
    os.symlink("/etc/passwd", tmp_path / "checkpoint.pt")
    with pytest.raises(OSError):
        checkpoint_manifest(tmp_path)


def test_metrics_symlink_and_non_json_are_not_accepted(tmp_path):
    os.symlink("/etc/passwd", tmp_path / "metrics.json")
    with pytest.raises(OSError):
        metrics_manifest(tmp_path)
    (tmp_path / "metrics.json").unlink()
    (tmp_path / "metrics.json").write_text("[]")
    with pytest.raises(ValueError, match="invalid_metrics"):
        metrics_manifest(tmp_path)


@pytest.mark.parametrize("payload", ['{"loss":NaN}', '{"loss":1,"loss":2}', '{"../secret":1}'])
def test_metrics_reject_nonfinite_duplicate_or_unsafe_values(tmp_path, payload):
    (tmp_path / "metrics.json").write_text(payload)
    with pytest.raises(ValueError, match="invalid_metrics"):
        metrics_manifest(tmp_path)


def test_existing_checkpoint_directory_is_rejected(tmp_path):
    repo, sha = make_repo(tmp_path)
    with pytest.raises(FileExistsError):
        run_custom_training(repo, sha, "train.py", 5, tmp_path,
            expected_manifest_sha256="a" * 64, dependencies_lock="requirements.lock",
            expected_lock_sha256="b" * 64, run_id="a" * 32,
            gpu_profile="L4", drop_privileges=False)
