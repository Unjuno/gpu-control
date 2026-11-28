# Repository architecture map

**Snapshot:** 2026-11-28 (Asia/Tokyo)  
**Source under inspection:** PR #70, `codex/owner-training-workloads`, current
head and exact-head CI recorded in `refactoring-progress.md`.
**Release status:** PR #70 is open and unmerged. Neither passing checks nor
mergeability proves deployment or provider acceptance. Repository mode
remains `parked`.

**Current source snapshot:** code head `527a711` on PR #70. The Sites Worker
suite passes 187 tests and its graph is acyclic across 67 runtime modules. The
root Python suite passes 619 tests, one skipped, and five subtests. All seven
exact-head CI checks pass on `527a711`. Local success is not hosted release
evidence.
`worker/index.js` is 147 lines,
while `worker/index.test.js` is 1,978 lines and remains the largest integration
fixture. Dedicated integration tests cover ChatGPT authorization (125 lines),
Modal health (277 lines), local cancellation (102 lines), and artifact retrieval
(67 lines); the
owner-training registration integration test is 682 lines, the
experiment read-model route test is 222 lines, and the MCP request-auth route
test is 43 lines. The Gateway provider-runtime CI selection, including five
compatibility-module identity checks, passes locally. These measurements
describe this source candidate only.

This is an evidence-backed map of the current repository, not a claim that all
listed source paths are active in the hosted product.

## Product boundary and flow

The product goal is an ordinary conversation with an authenticated compatible
MCP client: the user describes an experiment, an agent resolves an authorized
repository and a currently supported external GPU route, submits a bounded
job, then returns observed progress, results and cleanup. ChatGPT chat/Work is
one important client, not a separate product boundary. The agent should not
need the user to invent internal IDs, commits, provider payloads or retry keys.
It must not treat repository instructions or logs as authority.

```mermaid
flowchart LR
  U[User in any compatible chat or agent] --> A[Agent chooses route from intent]
  A --> M[Authenticated GPU Control MCP]
  M --> C[Capabilities, registrations, source binding]
  M --> P[Preview and exact persisted plan]
  P --> G[Owner identity, policy, provider budget, admission]
  G --> D[(Sites D1 lifecycle and budget records)]
  G -->|fixed RunPod lane| R[RunPod REST]
  G -->|fixed Modal or owner-selected candidate| MA[Modal adapter]
  MA --> K[Kaggle]
  MA --> H[Hugging Face Space and artifact store]
  MA --> S[Isolated Modal Sandbox]
  M --> O[Owner-scoped R2 artifacts]
  D --> A
  R --> D
  K --> D
  H --> D
  S --> D
  O --> A
```

This diagram combines two distinct contracts: the released/previously accepted
fixed-workload routes and the current PR #70 owner-selected Modal candidate.
Do not infer the latter is deployed. The intended agent workflow must discover
the authorized source and currently compatible external GPU route from current
capabilities, keep provider IDs internal, and return verified result and
cleanup. Google Colab currently has owner-bound connection and read-only
capability discovery only; its execution lifecycle is not integrated. A direct
external Colab MCP call bypasses the Sites owner, budget, run-history, and
cleanup ledger.

The Colab owner-connection setup/callback handlers are composed through
`worker/google_colab_oauth_routes.js`. The independent OAuth surface for other
MCP clients—discovery, dynamic client registration, consent, token exchange,
and revocation—is composed through `worker/mcp_oauth_routes.js`. GitHub setup
and the shared callback that proves GitHub identity for both GitHub App and
MCP-client connections live in `worker/github_oauth_routes.js`. These route
modules reuse the Worker's shared request-body parsers and HTML renderer.

## Module dependency graph

```mermaid
flowchart TD
  CHAT[ChatGPT Work or compatible MCP client] --> SITE[Sites Worker transport and tool dispatch]
  SITE --> DOM[Domain modules: source, plan, auth, budgets, lifecycle]
  DOM --> D1[(Sites D1)]
  DOM --> R2[(Sites R2)]
  DOM --> RP[RunPod adapter]
  DOM --> MA[Signed Modal adapter client]
  MA --> AD[Modal provider_adapter]
  AD --> CT[Custom training modules]
  AD --> PR[provider_runtime package]
  CT --> MD[(Modal Dict dispatch journal)]
  CT --> MV[(Modal Volumes source/checkpoints)]
  PR --> KH[Kaggle and Hugging Face]
  RP --> D1
  AD --> D1
  PY[gpu_control Python package] --> GW[Gateway service]
  GW --> PG[(Gateway PostgreSQL)]
  GW --> PR
  GH[GitHub Actions issue bridge] -. separate interface .-> PC[project_control]
```

