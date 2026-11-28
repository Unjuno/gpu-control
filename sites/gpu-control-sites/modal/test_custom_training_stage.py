import subprocess
import hashlib
import json
from pathlib import Path

import pytest

from custom_training_stage import stage_to_volumes
from test_custom_training_source import make_repo


class Batch:
    def __init__(self, events):
        self.events = events
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def put_directory(self, source, destination):
        source = Path(source)
        assert source.is_dir()
        if list(source.glob("*.whl")):
            assert source.stat().st_mode & 0o777 == 0o555
            assert all(item.stat().st_mode & 0o777 == 0o444 for item in source.glob("*.whl"))
        self.events.append(("source" if (source / "objects").is_dir() else "wheelhouse", destination))
    def put_file(self, source, destination):
        assert source.read() == b""
        self.events.append(("checkpoint", destination))


class Volume:
    def __init__(self, events):
        self.events = events
    def batch_upload(self):
        return Batch(self.events)
    def commit(self):
        self.events.append(("commit",))


def test_verified_source_and_output_are_scoped_to_run(tmp_path):
    repo, sha = make_repo(tmp_path)
    (repo / ".gpu-control").mkdir()
    manifest = {"entrypoint": "train.py", "dependencies_lock": "requirements.lock", "python_version": "3.11"}
    (repo / ".gpu-control/experiment.json").write_text(json.dumps(manifest))
    (repo / "train.py").write_text("pass\n")
    (repo / "requirements.lock").write_text("torch==2.0.0\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "manifest"], check=True,
                   env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                        "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"})
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True).stdout.strip()
    events = []
    def fetch(repository, commit, target):
        assert repository == "owner/project" and commit == sha
        subprocess.run(["git", "clone", "--bare", str(repo), str(target)], check=True, capture_output=True)
    def download(_lock, destination, *, python_version):
        assert python_version == "3.11"
        destination.mkdir()
        (destination / "torch-2.0.0-py3-none-any.whl").write_bytes(b"wheel")
        return {"packages": 1, "bytes": 5, "sha256": "9" * 64}
    binding = stage_to_volumes("owner/project", sha, "a" * 32, source_volume=Volume(events),
                               checkpoint_volume=Volume(events), fetch=fetch, download=download)
    assert binding == {"commit": sha,
        "manifest_sha256": hashlib.sha256(json.dumps(manifest).encode()).hexdigest(),
        "lock_sha256": hashlib.sha256(b"torch==2.0.0\n").hexdigest(),
        "dependencies_lock": "requirements.lock", "entrypoint": "train.py",
        "wheelhouse_sha256": "9" * 64, "wheelhouse_packages": 1, "wheelhouse_bytes": 5}
    assert events == [("source", "/" + "a" * 32), ("wheelhouse", "/" + "a" * 32 + "/wheelhouse"),
                      ("checkpoint", "/" + "a" * 32 + "/.gpu-control-run"),
                      ("commit",), ("commit",)]


def test_unavailable_commit_never_uploads(tmp_path):
    repo, _ = make_repo(tmp_path)
    events = []
    def fetch(_repository, _commit, target):
        subprocess.run(["git", "clone", "--bare", str(repo), str(target)], check=True, capture_output=True)
    with pytest.raises(ValueError, match="commit_unavailable"):
        stage_to_volumes("owner/project", "b" * 40, "a" * 32, source_volume=Volume(events),
                         checkpoint_volume=Volume(events), fetch=fetch,
                         download=lambda *_: pytest.fail("must not download packages"))
    assert not events
