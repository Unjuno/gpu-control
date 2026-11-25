-- Forward-only lifecycle metadata. These columns preserve the deployed D1
-- schema while making cancellation, parent-run provenance, and terminal order
-- explicit. Status polling must not move a completed run in the history.
ALTER TABLE gateway_delegated_plans ADD COLUMN cancelled_at INTEGER;
ALTER TABLE gateway_delegated_plans ADD COLUMN terminal_at INTEGER;
ALTER TABLE gateway_delegated_plans ADD COLUMN source_run_id TEXT;
ALTER TABLE gateway_delegated_plans ADD COLUMN submit_attempted_at INTEGER;
ALTER TABLE runs ADD COLUMN completed_at INTEGER;

UPDATE gateway_delegated_plans
  SET terminal_at=COALESCE(updated_at, created_at)
  WHERE provider_state IN ('succeeded', 'failed', 'cancelled') AND terminal_at IS NULL;
UPDATE runs SET completed_at=updated_at
  WHERE state IN ('succeeded', 'failed', 'cancelled') AND completed_at IS NULL;

CREATE TRIGGER gateway_delegated_terminal_at_once
AFTER UPDATE OF provider_state ON gateway_delegated_plans
WHEN NEW.provider_state IN ('succeeded', 'failed', 'cancelled') AND NEW.terminal_at IS NULL
BEGIN
  UPDATE gateway_delegated_plans SET terminal_at=COALESCE(NEW.updated_at, NEW.created_at)
    WHERE id=NEW.id AND owner_id=NEW.owner_id AND terminal_at IS NULL;
END;

CREATE TRIGGER runs_completed_at_once
AFTER UPDATE OF state ON runs
WHEN NEW.state IN ('succeeded', 'failed', 'cancelled') AND NEW.completed_at IS NULL
BEGIN
  UPDATE runs SET completed_at=NEW.updated_at WHERE id=NEW.id AND completed_at IS NULL;
END;

CREATE INDEX idx_gateway_delegated_parent_run
  ON gateway_delegated_plans(owner_id, source_run_id, created_at DESC);
