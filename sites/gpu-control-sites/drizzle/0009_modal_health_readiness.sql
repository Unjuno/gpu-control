ALTER TABLE modal_authorized_health_checks
  ADD COLUMN ready INTEGER NOT NULL DEFAULT 0 CHECK (ready IN (0, 1));

PRAGMA foreign_key_check;
