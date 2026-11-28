ALTER TABLE github_app_installations
  ADD COLUMN user_authorized_repositories_json TEXT NOT NULL DEFAULT '[]'
  CHECK (length(user_authorized_repositories_json) <= 65536);

-- Existing bindings did not retain the authenticated user's repository scope.
-- Reconnect them instead of treating app-installation scope as user access.
DELETE FROM github_app_installations;

PRAGMA foreign_key_check;
