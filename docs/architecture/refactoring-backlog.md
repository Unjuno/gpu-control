# Architecture and product-fitness backlog

**Owner:** repository maintainers  
**Last refreshed:** 2026-11-28
**Scope:** make an ordinary ChatGPT request reliably run an authorized
owner-selected experiment on a compatible external compute provider, then
return verified results, while reducing architectural ambiguity.

This backlog is a task pool, not authorization to enable paid compute, change
provider accounts, deploy production, or remove externally used interfaces.
Current mode is `parked` in `policies/repository-state.yaml`.

## Ordering principles

1. Establish true source/release status before refactoring.
2. Close the end-to-end user path and security contract before optimizing
   internal abstractions.
3. Give each core concept one authority; generate cross-runtime copies where
   practical instead of maintaining behavior by hand.
4. Migrate callers, retain only required compatibility, then delete old code.
5. Keep every batch small, independently reviewable, reversible and green.

## P0 — release truth and runnable ChatGPT path

### A0. Reconcile branch, review, deployment and provider acceptance

- **Evidence:** PR #70 is the active source candidate. Its head, diff size,
  mergeability and check/review state change on every push. Refresh them from
  GitHub immediately before release claims; this backlog is not the authority
  for transient CI state. The PR remains separate from deployment and
  provider acceptance. Repository mode remains `parked`; owner-training
  admission and live D1 remain unchanged. Source, CI, review, migration and
  deployment evidence must be reported as separate facts.
- **Work:** maintain a compact release record that separately names source
  head, merge SHA, Sites deployment/version, applied D1 migration, live tool
  schema, provider configuration, and exact end-to-end acceptance run.
- **Current chat-first invariant:** the user describes the experiment in
  ordinary ChatGPT/Work conversation; the agent resolves authorized source and
  compatible external GPU, carries IDs/provider details internally, and
  returns verified result and cleanup. Modal is currently the only
  owner-selected route in PR #70; RunPod arbitrary-source is next, while
  Kaggle/Hugging Face remain fixed-workload routes and Colab is not integrated.
- **Done when:** no current-state document promotes PR source or old canaries
  into present-day deployed capability; the first-run ChatGPT prompt names
  actual available actions and blockers.

### A1. Make the owner-selected experiment a complete conversational journey

- **Evidence:** source modules exist for GitHub App selection, registration,
  default-branch pinning, manifest/lock inspection, plan, staging, isolated
  custom Modal Sandbox, outputs and cleanup. `experiment_capabilities`
  exposes owner-selected readiness separately from fixed workloads.
  `OWNER_TRAINING_ADMISSION_ENABLED` is independently gated; policy is parked.
- **Security correction in PR #70:** the GitHub Setup URL installation ID no
  longer binds directly to a Sites owner. A one-time GitHub user OAuth+PKCE
  flow proves access to the exact installation before binding. Forward
  migration 0033 invalidates older, unverified bindings. Modal CPU/memory hard
  limits, workload-readable staged wheels, manifest-Python wheel resolution,
  and the delegated artifact route are also enforced in source.
- **Account-budget correction in progress:** MAP L4 plans now require a
  short-lived operator-observed Modal Workspace usage/price record for the
  `$1.00` account limit. The record is bound into the approved plan, displayed
  on its confirmation page, checked before dispatch, and constrained by a
  hard `$1.00` Sites monthly maximum. It is not a signed live billing API
  attestation; release remains blocked until account-side limit and evidence
  are verified.
- **Remaining:** exact-head CI, independent security review, migration/deploy,
  production settings, admission, and a real ChatGPT end-to-end GPU lifecycle
  remain unverified. Source/tests do not close the product acceptance.
- **Work:** from a request such as “try training this repository,” discover
  repositories selected in the owner's GitHub App, pin the current default
  commit, inspect the contract, and select only a currently compatible and
  admitted external GPU route. The agent generates and carries internal
  registration/run IDs; it never asks the user to find or provide them. It
  previews bounded defaults, presents the exact destructive MCP confirmation
  once, submits idempotently, polls the same run, retrieves bounded
  metrics/artifacts, and verifies cleanup. Ask only for a missing product
  choice such as repository when the request is ambiguous. Keep missing
  capability explicit; never silently fall back to a different or paid
  provider.
