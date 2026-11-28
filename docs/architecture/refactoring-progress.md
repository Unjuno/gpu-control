# Architecture refactoring progress

This is the execution log for the architecture task pool in
[`refactoring-backlog.md`](refactoring-backlog.md). Each entry records source
work separately from merge, deployment, provider configuration and live
experiment acceptance.

## 2026-11-28 — A6: isolate Colab capability validation and projection

**Problem:** `google_colab_tools.js` owned OAuth/tool routing, provider-response
validation, and the public capability projection. That mixed the Sites use case
with Colab's external response contract and made later lifecycle work harder to
review independently.

**Change:** moved strict subscription/runtime validation and the minimal
capability projection into `worker/google_colab_capabilities.js`. The module
returns only tier, runtime counts, and allowlisted GPU spec fields; provider
tokens, URLs, and unrelated response fields cannot pass through. The tool
handler now owns orchestration and user-facing lifecycle status only.

**Validation:** the focused Colab capability tests and full Sites Worker suite
pass; the import graph remains acyclic across 33 runtime modules. No Google API,
OAuth configuration, runtime allocation, or provider setting was changed.

**Limit:** this is a read-only provider boundary. Colab still cannot be
prepared, submitted, monitored, cancelled, or cleaned up through the shared
Sites run lifecycle.

**Agent routing follow-up:** the public `experiment_capabilities` description
and operator Skill now direct Colab-specific requests to the separate
`colab_capabilities` read path and explicitly prohibit presenting CLI runs as
Sites-ledger runs. This closes the discovery/documentation gap without
advertising an unsupported submit route or silently switching providers.

**Quota semantics:** Google's current FAQ says paid accounts revert to free
tier restrictions after compute units are exhausted. The MCP still exposes no
remaining-unit balance or per-run quote. The capability response and provider
specification now distinguish subscription-quota availability from both
included-free execution and a dollar spending cap. GPU Control has no
additional-unit purchase or paid-provider fallback path.

**Client architecture:** the user-facing goal is not ChatGPT-only access.
ChatGPT chat/Work is the primary client; other authenticated MCP clients should
share the same owner-bound plan and run ledger. The official Colab CLI remains
standalone and its runs are outside GPU Control. The architecture docs now make
that distinction explicit and require any future client integration to reuse
the shared control-plane authorization and lifecycle rather than fork history.
This is a target contract, not evidence that a second client is already wired.

**A13 identity foundation:** migration `0035_github_owner_identity.sql` and
`github_app_connection.js` now persist the immutable numeric GitHub user ID
after the callback proves access to the exact selected installation. One
GitHub subject can bind to only one Sites owner, and an owner cannot silently
switch GitHub identities through a routine reconnect. Focused OAuth callback
and D1 migration checks pass. A14 now adds the OAuth authorization server and
scope/challenge path in source; deployment and external-client handshake
remain release gates.

## 2026-11-28 — A6: validate Colab capability responses at the provider boundary

**Problem:** the hosted Colab client bounded and parsed responses, but the
capability projection accepted loosely shaped runtime/spec arrays. These are
external provider facts used to choose a later execution plan, so malformed
resource identities should not be silently counted as current capacity.

**Change:** the Colab capability module now validates subscription tier,
runtime variant, accelerator, shape, eligibility and runtime resource name
before projecting GPU eligibility or active runtime counts. Runtime names,
proxy URLs and short-lived credentials remain outside the agent response.
Malformed or incomplete provider records fail closed with a stable error. The
capability contract also states that per-run cost and remaining quota are
unknown, and that no paid fallback is allowed; it cannot label an eligible GPU
as guaranteed free compute. The internal hosted-MCP client now allowlists only
the three read operations needed for capability discovery; runtime allocation,
session mutation and code execution are rejected until the owner-bound run
lifecycle exists.

**Validation:** 128 Sites Worker tests pass; the Worker module graph remains
acyclic across 31 modules; migration-forward tests, Worker build and artifact
validation pass; `git diff --check` passes. No Google request, OAuth setup,
runtime creation, provider configuration or deployment occurred.

**Limit:** this is a stricter read-only capability boundary. Colab still does
not have an exact plan, shared owner-run ledger lifecycle, execution, result
and artifact verification, cancellation or cleanup integration. It is not
yet an executable ChatGPT route.

## 2026-11-28 — A7: make canonical JSON serialization authoritative

