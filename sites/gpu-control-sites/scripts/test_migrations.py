"""Exercise the forward migration against a populated pre-migration D1 schema."""
from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "drizzle"
conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys=ON")

paths = sorted(MIGRATIONS.glob("*.sql"))
assert paths[-1].name == "0033_github_installation_user_authorization.sql"
history = next(path for path in paths if path.name == "0021_reliable_run_history.sql")
shared_budget = next(path for path in paths if path.name == "0032_modal_compute_budget.sql")
for path in paths[:paths.index(history)]:
    conn.executescript(path.read_text(encoding="utf-8"))

# Seed rows in the old schema to exercise a real forward upgrade. In
# particular, delegated plans retain CHECK(state IN ('prepared','submitted')).
conn.execute(
    """INSERT INTO plans (id,owner_id,idempotency_key,fingerprint,workload,repository,
       source_sha,image_digest,parameters_json,runtime_seconds,max_cost_usd,state,created_at,expires_at,provider)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    ("1" * 32, "owner", "plan-key-123", "b" * 64, "tiny-stories-inference-v1",
     "Unjuno/gpu-control", "c" * 40, "sha256:" + "a" * 64, "{}", 30, "0.01",
     "prepared", 100, 200, "modal_cpu"),
)
conn.execute(
    "INSERT INTO runs (id,owner_id,plan_id,state,created_at,updated_at,cleanup_state) VALUES (?,?,?,?,?,?,?)",
    ("c" * 32, "owner", "1" * 32, "succeeded", 100, 112, "confirmed"),
)
conn.execute(
    """INSERT INTO gateway_delegated_plans
       (id,owner_id,idempotency_key,fingerprint,workload,approved_plan_json,state,created_at,expires_at,
        provider_state,updated_at)
       VALUES (?,?,?,?,?,?,'submitted',?,?,?,?)""",
    ("a" * 32, "owner", "delegated-key-123", "d" * 64,
     "orbitune-zero-gpu-eval-v1", "{}", 100, 200, "succeeded", 333),
)
conn.execute(
    "INSERT INTO gateway_delegated_plans (id,owner_id,idempotency_key,fingerprint,workload,approved_plan_json,state,created_at,expires_at) VALUES (?,?,?,?,?,?,'prepared',?,?)",
    ("e" * 32, "owner", "prepared-key-123", "f" * 64,
     "orbitune-zero-gpu-eval-v1", "{}", 100, 200),
)

for path in paths[paths.index(history):paths.index(shared_budget)]:
    conn.executescript(path.read_text(encoding="utf-8"))

# Populate each pre-unification Modal ledger before applying 0032. The upgrade
# must carry all three types of already reserved spend into one account ledger.
shared_period = "2026-11"
shared_created_at = 1_795_800_000
conn.execute(
    "INSERT INTO provider_budget_reservations (run_id,provider,period_key,reserved_microusd,created_at) VALUES (?,?,?,?,?)",
    ("1" * 32, "modal_cpu", shared_period, 10_000, shared_created_at),
)
conn.execute(
    "INSERT INTO modal_gpu_budget_reservations (run_id,plan_fingerprint,period_key,reserved_microusd,created_at) VALUES (?,?,?,?,?)",
    ("a" * 32, "d" * 64, shared_period, 10_000, shared_created_at),
)
conn.execute(
    "INSERT INTO training_registrations (id,owner_id,repository,source_sha,created_at) VALUES (?,?,?,?,?)",
    ("8" * 32, "owner", "owner/repo", "e" * 40, shared_created_at),
)
conn.execute(
    """INSERT INTO training_plans
       (id,owner_id,registration_id,idempotency_key,fingerprint,plan_json,created_at,expires_at,dispatch_claimed_at)
       VALUES (?,?,?,?,?,?,?,?,?)""",
    ("2" * 32, "owner", "8" * 32, "owner-run", "f" * 64,
     '{"execution_kind":"owner_selected_python","max_cost_microusd":500000}',
     shared_created_at, shared_created_at + 300, shared_created_at),
)
conn.executescript(shared_budget.read_text(encoding="utf-8"))
github_user_authorization = next(path for path in paths if path.name == "0033_github_installation_user_authorization.sql")
conn.execute("INSERT INTO github_app_installations VALUES (?,?,?,?,?)",
             ("owner", "98765", "Unjuno", "selected", 123))
conn.execute("INSERT INTO github_installation_states VALUES (?,?,?,?,?)",
             ("a" * 64, "owner", 100, 200, None))
conn.executescript(github_user_authorization.read_text(encoding="utf-8"))
conn.execute(
    "UPDATE gateway_delegated_plans SET cancelled_at=101 WHERE owner_id=? AND id=? AND state='prepared'",
    ("owner", "e" * 32),
)
assert conn.execute("SELECT state,cancelled_at FROM gateway_delegated_plans WHERE id=?", ("e" * 32,)).fetchone() == (
    "prepared", 101,
)
assert conn.execute("SELECT terminal_at FROM gateway_delegated_plans WHERE id=?", ("a" * 32,)).fetchone() == (333,)
assert conn.execute("SELECT completed_at FROM runs WHERE id=?", ("c" * 32,)).fetchone() == (112,)
assert conn.execute("SELECT monthly_limit_microusd,per_run_limit_microusd FROM modal_compute_budget_policy WHERE scope='workspace'").fetchone() == (
    30_000_000, 1_000_000,
)
assert conn.execute("SELECT admission_enabled FROM modal_gpu_admission_policy WHERE scope='workspace'").fetchone() == (1,)
assert conn.execute("SELECT source,reserved_microusd FROM modal_compute_budget_reservations WHERE run_id=?", ("1" * 32,)).fetchone() == (
    "modal_cpu", 10_000,
)
assert conn.execute("SELECT source,reserved_microusd FROM modal_compute_budget_reservations WHERE run_id=?", ("a" * 32,)).fetchone() == (
    "modal_gpu_canary", 10_000,
)
assert conn.execute("SELECT source,reserved_microusd FROM modal_compute_budget_reservations WHERE run_id=?", ("2" * 32,)).fetchone() == (
    "owner_selected_training", 500_000,
)
assert conn.execute("SELECT COUNT(*) FROM provider_budget_policies WHERE provider='modal_cpu'").fetchone() == (0,)
assert conn.execute("SELECT COUNT(*) FROM provider_budget_reservations WHERE provider='modal_cpu'").fetchone() == (0,)
assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='modal_gpu_budget_policy'").fetchone() == (0,)

conn.execute("UPDATE runs SET updated_at=222 WHERE id=?", ("c" * 32,))
conn.execute("UPDATE gateway_delegated_plans SET updated_at=444 WHERE id=?", ("a" * 32,))
assert conn.execute("SELECT completed_at FROM runs WHERE id=?", ("c" * 32,)).fetchone() == (112,)
assert conn.execute("SELECT terminal_at FROM gateway_delegated_plans WHERE id=?", ("a" * 32,)).fetchone() == (333,)
assert {row[1] for row in conn.execute("PRAGMA table_info(github_installation_states)")} == {
    "state_hash", "owner_id", "created_at", "expires_at", "consumed_at", "oauth_state_hash",
    "pending_installation_id", "pending_account_login", "completion_nonce",
}
assert {row[1] for row in conn.execute("PRAGMA table_info(github_app_installations)")} == {
    "owner_id", "installation_id", "account_login", "repository_selection", "connected_at",
}
assert "cleanup_confirmed_at" in {row[1] for row in conn.execute("PRAGMA table_info(training_plans)")}
assert conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='github_app_installations'").fetchone()[0].find("UNIQUE") >= 0
assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name='github_installation_states_oauth_state'").fetchone() == (1,)
assert conn.execute("SELECT COUNT(*) FROM github_app_installations").fetchone() == (0,)
assert conn.execute("SELECT COUNT(*) FROM github_installation_states").fetchone() == (0,)
assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
print("D1 forward migration passed: legacy rows preserved, cancellation and stable terminal history verified")
