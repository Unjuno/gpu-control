-- The GitHub App OAuth callback proves both control of the selected
-- installation and the immutable GitHub account behind that authorization.
-- Keep this reusable client-auth identity separate from the App installation
-- record so the two ownership concepts have explicit authorities.
CREATE TABLE github_owner_identities (
  owner_id TEXT PRIMARY KEY,
  github_user_id TEXT NOT NULL UNIQUE CHECK (
    length(github_user_id) BETWEEN 1 AND 20 AND
    github_user_id NOT GLOB '*[^0-9]*' AND substr(github_user_id, 1, 1) BETWEEN '1' AND '9'
  ),
  verified_at INTEGER NOT NULL
);

PRAGMA foreign_key_check;
