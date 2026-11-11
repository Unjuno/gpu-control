ALTER TABLE runs ADD COLUMN result_artifact_id TEXT;
ALTER TABLE runs ADD COLUMN result_artifact_sha256 TEXT;
ALTER TABLE runs ADD COLUMN result_artifact_size INTEGER;
