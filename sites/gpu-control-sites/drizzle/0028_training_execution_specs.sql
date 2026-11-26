CREATE TABLE training_execution_specs (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  registration_id TEXT NOT NULL REFERENCES training_registrations(id),
  spec_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE(owner_id, registration_id, spec_json)
);
