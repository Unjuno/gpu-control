"""Emit a journal-visible capacity status for a dedicated artifact filesystem."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import stat
import time

from capacity_event_state import (CapacityEventError, CapacityEventFileSource,
                                  MAX_CAPACITY_SOURCE_RECORDS,
                                  validate_capacity_event)


def inspect_capacity(root: str, minimum_free_bytes: int) -> dict:
    if type(minimum_free_bytes) is not int or minimum_free_bytes <= 0:
        return {"available": False, "reason": "invalid_minimum_free_bytes"}
    if not isinstance(root, str) or not root or not Path(root).is_absolute():
        return {"available": False, "reason": "invalid_artifact_path"}
    path = Path(root)
    try:
        if path.is_symlink():
            return {"available": False, "reason": "symlink"}
        if not path.is_dir():
            return {"available": False, "reason": "not_directory"}
        if path.stat().st_dev == path.parent.stat().st_dev:
            return {"available": False, "reason": "not_dedicated_filesystem"}
        values = os.statvfs(path)
        free_bytes = values.f_bavail * values.f_frsize
        return {"available": free_bytes >= minimum_free_bytes,
                "reason": None if free_bytes >= minimum_free_bytes else "below_minimum_free_bytes",
                "free_bytes": free_bytes,
                "minimum_free_bytes": minimum_free_bytes}
    except OSError:
        return {"available": False, "reason": "probe_failed"}


def record_capacity_event(path: str, event: dict) -> None:
    """Atomically append a bounded record to the capacity-only shared spool."""
    validate_capacity_event(event)
    selected = Path(path)
    if not selected.is_absolute():
        raise CapacityEventError("capacity_event_path_invalid")
    try:
        records = CapacityEventFileSource(selected)._records()
    except CapacityEventError as exc:
        if not isinstance(exc.__cause__, FileNotFoundError):
            raise
        records = []
    cursor = str(int(records[-1]["cursor"]) + 1 if records else 1)
    entry = {"cursor": cursor, "timestamp_us": time.time_ns() // 1000, "event": event}
    records = [*records, entry][-MAX_CAPACITY_SOURCE_RECORDS:]
    payload = json.dumps({"version": 1, "records": records}, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    temporary = selected.with_name(f".{selected.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(temporary, flags, 0o640)
        try:
            os.fchmod(fd, 0o640)
            with os.fdopen(fd, "wb", closefd=False) as output:
                output.write(payload)
                output.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, selected)
        directory_fd = os.open(selected.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        try:
            if temporary.exists() and stat.S_ISREG(temporary.lstat().st_mode):
                temporary.unlink()
        except OSError:
            pass
        raise CapacityEventError("capacity_event_write_failed") from exc


def main() -> int:
    root = os.environ.get("GATEWAY_ARTIFACT_DIR", "")
    raw_minimum = os.environ.get("GATEWAY_ARTIFACT_MIN_FREE_BYTES", "")
    event_path = os.environ.get("GATEWAY_CAPACITY_EVENTS_PATH", "")
    try:
        minimum = int(raw_minimum)
    except (TypeError, ValueError):
        minimum = 0
    result = inspect_capacity(root, minimum)
    # Emit a stable state on every timer run so a journal/metrics bridge can
    # both raise and clear an alert. Delivery still belongs to the host sink.
    event = {"check": "gpu-control-artifact-capacity",
             "status": "ok" if result["available"] else "alert", **result}
    try:
        if not event_path:
            raise CapacityEventError("capacity_event_path_unconfigured")
        record_capacity_event(event_path, event)
    except CapacityEventError:
        print("capacity_event_result=write_failed", flush=True)
        return 2
    print(json.dumps(event, sort_keys=True, separators=(",", ":")), flush=True)
    return 0 if result["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
