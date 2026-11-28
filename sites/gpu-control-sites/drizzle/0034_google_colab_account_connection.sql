CREATE TABLE google_colab_oauth_states (
  setup_state_hash TEXT PRIMARY KEY CHECK (length(setup_state_hash) = 64),
  owner_id TEXT NOT NULL,
  oauth_state_hash TEXT,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER,
  CHECK (expires_at > created_at)
);

CREATE UNIQUE INDEX google_colab_oauth_states_oauth_state
  ON google_colab_oauth_states(oauth_state_hash) WHERE oauth_state_hash IS NOT NULL;

CREATE INDEX google_colab_oauth_states_expiry
  ON google_colab_oauth_states(expires_at, consumed_at);

CREATE TABLE google_colab_accounts (
  owner_id TEXT PRIMARY KEY,
  google_subject_id TEXT NOT NULL,
  account_email TEXT NOT NULL,
  refresh_token_ciphertext TEXT NOT NULL,
  refresh_token_iv TEXT NOT NULL CHECK (length(refresh_token_iv) = 16),
  connected_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  CHECK (length(google_subject_id) BETWEEN 1 AND 255),
  CHECK (length(account_email) BETWEEN 3 AND 320),
  CHECK (length(refresh_token_ciphertext) BETWEEN 24 AND 4096)
);

PRAGMA foreign_key_check;