**Problem:** plan identity, owner authorization, delegation signatures,
provider receipts, evidence checksums and stored plan comparisons each carried
their own recursive key-sorting serializer. Small semantic drift between those
copies could make equivalent plans compare differently or change signed bytes.

**Change:** added `worker/canonical_json.js` as the single Worker serializer
and migrated the Sites entrypoint, training plan, RunPod plan/lifecycle/result,
Modal account evidence, provider adapter signing, and experiment input
validation. Callers may supply their stable domain error code while the byte
representation remains one implementation. Existing exported adapter helper
and data formats remain compatible.

**Validation:** all 130 Sites Worker tests pass, including completion signing,
RunPod plan identity, delegated authorization and Modal evidence tests; the
32-module graph is acyclic; migration tests, Worker build and artifact checks
pass. No deployed rows or external provider state changed.

## 2026-11-28 — A6: start the hosted Colab provider foundation

**Problem:** Colab was requested as a ChatGPT-accessible compute resource, but
the retired local Runner cannot be reused and the hosted Google MCP was not yet
connected to the Sites owner identity boundary.

**Change:** documented ADR 0011 selecting Google's hosted Colab API MCP. Added
owner-scoped OAuth state, PKCE, verified Google identity, AES-GCM refresh-token
storage, access-token refresh, disconnect/revocation, and a fixed-origin
Google MCP client with a tool allowlist and bounded request/response sizes.
Added migration 0034 and a connection/capability tool surface. No provider run
or runtime creation is currently available; capability output states that the
execution lifecycle is not implemented. The official Colab CLI remains an
independent local/CI option and does not restore the retired Sites Runner.

**Validation:** all 127 Sites tests and migration tests pass; the 31-module
Worker graph is acyclic; the Worker artifact builds; `git diff --check` passes.
An unrelated Node 26 build failure in `copy-worker-runtime.mjs` was fixed by
wrapping `path.basename` in an explicit callback. No Google OAuth secret was
configured, no live Google request was made, no deployment occurred, and no
runtime was allocated.

The Codex Security diff-scan service rejected this worktree because it could
not resolve it as a non-bare Git worktree. This is an unresolved review gate,
not a clean security-scan result; no canonical scan report was generated.

**Remaining A6:** exact Google MCP output validation, connect/capability
integration tests, immutable GitHub source staging, exact plan, async run
ledger, safe cancellation, artifact verification, cleanup, provider selection,
deployed owner acceptance, and independent security review. This slice is not
Colab acceptance or completion.

## 2026-11-28 — A1: remove duplicate inspection from the chat run path

**Problem:** the operator Skill instructed an agent to call `training_inspect`
after registration and then call `training_prepare`, although prepare invokes
the same source contract and dependency-lock checks before adding the live
provider, GPU, quote, budget, and admission checks. The public registration
description also directed run requests through `training_preview` first.

**Change:** a run request now proceeds from capabilities to direct repository
registration and `training_prepare`; repository listing is conditional on an
ambiguous source or an unselected-repository response. Detailed inspection and
preview remain available for inspect-only or diagnostic requests. Updated the
MCP description, operator Skill, setup guide, Sites guide, and architecture
flow to share this sequence. No tool schema, provider, execution authority,
or budget behavior changed.

**Validation:** the full Sites Worker suite passes (120 tests); the 28-module
runtime graph is acyclic, generated workload registries are current, the Worker
artifact builds, and `git diff --check` passes. This removes redundant source
and provider reads from the normal repository-run path; it does not add a
provider or make the Modal candidate released/available.

## 2026-11-28 — A7: isolate owner-selected execution readiness

**Problem:** the fixed-workload capability projection also resolved a separate
owner-selected experiment contract: GitHub ownership, custom Modal runtime
profile, monthly/per-run budget, adapter profile match, and its next actions.
That mixed fixed-workload availability with a distinct path for ordinary-chat
repository experiments.

**Change:** moved the owner-selected capability projection and its delegated
adapter evidence into `worker/owner_training_capabilities.js`. The fixed-route
projection remains in `worker/provider_capabilities.js`, which composes the
owner-specific result into the existing MCP response and maps provider adapter
readiness to registered workloads. Response fields, blockers, ordering and
admission conditions are preserved. The new boundary is the place to evolve
owner-selected provider selection independently from fixed demos.