- **Product requirement:** the main user action is an ordinary ChatGPT/Work
  request such as “try this experiment.” The agent discovers the owner-selected
  repository and current executable routes, carries all internal IDs, and
  chooses a compatible external GPU without requiring a separate CLI or a
  pre-registered workload. A local/container-only result does not satisfy this
  requirement.
- **Provider sequence:** the first owner-selected implementation is Modal GPU.
  The same owner-bound plan and lifecycle must then support RunPod GPU for the
  same repository contract. Kaggle and Hugging Face remain eligible only for
  workloads their current platform adapters can execute; their fixed-workload
  routes do not count as arbitrary-repository support. Colab is tracked under
  A6 and must join the same lifecycle before it is advertised as integrated.
- **RunPod implementation constraint (2026-11-28):** its fixed Serverless
  endpoint executes a deployed custom worker image; queue endpoints document
  retry-on-failure behavior. The per-job policy exposes execution timeout and
  TTL, but available documentation does not establish that arbitrary source
  can run with Modal's separate staging/GPU-Sandbox boundary, no-egress rule,
  or one-attempt billing bound. Do not retrofit the fixed canary. First prove
  per-job isolation, worker-reuse cleanup, retry accounting, durable artifact
  capture, and current endpoint semantics under [ADR 0008](decisions/0008-runpod-owner-selected-execution.md).
  If those guarantees cannot be shown, RunPod must not advertise the
  owner-selected route.
- **Done when:** ordinary ChatGPT and Work tool schemas both expose the same
  owner-selected path; the agent resolves repository and commit without asking
  for internal IDs; compatible, authorized external GPU routes are selected
  from current capability evidence; and current acceptance proves plan through
  result retrieval and cleanup for each advertised owner-selected provider.
  No release claim based solely on unit tests, a plan, a staging sandbox, or an
  old run.

### A2. Resolve release gates without confusing them with user approval loops

- **Evidence:** user intent should survive prepare/status calls; native MCP
  confirmation of a destructive write is a client boundary. Repository policy
  separately requires exact-head CI, independent security review, and live
  activation gates.
- **Work:** document the distinct actors and each gate. Remove duplicate
  conversational questions for an already explicit run request; retain native
  write confirmation and hard review/security requirements.
- **Done when:** agent never asks the user to repeat the same run request, and
  never presents repository approval, security review, provider admission, or
  client write confirmation as interchangeable.

## P1 — authority, state and provider boundaries

### A3. Enforce lifecycle authority across D1, adapter journal and provider

- **Evidence:** Sites D1 stores owner-visible plans and cleanup evidence;
  Modal Dict stores adapter dispatch/idempotency claim; Volumes stage source,
  checkpoints and artifacts.
- **Current ownership:** ADR 0002 defines D1 as product authority for owner,
  immutable plan, one-time reservation, authorization, budget and verified
  cleanup; Modal Dict as the custom adapter's atomic dispatch/recovery journal;
  and provider inspection as execution evidence. Missing or conflicting
  observations stay uncertain and never authorize a replacement allocation.
- **Work:** verify this rule across fixed Modal, RunPod, Kaggle, Hugging Face and
  owner-selected routes; define journal retention and recovery after adapter
  data loss. Keep secrets and raw large artifacts out of D1.
- **Done when:** each route has one transition authority, cross-layer tests
  cover response loss, duplicate delivery, provider terminal mismatch and
  cleanup pending without duplicate allocation, and journal retention cannot
  strand a run or erase the only recovery evidence.

### A4. Retire or isolate the legacy Gateway service without losing its real callers

- **Evidence:** the user-facing product boundary is Sites; `gateway/app.py`
  labels its FastAPI app a local compatibility entrypoint. The repository still
  contains the FastAPI/OAuth/SQLAlchemy/PostgreSQL API, worker, Compose and
  systemd deployment templates, plus their historical service tests. Current
  `gateway-ci.yml` runs only the Sites-owned provider-runtime contract tests and
  compatibility imports; it does not build or test the Gateway service.
  `project-checks.yml` uses the separate `project_control/runner.py`. The CLI
  `gateway/scripts/comment_bridge.py` imports `gpu_gateway.ci_bridge`, but the
  workflow path declared in `ci_policy.json` is absent from this checkout.
  These source facts do not prove that nobody outside this repository uses the
  legacy package or deployment files.
