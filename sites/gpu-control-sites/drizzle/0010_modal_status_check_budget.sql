CREATE TABLE modal_status_check_limits (
  scope TEXT PRIMARY KEY CHECK (scope = 'workspace'),
  window_started_at INTEGER NOT NULL CHECK (window_started_at >= 0),
  last_checked_at INTEGER NOT NULL CHECK (last_checked_at >= 0),
  call_count INTEGER NOT NULL CHECK (call_count BETWEEN 1 AND 20)
);

PRAGMA foreign_key_check;
