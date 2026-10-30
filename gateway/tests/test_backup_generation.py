import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
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
            assert "--exclude=.gpu-control-probes" in args
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
    monkeypatch.setattr(
        backup_generation, "_assert_gateway_systemd_units_stopped",
        lambda: {unit: "inactive" for unit in backup_generation.SYSTEMD_BACKUP_UNITS})


def test_backup_generation_publishes_db_artifacts_and_manifest_atomically(tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(mode=0o700)
    (artifacts / "blob").write_bytes(b"artifact-bytes")

    result = backup_generation.create_generation(
        str(output), str(artifacts), services_stopped_confirmed=True)

    assert result.parent == output
    assert result.is_dir()
    assert {path.name for path in result.iterdir()} == {
        "database.dump", "artifacts.tar", "manifest.json",
    }
    manifest = json.loads((result / "manifest.json").read_text())
    assert manifest["consistency"] == "quiesced"
    assert manifest["services_stopped_confirmed"] is True
    assert manifest["schema_version"] == "unversioned"
    assert manifest["database"]["sha256"] == hashlib.sha256(
        b"synthetic-pg-dump").hexdigest()
    assert manifest["artifacts"]["sha256"] == backup_generation._sha256(result / "artifacts.tar")
    assert not list(output.glob(".gpu-control-incomplete-*"))
    assert backup_generation.verify_generation(str(result))["generation_id"] == result.name.removeprefix("gpu-control-")


def test_real_tar_excludes_transient_artifact_probe_directory(tmp_path):
    tar = shutil.which("tar")
    if tar is None:
        pytest.skip("tar executable is unavailable")
    root = tmp_path / "artifacts"
    scope = root / ("a" * 64)
    probe = root / ".gpu-control-probes"
    scope.mkdir(parents=True)
    probe.mkdir()
    (scope / ("b" * 64 + ".blob")).write_bytes(b"persisted")
    (probe / ".gpu-control-write-probe-test").write_bytes(b"transient")
    archive = tmp_path / "artifacts.tar"

    subprocess.run([tar, "--create", "--file", str(archive),
                    "--exclude=.gpu-control-probes", "--directory", str(root), "."],
                   check=True, capture_output=True, text=True,
                   env={**os.environ, "COPYFILE_DISABLE": "1"})

    with tarfile.open(archive) as result:
        names = result.getnames()
    assert any(name.endswith("b" * 64 + ".blob") for name in names)
    assert not any(".gpu-control-probes" in name for name in names)


def test_artifact_archive_failure_does_not_publish_partial_generation(tmp_path, monkeypatch):
    fake_commands(monkeypatch, fail_prefix="tar")
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "blob").write_bytes(b"artifact")

    with pytest.raises(RuntimeError, match="injected tar failure"):
        backup_generation.create_generation(
            str(output), str(artifacts), services_stopped_confirmed=True)

    assert list(output.iterdir()) == []


@pytest.mark.parametrize("failed_command", ["pg_dump", "pg_restore"])
def test_database_backup_failure_does_not_publish_partial_generation(
        tmp_path, monkeypatch, failed_command):
    fake_commands(monkeypatch, fail_prefix=failed_command)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)

    with pytest.raises(RuntimeError, match=f"injected {failed_command} failure"):
        backup_generation.create_generation(
            str(output), services_stopped_confirmed=True)

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
        backup_generation.create_generation(str(output), services_stopped_confirmed=True)
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
        backup_generation.create_generation(str(output), services_stopped_confirmed=True)
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
        backup_generation.create_generation(str(output), services_stopped_confirmed=True)
    assert list(output.iterdir()) == []


def test_verify_generation_rejects_checksum_mismatch(tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    generation = backup_generation.create_generation(
        str(output), services_stopped_confirmed=True)
    (generation / "database.dump").write_bytes(b"corrupted")

    with pytest.raises(ValueError, match="database archive size or checksum"):
        backup_generation.verify_generation(str(generation))


def test_create_generation_requires_stopped_services_attestation(tmp_path):
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)

    with pytest.raises(ValueError, match="must confirm all Gateway services are stopped"):
        backup_generation.create_generation(str(output))

    assert list(output.iterdir()) == []


def test_backup_cli_requires_and_records_stopped_services_attestation(
        tmp_path, monkeypatch, capsys):
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    called = []

    def create_generation(output_dir, artifact_dir, *, services_stopped_confirmed):
        called.append((output_dir, artifact_dir, services_stopped_confirmed))
        return output / "gpu-control-test-generation"

    monkeypatch.setattr(backup_generation, "create_generation", create_generation)
    with pytest.raises(SystemExit) as missing_confirmation:
        backup_generation.main(["--output-dir", str(output)])
    assert missing_confirmation.value.code == 2
    assert called == []

    result = backup_generation.main([
        "--output-dir", str(output), "--confirm-services-stopped"])
    assert result == 0
    assert called == [(str(output), None, True)]
    assert capsys.readouterr().out.strip().endswith("gpu-control-test-generation")


def test_verify_generation_rejects_explicit_false_service_attestation(tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    generation = backup_generation.create_generation(
        str(output), services_stopped_confirmed=True)
    manifest_path = generation / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["services_stopped_confirmed"] = False
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="does not record stopped-service confirmation"):
        backup_generation.verify_generation(str(generation))


def test_backup_gate_checks_and_records_every_systemd_unit(monkeypatch):
    monkeypatch.setattr(backup_generation.shutil, "which", lambda _name: "/usr/bin/systemctl")
    calls = []

    def systemctl(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "loaded\ninactive\n", "")

    monkeypatch.setattr(backup_generation.subprocess, "run", systemctl)
    observations = backup_generation._assert_gateway_systemd_units_stopped()

    assert observations == {unit: "inactive" for unit in backup_generation.SYSTEMD_BACKUP_UNITS}
    assert len(calls) == len(backup_generation.SYSTEMD_BACKUP_UNITS) == 7
    assert all(call[-1] in backup_generation.SYSTEMD_BACKUP_UNITS for call in calls)


def test_backup_gate_fails_closed_when_any_unit_is_active(monkeypatch):
    monkeypatch.setattr(backup_generation.shutil, "which", lambda _name: "/usr/bin/systemctl")

    def systemctl(args, **kwargs):
        state = "active" if args[-1] == "gpu-control-worker.service" else "inactive"
        return subprocess.CompletedProcess(args, 0, f"loaded\n{state}\n", "")

    monkeypatch.setattr(backup_generation.subprocess, "run", systemctl)
    with pytest.raises(ValueError, match="must be loaded and inactive"):
        backup_generation._assert_gateway_systemd_units_stopped()


def test_backup_gate_fails_closed_when_systemctl_is_unavailable(monkeypatch):
    monkeypatch.setattr(backup_generation.shutil, "which", lambda _name: None)
    with pytest.raises(ValueError, match="systemctl is required"):
        backup_generation._assert_gateway_systemd_units_stopped()


def test_verify_generation_accepts_legacy_manifest_without_service_attestation(
        tmp_path, monkeypatch):
    fake_commands(monkeypatch)
    output = tmp_path / "backups"
    output.mkdir(mode=0o700)
    generation = backup_generation.create_generation(
        str(output), services_stopped_confirmed=True)
    manifest_path = generation / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("services_stopped_confirmed")
    manifest.pop("systemd_units")
    manifest_path.write_text(json.dumps(manifest))

    assert backup_generation.verify_generation(str(generation))["generation_id"] == \
        generation.name.removeprefix("gpu-control-")


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
