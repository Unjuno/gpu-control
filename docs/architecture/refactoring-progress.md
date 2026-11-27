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

**Status:** source and migration-test batches are committed and pushed to PR #70.
Exact-head CI passed on `99e332626eed1ccc4c12cee83ece45034d9b3d19` across Python
3.11–3.13, Sites/D1, Gateway, project bridge and trusted-reference checks. The
initial failure was the stale filename expectation recorded above. Independent
code review and live migration/deployment acceptance remain pending. Parked
policy remains in force.

## 2026-11-28 — A1: remove a redundant custom-training tool hop

**Goal:** make the user-owned GitHub path straightforward for an agent to
operate from an ordinary ChatGPT request while keeping internal registration
IDs agent-carried.

**Changes:** `training_register`, capabilities, and `training_list` now direct
the agent to `training_preview`. Preview already performs the manifest and
hash-locked dependency checks from `training_inspect` and also validates current
runtime, GPU, quote, and budget. `training_inspect` remains available when the
user asks for details or the agent needs a separate diagnostic. The MCP tool
descriptions now explain this sequence and the shared Modal reservation ceiling
instead of describing retired route-local limits. Backlog evidence was updated
to the current 2,769-line Worker, 3,388-line test file, and 17-module dependency
check.

**Local evidence:** 114 Worker tests, migration-forward test, generated
registry/dependency check, build, and artifact validation passed. No external
provider was contacted; no production D1, admission, or deployment changed.

**Status:** committed and pushed to PR #70 as `9052881446c1e32194c84530663b652ed3089bd3`.
All exact-head checks passed: Python 3.11–3.13, Sites/D1 contract, Gateway, project
bridge, and trusted-reference container. Review and live admission/deployment
remain pending; repository mode remains parked.

## Open product path

The primary product outcome remains ordinary ChatGPT conversation selecting
the user's intended compatible external compute route, running the exact
authorized experiment, and returning verified results and cleanup. The
repository-wide backlog remains open. In particular, A1's current ChatGPT
end-to-end external-GPU acceptance, A3 lifecycle reconciliation, A4 legacy
Gateway disposition, A6 Colab lifecycle integration, and A7–A12 architecture
normalization and guardrails are not complete.

## 2026-11-28 — A7: make the MCP contract and Worker package graph explicit

**Goal:** reduce the Worker entrypoint's mixed responsibilities while ensuring
MCP tool definitions and production packaging have one clear authority.

**Changes:** moved input schemas, descriptions, output schema and MCP tool
annotations/list generation from `worker/index.js` into
`worker/mcp_tool_contract.js`. The entrypoint shrank from 2,769 to 2,564 lines.
Added one static import-graph scanner shared by the architecture check and the
build. Packaging now copies only the modules reachable from `index.js` and
fails if any runtime module is orphaned; this prevents future domain extraction
from silently producing an incomplete Site artifact. The dependency graph is
acyclic across 18 runtime modules.

**Local evidence:** all 114 Worker tests, generated workload registry check,
forward migration replay, Worker build and artifact import validation passed.
The built artifact imported successfully with all 18 runtime modules.

**Status:** implementation is local; exact-head CI, push and review remain
pending. No Site deployment, live D1 migration, provider change or experiment
was performed.