- **Decision:** do not treat Gateway as a production deployment. Keep its three
  concerns separate: GitHub Issue bridge, provider-runtime compatibility
  imports, and legacy Gateway service code. The Sites transport is named
  `provider_adapter_client.js` because it calls the authenticated Modal provider
  adapter. Historical D1 table names and `GATEWAY_DELEGATION_*` error codes are
  retained for compatibility; they do not imply a runtime dependency on the
  legacy Gateway service.
- **Work:** inventory exact app/service tests and imports; either move the
  Issue bridge to its own package or keep its narrow import with ownership
  documented. Remove or archive the legacy API/OAuth/store/queue/deploy stack
  only after its required contracts and historical evidence are preserved and
  the now-unused tests/build dependencies are migrated or retired.
- **Done when:** no current doc suggests deploying Gateway for ChatGPT GPU
  Control; CI names the behavior it truly checks; each retained module has a
  caller or an explicit archival reason.

### A5. Make provider capability and cost policy queryable from one contract

- **Evidence:** provider policy and capability semantics appear in Sites
  JavaScript, Python control library, Gateway, registry JSON and prose. Modal
  can be both compute provider and adapter host; these roles differ.
- **Progress (2026-11-28):** the Sites projection now groups Modal CPU and GPU
  compute under one D1 reservation ceiling of $30 per UTC month and $1 per run.
  Migration `0032_modal_compute_budget.sql` carries forward prior CPU, fixed
  GPU and claimed training reservations, then removes the superseded Modal
  route-specific ledgers. Owner-selected and MAP training reserve their exact
  plan ceilings in the same D1 batch as dispatch claim and authorization
  consumption; a failed claim removes the reservation. Existing lane-specific
  limits remain additional ceilings. RunPod remains separate at $1 per run
  with no product monthly cap; Kaggle and Hugging Face remain zero-cost with
  paid fallback disabled. The total is a conservative Sites reservation sum,
  not Modal billing usage or a provider-side charge stop. Modal control-function
  fees, adapter hosting for Kaggle/Hugging Face, external provider costs, and
  usage outside this Sites D1 are excluded. Unit and migration tests pass
  locally; live migration, deployment, and provider acceptance are not done.
  See ADR 0005. Broader provider capability generation, quote freshness and
  workload compatibility remain open.
- **Capability inventory (2026-11-28):** Sites workload capability rows now
  derive common identity, resource, cost, and cleanup fields from the generated
  workload registry. Only the five existing workload IDs are eligible for
  route-specific enablement; additional entries remain visible but disabled
  until explicitly supported. Response order is preserved. This removes a
  duplicate inventory without treating provider configuration as execution
  support. The generated provider catalog now owns route/provider IDs, billing
  class, credit eligibility, adapter hosting and fixed route metadata;
  capability readiness remains dynamic and does not imply execution support.
- **MAP account gate:** ADR 0007 adds a separate L4 Workspace evidence contract
  to prevent the Sites reservation from being mistaken for the actual Modal
  account cap. The candidate rejects a MAP monthly configuration above $1 and
  binds/rechecks the exact account evidence at submit. This evidence remains
  operator-supplied and does not replace verification of the provider-side
  usage limit.
- **Work:** extend the canonical contract only for concrete cross-runtime
  needs: quote/quota freshness, task compatibility, cancellation and cleanup
  evidence. Avoid static catalog fields that no consumer enforces. Generate
  client/server constants where runtime parity is required.
- **Done when:** adding/removing a provider or workload requires one canonical
  definition plus its adapter implementation and acceptance evidence; no
  provider can be advertised just because an adapter host is configured.

### A6. Integrate the hosted Colab API MCP behind Sites

- **Evidence (2026-11-28):** Google's official hosted Colab MCP exposes
  runtime discovery/allocation, code execution, session/runtime deletion, and
  subscription lookup. It supports Google OAuth/ADC but no dynamic client
  registration. `google-colab-cli` supports pipeline/CI use but cannot be run
  by a Cloudflare Worker and does not write results to Sites D1. The former
  macOS Runner, Keychain bearer and `/runner/*` path are explicitly retired and
  must not be restored. Colab's documented API does not provide a per-run
  dollar quote or CU balance; the CLI's CU endpoint is undocumented.
