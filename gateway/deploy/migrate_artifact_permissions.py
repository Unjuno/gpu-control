#!/usr/bin/env python3
"""Safely migrate an existing artifact tree to the systemd service-group layout.

Default behavior is a read-only audit. Pass --apply only after stopping every
Gateway service that can access the artifact filesystem.
"""
from __future__ import annotations

import argparse
import grp
import os
import pwd
import re
import stat
import sys
from pathlib import Path

SCOPE_NAME = re.compile(r"^[0-9a-f]{64}$")
BLOB_NAME = re.compile(r"^[0-9a-f]{64}\.blob$")
PROBE_NAME = ".gpu-control-probes"


class MigrationError(ValueError):
    pass


def _lstat(path: Path) -> os.stat_result:
    try:
        return path.lstat()
    except OSError as exc:
        raise MigrationError(f"cannot inspect {path}: {exc}") from exc


def inspect_tree(root: Path) -> tuple[list[Path], list[Path], Path | None]:
    """Return scope dirs and files after rejecting links and special objects."""
    root_info = _lstat(root)
    if not stat.S_ISDIR(root_info.st_mode):
        raise MigrationError("artifact root must be a real directory, not a symlink")

    scopes: list[Path] = []
    files: list[Path] = []
    probe: Path | None = None
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        raise MigrationError(f"cannot scan artifact root: {exc}") from exc

    for entry in entries:
        path = root / entry.name
        info = _lstat(path)
        if entry.name == PROBE_NAME:
            if not stat.S_ISDIR(info.st_mode):
                raise MigrationError("probe path exists but is not a real directory")
            probe = path
            try:
                probe_entries = list(os.scandir(path))
            except OSError as exc:
                raise MigrationError(f"cannot scan probe directory: {exc}") from exc
            if probe_entries:
                raise MigrationError(
                    "probe directory is not empty; inspect and remove stale probes after stopping services"
                )
            continue
        if not SCOPE_NAME.fullmatch(entry.name) or not stat.S_ISDIR(info.st_mode):
            raise MigrationError(f"unexpected artifact-root entry: {entry.name!r}")
        scopes.append(path)
        try:
            children = list(os.scandir(path))
        except OSError as exc:
            raise MigrationError(f"cannot scan run-scope directory {entry.name}: {exc}") from exc
        for child in children:
            child_path = path / child.name
            child_info = _lstat(child_path)
            if not stat.S_ISREG(child_info.st_mode):
                raise MigrationError(f"link, nested directory, or special file found: {child_path}")
            if child_info.st_nlink != 1:
                raise MigrationError(f"hard-linked file found: {child_path}")
            if not BLOB_NAME.fullmatch(child.name):
                raise MigrationError(f"unexpected run-scope file name: {child_path}")
            files.append(child_path)
    return scopes, files, probe


def migrate(root: Path, *, owner_uid: int, artifact_gid: int, probe_gid: int,
            apply: bool) -> dict[str, int | bool]:
    """Audit or apply ownership/modes; never follows links or deletes payloads."""
    root = Path(os.path.abspath(root))
    scopes, files, probe = inspect_tree(root)
    probe_created = probe is None
    changes = len(scopes) + len(files) + 1 + (probe is None)
    if apply:
        # Recheck each object immediately before changing it. The operator must
        # keep the services stopped so no process can mutate this tree in-flight.
        for directory in [root, *scopes]:
            info = _lstat(directory)
            if not stat.S_ISDIR(info.st_mode):
                raise MigrationError(f"directory changed during migration: {directory}")
            os.chown(directory, owner_uid, artifact_gid, follow_symlinks=False)
            os.chmod(directory, 0o2750, follow_symlinks=False)
        for path in files:
            info = _lstat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise MigrationError(f"file changed during migration: {path}")
            os.chown(path, owner_uid, artifact_gid, follow_symlinks=False)
            os.chmod(path, 0o640, follow_symlinks=False)
        if probe is None:
            probe = root / PROBE_NAME
            os.mkdir(probe, 0o3770)
        info = _lstat(probe)
        if not stat.S_ISDIR(info.st_mode):
            raise MigrationError("probe directory changed during migration")
        os.chown(probe, owner_uid, probe_gid, follow_symlinks=False)
        os.chmod(probe, 0o3770, follow_symlinks=False)

        # Verify the resulting contract before reporting success.
        expected = [(root, owner_uid, artifact_gid, 0o2750)]
        expected.extend((path, owner_uid, artifact_gid, 0o2750) for path in scopes)
        expected.extend((path, owner_uid, artifact_gid, 0o640) for path in files)
        expected.append((probe, owner_uid, probe_gid, 0o3770))
        for path, uid, gid, mode in expected:
            info = _lstat(path)
            if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (uid, gid, mode):
                raise MigrationError(f"post-migration ownership/mode mismatch: {path}")
    return {"applied": apply, "scope_directories": len(scopes),
            "artifact_files": len(files), "probe_directory_created": probe_created,
            "objects_updated": changes if apply else 0,
            "objects_to_update": changes if not apply else 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--worker-user", default="gpu-control-worker")
    parser.add_argument("--artifact-group", default="gpu-control-artifacts")
    parser.add_argument("--probe-group", default="gpu-control-artifact-probes")
    parser.add_argument("--apply", action="store_true",
                        help="change ownership and modes (requires stopped services and root)")
    args = parser.parse_args(argv)
    try:
        if args.apply and os.geteuid() != 0:
            raise MigrationError("--apply must run as root")
        worker = pwd.getpwnam(args.worker_user)
        artifact_group = grp.getgrnam(args.artifact_group)
        probe_group = grp.getgrnam(args.probe_group)
        result = migrate(args.artifact_root, owner_uid=worker.pw_uid,
                         artifact_gid=artifact_group.gr_gid,
                         probe_gid=probe_group.gr_gid, apply=args.apply)
    except (KeyError, OSError, MigrationError) as exc:
        print(f"artifact permission migration failed: {exc}", file=sys.stderr)
        return 2
    verb = "Applied" if args.apply else "Dry run"
    print(f"{verb}: {result['scope_directories']} scope directories, "
          f"{result['artifact_files']} files; probe directory "
          f"{'created' if result['probe_directory_created'] and args.apply else 'ready' if not result['probe_directory_created'] else 'would be created'}.")
    if not args.apply:
        print("No changes made. Stop API, worker, supervisor, and capacity services before rerunning with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
