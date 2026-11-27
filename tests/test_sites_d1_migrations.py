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
        "0009_modal_health_readiness.sql",
        "0010_modal_status_check_budget.sql",
        "0011_chatgpt_tool_authorization.sql",
        "0012_provider_runtime_state.sql",
        "0013_provider_budgets.sql",
        "0014_gateway_delegation.sql",
        "0015_modal_starter_budget.sql",
        "0016_provider_adapter_state.sql",
        "0017_free_provider_policies.sql",
        "0018_provider_cost_ceiling.sql",
        "0019_runpod_reconciliation_heartbeat.sql",
        "0020_modal_gpu_budget.sql",
        "0021_reliable_run_history.sql",
        "0022_training_registrations.sql",
        "0023_training_plans.sql",
        "0024_training_plan_cancellation.sql",
        "0025_training_submission_claim.sql",
        "0026_training_authorizations.sql",
        "0027_training_dispatch_rejection.sql",
        "0028_training_execution_specs.sql",
        "0029_training_authorization_evidence.sql",
        "0030_github_app_connections.sql",
        "0031_training_cleanup_confirmation.sql",
        "0032_modal_compute_budget.sql",
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

    assert {row[1] for row in db.execute("PRAGMA table_info(github_installation_states)")} == {
        "state_hash", "owner_id", "created_at", "expires_at", "consumed_at",
    }
    assert {row[1] for row in db.execute("PRAGMA table_info(github_app_installations)")} == {
        "owner_id", "installation_id", "account_login", "repository_selection", "connected_at",
    }
    assert "cleanup_confirmed_at" in {
        row[1] for row in db.execute("PRAGMA table_info(training_plans)")
    }
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
    assert {"authorization_challenges", "human_authorizations", "provider_account_leases", "provider_account_lease_events", "modal_authorized_health_checks", "modal_status_check_limits", "provider_free_policies", "provider_free_run_authorizations"} <= tables
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
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
