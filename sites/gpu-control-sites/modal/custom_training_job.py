"""Compose source staging and command execution inside an isolated worker.

The enclosing provider must enforce the job's container, network, GPU, storage,
runtime and credential boundaries. This module is not itself a sandbox.
"""
import hashlib
import os
import stat
import tempfile
from pathlib import Path

from custom_training_process import run_command
from custom_training_source import stage_commit


def checkpoint_manifest(checkpoint_dir, *, max_bytes=1024 * 1024 * 1024):
    """Inspect the designated checkpoint as data; never load or execute it."""
    path = Path(checkpoint_dir) / "checkpoint.pt"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= max_bytes:
            raise ValueError("invalid_checkpoint")
        digest = hashlib.sha256()
        total = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("invalid_checkpoint")
            digest.update(chunk)
        if total != info.st_size:
            raise ValueError("checkpoint_changed")
    return {"filename": "checkpoint.pt", "size_bytes": total, "sha256": digest.hexdigest()}


def run_custom_training(repository, commit, command, runtime_seconds, checkpoint_dir, *,
                        cancelled=lambda: False):
    """Execute a pinned source with a private, per-run checkpoint directory."""
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="gpu-control-source-") as temp:
        source = Path(temp) / "source"
        staged = stage_commit(repository, commit, source)
        result = run_command(command, source, runtime_seconds, cancelled=cancelled,
                             checkpoint_dir=checkpoint_dir)
    checkpoint = checkpoint_manifest(checkpoint_dir)
    return {**result, "source_sha": staged["commit"], "checkpoint": checkpoint}
