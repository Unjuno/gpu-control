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
  registration. The current official CLI supports headless Linux/macOS
  automation, ephemeral `colab run`, and `colab usage` account CU/balance
  display. Current CLI OAuth tokens use the OS-native keyring, while session
  metadata/history live under `~/.config/colab-cli/`; both are separate from
  Sites D1. Direct CLI jobs do not create Sites run records. A Worker cannot
  launch the CLI. The former macOS Runner, Keychain bearer and `/runner/*`
  path are explicitly retired and must not be restored. Colab's documented
  hosted API does not provide a per-run dollar quote or CU balance.
  **Policy evidence (2026-11-28):** the documented `get_subscription` schema
  returns only the tier, not CU balance. Google's usage policy restricts remote
  control, notebook-UI bypass, and distributed workers on managed runtimes
  when the account is free or has no positive CU balance. A future exact plan
  therefore needs a fresh GPU eligibility check and an explicit owner
  attestation of positive CU in the same native submit confirmation; there is
  no API-backed balance proof or USD ceiling. Free-tier execution without
  positive CU is disallowed. Sites must never purchase a Pay-As-You-Go top-up.
- **Decision:** GPU Control's owner-bound API/MCP is the one product control
  plane; ChatGPT chat/Work is the primary client, not the only client. ChatGPT,
  Codex, and future local/CI clients should use the same plan authorization,
  provider adapters, run ledger, results, and cleanup contract. Implement the
  hosted Colab MCP as a provider adapter with a one-time, owner-scoped Google
  OAuth connection. Encrypt refresh credentials in the Sites trust boundary
  and keep Google tokens away from the agent/workload. The official Colab CLI
  can run standalone CI jobs, but direct CLI jobs are not GPU Control runs. A
  CI execution host can join the product route only through the same
  owner-bound job, lifecycle, artifact, and cleanup contract; it must not
  create a second control plane or silently fork the ledger. Add another
  client only when it can call the shared control-plane contract under the
  same owner identity and authorization.
- **Work:** implement owner-bound Google OAuth connect/disconnect, protected
  credential refresh, hosted MCP client, exact-plan creation, idempotent
  runtime/session lifecycle, bounded source/result transfer, cancellation and
  cleanup receipts. Keep cost as unknown until account CU semantics can be
  trusted; never label the internal Sites reservation a Google billing cap.
  **Open boundary decision (2026-11-28):** Colab's managed runtime does not
  inherit the Modal sandbox's enforced no-egress policy; installing
  hash-locked dependencies may require Internet access from the runtime. The
  provider contract must state `network_egress: unrestricted`, keep
  provider/GitHub credentials and private data out of the runtime, and delete
  only a newly created run-owned runtime after the exact plan authorizes it.
  This material provider-specific disclosure is recorded for owner review;
  admission remains closed until the route and its authorization wording are
  accepted and implemented.
  Keep this provider policy behind a Colab-specific plan/adapter boundary;
  shared owner authorization, exact-plan confirmation, D1 run history, artifact
  metadata, and terminal cleanup remain the single lifecycle authority. Modal's
  owner-selected plan construction has been separated from the shared training
  orchestrator as a first boundary; it is not evidence of Colab readiness.
  Google runtime creation and execution can outlive one interactive MCP
  request. Persist stable Google request/session/execution IDs in the existing
  owner-bound training run and let later status calls reattach to the exact
  unfinished operation. Do not add a queue, a longer blocking HTTP wait, or a
  second run ledger unless a Colab operation proves unrecoverable through its
  documented idempotency contract. Never replay an execution after its result
  has been returned; treat a lost persistence response as uncertain. Runtime
  deletion remains an explicit owner action; automated cleanup closes only
  the session created for the run.
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
- **Progress (2026-11-28):** added a Worker HTTP integration test for protected
  resource and authorization-server discovery, DCR, consent-page creation,
  and rejection of a bearer header at the token endpoint. OAuth module tests
  cover the full local PKCE/owner-binding/token lifecycle. The independent
  external-client handshake and shared two-client ledger check remain release
  gates.

## P2 — reduce module entropy without moving complexity to callers

### A7. Decompose the Sites Worker by domain and narrow tool dispatch