**Validation:** all 120 Sites tests pass, including capability schema,
owner-bound GitHub, profile mismatch, budget and adapter readiness coverage;
the 28-module graph is acyclic, generated files are current, Worker build,
artifact validation and diff checks pass. This is local source only; no
provider setting or runtime state changed and no compute was started.

**Product boundary:** owner-selected execution remains Modal-only in PR #70.
RunPod, Kaggle, Hugging Face and Colab have not gained custom-repository
execution from this extraction.

## 2026-11-28 — A7: extract the bounded Modal HTTP client

**Problem:** the Worker entrypoint mixed provider origin/credential checks,
authenticated HTTP, redirect rejection, response-size enforcement, timeout
normalization, Modal request-payload projection and health-response matching
with MCP transport and lifecycle orchestration.

**Change:** moved that cohesive provider boundary into
`worker/modal_http_client.js`. The module owns exact-origin configuration,
bounded request/response behavior and health evidence. `index.js` now imports
the stable functions and remains responsible for policy, authorization,
budget reservations and lifecycle transitions. The entrypoint shrank by 126
lines, from 2,085 to 1,959.

**Validation:** all 120 Sites tests pass, including existing coverage for
credential forwarding, redirects, bounded responses, health evidence and
recovery; the 27-module Worker graph is acyclic, generated files are current,
the build and artifact checks pass, and `git diff --check` passes. No provider
settings, credentials or admission changed and no provider call was made.

**PR/release boundary:** the extraction was pushed to PR #70. Exact-head CI
and review remain independent from local validation; retrieve their current
state from GitHub before making release claims. The PR remains unmerged and
the new module is not deployed.

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
`bda7df121e3c0df6f340489f385c04eb38035089`; GitHub reports `mergeable: true`.
All seven checks on that exact head remain queued. The latest inline
review-thread read returned zero unresolved threads. PR metadata records a
108-file diff (+10,809/−501). The candidate only implements owner-selected arbitrary source
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

**Status:** source and documentation changes were committed and pushed as
`bda7df1`; follow-up evidence was recorded in `8318cc8`. At that recorded
snapshot, all seven exact-head CI checks were queued. The candidate still
exposes arbitrary owner-source execution only on Modal GPU and does not meet
the multi-provider acceptance requirement.

## 2026-11-28 — A7: align migration test inventory with GitHub owner proof

**Finding:** exact-head Python CI on `8318cc8` failed because the migration
inventory test stopped at migration 0032, while the source contained migration
0033. The failure was independent of the current Sites module rename.

**Change:** added migration 0033 to the expected inventory and extended the
forward migration test to assert its new OAuth state columns and its deliberate
invalidation of legacy, unverified GitHub installation bindings and state.

**Validation:** the focused migration test and the full Python suite pass
locally (`615 passed, 1 skipped, 5 subtests`). No live D1 migration was run.

**Status:** committed and pushed separately as `e3d0b6a`. Exact-head CI for
that revision is queued.

## 2026-11-28 — A4: name the Sites transport after its actual provider boundary

**Goal:** make the ChatGPT Sites execution path distinguishable from the
separate legacy Gateway service, so future external-provider work has a clear
transport boundary.

**Changes:** renamed the internal Sites client module and functions from
`gateway_delegation` / `delegateGatewayTool` to
`provider_adapter_client` / `callProviderAdapterTool`. The client uses
`PROVIDER_ADAPTER_*` configuration and authenticates to the Modal provider
adapter. Existing D1 table names and `GATEWAY_DELEGATION_*` error codes remain
because they are persisted/returned compatibility contracts. Repository and
backlog maps now explain that distinction. The legacy Gateway itself and its
separate callers are untouched.

**Validation:** all 118 Sites Worker tests pass; the 20-module import graph is
acyclic; the generated registry check, forward migration replay, Worker build,
artifact validation, full Python suite (`615 passed, 1 skipped, 5 subtests`),
and `git diff --check` pass locally. Existing external response error codes
retain their compatibility spelling. No provider, D1 production state,
admission flag, credential or deployment was changed.

**Status:** local changes are validated and ready to commit. This cleanup does
not alter product capabilities: arbitrary owner-source execution remains
Modal-GPU-only on this branch, and end-to-end ChatGPT external-GPU acceptance
is still outstanding.

## 2026-11-28 — A1/A5: bind MAP L4 account evidence to the confirmed plan