A static import graph is the single runtime module inventory: the architecture
check enforces acyclic imports and the build copies the reachable closure from
`worker/index.js`, rejecting orphan runtime modules. The architecture check
reports the current module count. `experiment_input_contract.js` owns exact
MCP argument validation and environment-bound plan normalization separately
from public schemas in `mcp_tool_contract.js`; `provider_capabilities.js`
owns the read-only provider/workload capability projection and derives common
workload metadata from the generated workload registry and provider route
catalog; `provider_budget_policy.js` owns the D1-backed budget projection and atomic provider reservation checks;
and `github_tools.js` owns owner-scoped GitHub MCP operations.

Python core plan, workload, capability, lifecycle, and result fingerprints use
`src/gpu_control/canonical_json.py` as their single serialization/digest
implementation. The Sites Worker has a separate `canonical_json.js` because it
runs in a different runtime; cross-runtime byte compatibility fixtures are
still needed at persisted-contract boundaries rather than importing Python
code into the Worker.

The intended product flow is Sites-first. The Gateway links above represent a
separately maintained local-compatibility source tree, not proof it is deployed
or the live ChatGPT path. `gateway/README.md`, `docs/CHATGPT_SETUP.md`, and
`docs/STATUS.md` agree that the FastAPI/PostgreSQL Gateway is not a production
dependency. Its retained local service and deployment templates remain under
backlog A4 because their external use cannot be inferred from this checkout.
`src/gpu_control` is used by the Gateway and CLI/offline workflows, not by the
Sites Worker.

## Runtime and source ownership

