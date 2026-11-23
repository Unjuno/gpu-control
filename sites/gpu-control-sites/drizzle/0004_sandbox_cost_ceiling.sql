-- Keep historical zero-dollar plans valid while permitting the reviewed
-- fixed Sandbox CPU/memory ceiling for newly prepared plans. This does not
-- cap separately billed Modal control-function calls.
CREATE TABLE plans_v2 (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  workload TEXT NOT NULL,
  repository TEXT NOT NULL,
  source_sha TEXT NOT NULL,
  image_digest TEXT NOT NULL CHECK (image_digest GLOB 'sha256:*' AND length(image_digest) = 71 AND substr(image_digest, 8) NOT GLOB '*[^0-9a-f]*'),
  parameters_json TEXT NOT NULL,
  runtime_seconds INTEGER NOT NULL CHECK (runtime_seconds BETWEEN 1 AND 30),
  max_cost_usd TEXT NOT NULL CHECK (max_cost_usd IN ('0.00', '0.01')),
  state TEXT NOT NULL CHECK (state IN ('prepared', 'queued', 'expired')),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);

-- Rebuild runs in the same migration because SQLite's foreign-key rename
-- behavior would otherwise retarget its reference to the temporary table.
CREATE TABLE runs_v2 (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  plan_id TEXT NOT NULL UNIQUE REFERENCES plans_v2(id),
  state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  lease_id TEXT,
  lease_expires_at INTEGER,
  attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 3),
  cleanup_state TEXT NOT NULL DEFAULT 'pending' CHECK (cleanup_state IN ('pending', 'confirmed')),
  result_json TEXT,
  cleanup_receipt_json TEXT,
  failure_code TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  result_artifact_id TEXT,
  result_artifact_sha256 TEXT,
  result_artifact_size INTEGER,
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0, 1))
);

INSERT INTO plans_v2 (
  id, owner_id, idempotency_key, fingerprint, workload, repository, source_sha,
  image_digest, parameters_json, runtime_seconds, max_cost_usd, state, created_at, expires_at
)
SELECT
  id, owner_id, idempotency_key, fingerprint, workload, repository, source_sha,
  image_digest, parameters_json, runtime_seconds, max_cost_usd, state, created_at, expires_at
FROM plans;

INSERT INTO runs_v2 (
  id, owner_id, plan_id, state, lease_id, lease_expires_at, attempt,
  cleanup_state, result_json, cleanup_receipt_json, failure_code,
  created_at, updated_at, result_artifact_id, result_artifact_sha256,
  result_artifact_size, cancel_requested
)
SELECT
  id, owner_id, plan_id, state, lease_id, lease_expires_at, attempt,
  cleanup_state, result_json, cleanup_receipt_json, failure_code,
  created_at, updated_at, result_artifact_id, result_artifact_sha256,
  result_artifact_size, cancel_requested
FROM runs;

DROP TABLE runs;
DROP TABLE plans;
ALTER TABLE plans_v2 RENAME TO plans;
ALTER TABLE runs_v2 RENAME TO runs;

CREATE UNIQUE INDEX plans_owner_idempotency
  ON plans(owner_id, idempotency_key);
CREATE INDEX plans_owner_created
  ON plans(owner_id, created_at DESC);
CREATE INDEX runs_owner_created
  ON runs(owner_id, created_at DESC);
CREATE INDEX runs_queue
  ON runs(state, created_at);
CREATE UNIQUE INDEX runs_single_active_slot
  ON runs((1)) WHERE state IN ('queued', 'running');

PRAGMA foreign_key_check;