- **Evidence:** at source head `c6c69c2`, `worker/index.js` is 816 lines and
  remains the transport and composition root for authentication, owner identity,
  routing and provider
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
slug is centralized in `training_source.js`. Historical checkpoints measured
2,333 and 2,175 lines before later lifecycle and transport extractions; the
entrypoint has since been reduced to 471 lines. Provider-specific Colab OAuth,
external-MCP OAuth, and the shared GitHub owner-proof callbacks now have
dedicated route modules. Remaining A7 work is to further reduce the HTTP/MCP
composition root without duplicating transport contracts.
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

**Progress (2026-11-28):** authenticated MCP tool-to-domain/provider routing
now lives in `worker/mcp_tool_dispatch.js`. `index.js` retains request parsing,
MCP metadata/scope checks, HTTP routing and response envelopes, then passes the
normalized call and bounded submission callbacks to the dispatch interface.
Unused provider/workload imports and constants were removed from the entrypoint.
The Worker graph remains acyclic and all 169 Sites contract tests pass;
`index.js` is now 471 lines. Colab's provider-specific OAuth setup/callback
handlers live in `worker/google_colab_oauth_routes.js`; external MCP discovery,
registration, consent, token and revocation routes live in
`worker/mcp_oauth_routes.js`; GitHub App and MCP client owner proof flows live
in `worker/github_oauth_routes.js`. These route modules reuse the shared HTTP
composition safely.

**Progress (2026-11-28):** Colab OAuth setup and callback handlers now live in
`worker/google_colab_oauth_routes.js`; `index.js` supplies the shared HTML
renderer and `escapeHtml` helper. The PKCE cookie, callback origin/path check,
state/code validation, response headers, and public messages are preserved.
All 166 Sites tests pass and the runtime graph is acyclic across 59 modules.
Independent security review found no actionable issues. No Google account,
provider, run, credential, deployment, or admission state was touched.

**Progress (2026-11-28):** external MCP OAuth discovery and HTTP flows now live
in `worker/mcp_oauth_routes.js`; `index.js` retains only GitHub OAuth callback
identity proof needed to bind both the GitHub App and MCP-client flows. OAuth
business rules remain in `mcp_oauth.js`; request parsing is reused from the
Worker. Invalid consent submissions now reliably clear their one-time CSRF
cookie (the old four-argument `htmlPage` call silently ignored its cookie
argument). The full 167-test suite passes and the 60-module graph is acyclic.
Independent security review found no actionable issues. No live OAuth,
provider, deployment, or admission action occurred.

**Progress (2026-11-28):** GitHub App setup and the callback shared with
external MCP owner proof now live in `worker/github_oauth_routes.js`. The route
chooses the existing owner-proof flow from its persisted state, while GitHub
installation verification, OAuth exchange, and MCP authorization state remain
in their respective domain modules. The original PKCE cookie separation and
callback/error behavior are preserved. All 169 Sites tests pass; the 61-module
graph is acyclic. Independent security review found no actionable issues. No
GitHub identity, credential, provider, run, deployment, or admission state was
changed.

### A8. Split test fixtures by contract and reuse domain builders

- **Evidence:** Sites `index.test.js` measured 3,444 lines at source candidate
  `615e039`; at head `ae2f1fc` it is 2,435 lines after contract, source,
  authentication, and read-model route tests were extracted. It still combines
  route, capability, provider,
  cancellation, artifact and run-list integration concerns. Gateway
  store/worker tests are also large. The suite has valuable runtime contracts.
- **Work:** partition tests by domain and lifecycle; extract only stable test
  builders. Preserve explicit failure cases and avoid generic fixture engines.
- **Done when:** a contributor can run one domain's tests and understand its
  setup; full CI still covers public schemas, migrations, replay and cleanup.
- **Progress (2026-11-28):** moved the 631-line owner-selected training
  registration integration test out of `index.test.js` into
  `training_registration.integration.test.js`. The test keeps the SQLite/D1
  behavior and assertions; it now owns only the minimal worker environment it
  needs. It is 680 lines at current head. The full suite has grown to 163 tests
  and the Worker graph to 52 modules. Further lifecycle groups and repeated
  fixture shapes still need inventory before introducing shared builders.
