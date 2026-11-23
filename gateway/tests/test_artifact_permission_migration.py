"""Safety tests for the offline artifact permission migration utility."""
import importlib.util
import os
import stat
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "migrate_artifact_permissions.py"
SPEC = importlib.util.spec_from_file_location("migrate_artifact_permissions", SCRIPT)
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


def make_tree(root):
    scope = root / ("a" * 64)
    scope.mkdir(parents=True, mode=0o700)
    blob = scope / ("b" * 64 + ".blob")
    blob.write_bytes(b"artifact")
    blob.chmod(0o600)
    return scope, blob


def test_default_migration_is_a_dry_run_and_apply_sets_exact_modes(tmp_path):
    scope, blob = make_tree(tmp_path)
    result = migration.migrate(tmp_path, owner_uid=os.getuid(), artifact_gid=os.getgid(),
                              probe_gid=os.getgid(), apply=False)
    assert result["applied"] is False
    assert result["probe_directory_created"] is True
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert not (tmp_path / migration.PROBE_NAME).exists()

    result = migration.migrate(tmp_path, owner_uid=os.getuid(), artifact_gid=os.getgid(),
                              probe_gid=os.getgid(), apply=True)
    assert result["applied"] is True
    assert result["probe_directory_created"] is True
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o2750
    assert stat.S_IMODE(scope.stat().st_mode) == 0o2750
    assert stat.S_IMODE(blob.stat().st_mode) == 0o640
    probe = tmp_path / migration.PROBE_NAME
    assert probe.stat().st_uid == os.getuid()
    assert probe.stat().st_gid == os.getgid()
    assert stat.S_IMODE(probe.stat().st_mode) == 0o3770


@pytest.mark.parametrize("entry_kind", ["symlink", "hardlink", "nested", "special-root-entry", "unknown-file"])
def test_migration_rejects_unsafe_or_unexpected_entries(tmp_path, entry_kind):
    scope, blob = make_tree(tmp_path)
    if entry_kind == "symlink":
        (scope / "linked.blob").symlink_to(blob)
    elif entry_kind == "hardlink":
        os.link(blob, scope / "second.blob")
    elif entry_kind == "nested":
        (scope / "nested").mkdir()
    elif entry_kind == "unknown-file":
        (scope / "credentials.txt").write_text("must not become group-readable")
    else:
        (tmp_path / "unknown").write_text("unexpected")

    with pytest.raises(migration.MigrationError):
        migration.migrate(tmp_path, owner_uid=os.getuid(), artifact_gid=os.getgid(),
                           probe_gid=os.getgid(), apply=True)


def test_migration_refuses_to_rewrite_nonempty_probe_directory(tmp_path):
    make_tree(tmp_path)
    probe = tmp_path / migration.PROBE_NAME
    probe.mkdir()
    (probe / "unexpected").write_text("preserve")

    with pytest.raises(migration.MigrationError, match="probe directory is not empty"):
        migration.migrate(tmp_path, owner_uid=os.getuid(), artifact_gid=os.getgid(),
                           probe_gid=os.getgid(), apply=True)


def test_migration_rejects_symlink_artifact_root(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)

    with pytest.raises(migration.MigrationError, match="real directory"):
        migration.migrate(link, owner_uid=os.getuid(), artifact_gid=os.getgid(),
                           probe_gid=os.getgid(), apply=True)


def test_partial_apply_failure_preserves_payload_and_is_recoverable_on_rerun(
        tmp_path, monkeypatch):
    scope, blob = make_tree(tmp_path)
    original = os.chown
    failed = False

    def fail_once_at_blob(path, uid, gid, *, follow_symlinks=True):
        nonlocal failed
        if Path(path) == blob and not failed:
            failed = True
            raise PermissionError("injected ownership failure")
        return original(path, uid, gid, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(migration.os, "chown", fail_once_at_blob)
    with pytest.raises(PermissionError, match="injected ownership failure"):
        migration.migrate(tmp_path, owner_uid=os.getuid(), artifact_gid=os.getgid(),
                          probe_gid=os.getgid(), apply=True)

    assert blob.read_bytes() == b"artifact"
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o2750
    assert stat.S_IMODE(scope.stat().st_mode) == 0o2750

    monkeypatch.setattr(migration.os, "chown", original)
    result = migration.migrate(tmp_path, owner_uid=os.getuid(), artifact_gid=os.getgid(),
                               probe_gid=os.getgid(), apply=True)

    assert result["applied"] is True
    assert blob.read_bytes() == b"artifact"
    assert stat.S_IMODE(blob.stat().st_mode) == 0o640
    probe = tmp_path / migration.PROBE_NAME
    assert probe.is_dir()
    assert stat.S_IMODE(probe.stat().st_mode) == 0o3770
