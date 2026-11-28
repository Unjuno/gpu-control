-- Keep the owner's Colab quota attestation with the exact delegated plan
-- authorization. Existing provider authorizations are intentionally false.
ALTER TABLE gateway_delegated_authorizations
  ADD COLUMN positive_compute_units_attested INTEGER NOT NULL DEFAULT 0
  CHECK (positive_compute_units_attested IN (0, 1));

PRAGMA foreign_key_check;
