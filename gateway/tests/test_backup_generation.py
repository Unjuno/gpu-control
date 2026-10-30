import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))
import backup_generation


def quiescent_sql(query: str) -> str:
    if "state NOT IN" in query:
        return "0"
    if "COALESCE((SELECT active_count" in query:
        return "0"
    if "information_schema.columns" in query:
        return "0"
    if "json_typeof(result->'artifacts')" in query:
        return "0"
    if "to_regclass" in query:
        return ""
    if "SELECT count(*) FROM gateway_runs_v1" in query:
        return "0"
    raise AssertionError(f"unexpected query: {query}")


def fake_commands(monkeypatch, *, fail_prefix: str | None = None):
    def run(args: list[str], *, capture: bool = False, env: dict[str, str] | None = None) -> str:
        if args[0] == "tar" and "--create" in args:
            assert env == {"COPYFILE_DISABLE": "1"}
        if fail_prefix and args[0] == fail_prefix:
            raise RuntimeError(f"injected {fail_prefix} failure")
        if args[0] == "pg_dump":
            target = Path(next(arg.removeprefix("--file=") for arg in args if arg.startswith("--file=")))
            target.write_bytes(b"synthetic-pg-dump")
        elif args[0] == "tar" and "--create" in args:
            target = Path(args[args.index("--file") + 1])
            scope = "a" * 64
            with tarfile.open(target, "w") as archive:
                directory = tarfile.TarInfo("./" + scope)
                directory.type = tarfile.DIRTYPE
                archive.addfile(directory)
                blob = tarfile.TarInfo("./" + scope + "/" + "b" * 64 + ".blob")
                blob.size = 1
                archive.addfile(blob, io.BytesIO(b"x"))
        return ""

    monkeypatch.setattr(backup_generation, "_sql", quiescent_sql)
    monkeypatch.setattr(backup_generation, "_run", run)


def test_backup_generation_publishes_db_artifacts_and_manifest_atomically(tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(mode=0o700)
    (artifacts / "blob").write_bytes(b"artifact-bytes")

    result = backup_generation.create_generation(str(output), str(artifacts))

    assert result.parent == output
    assert result.is_dir()
    assert {path.name for path in result.iterdir()} == {
        "database.dump", "artifacts.tar", "manifest.json",
    }
    manifest = json.loads((result / "manifest.json").read_text())
    assert manifest["consistency"] == "quiesced"
    assert manifest["schema_version"] == "unversioned"
    assert manifest["database"]["sha256"] == hashlib.sha256(
        b"synthetic-pg-dump").hexdigest()
    assert manifest["artifacts"]["sha256"] == backup_generation._sha256(result / "artifacts.tar")
    assert not list(output.glob(".gpu-control-incomplete-*"))
    assert backup_generation.verify_generation(str(result))["generation_id"] == result.name.removeprefix("gpu-control-")


def test_artifact_archive_failure_does_not_publish_partial_generation(tmp_path, monkeypatch):
    fake_commands(monkeypatch, fail_prefix="tar")
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "blob").write_bytes(b"artifact")

    with pytest.raises(RuntimeError, match="injected tar failure"):
        backup_generation.create_generation(str(output), str(artifacts))

    assert list(output.iterdir()) == []


def test_database_artifact_manifests_require_artifact_volume(tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    original_sql = backup_generation._sql

    def sql_with_artifacts(query: str) -> str:
        if "json_typeof(result->'artifacts')" in query:
            return "1"
        return original_sql(query)

    monkeypatch.setattr(backup_generation, "_sql", sql_with_artifacts)
    with pytest.raises(ValueError, match="artifact manifests but --artifact-dir was omitted"):
        backup_generation.create_generation(str(output))
    assert list(output.iterdir()) == []


def test_nonquiescent_database_is_refused_before_backup_commands(tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)

    def nonquiescent(query: str) -> str:
        if "state NOT IN" in query:
            return "1"
        return quiescent_sql(query)

    monkeypatch.setattr(backup_generation, "_sql", nonquiescent)
    with pytest.raises(ValueError, match="database is not quiescent"):
        backup_generation.create_generation(str(output))
    assert list(output.iterdir()) == []


def test_cleanup_unknown_v6_run_blocks_backup(tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)

    def unsettled_cleanup(query: str) -> str:
        if "information_schema.columns" in query:
            return "2"
        if "cleanup_state NOT IN" in query:
            return "1"
        return quiescent_sql(query)

    monkeypatch.setattr(backup_generation, "_sql", unsettled_cleanup)
    with pytest.raises(ValueError, match="without cleanup proof"):
        backup_generation.create_generation(str(output))
    assert list(output.iterdir()) == []


def test_verify_generation_rejects_checksum_mismatch(tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    generation = backup_generation.create_generation(str(output))
    (generation / "database.dump").write_bytes(b"corrupted")

    with pytest.raises(ValueError, match="database archive size or checksum"):
        backup_generation.verify_generation(str(generation))


@pytest.mark.parametrize("member_name", ["../outside", "/absolute/path", "scope/nested/escape"])
def test_artifact_archive_rejects_unsafe_member_paths(tmp_path, member_name):
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as target:
        entry = tarfile.TarInfo(member_name)
        entry.size = 1
        target.addfile(entry, io.BytesIO(b"x"))

    with pytest.raises(ValueError, match="unsafe artifact archive member"):
        backup_generation._validate_artifact_archive(archive)


@pytest.mark.parametrize("member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_artifact_archive_rejects_non_regular_members(tmp_path, member_type):
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as target:
        entry = tarfile.TarInfo("./" + "a" * 64 + "/" + "b" * 64 + ".blob")
        entry.type = member_type
        entry.linkname = "../../outside"
        target.addfile(entry)

    with pytest.raises(ValueError, match="unsafe artifact archive member"):
        backup_generation._validate_artifact_archive(archive)
