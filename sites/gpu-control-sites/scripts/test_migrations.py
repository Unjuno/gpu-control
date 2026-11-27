"""Exercise the forward migration against a populated pre-migration D1 schema."""
from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "drizzle"
conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys=ON")

paths = sorted(MIGRATIONS.glob("*.sql"))
assert paths[-1].name == "0031_training_cleanup_confirmation.sql"
history = next(path for path in paths if path.name == "0021_reliable_run_history.sql")
for path in paths[:paths.index(history)]:
    conn.executescript(path.read_text(encoding="utf-8"))

# Seed rows in the old schema to exercise a real forward upgrade. In
# particular, delegated plans retain CHECK(state IN ('prepared','submitted')).
conn.execute(
    """INSERT INTO plans (id,owner_id,idempotency_key,fingerprint,workload,repository,
       source_sha,image_digest,parameters_json,runtime_seconds,max_cost_usd,state,created_at,expires_at,provider)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    ("p" * 32, "owner", "plan-key-123", "b" * 64, "tiny-stories-inference-v1",
     "Unjuno/gpu-control", "c" * 40, "sha256:" + "a" * 64, "{}", 30, "0.01",
     "prepared", 100, 200, "modal_cpu"),
)
conn.execute(
    "INSERT INTO runs (id,owner_id,plan_id,state,created_at,updated_at,cleanup_state) VALUES (?,?,?,?,?,?,?)",
    ("c" * 32, "owner", "p" * 32, "succeeded", 100, 112, "confirmed"),
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

for path in paths[paths.index(history):]:
    conn.executescript(path.read_text(encoding="utf-8"))
conn.execute(
    "UPDATE gateway_delegated_plans SET cancelled_at=101 WHERE owner_id=? AND id=? AND state='prepared'",
    ("owner", "e" * 32),
)
assert conn.execute("SELECT state,cancelled_at FROM gateway_delegated_plans WHERE id=?", ("e" * 32,)).fetchone() == (
    "prepared", 101,
)
assert conn.execute("SELECT terminal_at FROM gateway_delegated_plans WHERE id=?", ("a" * 32,)).fetchone() == (333,)
assert conn.execute("SELECT completed_at FROM runs WHERE id=?", ("c" * 32,)).fetchone() == (112,)

conn.execute("UPDATE runs SET updated_at=222 WHERE id=?", ("c" * 32,))
conn.execute("UPDATE gateway_delegated_plans SET updated_at=444 WHERE id=?", ("a" * 32,))
assert conn.execute("SELECT completed_at FROM runs WHERE id=?", ("c" * 32,)).fetchone() == (112,)
assert conn.execute("SELECT terminal_at FROM gateway_delegated_plans WHERE id=?", ("a" * 32,)).fetchone() == (333,)
assert {row[1] for row in conn.execute("PRAGMA table_info(github_installation_states)")} == {
    "state_hash", "owner_id", "created_at", "expires_at", "consumed_at",
}
assert {row[1] for row in conn.execute("PRAGMA table_info(github_app_installations)")} == {
    "owner_id", "installation_id", "account_login", "repository_selection", "connected_at",
}
assert "cleanup_confirmed_at" in {row[1] for row in conn.execute("PRAGMA table_info(training_plans)")}
assert conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='github_app_installations'").fetchone()[0].find("UNIQUE") >= 0
assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
print("D1 forward migration passed: legacy rows preserved, cancellation and stable terminal history verified")
