# ADR 0005: Reserve one shared ceiling for Modal compute routes

- **Status:** proposed in PR #70; not deployed or runtime-accepted.
- **Date:** 2026-11-28
- **Supersedes:** ADR 0004's separate Modal CPU and GPU budget scopes.
- **Scope:** Sites D1 reservation accounting for Modal CPU/GPU workload compute.

## Context

The user-facing product needs a simple ChatGPT request to use the available
compute route without independently exhausting a nominal Modal allowance on
each route. Previously, Modal CPU, fixed Modal GPU canaries, MAP training and
owner-selected training each reserved against different ledgers. Concurrent
routes could therefore exceed the requested product-level provider ceiling.

Modal also hosts adapter functions that call Kaggle and Hugging Face. Those
control-function invocations have separate charges and are not represented by
the fixed workload cost reservations. The D1 policy must not be described as a
Modal account billing stop or as an all-in account spend total.

## Decision

1. A single D1 `modal_compute_budget_policy` defines the product-level Modal
   compute reservation limits: $30 per UTC month and $1 per run.
2. A single `modal_compute_budget_reservations` table records the maximum
   declared cost ceiling for Modal CPU inference, the fixed Modal GPU canary,
   MAP training and owner-selected training. Each insertion atomically checks
   the per-run limit and sum of that month's reservations.
3. Training reserves the exact stored plan ceiling in the same D1 batch as its
   one-time dispatch claim and authorization consumption. If the claim loses a
   race or admission closes before the claim, the reservation is removed in
   that transaction. A lost provider response retains the reservation while
   the same run is reconciled; it must not be resubmitted as a new run.
4. The existing MAP and owner-selected lane limits remain stricter upper bounds
   where configured. The shared Modal ceiling is additional and cannot be
   bypassed by choosing another Modal workload route.
5. RunPod remains independent: no Sites monthly cap is configured, and its
   per-run reservation remains $1. Kaggle and Hugging Face remain free-first
   policies with paid fallback disabled.
6. `experiment_capabilities` reports one Modal compute budget with scope
   `modal_compute_shared_across_routes`. Modal CPU and GPU still have separate
   route readiness and admission gates.
7. This is a Sites-side reservation ceiling, not a hard limit in Modal billing.
   It does not include Modal control-function invocations used by the Kaggle or
   Hugging Face adapters, external-provider charges, unrelated Modal jobs, or
   account-level usage outside this Sites D1. Provider account billing and any
   provider-native spending controls remain separate.
8. Migration `0032_modal_compute_budget.sql` carries forward reservations from
   the previous Modal CPU, fixed GPU and claimed training ledgers before
   removing the redundant route-specific ledgers. RunPod reservations remain
   in their existing independent table.

## Consequences

- One Modal route cannot use a full independent allowance alongside another
  route; every accepted plan reserves against the same month and per-run cap.
- The reservation sum is deliberately conservative: it counts each run's
  declared maximum, not provider-reported actual spend. This prevents
  concurrent oversubscription but can leave unused headroom after a cheap or
  rejected run until the reservation period rolls over.
- Existing route-specific admission, owner authorization, exact-plan checks,
  provider lifecycle, result verification and cleanup remain required.
- The budget is advisory product accounting and admission control. It does not
  cap charges incurred by other services or provide billing protection by
  itself.

## Evidence and limits

- Policy and reservation SQL: `worker/provider_budget_policy.js`.
- Forward migration and historical reservation copy:
  `drizzle/0032_modal_compute_budget.sql`.
- Training claim/authorization/reservation transaction:
  `worker/training_plan.js`.
- Fixed Modal CPU claim transaction: `worker/index.js`.
- Tests cover policy projection, shared reservation limits, migration history,
  and cleanup of unclaimed reservations. No provider account, live D1,
  admission switch, deployed Site or experiment was changed by this batch.
