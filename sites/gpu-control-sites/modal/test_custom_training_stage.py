import subprocess
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
        assert (Path(source) / "objects").is_dir()
        self.events.append(("source", destination))
    def put_file(self, source, destination):
        assert source.read() == b""
        self.events.append(("checkpoint", destination))


class Volume:
    def __init__(self, events):
        self.events = events
    def batch_upload(self):
        return Batch(self.events)


def test_verified_source_and_output_are_scoped_to_run(tmp_path):
    repo, sha = make_repo(tmp_path)
    events = []
    def fetch(repository, commit, target):
        assert repository == "owner/project" and commit == sha
        subprocess.run(["git", "clone", "--bare", str(repo), str(target)], check=True, capture_output=True)
    stage_to_volumes("owner/project", sha, "a" * 32, source_volume=Volume(events),
                     checkpoint_volume=Volume(events), fetch=fetch)
    assert events == [("source", "/" + "a" * 32), ("checkpoint", "/" + "a" * 32 + "/.gpu-control-run")]


def test_unavailable_commit_never_uploads(tmp_path):
    repo, _ = make_repo(tmp_path)
    events = []
    def fetch(_repository, _commit, target):
        subprocess.run(["git", "clone", "--bare", str(repo), str(target)], check=True, capture_output=True)
    with pytest.raises(ValueError, match="commit_unavailable"):
        stage_to_volumes("owner/project", "b" * 40, "a" * 32, source_volume=Volume(events),
                         checkpoint_volume=Volume(events), fetch=fetch)
    assert not events