- **Decision:** GPU Control's owner-bound API/MCP is the one product control
  plane; ChatGPT chat/Work is the primary client, not the only client. ChatGPT,
  Codex, and future local/CI clients should use the same plan authorization,
  provider adapters, run ledger, results, and cleanup contract. Implement the
  hosted Colab MCP as a provider adapter with a one-time, owner-scoped Google
  OAuth connection. Encrypt refresh credentials in the Sites trust boundary
  and keep Google tokens away from the agent/workload. The official Colab CLI
  may remain a standalone developer tool, but its runs are not GPU Control
  runs; do not present that separate path as an integrated client or silently
  fork the run ledger. Add another client only when it can call the shared
  control-plane contract under the same owner identity and authorization.
- **Work:** implement owner-bound Google OAuth connect/disconnect, protected
  credential refresh, hosted MCP client, exact-plan creation, idempotent
  runtime/session lifecycle, bounded source/result transfer, cancellation and
  cleanup receipts. Keep cost as unknown until account CU semantics can be
  trusted; never label the internal Sites reservation a Google billing cap.
  Keep admission closed until exact-head CI, independent security review, and
  one bounded end-to-end GPU acceptance pass.
- **Done when:** from ordinary ChatGPT chat/Work and at least one documented
  non-ChatGPT MCP client, the owner can ask for a registered repository
  experiment without supplying internal IDs; each client uses the same
  owner-bound plans and run ledger; Colab is selected only when its current
  connected-account capabilities and product bounds permit it; and provider
  GPU, outputs/digests, terminal state, and cleanup are verified in that same
  ledger. Standalone CLI runs are clearly labeled outside GPU Control.

### A13. Add owner-bound OAuth for non-ChatGPT MCP clients

- **Evidence:** source implementation is in PR #70: DCR, protected resource
  and authorization-server metadata, consent, GitHub subject linking, PKCE,
  audience-bound access tokens, refresh rotation/replay revocation, scopes,
  migration `0036_mcp_oauth_clients.sql`, and a common MCP dispatcher. See
  [`MCP_CLIENTS.md`](../../sites/gpu-control-sites/MCP_CLIENTS.md). This is
  not yet a deployed or live-verified client connection.
- **Decision:** follow
  [ADR 0012](decisions/0012-mcp-oauth-multi-client.md). Add a standards-based
  OAuth authorization flow for external MCP clients, bound to an owner through
  the immutable GitHub subject already verified during account linking. Do not
  expose long-lived personal API keys or create a separate execution ledger.
- **Work:** apply migration 0036, deploy the metadata and callback routes, then
  connect an independent OAuth-capable MCP client to a non-production Site
  without submitting an experiment. Do not enable providers or change budgets
  as part of this handshake.
- **Done when:** two separately configured MCP clients for one linked owner
  see the same plans and runs; a second owner cannot observe or cancel them;
  wrong-audience, expired, revoked, replayed-refresh, and insufficient-scope
  requests fail at the HTTP boundary; and existing ChatGPT auth/schema remains
  compatible. No provider execution is enabled by OAuth itself.

## P2 — reduce module entropy without moving complexity to callers

### A7. Decompose the Sites Worker by domain and narrow tool dispatch

- **Evidence:** `worker/index.js` is 2,175 lines at source candidate `615e039`
  and remains a large transport
  and composition root for authentication, owner identity, routing and provider
  workflows. MCP schemas/descriptions, experiment input contracts, GitHub
  ownership, training lifecycle, budgets, RunPod lifecycle, fixed-route and
  owner-training capability projections, and the bounded Modal HTTP client now
  have separate modules, but
  provider lifecycle orchestration and route dispatch still occupy the entry.
- **Work:** make `index.js` a small transport/composition root; move cohesive
  GitHub-source, training-plan, artifact, capability and provider operations
  behind stable domain interfaces. Inject D1, fetch, clock and provider ports
  where they enable deterministic isolation.
- **Done when:** each domain owns its validation and transitions; routes call a
  small public interface; no circular imports; tools and response contracts stay
  backward compatible; cross-domain regression suite remains green.

