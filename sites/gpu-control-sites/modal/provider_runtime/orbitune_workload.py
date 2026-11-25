"""Trusted Sites/Modal staging for the registered Orbitune Kaggle workload."""
from __future__ import annotations

import json
import base64
import hashlib
import io
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


ORBITUNE_REPOSITORY = "Unjuno/orbitune"
ORBITUNE_SOURCE_SHA = "44a1b806160ab5bc721a370d034a6dfcb28f27a8"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
_BUNDLE_MARKER = "__GPU_CONTROL_ORBITUNE_BUNDLE_B64__"
_BUNDLE_SHA_MARKER = "__GPU_CONTROL_ORBITUNE_BUNDLE_SHA256__"


def staged_bundle_digest(target: str | Path) -> str:
    root = Path(target)
    entrypoint = root / "train.py"
    package = root / "orbitune"
    if not entrypoint.is_file() or entrypoint.is_symlink() or not package.is_dir() or package.is_symlink():
        raise ValueError("staged Orbitune bundle is incomplete")
    staged_files = [entrypoint] + sorted(path for path in package.rglob("*") if path.is_file())
    if any(path.is_symlink() for path in staged_files):
        raise ValueError("staged Orbitune bundle contains a symlink")
    digest = hashlib.sha256()
    for path in staged_files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def staged_space_payload_digest(target: str | Path) -> str:
    root = Path(target)
    required = (root / "README.md", root / "app.py", root / "requirements.txt")
    package = root / "orbitune"
    allowed_root_names = {"README.md", "app.py", "requirements.txt", "orbitune"}
    root_entries = list(root.iterdir()) if root.is_dir() and not root.is_symlink() else []
    if ({path.name for path in root_entries} != allowed_root_names or
            any(path.is_symlink() for path in root_entries)):
        raise ValueError("staged ZeroGPU Space payload contains unexpected root entries")
    if (any(not path.is_file() or path.is_symlink() for path in required) or
            not package.is_dir() or package.is_symlink()):
        raise ValueError("staged ZeroGPU Space payload is incomplete")
    package_entries = list(package.rglob("*"))
    if any(path.is_symlink() for path in package_entries):
        raise ValueError("staged ZeroGPU Space payload contains a symlink")
    staged_files = list(required) + sorted(path for path in package_entries if path.is_file())
    digest = hashlib.sha256()
    for path in staged_files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def _git(checkout: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(checkout), *args),
        check=False, capture_output=True, text=True, timeout=15,
    )
    if completed.returncode != 0:
        raise ValueError("Orbitune source checkout is not a readable Git checkout")
    return completed.stdout.strip()


