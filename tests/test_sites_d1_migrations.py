"""Replay Sites D1 migrations without depending on a deployed database."""

from __future__ import annotations

import sqlite3
from pathlib import Path


MIGRATIONS = (
    Path(__file__).parents[1]
    / "sites"
    / "gpu-control-sites"
    / "drizzle"
)


def _insert_plan(db: sqlite3.Connection, plan_id: str, created_at: int = 1) -> None:
    db.execute(
        """INSERT INTO plans VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            plan_id,
            "owner-1",
            f"idempotency-{plan_id}",
            "a" * 64,
            "tiny-stories-inference-v1",
            "Unjuno/gpu-control",
            "b" * 40,
            "sha256:" + "c" * 64,
            '{"prompt":"Once","max_new_tokens":1,"seed":61112}',
            1,
            "0.00",
            "prepared",
            created_at,
            created_at + 300,
        ),
    )


def test_human_authorization_migration_preserves_existing_d1_rows() -> None:
    migrations = sorted(MIGRATIONS.glob("*.sql"))
    assert [path.name for path in migrations] == [
        "0000_control_plane.sql",
        "0001_result_artifacts.sql",
        "0002_cancellation.sql",
        "0003_runner_cancellation_protocol.sql",
        "0004_sandbox_cost_ceiling.sql",
        "0005_human_plan_authorization.sql",
        "0006_runpod_account_leases.sql",
        "0007_modal_health_check_limit.sql",
        "0008_modal_plan_health_authorization.sql",
    ]

    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(migrations[0].read_text())
    _insert_plan(db, "plan-existing")
    db.execute(
        """INSERT INTO runs (
            id, owner_id, plan_id, state, lease_id, lease_expires_at, attempt,
            cleanup_state, result_json, cleanup_receipt_json, failure_code,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "run-existing",
            "owner-1",
            "plan-existing",
            "failed",
            "lease-existing",
            40,
            1,
            "confirmed",
            '{"legacy":"preserve"}',
            '{"cleanup":"confirmed"}',
            "LEGACY_FAILURE",
            2,
            3,
        ),
    )
    db.execute(
        """INSERT INTO runner_heartbeats
        (runner_id, last_seen_at, image_digest, source_sha)
        VALUES (?, ?, ?, ?)""",
        ("retired-runner", 3, "sha256:" + "c" * 64, "b" * 40),
    )

    original_plan = db.execute("SELECT * FROM plans").fetchone()
    original_run = db.execute("SELECT * FROM runs").fetchone()
    original_heartbeat = db.execute("SELECT * FROM runner_heartbeats").fetchone()

    for migration in migrations[1:]:
        db.executescript(migration.read_text())
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []

    assert db.execute(
        "SELECT id, owner_id, idempotency_key, fingerprint, max_cost_usd FROM plans"
    ).fetchall() == [("plan-existing", "owner-1", "idempotency-plan-existing", "a" * 64, "0.00")]
    migrated_run = db.execute(
        """SELECT id, owner_id, plan_id, state, lease_id, lease_expires_at,
            attempt, cleanup_state, result_json, cleanup_receipt_json,
            failure_code, created_at, updated_at, result_artifact_id,
            result_artifact_sha256, result_artifact_size, cancel_requested
        FROM runs"""
    ).fetchone()
    assert migrated_run[:13] == original_run
    assert migrated_run[13:] == (None, None, None, 0)
    assert db.execute(
        """SELECT runner_id, last_seen_at, image_digest, source_sha,
            cancellation_protocol FROM runner_heartbeats"""
    ).fetchall() == [
        ("retired-runner", 3, "sha256:" + "c" * 64, "b" * 40, 0)
    ]
    assert original_plan[0] == "plan-existing"
    assert original_heartbeat[0] == "retired-runner"
    assert db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='modal_health_check_limits'"
    ).fetchone()[0].find("scope TEXT PRIMARY KEY CHECK (scope = 'workspace')") >= 0

    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"authorization_challenges", "human_authorizations", "provider_account_leases", "provider_account_lease_events", "modal_authorized_health_checks"} <= tables
    db.execute("INSERT INTO modal_authorized_health_checks VALUES (?, ?, ?, ?)", ("plan-existing", "owner-1", "a" * 64, 6))
    db.execute(
        """INSERT INTO authorization_challenges
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("challenge-1", "owner-1", "plan-existing", "a" * 64, "d" * 64, 4, 120, None),
    )
    db.execute(
        """INSERT INTO human_authorizations
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("authorization-1", "owner-1", "plan-existing", "a" * 64, "ref-1", 5, 600, None),
    )
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
