-- A durable account-wide RunPod allocation lease. The account scope is an
-- HMAC digest, never a RunPod credential or raw operator scope identifier.
-- Leases have no time-based expiry: uncertain submission and cleanup continue
-- to block allocation until an explicit, evidence-backed release.
CREATE TABLE provider_account_leases (
  provider TEXT NOT NULL CHECK (provider = 'runpod'),
  account_scope_sha256 TEXT NOT NULL
    CHECK (account_scope_sha256 GLOB '[0-9a-f]*' AND length(account_scope_sha256) = 64 AND account_scope_sha256 NOT GLOB '*[^0-9a-f]*'),
  generation INTEGER NOT NULL CHECK (generation >= 1),
  revision INTEGER NOT NULL CHECK (revision >= 1),
  lease_token TEXT NOT NULL UNIQUE
    CHECK (lease_token GLOB '[0-9a-f]*' AND length(lease_token) = 64 AND lease_token NOT GLOB '*[^0-9a-f]*'),
  run_id TEXT NOT NULL REFERENCES runs(id),
  owner_id TEXT NOT NULL,
  plan_fingerprint TEXT NOT NULL
    CHECK (plan_fingerprint GLOB '[0-9a-f]*' AND length(plan_fingerprint) = 64 AND plan_fingerprint NOT GLOB '*[^0-9a-f]*'),
  authorization_id TEXT NOT NULL REFERENCES human_authorizations(id),
  challenge_sha256 TEXT NOT NULL
    CHECK (challenge_sha256 GLOB '[0-9a-f]*' AND length(challenge_sha256) = 64 AND challenge_sha256 NOT GLOB '*[^0-9a-f]*'),
  state TEXT NOT NULL CHECK (state IN ('reserved', 'submitting', 'uncertain', 'active', 'cleanup_pending', 'released')),
  provider_job_id TEXT,
  release_evidence_type TEXT,
  release_evidence_sha256 TEXT
    CHECK (release_evidence_sha256 IS NULL OR (release_evidence_sha256 GLOB '[0-9a-f]*' AND length(release_evidence_sha256) = 64 AND release_evidence_sha256 NOT GLOB '*[^0-9a-f]*')),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  released_at INTEGER,
  PRIMARY KEY (provider, account_scope_sha256),
  CHECK (state NOT IN ('active', 'cleanup_pending') OR (provider_job_id IS NOT NULL AND length(provider_job_id) BETWEEN 1 AND 128)),
  CHECK (state NOT IN ('reserved', 'submitting', 'uncertain') OR provider_job_id IS NULL),
  CHECK ((state = 'released') = (release_evidence_type IS NOT NULL AND release_evidence_sha256 IS NOT NULL AND released_at IS NOT NULL))
);

-- A run cannot hold multiple provider-account leases at once. A released row
-- can be replaced for a later generation of the same account scope.
CREATE UNIQUE INDEX provider_account_leases_one_active_per_run
  ON provider_account_leases(run_id) WHERE state <> 'released';
CREATE UNIQUE INDEX provider_account_leases_provider_job
  ON provider_account_leases(provider, provider_job_id) WHERE provider_job_id IS NOT NULL;

CREATE TABLE provider_account_lease_events (
  event_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  account_scope_sha256 TEXT NOT NULL,
  generation INTEGER NOT NULL CHECK (generation >= 1),
  revision INTEGER NOT NULL CHECK (revision >= 1),
  run_id TEXT NOT NULL,
  from_state TEXT CHECK (from_state IS NULL OR from_state IN ('reserved', 'submitting', 'uncertain', 'active', 'cleanup_pending', 'released')),
  to_state TEXT NOT NULL CHECK (to_state IN ('reserved', 'submitting', 'uncertain', 'active', 'cleanup_pending', 'released')),
  evidence_type TEXT NOT NULL,
  evidence_sha256 TEXT NOT NULL
    CHECK (evidence_sha256 GLOB '[0-9a-f]*' AND length(evidence_sha256) = 64 AND evidence_sha256 NOT GLOB '*[^0-9a-f]*'),
  created_at INTEGER NOT NULL,
  UNIQUE (provider, account_scope_sha256, generation, revision),
  FOREIGN KEY (provider, account_scope_sha256)
    REFERENCES provider_account_leases(provider, account_scope_sha256)
);

CREATE INDEX provider_account_lease_events_run
  ON provider_account_lease_events(run_id, created_at);

CREATE TRIGGER provider_account_lease_events_no_update
  BEFORE UPDATE ON provider_account_lease_events
  BEGIN SELECT RAISE(ABORT, 'provider_account_lease_events is append-only'); END;
CREATE TRIGGER provider_account_lease_events_no_delete
  BEFORE DELETE ON provider_account_lease_events
  BEGIN SELECT RAISE(ABORT, 'provider_account_lease_events is append-only'); END;