| Area | Canonical responsibility | Main source | Boundary / status |
| --- | --- | --- | --- |
| Chat product surface | MCP tool names, schemas, user-facing descriptions, owner identity | `worker/mcp_tool_contract.js`, `worker/experiment_input_contract.js`, `worker/provider_capabilities.js`, `worker/owner_training_capabilities.js`, `worker/github_tools.js`, `worker/mcp_request_auth.js`, `worker/index.js`, `docs/CHATGPT_SETUP.md` | `mcp_tool_contract.js` owns public schemas, descriptions, output schema and annotations; `experiment_input_contract.js` owns exact runtime input validation; `provider_capabilities.js` projects fixed-route/workload readiness; `owner_training_capabilities.js` combines owner GitHub connection, Modal profile/budget and delegated-adapter readiness for custom repositories; `github_tools.js` owns owner-scoped GitHub connection tools; `mcp_request_auth.js` is the single boundary for ChatGPT identity header interpretation, allowlist resolution and OAuth principal verification. Sites is the intended ChatGPT surface; `index.js` owns transport composition and tool dispatch. |
| Fixed workload definitions | IDs, provider route, declared fixed resource/workload metadata | `sites/gpu-control-sites/workloads/registry.json` | Generated into Worker JS and Modal Python; generator validates provider route compatibility. |
| Provider and route identity | Provider billing class, credit eligibility, canonical route IDs, GPU/adapter-host flags and fixed route metadata | `sites/gpu-control-sites/workloads/provider-catalog.json` | Generated into `worker/provider_catalog.js`; MCP filters, capability projection, budget route mapping and adapter-route selection consume this copy. D1/provider evidence still owns current readiness, limits and execution state. |
| Owner-selected source identity | GitHub App installation proof, immutable GitHub user subject linked to one Sites owner, selected-repository-scoped installation tokens | `worker/github_app_connection.js`, `worker/github_tools.js`, `worker/training_source.js`, `drizzle/0035_github_owner_identity.sql` | `github_app_connection.js` verifies `/user` and exact installation access in the GitHub setup OAuth flow, stores only the numeric GitHub subject in `github_owner_identities`, and rejects cross-owner reuse or silent identity switches. `github_tools.js` owns Sites tool orchestration; `training_source.js` owns source registration and immutable commit resolution. User OAuth tokens are discarded; installation tokens are exact-repository read-only and trusted control-plane/stager input, never workload input. The immutable subject is also the external MCP login link. |
| External MCP client authentication | DCR, consent, GitHub owner proof, PKCE, short-lived access/rotating refresh tokens, audience and scope checks | `worker/mcp_oauth.js`, `worker/mcp_oauth_routes.js`, `worker/github_oauth_routes.js`, `worker/mcp_request_auth.js`, `worker/index.js`, `worker/github_app_connection.js`, `drizzle/0036_mcp_oauth_clients.sql` | `mcp_oauth.js` owns OAuth state/token protocol; `mcp_oauth_routes.js` owns discovery, registration, consent, token and revocation HTTP contracts; `github_oauth_routes.js` owns GitHub setup/callback and selects the corresponding owner-proof flow from persisted state; `mcp_request_auth.js` resolves ChatGPT/OAuth request identity and produces bearer challenges; `index.js` composes route dispatch and passes a resolved owner principal to existing tools. Clients share the same D1 plans, provider policies, run ledger and artifacts; OAuth execute scope does not bypass plan authorization or provider admission. Source is not deployed until migration and external-client handshake are verified. |
| Custom workload contract and inspection use case | Allowed task, entrypoint, Python version, GPU profiles, output paths, pinned lock and safe user-facing inspection response | `worker/training_contract.js`, `worker/training_inspection.js` | `readTrainingSourceContract` owns provider-neutral immutable manifest/lock verification; `readPublicTrainingContract` composes Modal readiness for compatibility. `.gpu-control/experiment.json` is required at the immutable commit; no repository Dockerfile or arbitrary shell command. |
| Training policy, runtime profile, and authorization identity | Authoritative lane ceilings/defaults, normalized owner-selected runtime environment, and shared training control-plane identity | `worker/training_policy.js`, `worker/training_runtime_profile.js`, `worker/map_training_configuration.js`, `worker/training_security_configuration.js` | Input/MCP contracts consume policy constants; MAP runtime bindings are normalized by `map_training_configuration.js`; owner runtime bindings are normalized by `training_runtime_profile.js`; the shared control-plane SHA is read only by `training_security_configuration.js`. The architecture check enforces these raw-binding boundaries. These leaf modules do not depend on plan orchestration. |
| Modal CPU workload policy | Fixed CPU resource limits, cost estimate and pricing provenance | `worker/modal_cpu_policy.js` | Capability reporting and execution use one fixed policy source; it does not configure provider account limits or enable GPU execution. |
| Plan, admission and accounting | Preview, execution plan fingerprint, idempotency, budget reservation, authorization, lifecycle | `worker/training_plan.js`, `worker/training_plan_state.js`, `worker/training_authorization.js`, `worker/modal_cpu_submission.js`, `worker/provider_budget_policy.js`, `worker/modal_account_evidence.js`, `drizzle/*.sql` | `training_plan.js` coordinates provider-neutral preview/prepare/submit; `training_plan_state.js` owns persisted status, readiness, cancellation and cleanup receipt projection; `training_authorization.js` owns exact owner confirmation and its canonical URL. `modal_cpu_submission.js` owns exact owner-plan authorization, health gate, shared-budget reservation, and idempotent local run creation for Modal CPU. `provider_budget_policy.js` owns atomic provider reservation and read-model rules; Modal routes additionally share the Modal reservation ledger. D1 owns Sites-side reservations; `modal_account_evidence.js` validates short-lived operator-observed provider account evidence separately from that ledger. `gateway_delegated_plans` is a historical table name for Sites adapter runs. Branch candidate admission remains off under parked policy. |
| Sites transport and MCP dispatch | Validate request, authenticate, route to domain/provider modules | `worker/index.js`, `worker/http_request_body.js`, `worker/http_response_body.js`, `worker/training_authorization_routes.js`, `worker/mcp_protocol.js`, `worker/mcp_tool_dispatch.js`, `worker/mcp_tool_errors.js`, `worker/mcp_tool_result.js`, `worker/experiment_list.js`, `worker/experiment_status.js`, `worker/execution_origin.js`, `worker/provider_adapter_run_store.js`, `worker/local_run_cancellation.js`, `worker/run_reconciliation.js`, `worker/modal_cpu_submission.js`, `worker/modal_cpu_lifecycle.js`, `worker/delegated_experiment_lifecycle.js`, `worker/modal_http_client.js`, `worker/provider_adapter_client.js`, provider lifecycle modules | `index.js` owns HTTP route composition and wires protocol, identity, result, authentication, and provider-specific route modules; `http_request_body.js` owns bounded request-body reading and format-neutral form/JSON decoding; `http_response_body.js` owns bounded external response byte collection and cancellation while callers retain provider-specific status, decoding, and public error semantics; `training_authorization_routes.js` owns the legacy MAP/fixed-CPU Sites browser confirmation and exact one-use challenge lifecycle; owner-selected plans use MCP submit authorization; `mcp_protocol.js` owns supported versions, request metadata/name checks, and read/execute scope selection; `mcp_tool_dispatch.js` owns authenticated tool-to-domain/provider routing; `mcp_tool_errors.js` owns the bounded stable public MCP error-code mapping; `mcp_tool_result.js` owns the canonical result envelope and versioned text/structured response projection; `experiment_list.js` owns the owner-scoped merged local/delegated run-list read model; `experiment_status.js` owns the local ledger status/result projection; `modal_cpu_submission.js` owns the owner-bound Modal CPU submit use case; `modal_cpu_lifecycle.js` owns Modal CPU status synchronization, recovery, cancellation finalization, result verification and artifact persistence; `delegated_experiment_lifecycle.js` owns adapter-backed plan preparation, exact authorization, provider budget/lease claims, submit recovery, and existing-run status/cancel/artifact routing; `execution_origin.js` owns shared run-bound execution provenance validation; `provider_adapter_run_store.js` owns bounded provider-observation persistence and private-handle redaction; `local_run_cancellation.js` owns local queued/running cancellation transitions and RunPod adapter dispatch; `run_reconciliation.js` owns recovery selection/aggregation across existing delegated and RunPod runs. `modal_http_client.js` owns the fixed-origin bounded HTTP contract for Modal CPU lifecycle operations; `provider_adapter_client.js` owns signed Sites-to-Modal-adapter delegation. Persisted D1 table names and `GATEWAY_DELEGATION_*` diagnostics are retained compatibility identifiers. `index.js` remains the HTTP/auth composition root, not an experiment/provider dispatcher.
| Modal provider adapter | Verify signed Sites envelope; dispatch bounded provider/runtime operations | `modal/provider_adapter.py`, `modal/provider_adapter_core.py` | Separate Modal service and secret boundary. Adapter has provider-specific code and owner-training orchestration. |
| Custom GPU staging/execution | Fetch pinned source, resolve hash-locked wheels for manifest Python, execute manifest entrypoint under CPU/memory hard limits, collect bounded outputs and cleanup | `modal/custom_training_*.py`, `modal/custom_sandbox_entrypoint.py` | Implemented in PR #70 source; admission and release acceptance are separate. Source fetch and job execution are separate sandboxes. |
| Provider runtime shared with Gateway tests | Shared Kaggle/HF contracts, backends, artifacts, settings and canonical Orbitune payloads | `sites/gpu-control-sites/modal/provider_runtime/` | Packaged into the adapter and Gateway worker image, imported/wrapped by Gateway code. Gateway no longer carries a second Orbitune payload copy. Verify every compatibility wrapper's real caller before retirement. |
| Generic Python control library | Offline policy, source/container verification, execution plans, provider lifecycle and RunPod client | `src/gpu_control/` | Root package; Gateway depends on it. Sites Worker does not import it. An AST contract test keeps `gpu_control` independent of `gpu_gateway` and the Sites provider runtime. It is not automatically the live Sites policy engine. |
| Legacy Gateway service | OAuth, FastAPI, PostgreSQL store, queue worker, recovery supervisor and API | `gateway/gpu_gateway/`, `gateway/deploy/` | Not the current production path; `gateway/app.py` identifies local compatibility use. Do not deploy its templates for Sites. |
| GitHub Project Checks | Owner-selected, immutable-source CPU checks in a trusted container; separate from GPU experiment routing | `project_control/`, `.github/workflows/project-checks-ci.yml` | Active Project Checks workflow; no imports from the retired Gateway comment bridge. Results are public repository comments and do not change GPU provider admission. |
| Workload examples | Fixed and research workloads, Dockerfiles, data contracts | `workloads/`, `sites/gpu-control-sites/modal/provider_runtime/workloads/` | Source payloads and workload instructions are untrusted data, not control-plane policy. |
| Policy and release evidence | Parked mode, trust rules, authorization constraints, dated acceptance evidence | `policies/`, `docs/acceptance/`, `docs/RELEASE_MATRIX.md` | Policy files constrain activation. Dated records are not current runtime state. |

