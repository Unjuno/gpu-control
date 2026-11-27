# ADR 0004: D1 provider budget policy is authoritative for capability display

- **Status:** superseded by ADR 0005; historical source decision retained.
- **Date:** 2026-11-28
- **Scope:** Sites capability projection and provider-specific budget readiness.

## Context

`experiment_capabilities` duplicated provider budget amounts as constants while
execution reservation read D1 policy tables. The copies diverged: the capability
response reported a $1 Modal CPU monthly limit while the D1 policy held $30.
Stale limits mislead the agent about whether a provider is available and how
much it may spend.

## Decision

1. D1 provider policy rows used by registered-workload reservation are the
   authority for that ChatGPT-facing budget projection. Sites reads those
   rows through the read-only `provider_budget_policy.js` module.
2. The projection is provider-specific and versioned. Modal CPU and Modal GPU
   are distinct execution routes under the shared Modal compute policy; RunPod,
   Kaggle and Hugging Face retain their own provider policies. A null RunPod
   monthly limit means no product-level monthly cap, not that the provider is
   free.
3. Missing, malformed or contradictory rows produce `state=unavailable`, omit
   monetary values and disable runnable capability claims. The projection
   never supplies fallback numbers.
4. Modal GPU is runnable only when both the existing environment admission
   switch and the D1 `admission_enabled` bit are enabled. This projection does
   not change either gate.
5. Sites replaces a nested adapter budget copy in the public response with its
   own D1 projection, preventing the downstream copy from appearing
   authoritative.
6. Owner-selected training originally used a separate dispatch ledger. ADR 0005
   replaces that design with a shared Modal compute reservation ledger.

## Consequences

- Capability terms now match the policy rows consulted by registered-route
  reservation, and the previously observed Modal CPU discrepancy is removed.
- An unavailable ledger is visible as a blocker before prepare or submit.
- This ADR did not establish a cross-route spend ceiling. See ADR 0005 for the
  shared compute reservation scope and its exclusions.
- Adapter and workload details such as runtime compatibility, current quotes,
  control-plane charges and execution evidence remain separate contract work;
  this ADR does not make any provider generally usable.

## Evidence and limits

- Projection and validation: `sites/gpu-control-sites/worker/provider_budget_policy.js`.
- Historical reservation policy tables: migrations `0013_provider_budgets.sql`,
  `0017_free_provider_policies.sql` and `0020_modal_gpu_budget.sql`.
- Focused unit tests cover expected seeded policy values and fail-closed
  handling. Worker tests do not prove a hosted D1 contains the migrations or
  the expected current rows. No production policy, admission, deployment or
  provider account setting was changed.
