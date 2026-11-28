CREATE TABLE mcp_oauth_clients (
  client_id TEXT PRIMARY KEY,
  client_name TEXT NOT NULL CHECK (length(client_name) BETWEEN 1 AND 100),
  redirect_uris_json TEXT NOT NULL CHECK (length(redirect_uris_json) BETWEEN 2 AND 32768),
  created_at INTEGER NOT NULL,
  revoked_at INTEGER
);

CREATE TABLE mcp_oauth_registration_limits (
  ip_hash TEXT NOT NULL CHECK (length(ip_hash) = 64),
  period_day TEXT NOT NULL CHECK (length(period_day) = 10),
  registration_count INTEGER NOT NULL CHECK (registration_count BETWEEN 1 AND 200),
  PRIMARY KEY (ip_hash, period_day)
);

CREATE TABLE mcp_oauth_authorization_requests (
  consent_hash TEXT PRIMARY KEY CHECK (length(consent_hash) = 64),
  client_id TEXT NOT NULL,
  redirect_uri TEXT NOT NULL CHECK (length(redirect_uri) BETWEEN 1 AND 2048),
  client_state TEXT NOT NULL CHECK (length(client_state) BETWEEN 1 AND 512),
  code_challenge TEXT NOT NULL CHECK (length(code_challenge) = 43),
  scope TEXT NOT NULL CHECK (length(scope) BETWEEN 1 AND 128),
  resource TEXT NOT NULL CHECK (length(resource) BETWEEN 1 AND 512),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  github_state_hash TEXT UNIQUE,
  consumed_at INTEGER,
  CHECK (expires_at > created_at)
);

CREATE INDEX mcp_oauth_authorization_requests_expiry
  ON mcp_oauth_authorization_requests(expires_at, consumed_at);

CREATE TABLE mcp_oauth_authorization_codes (
  code_hash TEXT PRIMARY KEY CHECK (length(code_hash) = 64),
  client_id TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  redirect_uri TEXT NOT NULL CHECK (length(redirect_uri) BETWEEN 1 AND 2048),
  code_challenge TEXT NOT NULL CHECK (length(code_challenge) = 43),
  scope TEXT NOT NULL CHECK (length(scope) BETWEEN 1 AND 128),
  resource TEXT NOT NULL CHECK (length(resource) BETWEEN 1 AND 512),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER,
  exchange_id TEXT,
  CHECK (expires_at > created_at)
);

CREATE INDEX mcp_oauth_authorization_codes_expiry
  ON mcp_oauth_authorization_codes(expires_at, consumed_at);

CREATE TABLE mcp_oauth_tokens (
  token_hash TEXT PRIMARY KEY CHECK (length(token_hash) = 64),
  token_type TEXT NOT NULL CHECK (token_type IN ('access', 'refresh')),
  client_id TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  scope TEXT NOT NULL CHECK (length(scope) BETWEEN 1 AND 128),
  resource TEXT NOT NULL CHECK (length(resource) BETWEEN 1 AND 512),
  family_id TEXT NOT NULL CHECK (length(family_id) = 32),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER,
  revoked_at INTEGER,
  rotation_id TEXT,
  CHECK (expires_at > created_at)
);

CREATE INDEX mcp_oauth_tokens_owner_client
  ON mcp_oauth_tokens(owner_id, client_id, token_type, revoked_at, expires_at);
CREATE INDEX mcp_oauth_tokens_family
  ON mcp_oauth_tokens(family_id, token_type, revoked_at);

PRAGMA foreign_key_check;