## User interface surfaces

- **Agent interface:** natural-language conversation in ChatGPT/Work or another
  authenticated compatible MCP client. Tool descriptions and the operator
  Skill should let the agent discover the lifecycle without requiring users to supply internal
  identifiers. `experiment_capabilities.owner_selected_training` describes the
  custom GitHub source flow separately from fixed workload inventory; its
  per-owner connection state is read-only, and preview remains authoritative
  for each source's current runtime, manifest, quote and budget.
- **External-compute acceptance:** a configured GPU provider is not necessarily
  able to run an owner-selected repository. PR #70 proposes the first such lane
  on Modal only; existing RunPod, Kaggle and Hugging Face fixed workloads do
  not imply arbitrary-source support. See
  [ADR 0006](decisions/0006-chat-first-external-compute.md).
- **Sites web surface:** public status/connection pages and the legacy MAP
  exact-plan confirmation page. Public visibility is separate from owner-bound
  tool authorization. The owner-selected path uses the native destructive MCP
  write confirmation in the candidate.
- **Gateway static UI:** `gateway/gpu_gateway/static/` belongs to the separate
  FastAPI Gateway surface. It is not the ChatGPT Sites interface and should not
  become a dependency of the Sites user journey without an explicit decision.

## State and authority map

| State or fact | Intended authority | Copies/observations | Risk to manage |
| --- | --- | --- | --- |
| Current activation mode and allowed exceptions | `policies/repository-state.yaml` | Human-readable policy documents and tool behavior | Must stay fail-closed; no runtime config can override policy without reviewed change. |
| Sites fixed workload identity/defaults | `sites/gpu-control-sites/workloads/registry.json` | Generated `worker/workload_registry.js`, `modal/workload_registry.py` | CI checks generated copies; update source JSON and regenerate, never hand-edit generated copies. The legacy Gateway deploy fixture repeats selected immutable Kaggle/HF pins and has a focused contract test; its resource limits, transport, cleanup, and cost policy remain Gateway-owned. |
| Selected GitHub installation/repositories | Sites D1 GitHub App tables plus server-side GitHub App configuration | GitHub installation is external authority for repository access | Connector login alone is not the Worker credential. Installation token is short-lived and repo-scoped. |
| Registration, exact source SHA and execution spec | Sites D1 | `training_register`/`training_list` tool responses | Registration is not by itself proof of executable runtime/admission. |
| Plan, idempotency, authorization, budget reservation, owner-visible run identity and cleanup evidence | Sites D1 | MCP response and provider observations | D1 is the product ledger. For owner-selected training it records the immutable plan, one-time dispatch reservation, rejection and verified cleanup; it does not mirror every transient provider state. |
| Provider/Sandbox execution and resource cleanup | Provider resource inspected by the adapter | Modal `modal.Dict` keeps the adapter's handle, claim and last accepted terminal receipt; Sites D1 stores verified cleanup evidence | Provider observations can be newer than either ledger. A timeout or missing handle is `uncertain`, never proof of failure or permission to create a replacement. |
| Custom adapter dispatch claim and run journal | Modal `modal.Dict` store in the PR #70 custom adapter | D1 reservation; Modal Volumes hold staged source/checkpoints/artifacts | Atomic claim prevents duplicate Sandbox creation. On response loss, query the same run and recover the deterministic handle; do not submit again. The journal is not the owner-facing product ledger. |
| Artifact bytes | Sites R2 or explicitly configured private external artifact store | D1 stores immutable owner/run/path/revision/size/digest reference | Metadata match does not prove bytes; independently retrieve and hash when acceptance requires it. |
| Provider credentials | Provider-specific Sites secret or Modal secret | Configuration names only in source/docs; never values | Must remain outside tool schemas, D1, artifacts, logs, and workload processes. |
| Provider pricing and quota | Provider account evidence plus provider-specific policy/quote | Saved plan snapshot | Historical prices/credits expire; internal budget is not account billing control. |
| Actual publication state | Sites deployment platform and GitHub deployment/version records | `docs/STATUS.md`, release records | Documentation is not the authority for current publication. Refresh live before claiming deployed. |

