import subprocess

import pytest

from custom_training_fetch import fetch_public_commit
from custom_training_source import stage_commit
from test_custom_training_source import make_repo


def test_fetch_pins_expected_github_url_and_commit(tmp_path):
    repo, sha = make_repo(tmp_path)
    calls = []
    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if "fetch" in args:
            index = args.index("--")
            assert args[index + 1:] == ["https://github.com/owner/project.git", sha]
            # Exercise the real fetch using a local fixture only in this test.
            args = list(args)
            args[args.index("protocol.file.allow=never")] = "protocol.file.allow=always"
            args[args.index("--") + 1] = str(repo)
            kwargs["env"] = {**kwargs["env"], "GIT_ALLOW_PROTOCOL": "file"}
        return subprocess.run(args, **kwargs)
    result = fetch_public_commit("owner/project", sha, tmp_path / "objects", _run=fake_run)
    assert result["commit"] == sha
    stage_commit(result["store"], sha, tmp_path / "staged")
    assert (tmp_path / "staged" / "train.py").read_text() == "old"
    assert all(call[1]["env"]["GIT_TERMINAL_PROMPT"] == "0" for call in calls)


@pytest.mark.parametrize("repo", ["https://evil.test/x", "../x", "owner/..", "owner/x?y"])
def test_rejects_non_github_source(tmp_path, repo):
    with pytest.raises(ValueError, match="invalid_source"):
        fetch_public_commit(repo, "a" * 40, tmp_path / "objects")


def test_fetch_failure_removes_partial_store(tmp_path):
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 1)
    with pytest.raises(subprocess.TimeoutExpired):
        fetch_public_commit("owner/project", "a" * 40, tmp_path / "objects", _run=fail)
    assert not (tmp_path / "objects").exists()
