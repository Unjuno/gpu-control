-- One Sites-side Modal compute ceiling covers CPU, registered GPU canaries,
-- MAP training and owner-selected GPU training. It is not a provider billing
-- stop and does not include Modal control-function or external-provider fees.
CREATE TABLE modal_compute_budget_policy (
  scope TEXT PRIMARY KEY CHECK (scope = 'workspace'),
  monthly_limit_microusd INTEGER NOT NULL CHECK (monthly_limit_microusd = 30000000),
  per_run_limit_microusd INTEGER NOT NULL CHECK (per_run_limit_microusd = 1000000),
  updated_at INTEGER NOT NULL CHECK (updated_at >= 0)
);

INSERT INTO modal_compute_budget_policy
  (scope, monthly_limit_microusd, per_run_limit_microusd, updated_at)
VALUES ('workspace', 30000000, 1000000, 0);

CREATE TABLE modal_gpu_admission_policy (
  scope TEXT PRIMARY KEY CHECK (scope = 'workspace'),
  admission_enabled INTEGER NOT NULL CHECK (admission_enabled IN (0, 1)),
  updated_at INTEGER NOT NULL CHECK (updated_at >= 0)
);

INSERT INTO modal_gpu_admission_policy (scope, admission_enabled, updated_at)
SELECT scope, admission_enabled, updated_at FROM modal_gpu_budget_policy;

CREATE TABLE modal_compute_budget_reservations (
  run_id TEXT PRIMARY KEY CHECK (length(run_id) = 32 AND run_id NOT GLOB '*[^0-9a-f]*'),
  source TEXT NOT NULL CHECK (source IN (
    'modal_cpu', 'modal_gpu_canary', 'map_training', 'owner_selected_training'
  )),
  plan_fingerprint TEXT NOT NULL CHECK (
    length(plan_fingerprint) = 64 AND plan_fingerprint NOT GLOB '*[^0-9a-f]*'
  ),
  period_key TEXT NOT NULL CHECK (
    length(period_key) = 7 AND period_key GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
  ),
  reserved_microusd INTEGER NOT NULL CHECK (reserved_microusd > 0 AND reserved_microusd <= 1000000),
  created_at INTEGER NOT NULL CHECK (created_at >= 0)
);

CREATE INDEX modal_compute_budget_reservations_period
  ON modal_compute_budget_reservations(period_key, created_at);

-- Preserve prior Modal CPU reservations as well as the old fixed-GPU ledger.
INSERT OR IGNORE INTO modal_compute_budget_reservations
  (run_id, source, plan_fingerprint, period_key, reserved_microusd, created_at)
SELECT r.run_id, 'modal_cpu', p.fingerprint, r.period_key, r.reserved_microusd, r.created_at
FROM provider_budget_reservations r JOIN plans p ON p.id=r.run_id
WHERE r.provider='modal_cpu';

INSERT OR IGNORE INTO modal_compute_budget_reservations
  (run_id, source, plan_fingerprint, period_key, reserved_microusd, created_at)
SELECT run_id, 'modal_gpu_canary', plan_fingerprint, period_key, reserved_microusd, created_at
FROM modal_gpu_budget_reservations;

-- Training plans already carry their exact max-cost ceiling. Include every
-- previously claimed Modal plan in the new shared compute ledger.
INSERT OR IGNORE INTO modal_compute_budget_reservations
  (run_id, source, plan_fingerprint, period_key, reserved_microusd, created_at)
SELECT id,
  CASE WHEN json_extract(plan_json, '$.execution_kind')='owner_selected_python'
    THEN 'owner_selected_training' ELSE 'map_training' END,
  fingerprint,
  strftime('%Y-%m', dispatch_claimed_at, 'unixepoch'),
  CAST(json_extract(plan_json, '$.max_cost_microusd') AS INTEGER),
  dispatch_claimed_at
FROM training_plans
WHERE dispatch_claimed_at IS NOT NULL
  AND typeof(json_extract(plan_json, '$.max_cost_microusd'))='integer'
  AND json_extract(plan_json, '$.max_cost_microusd') BETWEEN 1 AND 1000000
  AND strftime('%Y-%m', dispatch_claimed_at, 'unixepoch') IS NOT NULL;

-- Stop writing the route-local Modal CPU ledger. RunPod retains its independent
-- policy/reservations in provider_budget_policies/provider_budget_reservations.
DELETE FROM provider_budget_reservations WHERE provider='modal_cpu';
DELETE FROM provider_budget_policies WHERE provider='modal_cpu';
DROP TABLE modal_gpu_budget_reservations;
DROP TABLE modal_gpu_budget_policy;

PRAGMA foreign_key_check;
