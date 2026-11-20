CREATE TABLE IF NOT EXISTS gateway_delegated_plans (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  workload TEXT NOT NULL,
  approved_plan_json TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('prepared', 'submitted')),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  UNIQUE (owner_id, idempotency_key),
  UNIQUE (owner_id, id, fingerprint)
);

CREATE TABLE IF NOT EXISTS gateway_delegated_authorizations (
  authorization_id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  plan_id TEXT NOT NULL UNIQUE,
  fingerprint TEXT NOT NULL,
  authorization_source TEXT NOT NULL CHECK (authorization_source = 'chatgpt_mcp_write_confirmation'),
  authorized_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER,
  FOREIGN KEY (owner_id, plan_id, fingerprint)
    REFERENCES gateway_delegated_plans(owner_id, id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_gateway_delegated_plans_owner_created
  ON gateway_delegated_plans(owner_id, created_at DESC);
