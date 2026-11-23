CREATE TABLE runpod_reconciliation_heartbeat (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  owner_id TEXT NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 256),
  checked_at INTEGER NOT NULL CHECK (checked_at >= 0)
);

PRAGMA foreign_key_check;
