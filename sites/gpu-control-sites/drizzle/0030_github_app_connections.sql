CREATE TABLE github_installation_states (
  state_hash TEXT PRIMARY KEY CHECK (length(state_hash) = 64),
  owner_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER,
  CHECK (expires_at > created_at)
);

CREATE INDEX github_installation_states_expiry
  ON github_installation_states(expires_at, consumed_at);

CREATE TABLE github_app_installations (
  owner_id TEXT PRIMARY KEY,
  installation_id TEXT NOT NULL UNIQUE,
  account_login TEXT NOT NULL,
  repository_selection TEXT NOT NULL CHECK (repository_selection = 'selected'),
  connected_at INTEGER NOT NULL
);