**Progress:** owner-selected source inspection/error projection now lives in
`worker/training_inspection.js`; registration, plan, submit, status/cancel and
bounded result routing live in `worker/training_tools.js`. The MAP repository
slug is centralized in `training_source.js`. `index.js` was about 2.8k lines
before the A7 contract extraction; it measured 2,333 lines at an earlier
checkpoint and is 2,175 lines at source candidate `615e039`.
`experiment_capabilities.owner_selected_training` now advertises the custom
GitHub journey, current connection/adapter/admission gates, no paid fallback,
and the fact that registration IDs are agent-carried internals. Prepare and
status only advertise submit when both admission and the provider adapter are
configured. Training inspection and preview share one owner-runtime config
projection so an admitted profile is not mislabeled as disconnected. Sites and
Modal adapter readiness use the same versioned JSON conformance cases and canonical
profile fingerprint to catch drift in independently validated runtime/quote
bounds before owner-selected runs consume authorization or monthly budget. See
[ADR 0003](decisions/0003-owner-training-profile-readiness.md). The rest of the
  worker/router decomposition remains open. In the latest batch, exact
  environment-bound experiment validators and registered-input normalization
  moved to `worker/experiment_input_contract.js`, reducing the entrypoint by
  211 lines while keeping the existing MCP schemas and runtime behavior.
  Owner-scoped repository token issuance also moved behind the GitHub
  connection module.

**Progress (2026-11-28):** immutable training lane limits and MAP defaults now
have one authority in `worker/training_policy.js`; owner-selected Modal runtime
configuration is normalized by `worker/training_runtime_profile.js`. The MCP
and input-contract modules no longer import the training plan orchestrator to
read policy constants. The Worker architecture check now rejects direct
contract-to-plan dependencies. This is a boundary improvement only: Modal
remains the sole owner-selected provider in source, and PR #70 is not deployed.

**Progress (2026-11-28):** the ordinary custom-repository route is now
The default source-run path is now `experiment_capabilities` →
`training_register` → `training_prepare` → `training_submit`. A user-named,
connected repository goes directly to registration; repository listing is
reserved for ambiguous requests or an unselected repository. Prepare validates
the same immutable manifest and dependency lock as inspection/preview while
also checking the current provider, GPU, runtime, quote and budget. Inspection
and preview remain optional for diagnostics or plan-only requests. This avoids
duplicate source and provider reads in the ordinary run path.

### A8. Split test fixtures by contract and reuse domain builders

- **Evidence:** Sites `index.test.js` is 3,444 lines at source candidate
  `615e039` (2026-11-28); Gateway store/worker tests
  are similarly large. The suite has valuable migration and runtime contracts.
- **Work:** partition tests by domain and lifecycle; extract only stable test
  builders. Preserve explicit failure cases and avoid generic fixture engines.
- **Done when:** a contributor can run one domain's tests and understand its
  setup; full CI still covers public schemas, migrations, replay and cleanup.

### A9. Consolidate Python/Gateway provider runtime duplication by consumer

- **Evidence:** root `src/gpu_control` provides a reusable library; Gateway
  wraps/re-exports parts of `modal/provider_runtime`; adapter packaging tests
  constrain the Modal image.
- **Work:** build an import/call graph. Keep one provider implementation for
  Kaggle/HF semantics; remove wrappers only after every service/test imports the
  canonical contract and packaging still excludes unrelated Gateway services.
- **Done when:** one implementation owns each provider protocol, with
  intentional compatibility facades only where a real external caller needs
  them.

## P3 — standards that prevent regression

### A10. Normalize error, lifecycle and plan schemas across runtimes

- **Work:** define stable versioned schemas for plan, provider observation,
  cleanup, artifacts, capabilities and typed errors. Generate validators/docs
  or run cross-language conformance fixtures; do not hand-duplicate semantic
  rules.
- **Done when:** Worker, adapter and any retained Gateway pass identical
  contract fixtures and fail closed on unknown versions/fields.

### A11. Inventory and normalize configuration

- **Work:** enumerate env vars by owner, secret/config type, provider, stage,
  default, validation, and current consumers. Centralize parse/validation by
  domain; reject contradictory or orphaned settings. Never print secret values.
- **Done when:** every runtime setting has one owner and test; no undocumented
  magic fallback or stale configuration can advertise an unavailable route.

