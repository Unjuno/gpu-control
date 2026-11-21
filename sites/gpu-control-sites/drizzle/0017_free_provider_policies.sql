-- Kaggle and Hugging Face are separate provider policies even though their
-- registered routes are free-only.  A zero-cost authorization is persisted
-- before Sites contacts the adapter so a missing/changed policy fails closed.
CREATE TABLE provider_free_policies (
  provider TEXT PRIMARY KEY CHECK (provider IN ('kaggle', 'huggingface_space')),
  max_cost_microusd INTEGER NOT NULL DEFAULT 0 CHECK (max_cost_microusd = 0),
  paid_fallback_allowed INTEGER NOT NULL DEFAULT 0 CHECK (paid_fallback_allowed = 0),
  updated_at INTEGER NOT NULL CHECK (updated_at >= 0)
);

INSERT INTO provider_free_policies
  (provider, max_cost_microusd, paid_fallback_allowed, updated_at)
VALUES
  ('kaggle', 0, 0, 0),
  ('huggingface_space', 0, 0, 0);

CREATE TABLE provider_free_run_authorizations (
  run_id TEXT PRIMARY KEY REFERENCES gateway_delegated_plans(id) ON DELETE CASCADE,
  provider TEXT NOT NULL REFERENCES provider_free_policies(provider),
  plan_fingerprint TEXT NOT NULL CHECK (
    length(plan_fingerprint) = 64 AND plan_fingerprint NOT GLOB '*[^0-9a-f]*'
  ),
  authorized_microusd INTEGER NOT NULL DEFAULT 0 CHECK (authorized_microusd = 0),
  created_at INTEGER NOT NULL CHECK (created_at >= 0)
);

CREATE INDEX provider_free_run_authorizations_provider
  ON provider_free_run_authorizations(provider, created_at);

PRAGMA foreign_key_check;
