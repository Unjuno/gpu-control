"""Compose source staging and command execution inside an isolated worker.

The enclosing provider must enforce the job's container, network, GPU, storage,
runtime and credential boundaries. This module is not itself a sandbox.
"""
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
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


def metrics_manifest(output_dir, *, max_bytes=8 * 1024):
    """Read a small JSON metrics object as data; never execute or trust it."""
    path = Path(output_dir) / "metrics.json"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= max_bytes:
            raise ValueError("invalid_metrics")
        raw = stream.read(max_bytes + 1)
        if len(raw) != info.st_size or len(raw) > max_bytes:
            raise ValueError("metrics_changed")
    try:
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate_metrics_key")
                value[key] = item
            return value
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid_metrics") from exc
    if (not isinstance(value, dict) or not 1 <= len(value) <= 64 or
            any(not isinstance(key, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", key) is None
                or not (type(item) in {int, float, bool} or
                        isinstance(item, str) and len(item.encode("utf-8")) <= 256)
                or type(item) is float and not math.isfinite(item)
                for key, item in value.items())):
        raise ValueError("invalid_metrics")
    return {"filename": "metrics.json", "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "values": value}


def probe_gpu(gpu_profile, *, python=None, drop_privileges=True):
    """Probe the assigned CUDA device from trusted wrapper code."""
    if gpu_profile not in {"T4", "L4"}:
        raise ValueError("invalid_gpu_profile")
    probe = (
        "import json, torch; "
        "ok=torch.cuda.is_available(); "
        "p=torch.cuda.get_device_properties(0) if ok else None; "
        "print(json.dumps({'available':ok,'name':p.name if p else None,"
        "'capability':[p.major,p.minor] if p else None,"
        "'cuda':torch.version.cuda if ok else None}))"
    )
    privilege = {"user": 10001, "group": 10001, "extra_groups": ()} if drop_privileges else {}
    result = subprocess.run([python or sys.executable, "-c", probe], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/dev/null"},
                            timeout=15, check=True, **privilege)
    try:
        value = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("gpu_probe_invalid") from exc
    name = value.get("name")
    if (value.get("available") is not True or not isinstance(name, str) or
            gpu_profile.lower() not in name.lower() or
            not isinstance(value.get("capability"), list) or len(value["capability"]) != 2):
        raise ValueError("gpu_profile_not_available")
    return {"name": name, "capability": value["capability"], "cuda": value.get("cuda")}


def install_locked_dependencies(source, lock_relative_path, wheelhouse, runtime_dir, *, drop_privileges=True):
    """Install a complete hashed wheel lock offline in an isolated venv."""
    source = Path(source).resolve(strict=True)
    lock = source / lock_relative_path
    if (Path(lock_relative_path).is_absolute() or ".." in Path(lock_relative_path).parts or
            lock.is_symlink() or not lock.resolve(strict=True).is_relative_to(source) or not lock.is_file()):
        raise ValueError("invalid_dependency_lock")
    wheelhouse = Path(wheelhouse).resolve(strict=True)
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise ValueError("invalid_wheelhouse")
    wheels = list(wheelhouse.iterdir())
    if not wheels or any(item.is_symlink() or not item.is_file() or item.suffix != ".whl" for item in wheels):
        raise ValueError("invalid_wheelhouse")
    runtime_dir = Path(runtime_dir)
    subprocess.run([sys.executable, "-m", "venv", str(runtime_dir)], stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45, check=True)
    if drop_privileges:
        if os.name != "posix" or os.geteuid() != 0:
            raise ValueError("cannot_drop_workload_privileges")
        for item in runtime_dir.rglob("*"):
            if item.is_symlink():
                continue
            os.chown(item, 10001, 10001)
            if item.is_dir():
                item.chmod(0o755)
        os.chown(runtime_dir, 10001, 10001)
        runtime_dir.chmod(0o755)
    python = runtime_dir / "bin" / "python"
    env = {"PATH": f"{runtime_dir}/bin:/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
           "TMPDIR": "/tmp", "PIP_CONFIG_FILE": "/dev/null", "PIP_NO_INPUT": "1",
           "PIP_NO_INDEX": "1", "PIP_NO_CACHE_DIR": "1", "PYTHONNOUSERSITE": "1",
           "PYTHONUNBUFFERED": "1", "LC_ALL": "C"}
    privilege = {"user": 10001, "group": 10001, "extra_groups": ()} if drop_privileges else {}
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-index", "--no-cache-dir", "--require-hashes",
                    "--find-links", str(wheelhouse), "-r", str(lock)],
                   cwd=str(source), env=env, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=90, check=True, **privilege)
    return python


def gpu_activity_probe():
    """Observe nonzero GPU utilization using a fixed trusted executable."""
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return False
    try:
        result = subprocess.run([executable, "--query-gpu=utilization.gpu",
                                 "--format=csv,noheader,nounits"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=2, check=True)
        return any(int(line.strip()) > 0 for line in result.stdout.decode("ascii").splitlines()
                   if line.strip().isdigit())
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError, ValueError):
        return False


