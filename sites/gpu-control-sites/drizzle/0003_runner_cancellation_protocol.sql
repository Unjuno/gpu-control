ALTER TABLE runner_heartbeats
  ADD COLUMN cancellation_protocol INTEGER NOT NULL DEFAULT 0
  CHECK (cancellation_protocol IN (0, 1));
