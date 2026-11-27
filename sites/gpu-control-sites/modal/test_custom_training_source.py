import os
import subprocess

import pytest

from custom_training_source import stage_commit


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    (repo / "train.py").write_text("old")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "first")
    return repo, git(repo, "rev-parse", "HEAD")


def test_stages_exact_commit_not_worktree(tmp_path):
    repo, sha = make_repo(tmp_path)
    (repo / "train.py").write_text("modified")
    result = stage_commit(repo, sha, tmp_path / "staged")
    assert result["commit"] == sha
    assert (tmp_path / "staged" / "train.py").read_text() == "old"
    assert not (tmp_path / "staged" / ".git").exists()


def test_rejects_missing_commit_and_limits(tmp_path):
    repo, sha = make_repo(tmp_path)
    with pytest.raises(ValueError, match="commit_unavailable"):
        stage_commit(repo, "a" * 40, tmp_path / "missing")
    assert not (tmp_path / "missing").exists()
    with pytest.raises(ValueError, match="source_limit_exceeded"):
        stage_commit(repo, sha, tmp_path / "small", max_bytes=1)


def test_rejects_symlinks(tmp_path):
    repo, _ = make_repo(tmp_path)
    os.symlink("/etc/passwd", repo / "link")
    git(repo, "add", "link")
    git(repo, "commit", "-m", "link")
    with pytest.raises(ValueError, match="unsafe_archive_entry"):
        stage_commit(repo, git(repo, "rev-parse", "HEAD"), tmp_path / "staged")
