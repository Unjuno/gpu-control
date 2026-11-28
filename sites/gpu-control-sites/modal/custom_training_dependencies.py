"""Fetch only hash-pinned Python wheels; package code is never run here."""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


MAX_LOCK_BYTES = 64 * 1024
MAX_PACKAGES = 128
MAX_WHEELHOUSE_BYTES = 1024 * 1024 * 1024
PACKAGE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]{0,127})==([A-Za-z0-9][A-Za-z0-9.!+_-]{0,127})$")
HASH = re.compile(r"^--hash=sha256:([0-9a-f]{64})$")


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_hashed_lock(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_LOCK_BYTES:
        raise ValueError("training_lock_invalid")
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        raise ValueError("training_lock_invalid") from exc
    packages = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        match = PACKAGE.fullmatch(fields[0]) if fields else None
        hashes = [HASH.fullmatch(value) for value in fields[1:]]
        if (match is None or not hashes or any(value is None for value in hashes) or
                len(fields) != 1 + len(hashes)):
            raise ValueError("training_lock_must_pin_wheel_hashes")
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        if name in packages:
            raise ValueError("training_lock_duplicate_package")
        packages[name] = {value.group(1) for value in hashes}
        if len(packages) > MAX_PACKAGES:
            raise ValueError("training_lock_package_limit")
    if not packages:
        raise ValueError("training_lock_empty")
    return packages


def download_locked_wheels(lock_path, destination, *, python_version, timeout=90, run=subprocess.run):
    """Download binary wheels from PyPI without executing package build hooks."""
    if python_version not in {"3.11", "3.12"}:
        raise ValueError("training_python_version_invalid")
    lock_path = Path(lock_path)
    expected = validate_hashed_lock(lock_path)
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    pip = [sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
           "--no-deps", "--only-binary=:all:", "--require-hashes", "--no-cache-dir",
           "--python-version", python_version, "--implementation", "cp",
           "--abi", f"cp{python_version.replace('.', '')}", "--abi", "abi3", "--abi", "none",
           "--dest", str(destination), "--index-url", "https://pypi.org/simple",
           "-r", str(lock_path)]
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
           "HOME": "/dev/null", "PIP_CONFIG_FILE": "/dev/null", "PIP_NO_INPUT": "1",
           "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_CACHE_DIR": "1",
           "PYTHONNOUSERSITE": "1", "LC_ALL": "C"}
    try:
        run(pip, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=True, timeout=timeout)
        from packaging.utils import parse_wheel_filename
        found = set()
        total = 0
        for item in destination.iterdir():
            if item.is_symlink() or not item.is_file() or item.suffix != ".whl":
                raise ValueError("training_wheelhouse_invalid")
            try:
                package, _version, _build, _tags = parse_wheel_filename(item.name)
            except Exception as exc:
                raise ValueError("training_wheelhouse_invalid") from exc
            name = re.sub(r"[-_.]+", "-", str(package)).lower()
            digest = _sha256_file(item)
            if name not in expected or digest not in expected[name]:
                raise ValueError("training_wheel_hash_mismatch")
            found.add(name)
            total += item.stat().st_size
            if total > MAX_WHEELHOUSE_BYTES:
                raise ValueError("training_wheelhouse_too_large")
        if found != set(expected):
            raise ValueError("training_wheelhouse_incomplete")
        wheel_hashes = []
        for item in destination.iterdir():
            wheel_hashes.append(_sha256_file(item))
        return {"packages": len(found), "bytes": total,
                "sha256": hashlib.sha256("\n".join(sorted(wheel_hashes)).encode("ascii")).hexdigest()}
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
