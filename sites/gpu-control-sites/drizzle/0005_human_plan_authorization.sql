-- A browser-confirmed, short-lived approval is bound to one immutable plan.
-- Challenge tokens are stored only as SHA-256 hashes and consumed on form POST.
CREATE TABLE authorization_challenges (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  plan_id TEXT NOT NULL UNIQUE REFERENCES plans(id),
  fingerprint TEXT NOT NULL CHECK (fingerprint GLOB '[0-9a-f]*' AND length(fingerprint) = 64 AND fingerprint NOT GLOB '*[^0-9a-f]*'),
  token_hash TEXT NOT NULL UNIQUE CHECK (token_hash GLOB '[0-9a-f]*' AND length(token_hash) = 64 AND token_hash NOT GLOB '*[^0-9a-f]*'),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER
);

CREATE TABLE human_authorizations (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  plan_id TEXT NOT NULL UNIQUE REFERENCES plans(id),
  fingerprint TEXT NOT NULL CHECK (fingerprint GLOB '[0-9a-f]*' AND length(fingerprint) = 64 AND fingerprint NOT GLOB '*[^0-9a-f]*'),
  authorization_reference TEXT NOT NULL UNIQUE,
  authorized_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER,
  CHECK (expires_at > authorized_at),
  CHECK (expires_at - authorized_at <= 900)
);

CREATE INDEX human_authorizations_owner_expiry
  ON human_authorizations(owner_id, expires_at);

PRAGMA foreign_key_check;
