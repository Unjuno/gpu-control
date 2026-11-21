-- The legacy max_cost_usd column is constrained to the original Modal CPU
-- values.  Keep it for historical rows and add one provider-neutral integer
-- ceiling so Runpod plans can express the reviewed $1 loss ceiling without a
-- destructive table rebuild or floating-point comparisons.
ALTER TABLE plans ADD COLUMN provider_cost_ceiling_microusd INTEGER
  CHECK (provider_cost_ceiling_microusd IS NULL OR provider_cost_ceiling_microusd BETWEEN 0 AND 1000000);

UPDATE plans SET provider_cost_ceiling_microusd =
  CASE max_cost_usd WHEN '0.01' THEN 10000 ELSE 0 END
WHERE provider_cost_ceiling_microusd IS NULL;

PRAGMA foreign_key_check;
