-- Provider-neutral plan identity and bounded Runpod runtime state. Existing
-- Modal rows retain their behavior through the default provider value.
ALTER TABLE plans ADD COLUMN provider TEXT NOT NULL DEFAULT 'modal_cpu'
  CHECK (provider IN ('modal_cpu', 'runpod_gpu'));
ALTER TABLE plans ADD COLUMN provider_plan_json TEXT
  CHECK (provider_plan_json IS NULL OR (json_valid(provider_plan_json) AND length(provider_plan_json) <= 4096));

ALTER TABLE runs ADD COLUMN provider_job_id TEXT
  CHECK (provider_job_id IS NULL OR (length(provider_job_id) BETWEEN 4 AND 128 AND provider_job_id NOT GLOB '*[^A-Za-z0-9_-]*'));
ALTER TABLE runs ADD COLUMN provider_phase TEXT NOT NULL DEFAULT 'not_started'
  CHECK (provider_phase IN ('not_started', 'creating', 'provisioning', 'ready', 'executing', 'terminating', 'terminal', 'uncertain'));
ALTER TABLE runs ADD COLUMN provider_nonce TEXT
  CHECK (provider_nonce IS NULL OR (length(provider_nonce) = 64 AND provider_nonce NOT GLOB '*[^0-9a-f]*'));
ALTER TABLE runs ADD COLUMN provider_started_at INTEGER
  CHECK (provider_started_at IS NULL OR provider_started_at >= 0);
ALTER TABLE runs ADD COLUMN completion_key_id TEXT
  CHECK (completion_key_id IS NULL OR (length(completion_key_id) = 32 AND completion_key_id NOT GLOB '*[^0-9a-f]*'));
ALTER TABLE runs ADD COLUMN completion_key_iv_b64 TEXT
  CHECK (completion_key_iv_b64 IS NULL OR length(completion_key_iv_b64) BETWEEN 16 AND 32);
ALTER TABLE runs ADD COLUMN completion_key_ciphertext_b64 TEXT
  CHECK (completion_key_ciphertext_b64 IS NULL OR length(completion_key_ciphertext_b64) BETWEEN 64 AND 256);

CREATE UNIQUE INDEX runs_provider_job_id_unique
  ON runs(provider_job_id) WHERE provider_job_id IS NOT NULL;

PRAGMA foreign_key_check;
