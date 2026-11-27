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

- **Evidence (2026-11-28):** PR #70 is open and unmerged at
  `a9a85e2db90a54d521c649a68745e6320096f6b3`. The seven checks for the
  preceding documentation-only head `b2c6755afdb4fbed7c0f330c38d80acbb3c59318`
  are running; all seven passed on code SHA
  `44f21867dbd7f7066ca16bb6441cf9ea3b07edee`. The PR diff is 112 files
  (+11,247/−575). Ten of 19 inline review threads were unresolved before
  review; each was checked against current code/tests and resolved. Its
  description is now synchronized. GitHub's mergeable flag does not establish
  independent security review, deployment, or provider acceptance. Repository
  mode remains `parked`; owner-training admission and live D1 remain unchanged.
  Source head, CI, review, migration and deployment evidence are tracked
  separately in `refactoring-progress.md`.
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
- **MAP account gate:** ADR 0007 adds a separate L4 Workspace evidence contract
  to prevent the Sites reservation from being mistaken for the actual Modal
  account cap. The candidate rejects a MAP monthly configuration above $1 and
  binds/rechecks the exact account evidence at submit. This evidence remains
  operator-supplied and does not replace verification of the provider-side
  usage limit.
- **Work:** define a versioned provider/workload capability contract with
  provider identity, compute-vs-host role, task compatibility, quote/quota
  freshness, ceilings, paid/free semantics, cancellation and cleanup evidence.
  Generate client/server constants where runtime parity is required.
- **Done when:** adding/removing a provider or workload requires one canonical
  definition plus its adapter implementation and acceptance evidence; no
  provider can be advertised just because an adapter host is configured.

### A6. Decide Colab integration at the shared lifecycle boundary

- **Evidence:** `docs/architecture/google-colab-provider.md` describes a
  hosted MCP, but direct calls bypass Sites D1 owner/run/budget/cleanup state.
- **Work:** compare direct ChatGPT MCP connection with a Sites-owned adapter.
  Preferred product path is a provider adapter behind the same owner, plan,
  run, result and cleanup contract. First prove identity delegation, interactive
  session lifetime, GPU/runtime quota visibility, cancellation and durable
  artifact handoff. Keep Colab unavailable until all are enforceable.
- **Done when:** user can ask the same ordinary-language experiment request and
  agent can safely choose Colab only when current capability and quota permit;
  otherwise it explains the concrete blocker without paid fallback.

## P2 — reduce module entropy without moving complexity to callers

### A7. Decompose the Sites Worker by domain and narrow tool dispatch

- **Evidence:** `worker/index.js` is 2,351 lines and remains a large transport
  and composition root for authentication, owner identity, routing and provider
  workflows. MCP schemas/descriptions, experiment input contracts, GitHub
  ownership, training lifecycle, budgets and RunPod lifecycle now have separate
  modules, but provider operations and route dispatch still occupy the entry.
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
slug is centralized in `training_source.js`. `index.js` was about 2.8k lines before the A7 contract extraction; it is now 2,564 lines.
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

**Progress (2026-11-28):** the ordinary custom-repository route is now
`training_register` → `training_preview` → `training_prepare` →
`training_submit`. Preview already validates the same immutable manifest and
dependency lock as `training_inspect`, while also checking the current GPU,
runtime, quote and budget; inspect remains available as an optional diagnostic.
Capabilities, registration responses and `training_list` now point directly to
preview, avoiding a redundant tool call. MCP descriptions now state the shared
Modal reservation ceiling accurately. The 114 Worker tests, migration replay,
build and artifact validation passed locally; exact-head CI is pending.

### A8. Split test fixtures by contract and reuse domain builders

- **Evidence:** Sites `index.test.js` is 3,388 lines (2026-11-28); Gateway store/worker tests
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
