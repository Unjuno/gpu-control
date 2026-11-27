ALTER TABLE github_installation_states ADD COLUMN oauth_state_hash TEXT;
ALTER TABLE github_installation_states ADD COLUMN pending_installation_id TEXT;
ALTER TABLE github_installation_states ADD COLUMN pending_account_login TEXT;
ALTER TABLE github_installation_states ADD COLUMN completion_nonce TEXT;

-- Prior bindings relied only on the installation callback's ID and were not
-- proof that the authenticated Site owner controlled the GitHub account.
-- Force the one-time OAuth check before trusting any pre-existing binding.
DELETE FROM github_app_installations;
DELETE FROM github_installation_states;

CREATE INDEX github_installation_states_oauth_expiry
  ON github_installation_states(oauth_state_hash, expires_at, consumed_at);
CREATE UNIQUE INDEX github_installation_states_oauth_state
  ON github_installation_states(oauth_state_hash) WHERE oauth_state_hash IS NOT NULL;

PRAGMA foreign_key_check;
