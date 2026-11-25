CREATE TABLE training_plans (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  registration_id TEXT NOT NULL REFERENCES training_registrations(id),
  idempotency_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  plan_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  UNIQUE (owner_id, idempotency_key)
);
