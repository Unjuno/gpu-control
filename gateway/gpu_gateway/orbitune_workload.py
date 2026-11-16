"""Trusted offline staging for the registered Orbitune Kaggle workload."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess


ORBITUNE_REPOSITORY = "Unjuno/orbitune"
ORBITUNE_SOURCE_SHA = "44a1b806160ab5bc721a370d034a6dfcb28f27a8"
MAX_SOURCE_BYTES = 64 * 1024 * 1024


def _git(checkout: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(checkout), *args),
        check=False, capture_output=True, text=True, timeout=15,
    )
    if completed.returncode != 0:
        raise ValueError("Orbitune source checkout is not a readable Git checkout")
    return completed.stdout.strip()


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
    files = [path for path in package.rglob("*") if path.is_file()]
    if any(path.is_symlink() for path in files):
        raise ValueError("Orbitune package may not contain symlinked files")
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
    entrypoint = Path(__file__).parents[1] / "workloads" / "orbitune-kaggle-100" / "train.py"
    shutil.copyfile(entrypoint, target / "train.py")
    provenance = {
        "schema_version": 1,
        "workload_id": "orbitune-kaggle-100-step-v1",
        "source_repository": ORBITUNE_REPOSITORY,
        "source_sha": expected_sha,
        "data_kind": "synthetic",
        "steps": 100,
    }
    (target / "gpu-control-provenance.json").write_text(
        json.dumps(provenance, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return provenance