### A12. Add architecture checks only after rules have an owner

- **Work:** enforce generated registry freshness, forbidden dependency
  directions, no control imports from workload payloads, migration append-only
  policy, schema parity, and source/deployment status labels in CI.
- **Done when:** checks reject an actual known regression and give a local,
  actionable message; avoid broad lint rules with no established invariant.

**Progress:** `npm test` runs `scripts/check-worker-architecture.mjs`, which
uses the same static Worker import graph as packaging. It checks static in-tree
imports, rejects dynamic imports and entrypoint backedges, and fails on cycles.
The build copies exactly the 18 modules reachable from `index.js` and fails if
a runtime module is orphaned. This establishes Worker dependency and packaging
rules only; provider/workload boundaries, Python imports, schema parity, and
append-only migrations remain open.

## Decision queue

1. Can the legacy Gateway package and Compose/systemd deployment contract be
   retired without breaking an external operator? Repository CI and current
   Sites flow do not use that service, but external consumers are not observable
   from this checkout.
2. Is Colab integrated through the shared Sites lifecycle, and what Google
   session/quota/cancel mechanism is acceptable?
3. What strict execution profile, cancellation guarantee and cost evidence are
   required before RunPod can execute arbitrary owner-selected repository
   code? PR #70 only proposes Modal; fixed Kaggle/HF/RunPod workloads do not
   imply this capability.

**Resolved:** Modal CPU, fixed GPU, and training reservations share the Sites
compute budget in ADR 0005 and PR #70. Its source is not deployed. While the
remaining decisions are open, continue
documentation truth repair, module inventory, source-only tests and
non-production refactoring. Do not enable provider admission or remove a
potentially live contract.

## Batch record template

For each implementation round record: goal and observed baseline; files and
public contracts touched; old callers migrated; deleted/retained compatibility
and why; local validation and exact-head CI; review result; source SHA; merge,
deployment and live acceptance as separate fields; remaining backlog IDs.


**Progress (2026-11-28):** read-only provider/workload capability projection
now lives in `worker/provider_capabilities.js`; fixed Modal CPU resource and
cost policy lives in `worker/modal_cpu_policy.js`. The Worker entrypoint now
composes the capability query instead of owning its provider matrix and
owner-training readiness logic. This preserves the current behavior and does
not enable GPU admission or add a provider. The composition root remains large;
next A7 work should extract coherent domain operations with explicit ports,
while the end-to-end external-GPU acceptance and provider security gates stay
separate completion requirements.


**Progress (2026-11-28):** D1/R2 result artifact persistence, cancellation-race cleanup, owner-bound lookup, metadata/checksum verification, and bounded base64 chunk reads now live in `worker/run_artifacts.js`. The entrypoint delegates both Modal result finalization and `experiment_artifact`; a static architecture check keeps direct R2 get/put/delete calls inside this module. Existing artifact identifiers remain readable for stored runs. Focused module tests cover writes, cancellation cleanup, integrity, chunking, and size bounds. `index.js` is now 2,119 lines; the import graph is acyclic across 35 Worker runtime modules.

**Progress (2026-11-28):** fixed registered-workload ID validation and translation to immutable provider plan defaults now live in `worker/registered_prepare.js`. It owns the optional Kaggle-to-ZeroGPU artifact-reference resolution and uses the workload registry as the source for CPU/Kaggle/RunPod/Modal defaults. Existing `experiment_prepare` input and result contracts are unchanged. The entrypoint fell from 2,119 to 2,022 lines from parent `6cc311a`; direct module tests cover fixed defaults and fail-closed unknown IDs.


**Progress (2026-11-28):** owner-authorized Modal health checking now has one
authority in `worker/provider_health_diagnostic.js`. Both `experiment_provider_health`
and `experiment_submit` use the same workspace rate limit, plan one-use gate,
provider probe and persisted readiness result; submit can reuse a successful
plan health check. The existing submit contract is adapted at the caller so its
error codes remain compatible. `worker/index.js` fell from 2,022 to 1,875
lines from parent `30c77fc`; the 37-module graph remains acyclic.


