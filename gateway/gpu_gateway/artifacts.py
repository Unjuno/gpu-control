"""Bounded private artifact storage for completed experiment results."""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import stat
import time
from pathlib import Path
from collections.abc import Iterable

from .contracts import ArtifactMetadata

MAX_ARTIFACT_BYTES = 1 * 1024 * 1024
MAX_RUN_ARTIFACT_BYTES = 10 * 1024 * 1024
MAX_ARTIFACTS_PER_RUN = 10
ARTIFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def inspect_artifact_storage(root: str, minimum_free_bytes: int = 0) -> dict:
    """Report whether the configured artifact filesystem can accept writes."""
    if type(minimum_free_bytes) is not int or minimum_free_bytes < 0:
        return {"configured": bool(root), "available": False, "free_bytes": None,
                "reason": "invalid_minimum_free_bytes"}
    if not isinstance(root, str) or not root:
        return {"configured": False, "available": False, "free_bytes": None,
                "reason": "not_configured"}
    try:
        path = Path(root).expanduser()
        if path.is_symlink():
            return {"configured": True, "available": False, "free_bytes": None,
                    "reason": "symlink"}
        if not path.is_dir():
            return {"configured": True, "available": False, "free_bytes": None,
                    "reason": "not_directory"}
        if path.stat().st_dev == path.parent.stat().st_dev:
            return {"configured": True, "available": False, "free_bytes": None,
                    "minimum_free_bytes": minimum_free_bytes,
                    "reason": "not_dedicated_filesystem"}
        probe_path = path / ".gpu-control-probes"
        if probe_path.is_symlink() or not probe_path.is_dir():
            return {"configured": True, "available": False, "free_bytes": None,
                    "reason": "probe_directory_unavailable"}
        if probe_path.stat().st_dev != path.stat().st_dev:
            return {"configured": True, "available": False, "free_bytes": None,
                    "reason": "probe_directory_not_on_artifact_filesystem"}
        if not os.access(path, os.R_OK | os.X_OK):
            return {"configured": True, "available": False, "free_bytes": None,
                    "reason": "permissions"}
        if not os.access(probe_path, os.R_OK | os.W_OK | os.X_OK):
            return {"configured": True, "available": False, "free_bytes": None,
                    "reason": "probe_directory_permissions"}
        values = os.statvfs(path)
        free_bytes = values.f_bavail * values.f_frsize
        available = free_bytes > 0 and free_bytes >= minimum_free_bytes
        if not available:
            return {"configured": True, "available": False,
                    "free_bytes": free_bytes,
                    "minimum_free_bytes": minimum_free_bytes,
                    "reason": "no_free_space" if free_bytes == 0
                    else "below_minimum_free_bytes"}

        # os.access() can report writable for a read-only mount (and does not
        # exercise the service account's actual create/write path). Create an
        # exclusive file, unlink it immediately, then write and sync through
        # its open descriptor so a stopped process does not leave a probe blob.
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        directory_fd = os.open(probe_path, directory_flags)
        probe_name: str | None = ".gpu-control-write-probe-" + secrets.token_hex(16)
        probe_fd = None
        try:
            # A hard stop between create and unlink can leave an empty probe
            # file. Remove only old, empty files owned by this API account;
            # the directory's sticky bit protects probes from other users.
            cutoff = time.time() - 3600
            with os.scandir(probe_path) as entries:
                for entry in entries:
                    if not entry.name.startswith(".gpu-control-write-probe-"):
                        continue
                    try:
                        stale = os.stat(entry.name, dir_fd=directory_fd,
                                        follow_symlinks=False)
                        if (stat.S_ISREG(stale.st_mode) and stale.st_uid == os.geteuid()
                                and stale.st_size == 0 and stale.st_mtime < cutoff):
                            os.unlink(entry.name, dir_fd=directory_fd)
                    except FileNotFoundError:
                        continue
            probe_fd = os.open(probe_name,
                               os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                               0o600, dir_fd=directory_fd)
            os.unlink(probe_name, dir_fd=directory_fd)
            probe_name = None
            os.fsync(directory_fd)
            if os.write(probe_fd, b"\0") != 1:
                raise OSError("short artifact storage write probe")
            os.fsync(probe_fd)
            os.close(probe_fd)
            probe_fd = None
        except Exception:
            if probe_fd is not None:
                try:
                    os.close(probe_fd)
                except OSError:
                    pass
            if probe_name is not None:
                try:
                    os.unlink(probe_name, dir_fd=directory_fd)
                except OSError:
                    pass
            return {"configured": True, "available": False,
                    "free_bytes": free_bytes,
                    "minimum_free_bytes": minimum_free_bytes,
                    "reason": "write_probe_failed"}
        finally:
            os.close(directory_fd)
        return {"configured": True, "available": True,
                "free_bytes": free_bytes,
                "minimum_free_bytes": minimum_free_bytes,
                "reason": None}
    except Exception:
        return {"configured": True, "available": False, "free_bytes": None,
                "reason": "unavailable"}