**Finding:** the PR's fixed Modal T4 canary required short-lived account
evidence, but MAP L4 training relied only on configured price and the Sites D1
reservation. Those do not establish the Modal Workspace's actual usage limit
or current utilization.

**Changes:** introduced one shared Sites validator for Modal GPU account
observations and reused it for the fixed T4 route. MAP L4 preview now requires
an operator-observed `unjuno/main` Workspace record with an exact `$1.00`
limit, matching L4 quote, current credits/charges, short expiry and enough
remaining headroom for the confirmed plan ceiling plus one cent. The complete
record is included in the immutable plan/fingerprint and shown on the owner
confirmation page. Submit validates the evidence again before budget
reservation, authorization consumption, or adapter dispatch. MAP's configured
monthly ceiling is hard-bounded at `$1.00`. ADR 0007 records that this is
operator-supplied evidence, not a signed live billing API attestation.

**Validation:** 120 Sites Worker tests pass, including fresh/stale/over-budget
L4 evidence, exact quote and cap binding, and submit-time evidence change
rejection. The Worker graph is acyclic across 21 modules. Registry drift,
migration replay, artifact build/validation, and the custom-training Python
test suite pass locally. No provider or production setting was touched.

**Status:** local changes are validated and uncommitted. The branch still
provides arbitrary owner-selected execution only on Modal GPU; RunPod custom
repository execution and ordinary ChatGPT end-to-end acceptance remain open.

## 2026-11-28 — A0/A1: align the candidate with the chat-first product goal

**Product invariant:** in an ordinary ChatGPT or Work conversation, the user
describes an experiment in natural language; the agent resolves the user's
authorized source and compatible external GPU route, carries internal IDs and
provider details itself, then returns verified progress, results and cleanup.
Local containers are for development and checks; they do not satisfy the
product outcome. This invariant is recorded in ADR 0006 and governs the
provider roadmap.

**Current evidence:** PR #70 is open and unmerged at
`a9a85e2db90a54d521c649a68745e6320096f6b3`. All seven GitHub checks for the
preceding code SHA `44f21867dbd7f7066ca16bb6441cf9ea3b07edee` pass; exact-head
checks for this documentation-only update are running. The candidate adds
owner-selected source execution on Modal GPU only. RunPod remains
fixed-workload; Kaggle and Hugging Face remain fixed registered workloads;
Colab is not integrated. The repository remains parked, so no live
arbitrary-source admission or deployment is implied. The PR diff is 112 files
(+11,247/−575). Ten of 19 inline review threads were unresolved at the initial
read; after matching each finding to current code and tests, all inline threads
have been resolved. The PR description is synchronized with the current
capability boundary and check state.

**Next implementation order:** keep the Modal candidate isolated and reviewable;
close remaining current-head correctness/security findings; then implement the
same owner-selected lifecycle for RunPod behind a provider adapter that shares
source identity, plan, authorization, provider-specific budget, idempotency,
status/cancel, artifacts and cleanup contracts. Do not infer this from the
fixed RunPod canary. Before advertising or activating any route, prove its
exact capability from current policy and acceptance evidence. Colab follows
only if it can honor the same owner, quota/budget, cancellation and artifact
contract; a direct independent MCP would bypass the product lifecycle.

**Validation:** exact-head check diagnostics report seven successes for the
preceding code SHA; the latest documentation-only head's seven checks are
running. Read-only PR metadata and review-thread state were refreshed. No
provider call, live D1 operation, secret, admission change, deployment or
experiment was performed.

**Status:** code and architecture records are pushed, the PR description is
synchronized, and addressed review threads are reconciled. This is not product completion:
there is no deployed ChatGPT end-to-end owner-selected GPU acceptance for the
current candidate, and RunPod arbitrary-source execution is not implemented.

## 2026-11-28 — A1: define RunPod owner-selected execution gates

**Finding:** the checked-in RunPod integration is a fixed Serverless canary.
Official RunPod documentation describes queue endpoints as retrying failed
jobs, with per-job execution timeout and TTL controls. Its workers are deployed
custom Docker images and can process requests successively. The current
RunPod contract does not establish source-code isolation, clean per-job state,
bounded retry billing, or durable result capture for user-selected code.

**Change:** added proposed ADR 0008 and linked it from the architecture index,
backlog, and provider map. The ADR requires a GPU Control-owned immutable
worker, strict owner/plan-bound envelopes, per-job isolation, worker-reuse
cleanup, retry-aware cost bounds, durable result/artifact capture, and exact
provider acceptance. It explicitly does not authorize endpoint mutation,
secrets, deployment, or GPU execution.