**Progress (2026-11-28):** bounded Modal CPU plan validation, fingerprinting,
owner/idempotency persistence and response projection now live in
`worker/prepare_modal_cpu_plan.js`. The 10-minute single-use human
authorization lifetime has one authority in `worker/human_authorization_policy.js`
shared with the confirmation routes. Provider routing stays in the Worker
dispatcher; CPU plan creation is now its own domain operation. `index.js` fell
from 1,875 to 1,854 lines from parent `36935b3`.


**Progress (2026-11-28):** all Worker production SHA-256 digest generation now
uses `worker/sha256.js`, which defines the text-or-byte input contract and
canonical lowercase hex encoding. PKCE callers use the same byte digest before
base64url encoding. Removed parallel implementations from the entrypoint,
OAuth, provider, artifact and training modules. Known-vector tests cover text,
bytes, the empty digest and invalid input. The worker graph is acyclic across
40 runtime modules; `index.js` is 1,850 lines.

**Progress (2026-11-28):** `worker/experiment_list.js` now owns the shared
read model that merges owner-scoped local and delegated-provider runs, projects
their lifecycle/cleanup evidence, and applies filters and cursors. The MCP
contract and persisted state are unchanged; this reduces dispatch composition
without creating a second provider lifecycle. All 148 Worker tests pass and
the Worker import graph remains acyclic across 41 runtime modules.

**Progress (2026-11-28):** `worker/experiment_status.js` now owns local
owner-scoped run status/result reads, bounded output projection, and provider
sync callbacks for the common Sites ledger. Delegated plans retain their
existing adapter lifecycle and take precedence before this local path. The
Worker dispatcher shrank from 1,752 to 1,707 lines; all 148 Worker tests and
the 42-module acyclic import-graph check pass.

**Progress (2026-11-28):** execution-origin classification now has one
authority in `worker/execution_origin.js`, shared by the run-list and
status/result read models. It accepts only a run-bound cleanup receipt for the
retired local Runner classification. All 148 Worker tests pass and packaging
includes the 43-module acyclic Worker graph.

**Progress (2026-11-28):** `worker/provider_adapter_run_store.js` now owns
owner-scoped delegated-plan lookup, bounded adapter-state persistence and
redaction of private provider handles from MCP responses. Provider submission
policy remains in the orchestrator. Focused storage tests and the complete 151
Worker tests pass; the 44-module import graph is acyclic.

**Progress (2026-11-28):** `worker/local_run_cancellation.js` now owns local
queued/running cancellation transitions and dispatches RunPod cancellation
through its lifecycle adapter. Delegated cancellation remains adapter-owned;
Modal CPU cancellation remains a persisted cooperative request. The shared
151-test suite passes with an acyclic 45-module graph.

**Progress (2026-11-28):** `worker/run_reconciliation.js` now owns recovery
selection and result aggregation for existing delegated and RunPod runs. It
invokes existing lifecycle adapters and never submits new work. The complete
151-test suite, D1 migration check, Worker build and artifact verification
pass; the import graph is acyclic across 46 runtime modules.

**Progress (2026-11-28):** the owner-bound Modal CPU submit workflow now lives
in `worker/modal_cpu_submission.js`. It centralizes exact plan and single-use
authorization matching, health gating, budget reservation, idempotent run
creation and lost-submit recovery behind explicit provider/helper ports. All
151 Worker tests pass; the 47-module graph is acyclic and the packaged artifact
validates.

**Progress (2026-11-28):** Modal CPU status/submit/cancel synchronization,
bounded missing-Sandbox recovery, result verification and artifact finalization
now live in `worker/modal_cpu_lifecycle.js`. The dispatcher composes lifecycle
operations through narrow imports, and provider result trust rules stay with
their provider. All 151 Worker tests, D1 migration checks, build and artifact
validation pass; the 48-module graph remains acyclic. Exact-head CI is pending.

**Progress (2026-11-28):** adapter-backed prepare, authorization, provider
budget/lease claims, submit recovery and existing-run lifecycle routing now live
in `worker/delegated_experiment_lifecycle.js`. The dispatcher supplies the
short-lived Modal account evidence and secure random source, and chooses the
native or delegated lifecycle. This keeps the shared D1 run and authorization
contracts intact for all compatible MCP clients. All 151 Worker tests pass;
the 49-module graph is acyclic; D1 migration, build and artifact validation
pass. Independent Security Review found no actionable findings.
