-- Permit one billed Modal health probe only after the owner confirms that exact plan.
CREATE TABLE modal_authorized_health_checks (
  plan_id TEXT PRIMARY KEY REFERENCES plans(id),
  owner_id TEXT NOT NULL,
  fingerprint TEXT NOT NULL CHECK (fingerprint GLOB '[0-9a-f]*' AND length(fingerprint) = 64 AND fingerprint NOT GLOB '*[^0-9a-f]*'),
  checked_at INTEGER NOT NULL CHECK (checked_at >= 0)
);

CREATE INDEX modal_authorized_health_checks_owner_checked
  ON modal_authorized_health_checks(owner_id, checked_at);

PRAGMA foreign_key_check;
