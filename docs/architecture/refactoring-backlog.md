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

- **Evidence:** PR #70 candidate branch is open, mandatory review required,
  merge blocked; repository mode `parked`; owner-training admission must remain
  false until its release gates pass.
- **Work:** maintain a compact release record that separately names source
  head, merge SHA, Sites deployment/version, applied D1 migration, live tool
  schema, provider configuration, and exact end-to-end acceptance run.
- **Done when:** no current-state document promotes PR source or old canaries
  into present-day deployed capability; the first-run ChatGPT prompt names
  actual available actions and blockers.

### A1. Make the owner-selected experiment a complete conversational journey

- **Evidence:** source modules exist for GitHub App selection, registration,
  default-branch pinning, manifest/lock inspection, plan, staging, isolated
  custom Modal Sandbox, outputs and cleanup. `OWNER_TRAINING_ADMISSION_ENABLED`
  is independently gated; policy is parked.
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
- **Done when:** ordinary ChatGPT and Work tool schemas both expose the same
  supported lane; a current authorized test demonstrates the complete lifecycle
  on the intended external GPU and owner-scoped result retrieval. No release
  claim based solely on unit tests, a plan, a staging sandbox, or old run.

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
  labels its FastAPI app a local compatibility entrypoint. The Gateway CI
  workflow tests the Sites-owned provider runtime and its wrappers, not the
  FastAPI/PostgreSQL service. `gateway/scripts/comment_bridge.py` still imports
  `gpu_gateway.ci_bridge`; historical service tests also cover the retained
  API/store/worker implementation.
- **Decision:** do not treat Gateway as a production deployment. Keep its three
  concerns separate: GitHub Issue bridge, provider-runtime compatibility
  imports, and legacy Gateway service code.
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

- **Evidence:** `worker/index.js` is 2,607 lines and includes tool descriptions,
  authentication, owner identity, dispatch and several provider handlers;
  `training_plan.js` and RunPod modules already provide extraction seams.
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
slug is centralized in `training_source.js`. `index.js` is now 2,607 lines.
The rest of the worker/router decomposition remains open.

### A8. Split test fixtures by contract and reuse domain builders

- **Evidence:** Sites `index.test.js` is 3,143 lines; Gateway store/worker tests
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

## Decision queue

1. Is Gateway a supported product/runtime or is it a retirement candidate?
2. Is Colab integrated through the shared Sites lifecycle, and what Google
   session/quota/cancel mechanism is acceptable?
3. Which external providers are allowed to run arbitrary owner-selected
   repository code under the strict manifest contract? PR #70 only proposes
   Modal; fixed Kaggle/HF/RunPod workloads do not imply this capability.

While these decisions are open, continue documentation truth repair, module
inventory, source-only tests and non-production refactoring. Do not enable
provider admission or remove a potentially live contract.

## Batch record template

For each implementation round record: goal and observed baseline; files and
public contracts touched; old callers migrated; deleted/retained compatibility
and why; local validation and exact-head CI; review result; source SHA; merge,
deployment and live acceptance as separate fields; remaining backlog IDs.
