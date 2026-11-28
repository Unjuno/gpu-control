"""Replay Sites D1 migrations without depending on a deployed database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


MIGRATIONS = (
    Path(__file__).parents[1]
    / "sites"
    / "gpu-control-sites"
    / "drizzle"
)


def _insert_plan(db: sqlite3.Connection, plan_id: str, created_at: int = 1) -> None:
    db.execute(
        """INSERT INTO plans (
            id, owner_id, idempotency_key, fingerprint, workload, repository,
            source_sha, image_digest, parameters_json, runtime_seconds,
            max_cost_usd, state, created_at, expires_at
        ) VALUES
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
    assert migrations, "the D1 migration directory must not be empty"
    migration_versions = [path.name.split("_", 1)[0] for path in migrations]
    assert migration_versions == [f"{version:04d}" for version in range(len(migrations))]

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
        if migration.name == "0033_github_installation_user_authorization.sql":
            db.execute(
                """INSERT INTO github_installation_states
                (state_hash, owner_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)""",
                ("d" * 64, "owner-1", 4, 300),
            )
            db.execute(
                """INSERT INTO github_app_installations
                (owner_id, installation_id, account_login, repository_selection, connected_at)
                VALUES (?, ?, ?, ?, ?)""",
                ("owner-1", "installation-1", "owner-login", "selected", 4),
            )
        db.executescript(migration.read_text())

    assert {row[1] for row in db.execute("PRAGMA table_info(github_installation_states)")} == {
        "state_hash", "owner_id", "created_at", "expires_at", "consumed_at",
        "oauth_state_hash", "pending_installation_id", "pending_account_login",
        "completion_nonce",
    }
    assert {row[1] for row in db.execute("PRAGMA table_info(github_app_installations)")} == {
        "owner_id", "installation_id", "account_login", "repository_selection", "connected_at",
    }
    assert "cleanup_confirmed_at" in {
        row[1] for row in db.execute("PRAGMA table_info(training_plans)")
    }
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("SELECT COUNT(*) FROM github_installation_states").fetchone() == (0,)
    assert db.execute("SELECT COUNT(*) FROM github_app_installations").fetchone() == (0,)

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
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE runs SET cancel_requested = 2 WHERE id = ?", ("run-existing",))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE plans SET max_cost_usd = '0.02' WHERE id = ?", ("plan-existing",))
    assert db.execute(
        """SELECT runner_id, last_seen_at, image_digest, source_sha,
            cancellation_protocol FROM runner_heartbeats"""
    ).fetchall() == [
        ("retired-runner", 3, "sha256:" + "c" * 64, "b" * 40, 0)
    ]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE runner_heartbeats SET cancellation_protocol = 2 WHERE runner_id = ?",
            ("retired-runner",),
        )
    assert original_plan[0] == "plan-existing"
    assert original_heartbeat[0] == "retired-runner"
    assert db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='modal_authorized_health_checks_owner_checked'"
    ).fetchone() == ("modal_authorized_health_checks_owner_checked",)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO modal_health_check_limits (scope, last_checked_at) VALUES (?, ?)",
            ("other", 11),
        )

    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"authorization_challenges", "human_authorizations", "provider_account_leases", "provider_account_lease_events", "modal_authorized_health_checks", "modal_status_check_limits", "provider_free_policies", "provider_free_run_authorizations"} <= tables
    lease_columns = {
        row[1] for row in db.execute("PRAGMA table_info(provider_account_leases)")
    }
    assert "lease_expires_at" not in lease_columns
    assert db.execute(
        """SELECT provider, max_cost_microusd, paid_fallback_allowed
        FROM provider_free_policies ORDER BY provider"""
    ).fetchall() == [
        ("huggingface_space", 0, 0),
        ("kaggle", 0, 0),
    ]
    delegated_columns = {
        row[1] for row in db.execute("PRAGMA table_info(gateway_delegated_plans)")
    }
    assert {"provider_handle_json", "provider_state", "provider_response_json", "updated_at"} <= delegated_columns
    assert db.execute("SELECT provider, provider_plan_json FROM plans WHERE id=?", ("plan-existing",)).fetchone() == ("modal_cpu", None)
    assert db.execute("SELECT provider_job_id, provider_phase, provider_nonce, completion_key_ciphertext_b64 FROM runs WHERE id=?", ("run-existing",)).fetchone() == (None, "not_started", None, None)
    assert db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND name='runs_provider_job_id_unique'"
    ).fetchone() == ("runs_provider_job_id_unique",)
    db.execute(
        """INSERT INTO modal_authorized_health_checks
        (plan_id, owner_id, fingerprint, checked_at)
        VALUES (?, ?, ?, ?)""",
        ("plan-existing", "owner-1", "a" * 64, 6),
    )
    assert db.execute(
        "SELECT ready FROM modal_authorized_health_checks WHERE plan_id = ?",
        ("plan-existing",),
    ).fetchone() == (0,)
    db.execute(
        """INSERT INTO modal_status_check_limits
        (scope, window_started_at, last_checked_at, call_count)
        VALUES (?, ?, ?, ?)""",
        ("workspace", 10, 10, 1),
    )
    assert db.execute(
        "SELECT call_count FROM modal_status_check_limits WHERE scope = ?",
        ("workspace",),
    ).fetchone() == (1,)
    try:
        db.execute(
            "UPDATE modal_authorized_health_checks SET ready = 2 WHERE plan_id = ?",
            ("plan-existing",),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("health readiness must reject values outside 0 and 1")
    db.execute(
        """INSERT INTO authorization_challenges
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("challenge-1", "owner-1", "plan-existing", "a" * 64, "d" * 64, 4, 120, None),
    )
    db.execute(
        """INSERT INTO human_authorizations
        (id, owner_id, plan_id, fingerprint, authorization_reference,
            authorized_at, expires_at, consumed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("authorization-1", "owner-1", "plan-existing", "a" * 64, "ref-1", 5, 600, None),
    )
    assert db.execute(
        "SELECT authorization_source FROM human_authorizations WHERE id = ?",
        ("authorization-1",),
    ).fetchone() == ("site_confirmation",)
    _insert_plan(db, "plan-expiry-check")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO human_authorizations
            (id, owner_id, plan_id, fingerprint, authorization_reference,
                authorized_at, expires_at, consumed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("authorization-too-long", "owner-1", "plan-expiry-check", "a" * 64,
             "ref-too-long", 5, 906, None),
        )
    db.execute(
        "UPDATE human_authorizations SET authorization_source = ? WHERE id = ?",
        ("chatgpt_mcp_write_confirmation", "authorization-1"),
    )
    try:
        db.execute(
            "UPDATE human_authorizations SET authorization_source = ? WHERE id = ?",
            ("untrusted_model_output", "authorization-1"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("authorization source must reject unrecognized values")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO provider_account_leases
            (provider, account_scope_sha256, generation, revision, lease_token,
                run_id, owner_id, plan_fingerprint, authorization_id,
                challenge_sha256, state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("runpod", "a" * 64, 1, 1, "b" * 64, "run-existing", "owner-1",
             "c" * 64, "authorization-1", "d" * 64, "active", 10, 10),
        )
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
