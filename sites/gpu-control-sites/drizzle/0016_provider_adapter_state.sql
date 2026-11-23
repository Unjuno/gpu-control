-- Durable provider-adapter state. The historical table name is retained for a
-- forward-only migration of the already deployed D1 database.
ALTER TABLE gateway_delegated_plans ADD COLUMN provider_handle_json TEXT;
ALTER TABLE gateway_delegated_plans ADD COLUMN provider_state TEXT;
ALTER TABLE gateway_delegated_plans ADD COLUMN provider_response_json TEXT;
ALTER TABLE gateway_delegated_plans ADD COLUMN updated_at INTEGER;

CREATE INDEX IF NOT EXISTS idx_gateway_delegated_plans_provider_state
  ON gateway_delegated_plans(owner_id, provider_state, updated_at DESC);