## External compute routing

| Provider | Checked-in/currently described path | Product status distinction |
| --- | --- | --- |
| Modal fixed CPU/GPU | Sites -> authenticated Modal control/adapter | Historical live acceptances exist for exact old revisions. Current admission depends on live flags and policy. |
| RunPod fixed workload | Sites -> RunPod REST v2 or adapter relay, depending on lifecycle | Fixed canary has historical acceptance. Queue endpoints document automatic retry-on-failure; no owner-selected route is supported. See [ADR 0008](decisions/0008-runpod-owner-selected-execution.md) for the isolation, retry-accounting and artifact durability gates. |
| Kaggle GPU | Sites -> authenticated Modal adapter -> fixed registered Kaggle workload | Fixed workload route has historical live acceptance; free quota and exact current account state must be refreshed. |
| Hugging Face ZeroGPU/artifacts | Sites -> Modal adapter -> fixed Space/private artifact path | Fixed workload and immutable artifact round trip have historical evidence; not general arbitrary-code execution. |
| Owner-selected repository | Sites GitHub App selection -> immutable SHA -> strict manifest/lock -> trusted Modal stager -> isolated Modal GPU Sandbox | PR #70 source advertises this as a separate capability; owner admission is separate and repository policy remains parked. Not released/accepted by this map. |
| Google Colab | Candidate hosted Colab MCP/provider path | Not wired into Sites lifecycle. Direct MCP would be outside shared owner, budget, retry, artifact and cleanup contract. |

