-- Modal GPU is a separate provider policy from Modal CPU.  The canary is
-- fixed at one T4 for 30 seconds, with a $0.01 reservation per approved run
-- and a $1 monthly project ceiling.  The provider Workspace hard limit remains
-- an independent outer stop.
CREATE TABLE modal_gpu_budget_policy (
  scope TEXT PRIMARY KEY CHECK (scope = 'workspace'),
  monthly_limit_microusd INTEGER NOT NULL CHECK (monthly_limit_microusd = 1000000),
  per_run_limit_microusd INTEGER NOT NULL CHECK (per_run_limit_microusd = 10000),
  admission_enabled INTEGER NOT NULL DEFAULT 1 CHECK (admission_enabled IN (0, 1)),
  updated_at INTEGER NOT NULL CHECK (updated_at >= 0)
);

INSERT INTO modal_gpu_budget_policy
  (scope, monthly_limit_microusd, per_run_limit_microusd, admission_enabled, updated_at)
VALUES ('workspace', 1000000, 10000, 1, 0);

CREATE TABLE modal_gpu_budget_reservations (
  run_id TEXT PRIMARY KEY REFERENCES gateway_delegated_plans(id) ON DELETE CASCADE,
  plan_fingerprint TEXT NOT NULL CHECK (
    length(plan_fingerprint) = 64 AND plan_fingerprint NOT GLOB '*[^0-9a-f]*'
  ),
  period_key TEXT NOT NULL CHECK (
    length(period_key) = 7 AND period_key GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
  ),
  reserved_microusd INTEGER NOT NULL CHECK (reserved_microusd = 10000),
  created_at INTEGER NOT NULL CHECK (created_at >= 0)
);

CREATE INDEX modal_gpu_budget_reservations_period
  ON modal_gpu_budget_reservations(period_key, created_at);

CREATE TABLE modal_gpu_active_lease (
  scope TEXT PRIMARY KEY CHECK (scope = 'workspace'),
  run_id TEXT NOT NULL UNIQUE REFERENCES gateway_delegated_plans(id) ON DELETE RESTRICT,
  plan_fingerprint TEXT NOT NULL CHECK (
    length(plan_fingerprint) = 64 AND plan_fingerprint NOT GLOB '*[^0-9a-f]*'
  ),
  state TEXT NOT NULL CHECK (state IN ('submitting', 'active', 'cancel_pending')),
  acquired_at INTEGER NOT NULL CHECK (acquired_at >= 0),
  updated_at INTEGER NOT NULL CHECK (updated_at >= acquired_at)
);

PRAGMA foreign_key_check;
