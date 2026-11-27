import json

from custom_training_stage import stage_to_mounts


def test_trusted_stage_writes_verified_binding_without_persisting_installation_token(tmp_path):
    source_root, checkpoint_root = tmp_path / "source", tmp_path / "checkpoints"
    source_root.mkdir()
    checkpoint_root.mkdir()
    seen = []

    def fetch(repository, commit, destination, *, source_token=None):
        seen.append((repository, commit, source_token))
        destination.mkdir()
        (destination / "objects").write_bytes(b"bare-git-store")

    def materialize(_objects, commit, destination):
        destination.mkdir()
        (destination / ".gpu-control").mkdir()
        (destination / ".gpu-control" / "experiment.json").write_text(json.dumps({
            "entrypoint": "train.py", "dependencies_lock": "requirements.lock", "python_version": "3.12"}))
        (destination / "requirements.lock").write_text("torch==2.0.0")
        (destination / "train.py").write_text("print('train')")
        return {"commit": commit}

    def download(lock_path, destination, *, python_version):
        assert python_version == "3.12"
        destination.mkdir()
        (destination / "torch.whl").write_bytes(b"locked wheel")
        return {"sha256": "d" * 64, "packages": 1, "bytes": 11}

    result = stage_to_mounts("owner/project", "b" * 40, "a" * 32,
        source_root=str(source_root), checkpoint_root=str(checkpoint_root),
        source_token="x" * 32, fetch=fetch, download=download, materialize=materialize)

    assert seen == [("owner/project", "b" * 40, "x" * 32)]
    assert result["commit"] == "b" * 40
    assert (source_root / ("a" * 32) / "objects").is_file()
    assert (source_root / ("a" * 32) / "wheelhouse" / "torch.whl").is_file()
    assert (source_root / ("a" * 32) / "wheelhouse").stat().st_mode & 0o777 == 0o555
    assert (source_root / ("a" * 32) / "wheelhouse" / "torch.whl").stat().st_mode & 0o777 == 0o444
    marker = json.loads((source_root / ("a" * 32) / ".gpu-control-stage.json").read_text())
    assert marker == result and "source_token" not in marker
    assert (checkpoint_root / ("a" * 32) / ".gpu-control-run").is_file()