## Technology and contract inventory

| Surface | Language/runtime | Persistence/build/test |
| --- | --- | --- |
| Sites control plane | JavaScript ES modules, Cloudflare Worker | D1/Drizzle forward-only SQL, R2; npm; Node test runner; registry generator |
| Modal adapter and workloads | Python, Modal | Modal Dict/Volumes and provider APIs; pinned requirements; pytest; custom packaging checks |
| Generic control library | Python 3.11+ | `pyproject.toml`, `uv.lock`, pytest; package exposes `gpu-control` CLI |
| Gateway compatibility/service area | Python 3.11+, FastAPI/SQLAlchemy modules retained in source | `gateway/pyproject.toml`; current Gateway CI tests only the Sites-owned provider runtime and compatibility imports, not the FastAPI/PostgreSQL service |
| Project bridge | Python/GitHub Actions | Separate workflow and Docker-based check |
| External contracts | MCP JSON schemas, D1 schema, GitHub App API, Modal adapter HMAC envelope, provider APIs | MCP schemas/descriptions/annotations are canonical in `worker/mcp_tool_contract.js`; plan/lifecycle and cross-runtime provider semantics remain distributed across JavaScript, Python and docs. |

## Duplication and complexity inventory

These are investigation targets, not automatic deletion instructions.

1. **Legacy orchestration remains in source:** Sites owns the product path;
   the separate Gateway retains its own plans, lifecycle, authorization,
   persistence and provider logic, plus non-product CI-bridge and compatibility
   callers. Its FastAPI/PostgreSQL runtime is not current production. Inventory
   the legacy runtime's tests and remaining callers before staged removal; do
   not keep advertising it as a production alternative.
2. **Python/JavaScript parallel contracts:** `src/gpu_control` models policy,
   execution plans and provider lifecycle; Sites Worker implements the live
   user-facing contract independently in JavaScript. Some overlap is required
   by separate runtimes, but there is no single generated cross-runtime schema
   for plan/lifecycle/error semantics.
3. **Run state across D1 and Modal Dict:** the intended boundary is now
   recorded in [ADR 0002](decisions/0002-run-state-authority.md): D1 owns
   authorization, budget and product history; the adapter journal owns
   idempotent provider dispatch recovery; provider inspection owns current
   execution evidence. Cross-layer contract tests and retention behavior still
   need review before this can be considered settled for all provider routes.
