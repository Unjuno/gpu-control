import hashlib
import os
import sys

import pytest

from custom_training_job import checkpoint_manifest, run_custom_training
from test_custom_training_source import git, make_repo


def test_pinned_source_runs_and_returns_checkpoint_manifest(tmp_path):
    repo, _ = make_repo(tmp_path)
    (repo / "train.py").write_text(
        "import os, pathlib\n"
        "(pathlib.Path(os.environ['GPU_CONTROL_CHECKPOINT_DIR']) / 'checkpoint.pt').write_bytes(b'weights')\n"
    )
    git(repo, "add", "train.py")
    git(repo, "commit", "-m", "training")
    sha = git(repo, "rev-parse", "HEAD")
    (repo / "train.py").write_text("raise Exception('dirty worktree')")
    result = run_custom_training(repo, sha, [sys.executable, "train.py"], 5, tmp_path / "checkpoints")
    assert result["state"] == "succeeded" and result["source_sha"] == sha
    assert result["checkpoint"] == {"filename": "checkpoint.pt", "size_bytes": 7,
                                    "sha256": hashlib.sha256(b"weights").hexdigest()}


def test_checkpoint_symlink_is_not_followed(tmp_path):
    os.symlink("/etc/passwd", tmp_path / "checkpoint.pt")
    with pytest.raises(OSError):
        checkpoint_manifest(tmp_path)


def test_existing_checkpoint_directory_is_rejected(tmp_path):
    repo, sha = make_repo(tmp_path)
    with pytest.raises(FileExistsError):
        run_custom_training(repo, sha, [sys.executable, "train.py"], 5, tmp_path)