def _tracked_package_paths(checkout: Path, package: Path) -> set[str]:
    completed = subprocess.run(
        ("git", "-C", str(checkout), "ls-files", "-z", "--", "orbitune"),
        check=False, capture_output=True, timeout=15,
    )
    if completed.returncode != 0:
        raise ValueError("Orbitune tracked source inventory is unavailable")
    try:
        tracked = {
            item.decode("utf-8") for item in completed.stdout.split(b"\0") if item
        }
    except UnicodeDecodeError as exc:
        raise ValueError("Orbitune tracked source paths must be UTF-8") from exc
    actual = {
        path.relative_to(checkout).as_posix()
        for path in package.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if not tracked or actual != tracked:
        raise ValueError("Orbitune package must contain exactly tracked source files")
    for relative in sorted(tracked):
        if (_git(checkout, "rev-parse", f"HEAD:{relative}") !=
                _git(checkout, "hash-object", "--no-filters", "--", relative)):
            raise ValueError("Orbitune package content differs from the registered commit")
    return tracked


def _package_bundle(package: Path, files: list[Path]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files):
            relative = Path("orbitune") / path.relative_to(package)
            info = zipfile.ZipInfo(relative.as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            archive.writestr(info, path.read_bytes())
    return output.getvalue()


def stage_orbitune_checkout(
    checkout: str | Path,
    stage: str | Path,
    *,
    expected_sha: str = ORBITUNE_SOURCE_SHA,
) -> dict[str, object]:
    """Copy only reviewed Python package bytes into a new trusted stage.

    Network materialization is deliberately outside this function.  The worker
    receives a clean checkout whose exact commit was fetched and reviewed by an
    operator-controlled source-cache process.
    """
    if re.fullmatch(r"[0-9a-f]{40}", expected_sha or "") is None:
        raise ValueError("expected Orbitune source SHA is invalid")
    source = Path(checkout).resolve()
    package = source / "orbitune"
    if not package.is_dir() or package.is_symlink():
        raise ValueError("Orbitune package directory is unavailable")
    if _git(source, "rev-parse", "HEAD") != expected_sha:
        raise ValueError("Orbitune checkout SHA does not match the registered source SHA")
    if _git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Orbitune checkout must be clean before staging")
    entries = list(package.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise ValueError("Orbitune package may not contain symlinked entries")
    _tracked_package_paths(source, package)
    files = [path for path in entries if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    if total < 1 or total > MAX_SOURCE_BYTES:
        raise ValueError("Orbitune package exceeds the staging size bound")
    target = Path(stage)
    if target.exists():
        raise ValueError("Orbitune staging target must not already exist")
    target.mkdir(parents=True, mode=0o700)
    shutil.copytree(
        package,
        target / "orbitune",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    entrypoint = Path(__file__).parent / "workloads" / "orbitune-kaggle-100" / "train.py"
    template = entrypoint.read_text(encoding="utf-8")
    if template.count(_BUNDLE_MARKER) != 1 or template.count(_BUNDLE_SHA_MARKER) != 1:
        raise ValueError("registered Orbitune entrypoint bundle markers are invalid")
    bundle = _package_bundle(package, files)
    rendered = template.replace(_BUNDLE_MARKER, base64.b64encode(bundle).decode("ascii"))
    rendered = rendered.replace(_BUNDLE_SHA_MARKER, hashlib.sha256(bundle).hexdigest())
    (target / "train.py").write_text(rendered, encoding="utf-8")
    provenance = {
        "schema_version": 1,
        "workload_id": "orbitune-kaggle-100-step-v1",
        "source_repository": ORBITUNE_REPOSITORY,
        "source_sha": expected_sha,
        "data_kind": "synthetic",
        "steps": 100,
        "image_digest": staged_bundle_digest(target),
    }
    (target / "gpu-control-provenance.json").write_text(
        json.dumps(provenance, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return provenance


def stage_orbitune_zero_gpu_space(
    checkout: str | Path,
    stage: str | Path,
    *,
    expected_sha: str = ORBITUNE_SOURCE_SHA,
) -> dict[str, object]:
    """Build an upload-ready private Space payload from one reviewed checkout.

    This function is offline and never creates or updates a Hub repository. The
    resulting directory can be reviewed before a separately authorized upload.
    """
    if re.fullmatch(r"[0-9a-f]{40}", expected_sha or "") is None:
        raise ValueError("expected Orbitune source SHA is invalid")
    source = Path(checkout).resolve()
    package = source / "orbitune"
    if not package.is_dir() or package.is_symlink():
        raise ValueError("Orbitune package directory is unavailable")
    if _git(source, "rev-parse", "HEAD") != expected_sha:
        raise ValueError("Orbitune checkout SHA does not match the registered source SHA")
    if _git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Orbitune checkout must be clean before staging")
    entries = list(package.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise ValueError("Orbitune package may not contain symlinked entries")
    _tracked_package_paths(source, package)
    files = [path for path in entries if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    if total < 1 or total > MAX_SOURCE_BYTES:
        raise ValueError("Orbitune package exceeds the staging size bound")
    target = Path(stage)
    if target.exists():
        raise ValueError("Orbitune staging target must not already exist")
    target.mkdir(parents=True, mode=0o700)
    shutil.copytree(
        package,
        target / "orbitune",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    template_root = Path(__file__).parent / "workloads" / "orbitune-zero-gpu-eval"
    for name in ("README.md", "app.py", "requirements.txt"):
        template = template_root / name
        if not template.is_file() or template.is_symlink():
            raise ValueError("registered ZeroGPU Space template is incomplete")
        (target / name).write_bytes(template.read_bytes())
    provenance = {
        "schema_version": 1,
        "workload_id": "orbitune-zero-gpu-eval-v1",
        "source_repository": ORBITUNE_REPOSITORY,
        "source_sha": expected_sha,
        "space_payload_digest": staged_space_payload_digest(target),
    }
    return provenance
