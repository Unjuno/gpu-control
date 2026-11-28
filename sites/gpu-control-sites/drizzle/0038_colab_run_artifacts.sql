-- Colab outputs are kept in the existing private object store; D1 contains only
-- owner-bound metadata and immutable checksums for the common artifact tool.
CREATE TABLE google_colab_run_artifacts (
  run_id TEXT NOT NULL REFERENCES gateway_delegated_plans(id) ON DELETE CASCADE,
  owner_id TEXT NOT NULL,
  plan_fingerprint TEXT NOT NULL CHECK (length(plan_fingerprint) = 64),
  artifact_id TEXT NOT NULL CHECK (artifact_id GLOB 'artifact-[0-9][0-9]'),
  path TEXT NOT NULL CHECK (length(path) BETWEEN 1 AND 240),
  object_key TEXT NOT NULL CHECK (length(object_key) BETWEEN 1 AND 512),
  sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
  size_bytes INTEGER NOT NULL CHECK (size_bytes BETWEEN 1 AND 52428800),
  created_at INTEGER NOT NULL,
  PRIMARY KEY (run_id, artifact_id),
  FOREIGN KEY (owner_id, run_id, plan_fingerprint)
    REFERENCES gateway_delegated_plans(owner_id, id, fingerprint) ON DELETE CASCADE
);

CREATE INDEX idx_google_colab_artifacts_owner_run
  ON google_colab_run_artifacts(owner_id, run_id, artifact_id);

PRAGMA foreign_key_check;
