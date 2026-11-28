"""The migration guard allows append-only history and rejects rewrites."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
GUARD_SOURCE = REPOSITORY / "sites/gpu-control-sites/scripts/check_migrations_append_only.py"


def _run_git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=repository, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "repo"
    migrations = repository / "sites/gpu-control-sites/drizzle"
    migrations.mkdir(parents=True)
    guard = repository / "sites/gpu-control-sites/scripts/check_migrations_append_only.py"
    guard.parent.mkdir(parents=True)
    guard.write_bytes(GUARD_SOURCE.read_bytes())
    _run_git(repository, "init", "-q")
    _run_git(repository, "config", "user.email", "migration-test@example.invalid")
    _run_git(repository, "config", "user.name", "Migration test")
    (migrations / "0000_base.sql").write_text("CREATE TABLE base (id INTEGER);\n")
    _run_git(repository, "add", ".")
    _run_git(repository, "commit", "-qm", "base")
    return repository, _run_git(repository, "rev-parse", "HEAD")


def _check(repository: Path, base: str) -> subprocess.CompletedProcess[str]:
    guard = repository / "sites/gpu-control-sites/scripts/check_migrations_append_only.py"
    return subprocess.run(
        ["python3", str(guard), base],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )


def test_append_only_guard_accepts_new_migration_after_existing_history(tmp_path: Path) -> None:
    repository, base = _repository(tmp_path)
    (repository / "sites/gpu-control-sites/drizzle/0001_add_index.sql").write_text(
        "CREATE INDEX base_id ON base(id);\n"
    )

    result = _check(repository, base)

    assert result.returncode == 0, result.stderr
    assert "1 existing, 1 added" in result.stdout


@pytest.mark.parametrize("operation", ["modify", "delete", "rename"])
def test_append_only_guard_rejects_rewriting_existing_history(
    tmp_path: Path, operation: str
) -> None:
    repository, base = _repository(tmp_path)
    migration = repository / "sites/gpu-control-sites/drizzle/0000_base.sql"
    if operation == "modify":
        migration.write_text("CREATE TABLE base (id TEXT);\n")
    elif operation == "delete":
        migration.unlink()
    else:
        migration.rename(migration.with_name("0000_renamed.sql"))

    result = _check(repository, base)

    assert result.returncode != 0
    assert "existing migration" in result.stderr


def test_append_only_guard_rejects_new_migration_inserted_before_history(tmp_path: Path) -> None:
    repository, base = _repository(tmp_path)
    (repository / "sites/gpu-control-sites/drizzle/0000_new_base.sql").write_text(
        "CREATE TABLE other (id INTEGER);\n"
    )

    result = _check(repository, base)

    assert result.returncode != 0
    assert "must be appended" in result.stderr
