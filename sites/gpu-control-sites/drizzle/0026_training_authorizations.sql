CREATE TABLE training_authorizations (
  plan_id TEXT PRIMARY KEY REFERENCES training_plans(id),
  owner_id TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  control_plane_sha TEXT NOT NULL,
  challenge_hash TEXT NOT NULL UNIQUE,
  expires_at INTEGER NOT NULL,
  authorized_at INTEGER,
  CHECK (authorized_at IS NULL OR authorized_at < expires_at)
);
