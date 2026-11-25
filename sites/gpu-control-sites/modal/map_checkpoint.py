"""Verify MAP checkpoint bytes in the provider's private run volume."""
import hashlib
import json
import os
import re
import stat
from pathlib import Path


MAX_CHECKPOINT_BYTES = 1024 * 1024 * 1024


def _open_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stream = os.fdopen(fd, "rb")
    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
        stream.close()
        raise ValueError("checkpoint_not_regular")
    return stream


def checkpoint_manifest(runs_dir: Path, run_id: str) -> dict:
    """Return a verified immutable reference without deserializing model data."""
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise ValueError("invalid_run_id")
    root = runs_dir.resolve(strict=True)
    run_dir = root / run_id
    if run_dir.resolve(strict=True) != run_dir:
        raise ValueError("invalid_run_directory")
    with _open_regular(run_dir / "latest.json") as pointer:
        raw = pointer.read(4097)
    if len(raw) > 4096:
        raise ValueError("checkpoint_pointer_too_large")
    record = json.loads(raw)
    if not isinstance(record, dict):
        raise ValueError("invalid_checkpoint_pointer")
    filename, expected = record.get("file"), record.get("sha256")
    if (not isinstance(filename, str) or not re.fullmatch(r"step-[0-9]{9}-[a-f0-9]{8}\.pt", filename)
            or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)):
        raise ValueError("invalid_checkpoint_pointer")
    digest = hashlib.sha256()
    total = 0
    with _open_regular(run_dir / filename) as checkpoint:
        for chunk in iter(lambda: checkpoint.read(1024 * 1024), b""):
            total += len(chunk)
            if total > MAX_CHECKPOINT_BYTES:
                raise ValueError("checkpoint_too_large")
            digest.update(chunk)
    if total == 0 or digest.hexdigest() != expected:
        raise ValueError("checkpoint_integrity_failed")
    return {"filename": filename, "sha256": expected, "size_bytes": total}
