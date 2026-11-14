CREATE TABLE modal_health_check_limits (
    scope TEXT PRIMARY KEY CHECK (scope = 'workspace'),
    last_checked_at INTEGER NOT NULL CHECK (last_checked_at >= 0)
);