**Evidence:** current source inspection of the Sites RunPod provider, plan and
lifecycle modules; official RunPod [endpoint overview](https://docs.runpod.io/serverless/endpoints/overview),
[endpoint settings](https://docs.runpod.io/serverless/endpoints/endpoint-configurations),
and [request lifecycle](https://docs.runpod.io/serverless/endpoints/send-requests).
This confirms documented API behavior only; it does not prove account endpoint
settings or worker runtime isolation. No RunPod API was called.

**Status:** the implementation gate is now explicit. The route remains
unimplemented and unadvertised. Next, inspect the worker image/handler and
document a concrete isolated execution boundary plus retry/cost proof before
writing provider code. Current PR head CI remains pending from the last read;
no source test or provider execution was performed for this documentation-only
batch.

## 2026-11-28 — A0/A1: restore current release state and RunPod cost evidence

**Product invariant:** the product is for an ordinary ChatGPT/Work conversation
where the user describes an experiment and the agent resolves authorized
source, selects a compatible external GPU, carries internal identifiers,
executes, monitors, and returns results and cleanup evidence. A local container
is a development tool, not an acceptable substitute for this user outcome.

**Refreshed source/release state:** PR #70 remains open, unmerged and mergeable
at `d4a517797a8052f71e26b28d92aa22ba9b4cf661`; its diff is 113 files
(+11,379/−575). All seven exact-head checks pass. Inline review threads have
been reconciled, while independent security review and the required GitHub
review decision remain outstanding. Owner-selected arbitrary-repository
execution exists only in the PR candidate for Modal GPU. RunPod is a fixed
canary, Kaggle and Hugging Face are fixed registered workloads, and Colab is
not integrated. Policy remains parked; no deployment, admission change or
live arbitrary-source run is established.

**RunPod cost finding:** source models 305 billable seconds as the 300-second
job TTL plus 5-second idle timeout. RunPod's current endpoint settings guide
says workers are billed during initialization and the default init timeout is
420 seconds. The source does not bind that setting, so the existing estimate
understates cost even for one initialization; retry and repeated worker-start
accounting remain unresolved. ADR 0008 now records that the current canary
quote is not a proven hard maximum charge and requires enforced bounds before
owner-selected RunPod execution.

**Validation and limits:** refreshed PR metadata and exact-head GitHub checks
read-only; checked the provider client, plan, lifecycle and tests locally; read
RunPod's official endpoint settings and request-policy documentation. No
provider API, experiment, production setting, credential, D1, or deployment
was used. This documentation correction does not implement RunPod support or
complete the ordinary ChatGPT end-to-end experience.

## 2026-11-28 — A7: separate training policy/profile from plan orchestration

**Problem:** `experiment_input_contract.js` and `mcp_tool_contract.js` imported
`training_plan.js` only to read policy ceilings. That made public contract
modules depend inward on the planning use case; runtime-profile normalization
also lived in the plan module despite having other callers.

**Change:** moved immutable lane ceilings and MAP defaults to
`worker/training_policy.js`, and moved owner-selected runtime environment
normalization to `worker/training_runtime_profile.js`. Updated all callers and
removed the old definitions. Added a Worker architecture rule that contract
modules cannot import the generic training-plan orchestrator; the legitimate
RunPod plan validator dependency remains allowed. Refreshed the measured
Worker and test-file sizes in the repository map and backlog.

**Validation:** `npm test` passes all 120 Worker tests, registry drift check,
and architecture check across 23 runtime modules. Worker build copied all 23
reachable modules and artifact validation passed. `git diff --check` passes.
The first version of the new architecture rule also rejected the legitimate
RunPod provider-plan validator; narrowed it to the actual forbidden dependency
before the passing run. Exact-head CI passed all seven checks on
`e615b395f62fb70c28c37701dc66300ffc1c79b9`. No provider or production
configuration was touched.

**Review limitation:** attempted the independent Codex Security diff scan for
PR #70's exact `main...e615b395` range. The scan setup rejected the linked
Git worktree with “requires a non-bare Git worktree with a resolvable HEAD” and
returned no scan ID. No substitute scan or report was fabricated. Independent
security review of PR #70 remains open.

**Current source/release state:** PR #70 is open and unmerged at
`e615b395f62fb70c28c37701dc66300ffc1c79b9`, 115 files (+11,472/−575); all
seven exact-head checks pass. Owner-selected execution remains Modal-only in
the candidate; RunPod custom execution and the published ChatGPT end-to-end
path remain unfinished.


## 2026-11-28 — A7: extract capability projection and Modal CPU policy

**Problem:** `worker/index.js` built the read-only provider/workload matrix,
Modal CPU quote and owner-selected readiness response inline. That tied the
agent-facing discovery contract to the HTTP/MCP composition root and mixed
fixed CPU pricing policy with lifecycle code.

**Change:** moved capability projection into
`worker/provider_capabilities.js` and fixed Modal CPU limits/quote into
`worker/modal_cpu_policy.js`. Dispatch injects the existing `modalConfigured`
configuration predicate. Existing public tool and response contracts are
unchanged. No live health probe, provider execution, admission, credentials, or
deployment behavior was added.

**Validation:** `npm test` passes all 120 Sites Worker tests;
`node scripts/check-worker-architecture.mjs` reports an acyclic graph of 25
runtime modules; `node --check worker/provider_capabilities.js` and
`git diff --check` pass.

**Product boundary:** current-source candidate still offers owner-selected
execution through Modal only. RunPod is fixed-workload only; Kaggle and
Hugging Face remain registered-workload routes; Colab remains proposed. This
refactor improves agent-facing capability ownership but does not by itself
complete the ordinary-chat external-GPU product or prove deployed behavior.


**Current source/release state after this batch:** PR #70 is open and unmerged
at `f4ea1039bc9d7a2e2b0c96765f0818c389b903bd` (117 files, +11,652/−686).
All seven exact-head checks passed. Independent security review and required
GitHub review remain outstanding; owner-selected admission remains parked, and
this source candidate has not been deployed.

## 2026-11-28 — A6: distinguish Colab local MCP from hosted adapter surface

**Finding:** Google's official `googlecolab/colab-mcp` README describes a
local stdio server connected to a browser-open Colab session. It requires an
MCP client running on the user's device with `notifications/tools/list_changed`
support; listed compatible examples are Gemini CLI, Claude Code and Windsurf.
That local server does not establish ChatGPT web/Work compatibility and cannot
be called from the hosted GPU Control Sites Worker. The separate hosted Colab
API MCP is the candidate surface for the shared Sites lifecycle.

**Change:** clarified the distinction in the Colab architecture decision and
provider design doc. The standard product remains ChatGPT Sites → owner-bound
provider adapter → Colab API, with one run/budget/artifact/cleanup ledger. No
provider is added, no login is requested, and no runtime is allocated.

**References:** Google Developers Blog and official `googlecolab/colab-mcp`
README, checked 2026-11-28. The exact target client's ability to connect a local
stdio server must be verified independently; the local README does not claim
ChatGPT web support.


## 2026-11-28 — A5/A7: canonicalize provider and route identities

**Problem:** provider route IDs, billing classes, credit eligibility, adapter
host support, budget provider IDs and MCP provider filters were separately
hard-coded. A new route could drift between capability output, validation and
budget reporting.

**Change:** added `workloads/provider-catalog.json` as the authority for
provider billing semantics and route metadata. The workload registry
generator validates workload/route GPU and adapter-manifest compatibility and
generates `worker/provider_catalog.js`. Capability rows, provider budget IDs,
Modal route reporting, delegated adapter route selection, MCP provider enums
and provider filters now consume that generated catalog. Provider-specific
readiness and live budget state remain owned by the capability projection and
D1 policy; the catalog does not claim that a configured adapter can execute a
workload. Existing public route and budget order is preserved.

**Validation:** all 120 Sites tests pass, the 26-module runtime graph is
acyclic, generated registries are current, Worker build and artifact
validation pass, and `git diff --check` passes. No provider, production
setting, admission or credential was changed; no experiment was started.

**Remaining:** exact-head hosted CI, review, merge, deployment and live
ChatGPT/provider acceptance remain separate release gates. RunPod, Kaggle,
Hugging Face and Colab still lack owner-selected arbitrary-source execution;
this catalog refactor makes their actual routes clearer without adding
execution capability.

## 2026-11-28 — A5/A7: derive workload discovery from the canonical registry

**Problem:** the `experiment_capabilities.workloads` response repeated names,
provider IDs, GPU flags, runtime limits, cost ceilings, and cleanup behavior
that already have an authority in the generated workload registry. Adding a
registry entry could leave the agent-facing inventory silently incomplete.

**Change:** workload capability rows now derive their common metadata from the
registry. Provider runtime readiness still comes from current route-specific
checks, and only the explicit existing workload IDs can be marked enabled.
Unknown/new registry entries are included but remain disabled until a route is
explicitly supported. The previous capability array order is preserved.

**Validation:** all 120 Sites tests pass, including the exact capability IDs,
order, route blockers and enablement checks. Registry drift, the 25-module
acyclic architecture check, Worker build, artifact validation, and
`git diff --check` pass. The first test run caught an output-order regression;
the stable public order was restored before the passing run. No provider,
production setting, admission or credential was changed.

**Remaining:** route-specific execution contracts and provider adapters still
need independent compatibility work. Arbitrary repository execution remains
Modal-only in the unmerged candidate; this discovery refactor does not make
RunPod, Kaggle, Hugging Face or Colab arbitrary-source routes available.

## 2026-11-28 — A6: select Colab CLI owner-runner integration (superseded)

**Proposal:** this batch selected a paired, owner-controlled outbound runner
for the Google Colab CLI and recorded the protocol in ADR 0010. The following
correction records why this proposal was replaced before any runner code or
configuration was added.

## 2026-11-28 — A6 correction: preserve retired Runner boundary

**Correction:** the preceding entry's owner-runner direction conflicted with
the existing [`RELEASE_MATRIX.md`](../RELEASE_MATRIX.md) and
[`2026-11-11 Sites architecture pivot`](../decisions/2026-11-11-sites-d1-architecture-pivot.md),
which explicitly retire the macOS Runner, Keychain bearer, and `/runner/*`
routes. Do not implement or revive that path.

**Decision:** superseded ADR 0010 and replaced it with ADR 0011: connect the
official hosted Colab API MCP behind Sites using an owner-scoped Google OAuth
connection and encrypted refresh credential. This keeps ChatGPT Sites and D1
as the single provider/run control plane. `google-colab-cli` remains available
for independent local/CI clients; it is not the hidden Sites runner. Google
MCP OAuth requires a configured client because Google does not support dynamic
client registration. The exact OAuth client, callback and consent prerequisites
are external setup gates.

**Validation:** reviewed the official Google Colab MCP tool schemas, REST
runtime create/idempotency contract, Google OAuth/DCR guidance, CLI automation
and auth docs, and the repository's Runner retirement policy. Updated the
provider design, backlog, architecture index and decision history. No runner,
credential, admission, deployment, or Colab runtime was changed or created.

**Remaining:** implement the hosted-MCP OAuth connection and provider adapter,
including owner isolation, token-at-rest protection, async lifecycle recovery,
bounded results, cancellation, and verified cleanup. Colab remains unavailable
from ChatGPT until the full acceptance sequence passes.

## 2026-11-28 — A13: implement owner-bound OAuth for external MCP clients

**Problem:** ChatGPT's trusted Sites identity header was the only supported
MCP authentication route. Codex and other remote MCP clients could not use the
same owner-scoped run ledger. The verified GitHub subject mapping provided
owner proof but was not yet consumed by an MCP authorization flow.

**Change:** added DCR and OAuth discovery, explicit consent, GitHub user proof,
PKCE S256 authorization-code exchange, MCP audience-bound 15-minute access
tokens, hashed and rotating refresh tokens, replay-family revocation, token
revocation, and `experiments:read` / `experiments:execute` scope gates. ChatGPT
tool contracts remain intact. Both transports enter the same MCP dispatcher
and owner-scoped D1 ledger. Added migration, transport challenge, architecture
check, connection guide, and database-backed tests.

**Validation:** all 138 Worker tests pass; the module graph is acyclic across
34 modules; the forward-migration test, Worker build, and Site artifact
validation pass. The diff was also reviewed manually. The Codex Security diff
scan could not start: its setup inspection validated this worktree, but the
scan launcher twice returned “requires a non-bare Git worktree with a
resolvable HEAD.” No replacement canonical scan/report was created.

No migration, OAuth setting, Site deployment, provider operation, or live
experiment was performed.

**Release limit:** repository source is not a live second-client connection.
Migration 0036, deployed discovery/callback routes, and a fresh no-compute
handshake from an independent OAuth-capable MCP client remain required.


## 2026-11-28 — A7: isolate immutable run artifacts

**Problem:** Worker result persistence and MCP artifact retrieval directly
handled R2 objects in the large entrypoint, splitting ownership, integrity
checks and cancellation-race cleanup across transport and lifecycle code.

**Change:** introduced `worker/run_artifacts.js` as the authority for bounded
result serialization, immutable R2 writes, D1 terminal finalization,
cancellation-winner cleanup, owner-scoped artifact lookup, metadata/checksum
verification and chunk encoding. The entrypoint delegates to this interface.
The Worker architecture checker forbids R2 object calls outside the module.
Historic safe artifact IDs remain readable.

**Validation:** all 142 Worker tests pass; D1 forward migrations pass; Worker
build copied all 35 reachable runtime modules; artifact validation and
`git diff --check` pass. No deployment, migration application, or provider
operation was performed.


## 2026-11-28 — A7: isolate registered-workload prepare resolution

**Problem:** `experiment_prepare` fixed-ID validation, CPU/RunPod/provider
default completion and the owner-bound Kaggle result to ZeroGPU artifact lookup
were embedded in the Worker entrypoint. This made an input contract depend on
the transport composition root.

**Change:** moved those operations into `worker/registered_prepare.js`. The
module owns fixed workload defaults and source artifact selection; Worker
dispatch retains provider admission and plan persistence. Existing tool schema,
owner scope, immutable source pins and response flow are preserved. Added
direct tests for CPU/Kaggle/RunPod resolution and unknown-ID rejection.

**Validation:** all 146 Worker tests pass; D1 forward migration tests pass;
build packages all 36 reachable runtime modules; Site artifact validation and
`git diff --check` pass. `worker/index.js` shrank by 97 lines (2,119 to 2,022).
No live migration, deployment, or experiment was performed.


## 2026-11-28 — A7: unify authorized Modal health checks

**Problem:** the standalone health diagnostic and the submit path each owned
parallel workspace/plan reservation SQL and provider probing. This risked drift
in the one-use and rate-limit rules.

**Change:** moved the complete provider health diagnostic into
`worker/provider_health_diagnostic.js` and made submit reuse that exact path
after checking for an already successful diagnostic. The shared module now
owns readiness persistence and request budget semantics. Submit maps the
shared diagnostic response to the existing submit error code/shape.

**Validation:** all 146 Worker tests pass, including explicit health, provider
rate-limit, oversized response, parallel submit and lost-response cases. D1
forward migration tests pass; build packages all 37 reachable modules; Site
artifact validation and `git diff --check` pass. `worker/index.js` is now
1,875 lines. No live provider request or deployment occurred.


## 2026-11-28 — A7: isolate Modal CPU plan creation

**Problem:** the Worker dispatcher validated and fingerprinted the Modal CPU
plan, persisted its owner/idempotency record, and formatted cost/resource
approval details inline. The shared human authorization TTL was also owned by
the composition root despite being consumed by several flows.

**Change:** moved CPU plan creation to `worker/prepare_modal_cpu_plan.js`;
provider selection and admission remain at dispatch. Centralized the 600-second
single-use authorization lifetime in `worker/human_authorization_policy.js`
and shared it with the plan/confirmation flows. Existing MCP response shape,
fixed resource/cost limits and idempotency behavior remain unchanged.

**Validation:** all 146 Worker tests pass, including registered CPU prepare,
plan idempotency and invalid ceiling cases; D1 forward migration tests pass;
build packages all 39 reachable modules; Site artifact validation and
`git diff --check` pass. `worker/index.js` is 1,854 lines.


## 2026-11-28 — Normalize Worker SHA-256 operations

**Problem:** independently implemented Web Crypto digest-to-hex logic was
spread across authentication, artifact, provider, training and entrypoint
modules, including different handling of text and raw bytes.

**Change:** introduced `worker/sha256.js` as the one production digest
implementation for text/byte input, raw digest bytes and lowercase hex output.
Migrated all Worker production SHA-256 calls, including OAuth PKCE's
base64url digest input, without changing token encodings, identifiers or
checksums. Added known-vector and input-contract tests.

**Validation:** all 148 Worker tests pass; D1 forward migration tests pass;
build packages all 40 reachable modules; Site artifact validation and
`git diff --check` pass. A source scan confirms only the shared utility calls
`crypto.subtle.digest("SHA-256", ...)` in production Worker modules.
