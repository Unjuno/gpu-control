# Architecture refactoring progress

This is the execution log for the architecture task pool in
[`refactoring-backlog.md`](refactoring-backlog.md). Each entry records source
work separately from merge, deployment, provider configuration and live
experiment acceptance.

## 2026-11-28 — A5: shared Modal compute reservation

**Goal:** prevent independent Modal CPU, fixed GPU and training routes from
each spending their own full Sites-side allowance during ordinary ChatGPT
experiments.

**Changes in the PR #70 source candidate:**

- Added `modal_compute_budget_policy` and
  `modal_compute_budget_reservations` as the shared Sites D1 source for Modal
  CPU/GPU workload reservation; the policy is $30 per UTC month and $1 per run.
- Added forward migration `0032_modal_compute_budget.sql`; it carries forward
  old Modal CPU, fixed GPU and claimed training reservations and removes only
  the obsolete Modal route-specific ledgers. RunPod's ledger stays independent.
- Made MAP and owner-selected training reserve their plan ceilings in the same
  D1 batch as the authorization-bound dispatch claim. Made fixed Modal GPU
  claim and reservation atomic. Failed or closed claims remove unclaimed rows.
- Moved Modal CPU reservation after successful provider health and into the
  same batch as its authorization and run claim. A failed health probe no
  longer consumes workload budget.
- Added current-month reserved and remaining values to read-only provider
  capabilities. These values are reservation ceilings, not reported billing.
- Added ADR 0005 and clarified that Modal control-function fees, external
  provider charges and other account activity are outside this Sites ledger.

**Local evidence:** Sites Worker architecture check, workload registry drift
check, 114 Worker tests, migration-forward test, build and artifact validation
passed. The complete Python suite passed (615 passed, 1 skipped, 5 subtests).
Exact-head CI initially caught a stale migration filename expectation; the
expectation now includes `0032_modal_compute_budget.sql`. The focused test and
full Python suite pass locally. No provider was called and no live D1, admission
flag, account limit or deployed Site was changed.

**Status:** source batch is committed and pushed to PR #70. GitHub CI is rerunning
after the migration expectation fix. Independent code review and live
migration/deployment acceptance remain pending. Parked policy remains in force.

## Open product path

The primary product outcome remains ordinary ChatGPT conversation selecting
the user's intended compatible external compute route, running the exact
authorized experiment, and returning verified results and cleanup. The
repository-wide backlog remains open. In particular, A1's current ChatGPT
end-to-end external-GPU acceptance, A3 lifecycle reconciliation, A4 legacy
Gateway disposition, A6 Colab lifecycle integration, and A7–A12 architecture
normalization and guardrails are not complete.