def run_custom_training(repository, commit, entrypoint, runtime_seconds, checkpoint_dir, *,
                        expected_manifest_sha256, dependencies_lock, expected_lock_sha256,
                        run_id, gpu_profile, wheelhouse="/source-store/wheelhouse",
                        cancelled=lambda: False, drop_privileges=True):
    """Execute a pinned source with a private, per-run checkpoint directory."""
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise ValueError("invalid_run_id")
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    if drop_privileges:
        if os.name != "posix" or os.geteuid() != 0:
            raise ValueError("cannot_drop_workload_privileges")
        os.chown(checkpoint_dir, 10001, 10001)
        checkpoint_dir.chmod(0o700)
    with tempfile.TemporaryDirectory(prefix="gpu-control-source-") as temp:
        if drop_privileges:
            os.chmod(temp, 0o755)
        source = Path(temp) / "source"
        staged = stage_commit(repository, commit, source)
        if not isinstance(entrypoint, str) or Path(entrypoint).is_absolute() or ".." in Path(entrypoint).parts:
            raise ValueError("invalid_entrypoint")
        target = source / entrypoint
        if target.is_symlink() or not target.resolve(strict=True).is_relative_to(source.resolve()) or not target.is_file() or target.suffix != ".py":
            raise ValueError("invalid_entrypoint")
        if (not isinstance(expected_manifest_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) or
                not isinstance(expected_lock_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_lock_sha256) or
                not isinstance(dependencies_lock, str) or Path(dependencies_lock).is_absolute() or
                ".." in Path(dependencies_lock).parts):
            raise ValueError("invalid_source_binding")
        if not checkpoint_dir.is_dir():
            raise ValueError("invalid_checkpoint_directory")
        manifest_path = source / ".gpu-control" / "experiment.json"
        lock_path = source / dependencies_lock
        if (manifest_path.is_symlink() or lock_path.is_symlink() or
                not manifest_path.resolve(strict=True).is_relative_to(source.resolve()) or
                not lock_path.resolve(strict=True).is_relative_to(source.resolve())):
            raise ValueError("invalid_source_binding")
        manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        lock_digest = hashlib.sha256(lock_path.read_bytes()).hexdigest()
        if manifest_digest != expected_manifest_sha256 or lock_digest != expected_lock_sha256:
            raise ValueError("source_binding_mismatch")
        if drop_privileges:
            for item in source.rglob("*"):
                item.chmod(0o555 if item.is_dir() else 0o444)
            source.chmod(0o555)
        runtime_dir = Path(temp) / "runtime"
        try:
            training_python = install_locked_dependencies(source, dependencies_lock, wheelhouse,
                                                          runtime_dir, drop_privileges=drop_privileges)
        except (subprocess.SubprocessError, OSError, ValueError):
            return {"state": "failed", "failure_code": "TRAINING_DEPENDENCY_INSTALL_FAILED",
                    "run_id": run_id, "source_sha": staged["commit"],
                    "gpu_profile": gpu_profile, "manifest_sha256": expected_manifest_sha256,
                    "lock_sha256": expected_lock_sha256, "gpu_used": False,
                    "checkpoint": None, "output": "", "output_truncated": False}
        gpu = probe_gpu(gpu_profile, python=str(training_python))
        last_gpu_sample = 0.0
        def sample_gpu_activity():
            nonlocal last_gpu_sample
            now = time.monotonic()
            if now - last_gpu_sample < 1.0:
                return False
            last_gpu_sample = now
            return gpu_activity_probe()
        result = run_command([os.path.realpath(training_python), entrypoint], source, runtime_seconds, cancelled=cancelled,
                             checkpoint_dir=checkpoint_dir, drop_privileges=drop_privileges,
                             output_limit=8192, on_poll=sample_gpu_activity)
    checkpoint = checkpoint_manifest(checkpoint_dir)
    try:
        metrics = metrics_manifest(checkpoint_dir)
    except ValueError:
        metrics = None
        result = {**result, "state": "failed"}
        failure_code = "TRAINING_METRICS_INVALID"
    else:
        failure_code = None
        if result["state"] == "succeeded" and metrics is None:
            result = {**result, "state": "failed"}
            failure_code = "TRAINING_METRICS_MISSING"
    state = result["state"]
    if state == "succeeded" and not result["gpu_activity_seen"]:
        state, failure_code = "failed", "GPU_ACTIVITY_NOT_OBSERVED"
    return {**result, "state": state, **({"failure_code": failure_code} if failure_code else {}),
            "run_id": run_id, "source_sha": staged["commit"], "gpu_profile": gpu_profile,
            "manifest_sha256": expected_manifest_sha256,
            "lock_sha256": expected_lock_sha256, "gpu": gpu,
            "gpu_used": result["gpu_activity_seen"], "checkpoint": checkpoint,
            "metrics": metrics}
