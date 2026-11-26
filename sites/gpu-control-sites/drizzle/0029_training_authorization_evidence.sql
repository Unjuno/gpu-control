ALTER TABLE training_authorizations ADD COLUMN authorization_id TEXT;
ALTER TABLE training_authorizations ADD COLUMN authorization_source TEXT;
ALTER TABLE training_authorizations ADD COLUMN authorization_reference TEXT;
ALTER TABLE training_authorizations ADD COLUMN decision_record_id TEXT;
ALTER TABLE training_authorizations ADD COLUMN authorized_by TEXT;
ALTER TABLE training_authorizations ADD COLUMN target_repository TEXT;
ALTER TABLE training_authorizations ADD COLUMN target_sha TEXT;
ALTER TABLE training_authorizations ADD COLUMN image_digest TEXT;
ALTER TABLE training_authorizations ADD COLUMN provider TEXT;
ALTER TABLE training_authorizations ADD COLUMN provider_resource_id TEXT;
ALTER TABLE training_authorizations ADD COLUMN gpu_count INTEGER;
ALTER TABLE training_authorizations ADD COLUMN runtime_seconds INTEGER;
ALTER TABLE training_authorizations ADD COLUMN max_cost_microusd INTEGER;
ALTER TABLE training_authorizations ADD COLUMN consumed_at INTEGER;

CREATE UNIQUE INDEX training_authorizations_reference
  ON training_authorizations(authorization_reference)
  WHERE authorization_reference IS NOT NULL;
