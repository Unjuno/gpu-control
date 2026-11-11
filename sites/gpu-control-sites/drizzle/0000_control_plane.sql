CREATE TABLE IF NOT EXISTS plans (
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
  max_cost_usd TEXT NOT NULL CHECK (max_cost_usd = '0.00'),
  state TEXT NOT NULL CHECK (state IN ('prepared', 'queued', 'expired')),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS plans_owner_idempotency
  ON plans(owner_id, idempotency_key);
CREATE INDEX IF NOT EXISTS plans_owner_created
  ON plans(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  plan_id TEXT NOT NULL UNIQUE REFERENCES plans(id),
  state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  lease_id TEXT,
  lease_expires_at INTEGER,
  attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 3),
  cleanup_state TEXT NOT NULL DEFAULT 'pending' CHECK (cleanup_state IN ('pending', 'confirmed')),
  result_json TEXT,
  cleanup_receipt_json TEXT,
  failure_code TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS runs_owner_created
  ON runs(owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS runs_queue
  ON runs(state, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS runs_single_active_slot
  ON runs((1)) WHERE state IN ('queued', 'running');

CREATE TABLE IF NOT EXISTS runner_heartbeats (
  runner_id TEXT PRIMARY KEY,
  last_seen_at INTEGER NOT NULL,
  image_digest TEXT NOT NULL,
  source_sha TEXT NOT NULL
);
