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
exact `05958170...812ed0c` range in both the linked worktree and two standalone
clones, but the scan launcher rejected each valid non-bare Git worktree with
`Review changes requires a non-bare Git worktree with a resolvable HEAD`. No
security result was produced; the plugin review is not complete.

**Updated release evidence:** GitHub reports all seven checks successful on
head `812ed0c8c1e120beae46ba7c23a3bac7d0fb0987`: Python 3.11, 3.12, and 3.13;
Sites Worker and D1 contract; Gateway; Project bridge; and Trusted reference
container. PR #70 is still open and merge-blocked. Its net diff is 100 files
(+10,024/−349), which makes focused, independently reviewable change batches a
priority. The current head remains source only: no Site deployment, D1
migration, admission change, provider call, experiment, or secret operation
occurred in this batch.

## 2026-11-28 — A1 security and runtime-boundary correction

**Goal:** make the owner-selected GitHub-to-Modal source lane safe enough to
continue toward ordinary ChatGPT use, while closing independently reproduced
account-binding, resource-cap and artifact-routing gaps.

**Changes:** replaced installation-ID-only linking with a one-time, owner-bound
GitHub OAuth flow using state and PKCE; verified that the GitHub user token can
access the exact selected installation; discarded the token without persisting
it; and added migration 0033 to invalidate prior unverified installation
bindings. Installation access tokens now send GitHub's expected repository
name and verify the returned full repository identity. Modal staging and GPU
Sandboxes now use explicit CPU/memory request-limit tuples. Staged wheels are
readable by the unprivileged training user, wheel downloads target the manifest
Python ABI, and the Worker delegation allowlist includes declared
training_artifact retrieval. Added ADR 0007 and documented OAuth configuration
and the one-time reconnect consequence.

**Local evidence:** 117 Worker tests, acyclic 18-module graph, registry drift
check, forward migration replay, Sites build and artifact validation pass.
Modal Python tests pass with test_map_training_backend.py excluded locally
because this workspace lacks the Modal SDK; CI has a dedicated SDK-backed
test for it. No provider, production D1, account setting or deployment was
changed, and no experiment was started.

**Status:** code batch committed as ed76b405039f8b0c737ccce46e1e55b9caf51441
and pushed to PR #70. The PR is open and unmerged; all seven exact-head checks
were queued at that batch's last read. The independent security scan remains
incomplete; the local scanner has previously rejected valid worktrees without
producing results. Migration/deployment, GitHub OAuth hosted-flow test,
admission, real external-GPU acceptance, and end-to-end ChatGPT verification
remain release gates. Repository mode remains parked.

## 2026-11-28 — A0: refresh exact PR and release evidence

**Goal:** keep the architecture record aligned with the actual GitHub head and
the user's core product requirement: ordinary ChatGPT conversation must reach
authorized external GPU compute when the experiment needs it. A CPU container
route or a fixed-workload provider canary is not equivalent acceptance.

**Evidence refreshed:** PR #70 is open and unmerged at
`3c1f3a964bccea7d7a488e85c841c9d25c832fa9`; GitHub reports `mergeable: true`.
All seven checks on that exact head remain queued. The latest inline
review-thread read returned zero unresolved threads. PR metadata records a
107-file diff (+10,768/−501). The candidate only implements owner-selected arbitrary source
execution on Modal GPU; RunPod remains a fixed canary, Kaggle/Hugging Face remain
fixed-workload routes, and Colab is not integrated. The candidate is unmerged,
undeployed, and the repository remains parked.

**Change:** refreshed A0 and the repository-map release header so mergeability,
review, CI, deployment, and provider acceptance are described as separate
facts. The product outcome and external-GPU acceptance boundary remain explicit.

**Validation:** read-only GitHub PR/check/review-thread queries and local
worktree/commit inspection. No provider, production D1, credentials, admission,
deployment, or experiment was touched.

**Status:** the documentation refresh was committed as `7c6ec6d`, followed by
two A7 source batches (`118ef2e` and `3c1f3a9`) and pushed to PR #70. The
current source head remains a candidate, not a complete or deployed product.
The exact-head CI is queued. Next priority is continue A1/A3 and repository-wide
architecture batches against the actual ChatGPT-to-external-GPU lifecycle.
Do not represent PR #70 as a complete product.

## 2026-11-28 — A7: isolate exact MCP input validation

**Goal:** make the Sites entrypoint compose domain behavior rather than own
provider-aware request contracts, while preserving the existing public MCP
schema and strict owner/plan-bound runtime checks.

**Change:** moved the experiment and training runtime argument validators,
registered workload normalization, and provider-approved-plan validation from
`worker/index.js` into `worker/experiment_input_contract.js`. The module owns
the exact environment-bound validation seam and imports provider plan
validators; RunPod's approved-plan validator now lives beside its plan contract
in `worker/runpod_plan.js` and is re-exported by the lifecycle module for its
existing module callers. `mcp_tool_contract.js` continues to own the
client-visible JSON Schemas, descriptions and annotations. Existing external
tool names and payloads are unchanged. Also moved selected-repository
verification and short-lived read-token minting behind
`github_app_connection.js`; the Site entrypoint now supplies only the
owner-bound source-token port. The Worker entrypoint is 2,392 lines, 220 fewer
than the 2,612-line baseline; the input-contract extraction accounts for 211
lines of that reduction. The acyclic runtime graph increased from 18 to 19
modules.

**Validation:** all 118 Worker tests pass; the acyclic 19-module architecture
and generated registry checks pass; forward migration replay passes; the Site
build copies the complete reachable module graph; and artifact validation
passes. No provider or production operation was performed.

**Status:** implementation and architecture documentation are validated; the
changes were committed and pushed as `118ef2e` (contract extraction) and
`3c1f3a9` (owner-scoped source-token boundary). PR #70 exact-head CI is queued
on `3c1f3a9`.

## 2026-11-28 — A7: move GitHub MCP operations out of the composition root

**Goal:** keep `index.js` responsible for authenticated transport composition
while the GitHub source domain owns its user-facing tool workflow.

**Change:** moved GitHub connection start/status/disconnect and selected-
repository listing into `worker/github_tools.js`. `index.js` now routes those
tool names through the domain boundary and passes owner-scoped token issuance
to the training tools as a narrow source-read callback. Existing public MCP
names, response shapes, owner checks and callback/web OAuth routes are retained.

**Validation:** 118 Worker tests pass, including authenticated GitHub tool
dispatch and repository access; the import graph is acyclic across 20 reachable
modules. Migration replay and artifact build/validation are to be rerun before
this batch is committed. No provider call or production setting was changed.

**Status:** source and documentation changes are local and uncommitted. PR #70's
current remote head is `3c1f3a9`; the latest exact-head CI remained queued. The
candidate still exposes arbitrary owner-source execution only on Modal GPU and
does not meet the multi-provider acceptance requirement.
