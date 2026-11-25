CREATE TABLE training_registrations (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  repository TEXT NOT NULL,
  source_sha TEXT NOT NULL CHECK (length(source_sha) = 40),
  created_at INTEGER NOT NULL,
  UNIQUE (owner_id, repository, source_sha)
);

CREATE INDEX idx_training_registrations_owner_recent
  ON training_registrations(owner_id, created_at DESC, id DESC);
