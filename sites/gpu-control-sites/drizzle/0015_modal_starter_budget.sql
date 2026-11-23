-- Match the provider-side Starter workspace limit observed on 2026-11-20.
-- This is a defensive internal ceiling, not a claim that credits are free or
-- that Modal will permit the full amount at execution time.
UPDATE provider_budget_policies
SET monthly_limit_microusd = 1000000,
    updated_at = 0
WHERE provider = 'modal_cpu';
