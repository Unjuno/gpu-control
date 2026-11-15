-- Provider-specific loss ceilings. Amounts are integer micro-USD so budget
-- comparisons never depend on floating-point rounding.
CREATE TABLE provider_budget_policies (
  provider TEXT PRIMARY KEY CHECK (provider IN ('modal_cpu', 'runpod_gpu')),
  monthly_limit_microusd INTEGER CHECK (monthly_limit_microusd IS NULL OR monthly_limit_microusd > 0),
  per_run_limit_microusd INTEGER NOT NULL CHECK (per_run_limit_microusd > 0),
  updated_at INTEGER NOT NULL CHECK (updated_at >= 0)
);

INSERT INTO provider_budget_policies
  (provider, monthly_limit_microusd, per_run_limit_microusd, updated_at)
VALUES
  ('modal_cpu', 30000000, 10000, 0),
  ('runpod_gpu', NULL, 1000000, 0);

CREATE TABLE provider_budget_reservations (
  run_id TEXT PRIMARY KEY REFERENCES plans(id),
  provider TEXT NOT NULL REFERENCES provider_budget_policies(provider),
  period_key TEXT NOT NULL CHECK (length(period_key) = 7 AND period_key GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
  reserved_microusd INTEGER NOT NULL CHECK (reserved_microusd > 0),
  created_at INTEGER NOT NULL CHECK (created_at >= 0)
);

CREATE INDEX provider_budget_reservations_period
  ON provider_budget_reservations(provider, period_key, created_at);

PRAGMA foreign_key_check;