- **Progress (2026-11-28):** moved the public anonymous-request challenge and
  OAuth bearer audience/scope HTTP route tests into
  `worker/mcp_request_auth.integration.test.js`. Its local D1 fixture is
  purpose-built for token lookup and empty run listing, so it no longer depends
  on the broad `index.test.js` environment builder. Focused tests pass (2/2),
  the full suite remains 163/163, and `index.test.js` shrank by 48 lines.
- **Progress (2026-11-28):** moved seven owner-scoped run-list and status/result
  HTTP integration cases to `worker/experiment_read_models.integration.test.js`.
  The new file uses a minimal per-case D1 fixture rather than the provider-heavy
  general environment. All seven focused cases and the complete 163-test Sites
  suite pass. `index.test.js` shrank by 201 lines to 2,435 lines; the extracted
  file is 222 lines. Filtering, pagination, provider provenance, terminal
  cleanup state, and cross-owner privacy assertions remain intact.

### A9. Consolidate Python/Gateway provider runtime duplication by consumer

- **Evidence:** Kaggle and Hugging Face provider implementation has one
  canonical owner under `sites/gpu-control-sites/modal/provider_runtime/`.
  Five Gateway import paths (`kaggle_backend`, `huggingface_space_backend`,
  `huggingface_artifacts`, `kaggle_bridge`, and `orbitune_workload`) alias those
  exact module objects through `_sites_provider_runtime.py`. Gateway registry,
  worker, inventory code and existing tests still call those import paths;
  Docker images package the shared runtime. Root `src/gpu_control` remains a
  separate reusable control library rather than a second implementation of
  these provider adapters. It has no reverse imports from Gateway or the Sites
  provider runtime; Gateway consumes its capability, selection, pricing, and
  execution contracts.
- **Work:** build an import/call graph. Keep one provider implementation for
  Kaggle/HF semantics; retain only compatibility facades with real callers.
  Retire a facade only alongside its Gateway caller or after those callers use
  the canonical namespace and packaging still excludes unrelated Gateway
  services.
- **Done when:** one implementation owns each provider protocol, with
  intentional compatibility facades only where a real external caller needs
  them.
- **Progress (2026-11-28):** the loader resolves either the repository
  checkout's Sites-owned runtime or the copy packaged in the Gateway image;
  both Gateway Dockerfiles copy that canonical directory. The five Gateway
  facades replace their `sys.modules` entry with the canonical implementation.
  Added an identity contract test for all five paths to the provider-runtime
  CI workflow, and the full workflow test selection passes locally. This
  confirms no second implementation is being maintained; Gateway callers still
  justify the import facades, so removing them now would spread migration work
  or break callers. The service-level Gateway retirement decision remains
  open under A4.

## P3 — standards that prevent regression

### A10. Normalize error, lifecycle and plan schemas across runtimes

- **Work:** define stable versioned schemas for plan, provider observation,
  cleanup, artifacts, capabilities and typed errors. Generate validators/docs
  or run cross-language conformance fixtures; do not hand-duplicate semantic
  rules.
- **Done when:** Worker, adapter and any retained Gateway pass identical
  contract fixtures and fail closed on unknown versions/fields.
- **Progress (2026-11-28):** Python core plan, workload, capability,
  lifecycle, and result fingerprints now delegate canonical JSON bytes and
  SHA-256 formatting to `src/gpu_control/canonical_json.py`. A focused
  architecture test prevents those model modules from reintroducing direct
  `json.dumps`/`hashlib.sha256` implementations. The Worker keeps its own
  runtime-local serializer; matching persisted contracts still need
  cross-runtime fixtures before claiming end-to-end normalization.

### A11. Inventory and normalize configuration

- **Work:** enumerate env vars by owner, secret/config type, provider, stage,
  default, validation, and current consumers. Centralize parse/validation by
  domain; reject contradictory or orphaned settings. Never print secret values.
- **Done when:** every runtime setting has one owner and test; no undocumented
  magic fallback or stale configuration can advertise an unavailable route.