class ArtifactStore:
    """Filesystem blob store; callers must establish run ownership in the DB."""

    def __init__(self, root: str):
        self.root = Path(root).expanduser().absolute()

    @staticmethod
    def _scope(owner: str, run_id: str) -> str:
        return hashlib.sha256((owner + "\0" + run_id).encode()).hexdigest()

    def _directory(self, owner: str, run_id: str, *, create: bool) -> Path:
        directory = self.root / self._scope(owner, run_id)
        if create:
            self.root.mkdir(mode=0o2750, parents=True, exist_ok=True)
            directory.mkdir(mode=0o2750, exist_ok=True)
        if self.root.is_symlink() or directory.is_symlink():
            raise ValueError("artifact storage path must not contain symlinks")
        if create:
            os.chmod(self.root, 0o2750)
            os.chmod(directory, 0o2750)
        return directory

    def put(self, owner: str, run_id: str, artifact_id: str, data: bytes, *,
            media_type: str, expires_at: int | None) -> dict:
        if (not isinstance(owner, str) or not owner or not isinstance(run_id, str) or
                not re.fullmatch(r"[0-9a-f]{32}", run_id) or
                not isinstance(artifact_id, str) or not ARTIFACT_ID.fullmatch(artifact_id)):
            raise ValueError("invalid artifact identity")
        if not isinstance(data, bytes) or len(data) > MAX_ARTIFACT_BYTES:
            raise ValueError("artifact exceeds per-object size limit")
        if (not isinstance(media_type, str) or not re.fullmatch(r"[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+", media_type)
                or len(media_type) > 128):
            raise ValueError("invalid artifact media type")
        directory = self._directory(owner, run_id, create=True)
        if len(list(directory.iterdir())) >= MAX_ARTIFACTS_PER_RUN:
            raise ValueError("artifact count limit exceeded")
        destination = directory / (hashlib.sha256(artifact_id.encode()).hexdigest() + ".blob")
        temporary = directory / ("." + secrets.token_hex(16) + ".tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
                # The API account has read-only membership in the artifact
                # group. Publish group-readable bytes only after the complete
                # temporary file has been written and synced.
                os.fchmod(output.fileno(), 0o640)
                os.fsync(output.fileno())
            try:
                os.link(temporary, destination, follow_symlinks=False)
            except FileExistsError:
                existing_fd = os.open(destination, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                try:
                    existing_stat = os.fstat(existing_fd)
                    existing = os.pread(existing_fd, min(existing_stat.st_size + 1,
                                                         MAX_ARTIFACT_BYTES + 1), 0)
                finally:
                    os.close(existing_fd)
                if not stat.S_ISREG(existing_stat.st_mode) or existing != data:
                    raise ValueError("artifact ID already refers to different content")
            directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return ArtifactMetadata(artifact_id=artifact_id, sha256=hashlib.sha256(data).hexdigest(),
                                size_bytes=len(data), media_type=media_type,
                                expires_at=expires_at).model_dump(mode="json")

    def get(self, owner: str, run_id: str, artifact_id: str, *, offset: int,
            length: int, expected_sha256: str, expected_size: int) -> bytes:
        if (not ARTIFACT_ID.fullmatch(artifact_id) or type(offset) is not int or offset < 0 or
                type(length) is not int or not 1 <= length <= 24 * 1024 or
                not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or
                type(expected_size) is not int or not 0 <= expected_size <= MAX_ARTIFACT_BYTES):
            raise ValueError("invalid artifact range")
        directory = self._directory(owner, run_id, create=False)
        path = directory / (hashlib.sha256(artifact_id.encode()).hexdigest() + ".blob")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size != expected_size or info.st_size > MAX_ARTIFACT_BYTES:
                raise ValueError("artifact size does not match its manifest")
            if offset > info.st_size:
                raise ValueError("artifact offset exceeds object size")
            data = os.pread(fd, info.st_size, 0)
            if hashlib.sha256(data).hexdigest() != expected_sha256:
                raise ValueError("artifact digest does not match its manifest")
            return data[offset:offset + length]
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

    def prune(self, rows: Iterable[dict], *, now: int,
              orphan_grace_seconds: int = 24 * 3600) -> dict:
        """Remove expired blobs and old unmanifested files without touching active runs."""
        if type(now) is not int or type(orphan_grace_seconds) is not int or orphan_grace_seconds < 3600:
            raise ValueError("invalid artifact pruning clock or grace period")
        if not self.root.exists():
            return {"expired_files": 0, "orphan_files": 0, "bytes_removed": 0}
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("artifact root must be a real directory")

        active_scopes: set[str] = set()
        manifests: dict[str, dict[str, int | None]] = {}
        for row in rows:
            owner, run_id = row.get("owner"), row.get("id")
            if not isinstance(owner, str) or not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
                continue
            scope = self._scope(owner, run_id)
            if row.get("state") not in {"succeeded", "failed", "cancelled", "expired"}:
                active_scopes.add(scope)
            result = row.get("result")
            items = result.get("artifacts", []) if isinstance(result, dict) else []
            if not isinstance(items, list):
                continue
            values = manifests.setdefault(scope, {})
            for item in items:
                if not isinstance(item, dict):
                    continue
                artifact_id, expiry = item.get("artifact_id"), item.get("expires_at")
                if (isinstance(artifact_id, str) and ARTIFACT_ID.fullmatch(artifact_id) and
                        (expiry is None or type(expiry) is int)):
                    values[hashlib.sha256(artifact_id.encode()).hexdigest() + ".blob"] = expiry

        removed_expired = removed_orphan = removed_bytes = 0
        cutoff = now - orphan_grace_seconds
        for scope_entry in os.scandir(self.root):
            if not scope_entry.is_dir(follow_symlinks=False) or not re.fullmatch(r"[0-9a-f]{64}", scope_entry.name):
                continue
            scope = scope_entry.name
            known = manifests.get(scope, {})
            for file_entry in os.scandir(scope_entry.path):
                try:
                    file_stat = file_entry.stat(follow_symlinks=False)
                    if not stat.S_ISREG(file_stat.st_mode):
                        continue
                    if scope in active_scopes:
                        continue
                    if file_entry.name in known:
                        expiry = known[file_entry.name]
                        if expiry is None or expiry > now:
                            continue
                        expired = True
                    elif file_stat.st_mtime <= cutoff:
                        expired = False
                    else:
                        continue
                    os.unlink(file_entry.path)
                    removed_bytes += file_stat.st_size
                    if expired:
                        removed_expired += 1
                    else:
                        removed_orphan += 1
                except FileNotFoundError:
                    continue
            try:
                os.rmdir(scope_entry.path)
            except OSError:
                pass
        return {"expired_files": removed_expired, "orphan_files": removed_orphan,
                "bytes_removed": removed_bytes}
