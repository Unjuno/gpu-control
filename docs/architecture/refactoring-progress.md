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

**Validation correction:** exact-head CI caught a Skill contract test that
read tool names from the old `index.js` location. The test now reads the
authoritative `mcp_tool_contract.js`; the focused test and complete Python suite
(615 passed, 1 skipped, 5 subtests) pass locally.

**Status:** implementation and test correction were pushed to PR #70; all seven
exact-head CI checks passed on `ae9b96347864cdfa93574c43738dad0213bbb58b`. PR #70
remains open, blocked on required review. No Site deployment, live D1 migration,
provider change or experiment was performed.

## 2026-11-28 — A0: repair the public source/release documentation boundary

**Goal:** prevent old hosted-state notes from being mistaken for the current
Site and keep the documented chat journey aligned with PR #70 source.

**Changes:** relabeled the November 14 provider/environment section as a dated,
unrefreshed historical snapshot; replaced the obsolete PR #68 approval passage
with the current PR #70 source/deployment distinction; updated migration,
Modal adapter, selected-repository, tool-contract and build descriptions; and
refreshed the architecture map to identify `mcp_tool_contract.js` as the MCP
contract authority.

**Evidence:** PR #70 source head `ae9b96347864cdfa93574c43738dad0213bbb58b` had all
seven required CI checks pass. This documentation-only follow-up changes no
runtime files and does not claim deployment or live provider readiness.

## 2026-11-28 — Product alignment: chat-first external compute

**Goal:** keep repository-wide architecture work anchored to the actual user
outcome: ask ChatGPT to try an experiment in normal conversation and have the
agent use a real compatible external GPU without exposing internal IDs or
provider API details.

**Decision:** recorded in ADR 0006. “GPU configured” and “this owner-selected
repository can execute on that GPU” are distinct capabilities. Modal is the
first source lane in PR #70; RunPod arbitrary-source execution is the next
required route. Kaggle and Hugging Face fixed workloads remain limited to their
declared workload contracts, and Colab must join the same Sites lifecycle
before it is described as an integrated GPU Control provider. The user-facing
workflow stays provider-neutral and selects only currently compatible routes
within the owner's separate provider authorization and budget.

**Current gap:** no single owner-selected repository can yet be routed across
the external GPU providers. RunPod, Kaggle and Hugging Face fixed-workload
support does not satisfy that gap. PR #70 remains an unmerged, undeployed
candidate and repository activation remains parked.

**Independent review:** the Codex Security diff-review setup validated the
worktree and exact `main...a2f5bae` range, but the scan launcher then rejected
the non-bare-worktree request despite the target being a valid linked Git
worktree. No security result was produced; the plugin review is not complete.
The review must be retried through a supported target before this batch is
reported as independently reviewed. No provider, Site, D1, admission or secret
state was changed.
