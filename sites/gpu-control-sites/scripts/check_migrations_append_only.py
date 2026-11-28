"""Reject edits, deletions, and renames of previously committed D1 migrations."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = Path("sites/gpu-control-sites/drizzle")
REVISION = re.compile(r"^[0-9a-f]{40,64}$")


def check_append_only(base_revision: str) -> None:
    if not REVISION.fullmatch(base_revision):
        raise ValueError("base revision must be a full Git object ID")

    subprocess.run(
        ["git", "cat-file", "-e", f"{base_revision}^{{commit}}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    base_paths = _tracked_migrations(base_revision)
    current_paths = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / MIGRATIONS).glob("*.sql")
    }

    removed = sorted(base_paths - current_paths)
    if removed:
        raise ValueError(f"existing migrations were removed or renamed: {', '.join(removed)}")

    for path in sorted(base_paths):
        result = subprocess.run(
            ["git", "diff", "--quiet", base_revision, "--", path],
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 1:
            raise ValueError(f"existing migration was modified: {path}")
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"git diff failed for {path}")

    added = sorted(current_paths - base_paths)
    if added and base_paths:
        highest_existing = max(_migration_version(path) for path in base_paths)
        first_added = _migration_version(added[0])
        if first_added <= highest_existing:
            raise ValueError("new migrations must be appended after the existing highest version")

    print(f"D1 migration history is append-only ({len(base_paths)} existing, {len(added)} added).")


def _tracked_migrations(revision: str) -> set[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", revision, "--", MIGRATIONS.as_posix()],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line.endswith(".sql")}


def _migration_version(path: str) -> int:
    name = Path(path).name
    prefix, separator, _ = name.partition("_")
    if not separator or not prefix.isdecimal() or len(prefix) != 4:
        raise ValueError(f"migration filename must start with a four-digit version: {name}")
    return int(prefix)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_migrations_append_only.py BASE_REVISION")
    try:
        check_append_only(sys.argv[1])
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc
