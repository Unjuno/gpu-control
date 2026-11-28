-- Retain bounded terminal metadata in the product ledger so a provider-side
-- dispatch journal expiry cannot erase the only durable run result.
ALTER TABLE training_plans ADD COLUMN provider_result_json TEXT
  CHECK (provider_result_json IS NULL OR
    (length(provider_result_json) <= 65536 AND json_valid(provider_result_json)));