4. **Provider implementation wrappers:** `gateway/gpu_gateway` has modules
   such as Kaggle/HF backends that delegate to `modal/provider_runtime`; tests
   and Docker packaging enforce those compatibility imports. Preserve only
   wrappers with verified callers/contracts.
5. **Large files (current worktree at PR #70 code head `158ff2c`):**
   `worker/index.js` 147 lines; `worker/training_authorization_routes.js` 210 lines;
   `worker/mcp_tool_dispatch.js` 122 lines;
   `worker/delegated_experiment_lifecycle.js` 391 lines;
   `worker/modal_cpu_lifecycle.js` 165 lines; Worker integration test
   `worker/index.test.js` 1,918 lines; owner-selected training registration
   lifecycle coverage is in `worker/training_registration.integration.test.js`
   (682 lines). `worker/training_plan.js` is now 332 lines and coordinates
   preview/prepare/submit. `worker/training_plan_state.js` (78 lines) owns
   persisted state/readiness/cancellation/cleanup projection, while
   `worker/training_authorization.js` owns exact confirmation and its URL.
   MAP-specific plan
   construction is isolated in `worker/map_training_plan.js` (115 lines), the
   atomic D1 authorization/budget/dispatch claim in
   `worker/training_dispatch_claim.js` (78 lines), and the existing Modal
   owner-selected builder in `worker/modal_owner_training_plan.js`. Colab's capability
   handler is 82 lines and its transport
   client is 101 lines; no Colab plan or run lifecycle caller exists yet. MCP
   tool schema and GitHub source tests also live beside their module contracts.
   `gateway/gpu_gateway/store.py` 1,156; Gateway `worker.py` 1,094;
   `modal/provider_adapter.py` 720; `src/gpu_control/execution.py` 510.
   Split by cohesive domain/use case, not line count alone.
6. **Documentation state drift:** `chatgpt-selected-repository-experiments.md`
   and `sites/README.md` have previously described source inspection as the end
   of the owner-selected lane. PR #70 implements more, but policy disables
   admission; release/current-state documents must distinguish source from
   deployed. `training_prepare` performs manifest, dependency-lock, provider,
   runtime, quote and budget checks for a run request. `training_inspect` and
   `training_preview` remain optional detailed/plan-only diagnostics.
7. **Provider names vs compute routes:** Modal is both a compute provider and
   host for the Kaggle/HF adapter. Treat adapter infrastructure separately
   from the provider selected for the experiment.

## Dependency rules to preserve and enforce

- ChatGPT/agent -> Sites tool contract -> domain plan/lifecycle -> provider
  adapter -> external provider. Never let a provider module decide user intent.
- Domain policy must not depend on HTTP, D1 SQL, Modal SDK or UI details; put
  those behind narrow storage/provider interfaces where a real use case needs
  the boundary.
- Workload repositories, logs, artifacts and model output are data. They do
  not import or override control-plane policy.
- Each provider adapter implements the same externally visible run lifecycle,
  while retaining provider-specific cleanup and evidence semantics.
- Only explicitly generated files may be derived. Every other duplicated
  business rule needs an owner, a parity check, or a documented reason.

## Reproduction commands for structural inventory

```sh
git status --short --branch
git show -s --format='%H %cs %s' HEAD
wc -l sites/gpu-control-sites/worker/index.js \
  sites/gpu-control-sites/worker/index.test.js \
  sites/gpu-control-sites/worker/run_artifacts.js \
  sites/gpu-control-sites/worker/run_artifacts.test.js \
  sites/gpu-control-sites/worker/registered_prepare.js \
  sites/gpu-control-sites/worker/registered_prepare.test.js \
  sites/gpu-control-sites/worker/provider_health_diagnostic.js \
  sites/gpu-control-sites/worker/prepare_modal_cpu_plan.js \
  sites/gpu-control-sites/worker/human_authorization_policy.js \
  sites/gpu-control-sites/worker/sha256.js \
  sites/gpu-control-sites/worker/sha256.test.js \
  gateway/gpu_gateway/store.py gateway/gpu_gateway/worker.py \
  sites/gpu-control-sites/modal/provider_adapter.py \
  src/gpu_control/execution.py sites/gpu-control-sites/worker/training_plan.js
rg --files src/gpu_control gateway/gpu_gateway sites/gpu-control-sites/worker \
  sites/gpu-control-sites/modal
```