- **Progress (2026-11-28):** owner-selected runtime image, hourly/staging
  rates, quote expiry, runtime, and cost/monthly ceilings are parsed only by
  `worker/training_runtime_profile.js`. The training plan consumes that
  normalized object, and the architecture check forbids raw reads elsewhere.
  Focused validation covers configured and missing values. MAP-specific
  source, image, quote, runtime, and monthly settings now have the same
  normalization boundary and guard. The MAP admission flag is parsed at that
  boundary but remains a separate live gate from profile validity. Shared
  control-plane signing and other provider configuration still need the wider
  inventory.

### A12. Add architecture checks only after rules have an owner

- **Work:** enforce generated registry freshness, forbidden dependency
  directions, no control imports from workload payloads, migration append-only
  policy, schema parity, and source/deployment status labels in CI.
- **Done when:** checks reject an actual known regression and give a local,
  actionable message; avoid broad lint rules with no established invariant.

**Progress:** `npm test` runs `scripts/check-worker-architecture.mjs`, which
uses the same static Worker import graph as packaging. It checks static in-tree
imports, rejects dynamic imports and entrypoint backedges, and fails on cycles.
The build copies the modules reachable from `index.js` and fails if a runtime
module is orphaned. This establishes Worker dependency and packaging rules;
Python host direction, schema parity, and append-only migrations remain open.

**Progress (2026-11-28):** `tests/test_package_boundaries.py` parses the reusable
`src/gpu_control` package and rejects imports from Gateway or the Sites-owned
provider runtime. The root Python suite passes 616 tests and five subtests (one
skipped). The D1 replay test now treats the migration directory as its
authoritative filename inventory and checks only that version prefixes remain
ordered, unique, and gap-free.

**Progress (2026-11-28):** Gateway's legacy Kaggle/Hugging Face deployment
fixture and the Sites registry repeat provider identity, immutable source,
image, resource, and GPU pins. A focused Gateway contract test now checks those
shared facts against the Sites registry. Gateway-specific resource limits,
transport, cleanup, and cost policy remain independently owned because their
meanings and lifecycle differ; the two JSON files are not interchangeable
runtime registries. Retiring or generating the legacy deployment contract is
still gated by A4 and the external-operator decision.

**Progress (2026-11-28):** the legacy Gateway worker image no longer copies a
second Kaggle/ZeroGPU payload tree. The adapter's `provider_runtime` directory
is the actual source consumed by its staging code; Gateway's duplicate payloads
were only read by a stale source test. Tests now inspect the canonical payload,
and Gateway CI runs those payload contracts plus its previously uninvoked
systemd-template tests and syntax verifier. CPU smoke and tiny-LM assets remain
separate because they have independent consumers.

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


**Progress (2026-11-28):** provider-specific D1 reservation checks now share
the authoritative `worker/provider_budget_policy.js` module with budget
projection and shared Modal reservation construction. Added SQLite-backed
checks for RunPod per-run ceilings, exact retry binding and fail-closed unknown
providers. All 152 Worker tests, migration checks, build and artifact
validation pass; the graph remains acyclic across 49 modules.

**Progress (2026-11-28):** `worker/mcp_request_auth.js` now owns ChatGPT Sites
identity-header interpretation, allowlist resolution, OAuth principal
verification and bearer challenge construction. A static architecture guard
restricts those identity sources to the dedicated request-auth boundary. All
156 Worker tests, migration checks, build and artifact validation pass; the
acyclic Worker graph contains 50 runtime modules. Independent Security Review
found no actionable findings.

**Progress (2026-11-28):** moved public MCP schema/description assertions to
`worker/mcp_tool_contract.test.js`, GitHub source pinning cases to
`worker/training_source.test.js`. `worker/index.test.js` shrank from 3,445 to
3,326 lines at that checkpoint without dropping coverage. At head `ae2f1fc`,
it is 2,435 lines; all 163 Worker tests pass locally and the graph is acyclic
across 52 runtime modules. The 7-test read-model and 2-test request-auth route
slices pass on their own.

**Progress (2026-11-28):** the shared `MAP_TRAINING_CONTROL_PLANE_SHA`
authorization identity now has one Worker binding reader in
`worker/training_security_configuration.js`; capabilities, plan submission,
and Site confirmation routes use that boundary. A static architecture check
prevents direct reads elsewhere. All 163 Worker tests, migration checks,
build, and artifact validation pass; the 52-module graph is acyclic.
