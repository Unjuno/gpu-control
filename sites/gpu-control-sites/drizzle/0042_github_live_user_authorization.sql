ALTER TABLE github_app_installations
  ADD COLUMN access_token_ciphertext TEXT NOT NULL DEFAULT ''
  CHECK (length(access_token_ciphertext) <= 8192);
ALTER TABLE github_app_installations
  ADD COLUMN access_token_iv TEXT NOT NULL DEFAULT ''
  CHECK (length(access_token_iv) <= 64);
ALTER TABLE github_app_installations
  ADD COLUMN refresh_token_ciphertext TEXT NOT NULL DEFAULT ''
  CHECK (length(refresh_token_ciphertext) <= 8192);
ALTER TABLE github_app_installations
  ADD COLUMN refresh_token_iv TEXT NOT NULL DEFAULT ''
  CHECK (length(refresh_token_iv) <= 64);
ALTER TABLE github_app_installations
  ADD COLUMN access_token_expires_at INTEGER NOT NULL DEFAULT 0;
ALTER TABLE github_app_installations
  ADD COLUMN refresh_token_expires_at INTEGER NOT NULL DEFAULT 0;

-- Existing rows contain only a stale authorization snapshot. Reconnect so every
-- source read can be authorized against the user's current GitHub permissions.
DELETE FROM github_app_installations;

PRAGMA foreign_key_check;
