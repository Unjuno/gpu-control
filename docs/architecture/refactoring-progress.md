# Architecture refactoring progress

This is the execution log for the architecture task pool in
[`refactoring-backlog.md`](refactoring-backlog.md). Each entry records source
work separately from merge, deployment, provider configuration and live
experiment acceptance.

## 2026-11-29 — A19: move Modal GPU account policy behind its provider boundary

**Finding:** `mcp_tool_dispatch.js` owned the Modal GPU's fixed T4 identity and
$30.00 Workspace usage cap while the evidence validator lived in
`modal_account_evidence.js`. The composition layer therefore carried provider
policy in addition to routing tools.

**Change:** `modal_gpu_policy.js` now owns the exact account-evidence
requirements together with the admission predicate. The dispatcher delegates
to that provider operation; the existing `modalGpuProviderEvidence` export
remains as a compatibility alias. Policy tests bind valid evidence to T4 and
the configured cap and reject alternate values.

**Validation:** the compatibility export tests and focused Modal GPU policy
tests pass; the full Sites suite passes (220), the Worker graph is acyclic
across 82 runtime modules, registry freshness and architecture checks pass.
Worker build, artifact validation, D1 forward-migration replay, and
`git diff --check` pass. No provider, credential, admission, deployment, or
experiment state was changed.

## 2026-11-29 — A16: centralize Colab execution and artifact bounds

**Finding:** the Colab plan and generated runtime each capped runtime at 360
seconds. The generated Python runner, artifact downloader, and receipt parser
also carried separate literals for per-file and total output sizes; the receipt
parser independently repeated the output count and receipt-size ceilings.
Changes could therefore make the runner, persisted receipt, and control-plane
validator disagree.

**Change:** added `worker/google_colab_execution_limits.js` as the authority for
the owner-selected execution's runtime, artifact, and receipt ceilings. Plan
validation, generated Python, file retrieval, and receipt parsing consume those
exports. The existing `GOOGLE_COLAB_MAX_FILE_BYTES` export remains as a
compatibility alias. HTTP payload limits stay in their respective transport
modules because they protect different boundaries. The static Worker
architecture check now rejects reintroduced execution/artifact limit literals
in their consumer modules.

**Validation:** focused Colab plan/runner/artifact tests pass (11/11), the full
Sites suite passes (217), the Worker dependency graph is acyclic across 81
runtime modules, registry freshness and architecture checks pass, Worker build
and artifact validation pass, the D1 forward-migration replay passes, and
`git diff --check` passes. No provider, credential, admission, deployment, or
experiment was accessed or changed.

## 2026-11-29 — A17: centralize Modal GPU admission interpretation

**Finding:** capability projection and delegated submit independently
interpreted `MODAL_GPU_WORKLOAD_ADMISSION_ENABLED === "true"`. Although the
literal matched, the two paths could drift and capability discovery might
report a different gate from the one submit enforces.

**Change:** added `worker/modal_gpu_policy.js` as the single fail-closed
interpreter. Both capability projection and submit now use it. The Worker
architecture check prevents other runtime modules from reading this binding
directly; a unit test pins the literal-true behavior.

**Validation:** focused policy/budget tests pass, the full Sites suite passes
(218), the Worker dependency graph is acyclic across 82 runtime modules, and
registry freshness and architecture checks pass. Worker build and artifact
validation, D1 forward-migration replay, and `git diff --check` pass. No
provider, credential, admission, deployment, or experiment state was changed.

## 2026-11-29 — A18: project delegated run state once for list and filters

**Finding:** the delegated run-list query computed the same state CASE once in
its state filter and again in JavaScript for the returned row. Expiry time was
also read separately for those interpretations. This duplication could make
an item match a state filter but be returned with another state.

**Change:** the delegated list query now projects `projected_state` once in a
subquery. The outer query uses that field for state filtering before ordering
and limit; the response mapper reads the same projected field. Local run state
remains sourced from its authoritative `runs.state` column.

**Validation:** the experiment read-model suite passes, including a real
SQLite projection and filter-before-pagination case. The full Sites suite
passes (219), the Worker dependency graph is acyclic across 82 runtime modules,
registry and architecture checks pass, Worker build/artifact validation and
D1 forward-migration replay pass, and `git diff --check` passes. No provider,
credential, admission, deployment, or experiment was accessed or changed.

## 2026-11-29 — A11: share RunPod relay readiness validation

**Finding:** `runpodConfigured` treated a relay URL and two proxy-token strings
as sufficient configuration, while `jobTransport` used the provider adapter's
full validator for the pinned host, HMAC key, key ID, and token formats. This
could report a ready RunPod route that failed as soon as dispatch constructed
the transport.

**Change:** RunPod readiness now calls `providerAdapterConfigured`, the same
authority used by dispatch. Regression assertions cover malformed HMAC,
malformed proxy secret, and untrusted adapter host; valid relay and direct
RunPod-key configurations remain accepted.

**Validation:** the focused RunPod tests pass (11), the full Sites suite
passes (214), the Worker graph remains acyclic across 78 modules, and
`git diff --check` passes. No provider, credential, admission, deployment, or
billing state was touched.

## 2026-11-29 — A11: centralize Modal CPU admission parsing

**Finding:** capability projection, provider-health diagnostics, and Modal CPU
submission each interpreted `CPU_WORKLOAD_ADMISSION_ENABLED === "true"` on
their own. The behavior matched but had no setting owner and could drift.

**Change:** `modal_cpu_policy.js` now owns the literal-true predicate. All three
callers use it, and `check-worker-architecture.mjs` fails if another Worker
module reads the raw binding. A unit test covers missing and malformed values.

**Validation:** 47 focused Worker tests pass; the complete Sites suite passes
(215); the Worker graph remains acyclic across 78 modules; and `git diff
--check` passes. No provider, credential, admission, deployment, or billing
state was changed.

## 2026-11-29 — A11: centralize Google Colab OAuth callback matching

**Finding:** the OAuth configuration boundary validated the callback's HTTPS
origin and exact path, but the HTTP route separately parsed and matched that
same binding. This created a second place to interpret the redirect target.

**Change:** `google_colab_connection.js` now owns callback matching against a
request URL. The route calls that function and no longer reads the callback
binding. The Worker architecture guard enforces that ownership. Tests cover a
valid callback with query values, wrong path/host, and malformed configuration.

**Validation:** 43 focused Colab/Worker tests pass; the full Sites suite passes
(215); the Worker graph remains acyclic across 78 modules; and
`git diff --check` passes. No OAuth credentials or external accounts were
accessed or changed.

## 2026-11-29 — A15: isolate training MCP argument policy

**Finding:** `experiment_input_contract.js` mixed provider/workload argument
routing with MAP defaults, owner-training limits, GitHub source registration,
and checkpoint/artifact request validation. This pulled training policy and
configuration into the shared input router and made unrelated tool changes
coupled to the training contract.

**Change:** moved normalization and all `training_*` input validation into
`worker/training_input_contract.js`. The common validator now delegates the
training tool namespace to that module and continues to own provider/workload
tool dispatch. The established `normalizeTrainingArguments` export remains
available through its old module path. A static architecture check prevents
training policy/configuration from returning to the common router.

**Validation:** focused architecture, MCP, entrypoint, and training tests pass
(61/61); the full Sites suite passes 217 tests. The runtime graph remains
acyclic across 80 modules. Worker build, artifact validation, D1 forward
migration replay, and `git diff --check` pass. No provider API, credential,
admission, deployment, or experiment was accessed or changed.

## 2026-11-29 — A11: share MAP Modal profile parsing

**Finding:** the MAP function entrypoint validated source, image, and runtime
configuration at module load, while the submit backend independently read the
same source, image, price, quote expiry, and runtime values before spawn. These
two interpretations could drift and capability/dispatch validation did not
have one Modal-side configuration authority.

**Change:** added `map_training_configuration.py` as the Modal-side profile
reader. The entrypoint uses its validated values and explicit runtime
environment projection; the backend validates plans against the same parsed
profile. Tests cover fixed image/source/runtime and missing or mutable values.

**Validation:** focused MAP/packaging tests pass (18), the full Modal Python
suite passes (105), the full Sites suite passes (214), the Worker graph
remains acyclic across 78 modules, and `git diff --check` passes. No provider,
credential, admission, deployment, or billing state was touched.

## 2026-11-29 — A11: normalize owner-training admission in Modal

**Finding:** the Modal adapter independently read and interpreted
`OWNER_TRAINING_ADMISSION_ENABLED` when projecting capability status and again
when dispatching each training lifecycle call. The interpretations matched,
but the duplicated gate could drift.

**Change:** added `owner_training_admission_enabled` to the training profile
configuration owner and used it in both paths. Tests pin fail-closed behavior:
only the literal string `true` enables the lane.

**Validation:** the Modal Python suite passes (104), the complete Sites suite
passes (214), the Worker dependency graph remains acyclic across 78 modules,
and `git diff --check` passes. No provider, credential, admission,
deployment, or billing state was touched.

## 2026-11-29 — A11: give Modal health cooldown one policy owner

**Finding:** the workspace health-check cooldown was an inline constant in the
diagnostic implementation, while the integration test repeated the 61-second
assumption. A policy change could leave either runtime behavior or its test out
of sync.

**Change:** moved the 60-second cooldown to `provider_health_policy.js`; both
the diagnostic and its integration test consume the same named policy value.
No cooldown duration or database behavior changed.

**Validation:** focused health/RunPod tests pass (20) and the full Sites suite
passes (214). The Worker graph is acyclic across 78 modules. No provider,
credential, admission, deployment, or billing state was touched.

## 2026-11-29 — A12: guard Modal configuration ownership

**Change:** Modal packaging tests now inspect runtime Python ASTs and fail if
owner-training admission or MAP runtime-profile environment settings are read
outside their designated configuration modules. The check ignores test files
and string-only forwarding of bindings; it guards only actual `os.environ`
reads.

**Validation:** packaging guard suite passes (12), full Modal Python suite
passes (110), full Sites suite passes (214), Worker graph is acyclic across
78 modules, and Modal's runtime import graph is acyclic. Literal local dynamic
imports are included and a test confirms external imports stay out of the
graph; synthetic duplicate-read and two-module-cycle fixtures are rejected.
`git diff --check` passes. No provider, credential, admission, deployment, or
billing state was touched.

## 2026-11-29 — A10: make signing fixtures share the canonical JSON authority

**Finding:** four Worker test files carried local recursive key-sorting
serializers for evidence IDs, fingerprints, or HMAC fixtures. Although they
currently emitted the same bytes for these JSON-shaped values, a serializer
change could update production without updating the security-sensitive test
fixtures, weakening what those tests prove.

**Change:** all four fixtures now import `worker/canonical_json.js`; the
architecture check rejects local `canonical`/`canonicalJson` function copies
in Worker tests. This leaves one serializer implementation for production
and test evidence without changing a provider or external contract.

**Validation:** 44 directly affected Worker tests passed; the full Sites
suite passed (213), the Worker graph remained acyclic across 77 modules, the
registry/build/artifact checks passed, the D1 forward migration replay passed,
and `git diff --check` passed. No provider, credential, admission, deployment
or billing state was touched.

**Review:** the change is test-fixture and static-architecture-check only.
The Codex Security diff scanner has previously failed to initialize in both a
linked worktree and a regular clone (`Review changes requires a non-bare Git
worktree with a resolvable HEAD`). That tool result is not independent review
evidence; this batch received direct source/diff review only.

## 2026-11-29 — A10: pin shared Worker/Modal canonical bytes

**Finding:** Worker delegated requests and the Modal verifier both use sorted,
compact UTF-8 JSON for HMAC authentication, but Python duplicated its encoder
in `provider_adapter.py`, `provider_adapter_core.py`, and the fixed Modal CPU
`app.py`. A key-order, Unicode, or escaping change could silently split the
wire contract.

**Change:** introduced one Modal `canonical_json_bytes` implementation and
reused it in those three runtime modules. Added one shared JSON vector corpus
consumed by the Worker and Modal adapter tests; it covers recursive key order,
array order, BMP/supplementary Unicode, and JSON string escaping. Packaging
tests ensure the Modal modules do not reintroduce the byte policy locally.
Request authentication and serialized bytes remain unchanged for the vectors.

**Validation:** the full Sites suite passes (214), the Worker graph remains
acyclic across 77 runtime modules, registry freshness, Worker build/artifact
validation, D1 migration replay, and `git diff --check` pass. The complete Modal
directory pytest suite passes, including the shared byte-vector and packaging
checks. No provider, credential, admission, deployment, or billing state was
touched.

## 2026-11-29 — A8: keep owner-auth rejection in the auth integration suite

**Change:** moved the HTTP-level regression proving that a ChatGPT identity
outside `GPU_CONTROL_ALLOWED_USER_IDS` is rejected before D1 access from the
general `index.test.js` into `mcp_request_auth.integration.test.js`. It now
lives beside anonymous-challenge, OAuth bearer scope/audience, and cross-client
owner-ledger tests; its assertions and request contract are unchanged.

**Validation:** the focused `mcp_request_auth.integration.test.js` and
`index.test.js` suites pass, followed by the complete Sites suite (214 passed).
`git diff --check` passes. No runtime code or external contract changed.

## 2026-11-28 — A3: recover owner-training results after Modal Dict expiry

**Finding:** Modal Dict entries can expire after seven days without access. The
Sites D1 row retained the immutable plan and dispatch claim but no terminal
result; the run-scoped Volume retained the fixed runner's `result.json`, yet a
status call could not reconstruct the adapter record or inspect that receipt.
This made the common owner/run ledger dependent on an adapter cache for longer-
term status and artifact access.

**Change:** added migration `0040_training_terminal_result.sql` for a bounded,
write-once terminal result projection in D1. Status/cancel/checkpoint/artifact
calls now pass the exact plan read from the authenticated owner's D1 row over
the signed adapter channel. With no Modal Dict record, the adapter recovers
only the deterministic Sandbox or a run-bound Volume receipt; it never calls
`start()`. The backend reloads the Volume, rejects symlinks, non-regular or
oversized files, binds the receipt to the run/source, then applies existing
GPU, manifest, lock, checkpoint and artifact validation. If the provider
resource and receipt cannot be proven, status remains uncertain. Confirmed
terminal state is returned from D1 to all MCP clients, and `training_list`
projects the same terminal state. Large checkpoint/artifact bytes remain in
Modal Volume and are fetched through the owner/run-bound adapter.

**Validation:** focused Modal lifecycle/backend/adapter packaging tests pass
(20); focused Sites state and registration tests pass (4); full Sites suite
passes (213), Worker import graph is acyclic across 77 runtime modules, D1
forward migration replay passes, Worker build and artifact validation pass,
and the Python suite passes (626 passed, 1 skipped, 5 subtests). No provider,
GPU, credential, admission, deployment, or billing state was touched.

**Limit:** Modal Volumes persist until deleted and may incur storage charges;
an explicit artifact retention/deletion policy and background reconciliation
host remain open. This is source/test evidence only; exact-head CI, independent
security review, migration deployment and live provider recovery are not yet
verified. The Codex Security diff-scan entrypoint rejected both this linked
worktree and a normal clone with `Review changes requires a non-bare Git
worktree with a resolvable HEAD`; `git rev-parse --verify HEAD` succeeded for
both. A local source review was performed, but it is not independent review
evidence and must not be reported as such.

**Follow-up evidence (2026-11-29):** the batch was cherry-picked to PR #70 as
`2ce8c4f843df72eba3080e204a0d96275df5f063`; all seven exact-head GitHub checks
passed. The PR remains open, review-required and blocked. The failed independent
diff scan, deployed D1 migration, and live Modal recovery acceptance remain
open; this follow-up does not change those release boundaries.

## 2026-11-28 — A13: make cross-client onboarding actionable

**Finding:** the shared OAuth and run-ledger contract existed in source, but
the client guide described compatibility and release gates without a short
no-compute verification path. It also left the ChatGPT Sites identity and
external-client OAuth flows easy to conflate, and did not call out that a
client/workspace may allow MCP reads while blocking writes.

**Change:** `MCP_CLIENTS.md` now gives a four-step connect, authorize, verify,
and request workflow; distinguishes ChatGPT Sites identity from external MCP
OAuth; explains read/execute scopes and shared run history; and states the
current ChatGPT custom-MCP account-tier write limitation. The Colab CLI stays
documented as an independent executor unless it is routed through the shared
owner-bound lifecycle. Source commit: `1de3aa1`.

**Validation:** `git diff --check` passed. Exact-head PR #70 CI passed all
seven checks at `1de3aa10c1d47bdededeaf9fa106b6dc1cc87a78`. The PR remains open
with review required; this is source and CI evidence only, not a deployed
OAuth handshake or live run.

## 2026-11-28 — A3: correct the reconciliation execution contract

**Finding:** `experiment_reconcile` was described by the public MCP schema,
operator Skill and Colab ADR as an automatic Site cloud schedule. No scheduled
handler or schedule binding exists in the current repository. The tool is an
explicit owner-authenticated MCP operation. It advances at most one eligible
Colab, delegated-provider and RunPod run; it does not reconcile owner-selected
`training_*` jobs.

**Change:** corrected the MCP description and response summary to identify an
explicit call, aligned the Skill and Colab architecture records, and recorded
the missing background runner as an open architecture decision. Added a
contract assertion so the public tool text cannot again promise an automatic
schedule.

**Validation:** all 211 Sites tests pass; the Worker dependency graph is
acyclic across 77 runtime modules; Worker build and artifact validation pass;
D1 forward-migration replay and `git diff --check` pass. This is local source
evidence only. No background recovery, provider action, admission change,
deployment, or live run was performed.

**Follow-up evidence:** Modal's current security guide sets seven days of
inactivity retention for Dict entries. The custom-training adapter uses a Dict
as its dispatch/result journal, while no scheduled refresher is configured in
this repository. D1 remains `dispatching` until an adapter terminal result is
observed. Indefinite recovery after an interrupted chat is therefore not
established; durable journal retention is now an explicit A3 open item.

## 2026-11-28 — A1: synchronize operator guidance with current provider routes

**Follow-up finding:** the Sites README, ChatGPT setup guide and public
`training_submit` description still told MAP-44M users to open the legacy
ChatGPT-only authorization URL. The submit failure response also used the
owner-selected boolean instead of the shared MCP-confirmable plan allowlist,
so an authorization write failure could leak that URL for MAP plans.

**Change:** aligned these guides and MCP tool text with the exact-plan
client-neutral submit authorization. The failure response now uses the same
`supportsMcpTrainingSubmit` policy as prepare and status. Added contract checks
that reject a return of MAP's obsolete browser-confirmation instruction.

**Validation:** the Sites suite passes all 208 tests, root Skill/client checks
pass all five cases, the Worker graph is acyclic across 76 modules, Worker
build/artifact validation and D1 forward-migration replay pass, and
`git diff --check` passes.

**Finding:** the operator Skill still said Colab had no execution lifecycle and
that owner-selected Modal was categorically unavailable. The current source has
a Colab owner-selected plan/run lifecycle and a dynamic Modal readiness
contract; those statements would make agents refuse usable routes or report
stale blockers without reading capabilities.

**Change:** the Skill now checks current release state and provider
capabilities, treats Colab admission separately from account/GPU eligibility,
and describes its exact-plan CU attestation and recovery lifecycle. Owner-
selected Modal follows `ready_to_prepare` and `training_prepare` rather than a
static availability claim. The first verification prompt covers all five
provider families and owner-selected readiness without initiating compute.
Regression assertions reject the stale text.

**Validation:** `uv run pytest tests/test_gpu_control_operator_skill.py` passes
all five cases. The 208-test Sites suite, 76-module acyclic graph, Worker
build/artifact validation, D1 forward migration replay, and `git diff --check`
pass. This is source validation, not proof of a deployed release or enabled
provider admission.

## 2026-11-28 — A1: make MAP training authorization client-neutral

**Finding:** MAP-44M `training_prepare` still required an authorization page
that accepted only ChatGPT Sites identity headers. A different authenticated
OAuth MCP client could inspect the same owner ledger but could not submit its
prepared MAP plan, contradicting the shared-client contract.

**Change:** MAP plans now carry the control-plane SHA and use the existing
exact-plan, one-use MCP submit authorization already used for owner-selected
training. Browser authorization remains available for execution kinds outside
the explicit MCP-confirmable allowlist. Skill guidance no longer asks agents
to open a ChatGPT-only page or repeat the user's run instruction. Updated the
client guide to distinguish the official Colab CLI's standalone `colab run`
and CI use from the hosted Colab provider that records in the shared ledger.

**Validation:** the focused MAP authorization/registration tests pass, as does
the complete 208-test Sites suite and the 76-module acyclic graph. No
GPU/provider operation was called. Exact-head CI remains to be recorded before
this batch is committed.

**Colab CLI follow-up:** Google's official CLI supports ephemeral CI jobs, but
direct CLI calls have independent Google identity and no GPU Control owner,
budget, or cleanup record. Do not create a second product route. Any future
CLI-backed executor must claim the same exact owner-bound plan and report into
the same run journal; ordinary CI stays offline and no Colab runtime is
allocated by this repository's CI.

## 2026-11-28 — A13: exercise a real OAuth token through the shared MCP route

**Problem:** external OAuth issuance and ChatGPT/external tool parity were
covered separately. A token minted by the owner-binding flow had not been
shown entering the actual Worker MCP route and reading the same current-schema
run ledger as the Sites identity path.

**Change:** added an integration case using the complete forward-migration
schema. It registers two public clients, completes PKCE and linked GitHub
owner proof for each, exchanges authorization codes, then calls `tools/list`
and `experiment_list` through both independent access tokens and the ChatGPT
Sites identity for the same owner. All three responses match, neither external
client can read a second owner's run, and revoking one OAuth grant leaves the
other client's grant usable.

**Validation:** `node --test worker/mcp_oauth.test.js` passes all six cases.
This proves local OAuth-to-MCP HTTP integration and D1 owner filtering. It does
not prove a deployed OAuth handshake or any provider execution; repository
release policy remains parked.

## 2026-11-28 — A13: lock ChatGPT/external MCP contract parity

**Problem:** Sites-header authentication and external OAuth both entered the
same Worker, but the cross-client test only verified OAuth scope behavior. A
future client-specific dispatcher could have diverged without a test showing
that both authenticated transports expose the same MCP tool contract.

**Change:** added an integration case that sends `tools/list` and
`experiment_list` through the ChatGPT Sites identity header and an owner-bound
OAuth bearer for the same owner. It compares the complete tool/schema/
annotation response and verifies that both paths read the same owner-filtered
run ledger row. The contract remains shared; the two identity transports
remain separate.

**Validation:** the focused MCP request-auth integration suite passes all three
cases. The full Sites suite passes all 187 tests; the architecture checker
reports an acyclic graph across 67 runtime modules. This exercises mocked
D1/OAuth state and the local Sites Worker only; it does not verify a deployed
external-client handshake or execute a provider.

## 2026-11-28 — A13: make MCP write guidance client-neutral

**Finding:** the shared OAuth and run ledger support multiple authenticated
MCP clients, but several tool descriptions and owner-training response messages
still framed exact-plan execution authorization as a ChatGPT-only action. This
made a shared capability appear unavailable from other clients.

**Change:** public tool descriptions, plan authorization surfaces, runtime
summaries, and architecture docs now describe a destructive MCP write action
and leave any native confirmation UI to the connected client. The server still
binds the request to the authenticated owner, exact plan, one-use authorization,
and budget reservation. The historical `chatgpt_mcp_write_confirmation`
database value remains unchanged because it is part of the append-only
migration contract; comments identify it as shared by authenticated MCP
clients. OAuth deployment and account linking remain separate release/setup
requirements.

**Validation:** `npm test` passes all 187 Sites Worker tests; the import graph
is acyclic across 67 runtime modules and the workload registry is current.
`git diff --check` also passes. This validates the local source contract only;
it does not establish an external OAuth release or live client handshake. No
provider execution, credential, admission, budget, OAuth deployment, or live
Site configuration was changed.

## 2026-11-28 — Refresh the architecture map against the current implementation

**Finding:** the map's implementation snapshot referred to `527a711` and a
separate large-file inventory referred to `158ff2c`, while the active PR head
was `129f002`. The `index.test.js`, Colab client/capability, authorization, and
dispatch-claim line counts also differed from the checked-out files.

**Change:** refreshed the map to the verified implementation baseline
`129f002`, its current test and module counts, and measured file sizes. The map
continues to state that Colab has no plan or run-lifecycle caller and that PR
source is not a deployed release.

**Validation:** re-counted each named file from the checkout and ran
`git diff --check`. This documentation-only correction does not change source
behavior, provider policy, or release state.

## 2026-11-28 — A12: include static re-exports in the Worker dependency graph

**Finding:** the shared Worker graph parsed static `import` declarations but
not `export … from` declarations. A module could therefore depend on another
runtime module without that edge participating in cycle checks or the
architecture guard's dependency rules.

**Change:** the graph builder now records named and wildcard re-exports as
dependencies and rejects malformed re-export syntax. Added script-level graph
fixtures and included them in `npm test`, so future graph-parser changes are
checked in CI. The package build still uses the same graph builder and retains
its unreachable-module check.

**Validation:** `npm test` passes both new graph tests, all 187 Worker tests,
the architecture guard, and generated registry validation. The Worker graph
remains acyclic across 67 runtime modules. No product runtime behavior changed.

## 2026-11-28 — A13: synchronize client-neutral operations and source map

**Finding:** the operational guide and architecture map still described the
owner-selected write confirmation as ChatGPT-native and the repository map
pointed to an older source revision and test count. This contradicted the
shared MCP contract and made the architecture snapshot stale immediately after
the prior batch.

**Change:** the setup and lifecycle guides now name the connected MCP client's
native write confirmation, while retaining ChatGPT-specific sign-in guidance
where the current GitHub owner-link setup actually depends on Sites identity.
The repository map records the current commit and verified test/CI snapshot.

**Validation:** current head `527a711` has all seven exact-head CI checks green;
Sites tests pass 187/187, root `uv run pytest` passes 619 with one skipped and
five subtests, the architecture graph is acyclic across 67 runtime modules,
and `git diff --check` passes. This documentation/comment batch does not change
runtime behavior or prove OAuth deployment, external client handshake, or
Colab execution readiness.

## 2026-11-28 — A13: remove remaining client-specific architecture language

**Finding:** ADR 0006 and selected-repository/README descriptions still
treated ChatGPT write confirmation as a product requirement. The repository
map also assigned owner-selected MCP authorization to a browser route that
handles the legacy MAP/fixed-CPU flow.

**Change:** the ADR now defines conversation-first use across authenticated
compatible clients and leaves native confirmation to each client. README and
selected-source docs use client-neutral confirmation language. The module map
assigns browser confirmation only to the legacy MAP/fixed-CPU path and MCP
submit authorization to owner-selected plans.

**Validation:** source semantics were checked against `training_plan.js`,
`training_authorization_routes.js`, and the owner-bound OAuth dispatcher. This
batch does not change runtime behavior or prove OAuth deployment, external
client handshake, or Colab execution readiness.

## 2026-11-28 — A13: make the operator Skill client-neutral

**Finding:** the repository's primary agent Skill told operators to use only
the ChatGPT-named MCP tools and called owner-selected submission a destructive
ChatGPT write. That wording could make a compatible OAuth client appear to
need a separate workflow, even though the tool schemas and owner ledger are
shared.

**Change:** the Skill now names the shared authenticated MCP interface and
connected-client confirmation boundary, while stating that external OAuth is
not usable until deployed. It continues to distinguish the MAP legacy Sites
login and direct Colab CLI jobs from the shared agent lifecycle.

**Validation:** checked the Skill's claims against `MCP_CLIENTS.md`, PR #70's
OAuth source status, `training_prepare`/`training_submit` descriptions, and the
Colab capability blocker. No credentials, provider settings, admission, or
execution were changed.

**CI correction:** the first exact-head CI run found that the Skill contract
test also requires the ChatGPT app's discoverable product name and the retired
Keychain Runner warning to remain explicit. Both statements are preserved
without restoring a ChatGPT-only control flow. The focused Skill suite now
passes all three tests; a new exact-head CI run is required for the correction.

**Single-source correction:** the Skill now points to `MCP_CLIENTS.md` for the
current external OAuth release state instead of hard-coding a PR-specific
status that would go stale after deployment. The existing Skill contract test
now protects the shared owner boundary, release-status source, and connected-
client confirmation wording.

## 2026-11-28 — Normalize the client-neutral MCP product boundary

**Finding:** the owner-bound OAuth design, MCP client guide, and provider
specification already use one shared plan/run ledger for authenticated MCP
clients. Several current architecture summaries still described ChatGPT as the
primary client, which could imply that other clients were secondary product
paths even though the intended contract is shared.

**Change:** aligned the MCP client guide, Colab/provider architecture, ADR 0012,
repository map, and A0/A1 backlog wording around one client-neutral MCP
contract. ChatGPT's trusted Sites identity is documented as one transport
adapter. Authentication remains required; this does not make the API anonymous
or imply that an undeployed OAuth route is already available. Standalone
`google-colab-cli` jobs remain outside the GPU Control ledger; an automation
client can share that ledger only by calling the same authenticated MCP
lifecycle.

**Validation:** checked current MCP client setup and Colab integration docs
against ADRs 0010–0012 and the A0/A1 release gates. `git diff --check` passes.
No runtime code, OAuth configuration, provider, admission, deployment, or
experiment was changed. The client-neutral documentation batch is commit
`3ff08412c235bd2baa17e22bb863d95476ededf2`, pushed to PR #70. All seven
exact-head hosted checks passed on that commit. The Sites Worker and root
Python test counts remain the code-validation baseline recorded above.

## 2026-11-28 — A0: refresh the exact source and verification snapshot

**Source:** PR #70, branch `codex/owner-training-workloads`, head
`dce3f00ff676ef38d1115c53a7edb604b3ddb92e`. GitHub reports the PR open and
mergeable, review required, and all seven exact-head CI jobs queued. No merge,
deployment, D1 migration, admission change, or provider run is established by
this snapshot.

**Local verification:** root `uv run pytest` passes 616 tests and five
subtests, with one skipped; Sites `npm test` passes 166 tests and reports an
acyclic graph across 54 Worker runtime modules. Current structural counts are
recorded in [`repository-map.md`](repository-map.md). These checks do not
replace the queued GitHub checks or prove a live MCP/provider lifecycle.

## 2026-11-28 — A6: isolate Modal owner-training plan construction

**Problem:** `training_plan.js` combined shared training orchestration and
Modal-specific owner-selected plan construction. Adding Colab there would have
made provider policy and Google runtime semantics part of the same growing
module.

**Change:** moved Modal's owner-selected source/manifest/runtime/budget plan
construction into `worker/modal_owner_training_plan.js`. The existing public
`previewTrainingPlan` entrypoint, MAP path, D1 records, and downstream
authorization/submission contracts remain unchanged. This is an internal
boundary only; it does not add Colab planning or execution.

**Validation:** `npm test` in `sites/gpu-control-sites` passes (163 tests),
the worker import graph remains acyclic across 53 modules, and the generated
workload registry is current.

**Next:** keep provider-specific plan resolution behind named modules and the
existing shared lifecycle. Before Colab can execute, specify its `cost_unknown`
and quota contract, exact-plan binding, asynchronous operation recovery,
run-owned session/runtime cleanup, and output/artifact bounds. Colab remains
unavailable until those paths are integrated and accepted end to end.

## 2026-11-28 — A6: define the narrow Colab runtime operation contract

**Finding:** Google requires stable UUID request IDs for runtime-create retry,
stable session IDs for session recovery, and a new UUID execution ID per
execution. A timed-out execution must be reattached with the identical session
and execution ID. Session deletion aborts its running code; deleting a runtime
also destroys all user data and is documented only when the user requests it.
The existing Sites client had a generic 30-second request deadline and only a
read-only tool allowlist, so neither runtime allocation nor long-running
training could safely be routed through it as-is.

**Change:** added one Colab MCP contract module for exact tool arguments and
owner-run-bound runtime/session/execution response validation. The hosted MCP
client accepts only that narrow lifecycle allowlist and rejects runtime-wide
deletion. The public Sites tool surface remains read-only for Colab; no
runtime, session, or experiment was started.

**Validation:** the full Sites Worker suite passes (165 tests), the import
graph is acyclic across 54 runtime modules, and the workload registry check
passes.

**Remaining:** persist Google request/runtime/session/execution IDs in the
existing training run before each call. A later `training_status` must replay
only the same Google idempotency key after an ambiguous timeout, then resume
through the same owner-scoped run. Do not add a second queue or run ledger when
the provider's idempotency contract and the agent's status calls can recover
the operation. The current client is only the transport layer, not that
state machine. Admission remains closed until bounded quota semantics,
artifacts, cancellation, and session cleanup are wired and verified.

## 2026-11-28 — A6: separate immutable source verification from provider readiness

**Problem:** `training_contract.js` bundled pinned GitHub manifest/lock
validation with a Modal image and price profile. That made a valid repository
appear non-executable before a different provider such as Colab could evaluate
its own runtime and quota terms.

**Change:** extracted `readTrainingSourceContract` as the canonical
provider-neutral read of the immutable manifest, hash-locked dependency file,
and source-readiness checks. Existing `readPublicTrainingContract` composes
that contract with the existing Modal runtime gate, preserving its output and
caller behavior. The Colab route can now apply Colab-specific runtime and
quota rules to the same source contract without a second manifest parser.

**Validation:** the full Sites Worker suite passes (166 tests); focused tests
cover source verification without a Modal profile and existing Modal contract
behavior. The runtime-module import graph remains acyclic across 54 modules.

**Limit:** Colab still has no public prepare/submit/status caller. Source
inspection is reusable foundation, not evidence that Colab can execute a
repository.

## 2026-11-28 — A6: refresh Colab CLI boundary evidence

**Finding:** the current official [`google-colab-cli` README](https://github.com/googlecolab/google-colab-cli)
documents headless Linux/macOS use, ephemeral `colab run` with runtime
teardown, `colab usage` CU/balance output, OAuth2/ADC, and local state under
`~/.config/colab-cli/`. It does not describe storing OAuth credentials in the
OS keyring. Direct CLI runs remain outside Sites D1 and the shared MCP run
ledger.

**Change:** corrected the superseded runner ADR's credential-storage claim,
and clarified the current hosted-MCP ADR and backlog: CLI invocation in CI is
possible as a standalone job, while an integrated execution host must use the
same owner-bound Sites job and lifecycle contract. A parallel CLI dispatch
route would duplicate Colab execution, retries, authorization, and cleanup.

**Validation:** compared the current official README and CLI command reference
with ADR 0010/0011, the provider specification, and A6 acceptance gates. No
Google login, CLI install, runtime allocation, provider credential, D1 or
admission change occurred.


## 2026-11-28 — A7: centralize the public MCP tool-error contract

**Problem:** `worker/index.js` rebuilt two allowlists inside every caught tool
failure and mixed provider/domain error exposure policy into MCP dispatch.
Unknown failures needed to remain redacted, while existing known public codes
had to remain stable.

**Change:** moved the mapping into `worker/mcp_tool_errors.js` and migrated the
MCP call boundary. The module owns a single allowlist of public domain codes,
accepts RunPod codes only from its typed bounded error shape, collapses legacy
adapter errors to `GATEWAY_DELEGATION_FAILED`, and maps all other errors to
`INTERNAL_ERROR`. The JSON-RPC result envelope stays in the transport layer.

**Validation:** focused tests cover known domain codes, arbitrary error
redaction, typed RunPod validation and legacy error collapse. All 172 Sites
tests pass; the Worker graph is acyclic across 62 runtime modules. Independent
security review found no actionable issues and verified that provider text
stays out of MCP output. No provider call, experiment, deployment, admission,
or configuration change occurred.


## 2026-11-28 — A7: isolate MCP protocol negotiation and scope validation

**Problem:** `worker/index.js` mixed MCP version negotiation, protocol header
and metadata matching, resource-name matching, and OAuth read/execute scope
selection with tool dispatch and provider execution.

**Change:** moved the MCP wire-level validation into
`worker/mcp_protocol.js`. It owns supported-version constants, parsing result
errors, current-version metadata/header checks, tool/resource name checks, and
the scope decision derived from the canonical read-only tool classification.
The entrypoint routes only requests accepted by this boundary. Tool routing,
plan validation, and provider execution remain downstream.

**Validation:** focused protocol tests cover legacy default negotiation,
unsupported versions, current-version metadata mismatch, read-only calls and
write-scope denial. All 175 Sites tests pass; the Worker graph is acyclic
across 63 runtime modules. Independent read-only security review found no
actionable issues and confirmed authorization and metadata validation precede
dispatch. No provider call, experiment, deployment or admission change
occurred.

## 2026-11-28 — A7: align Colab client guide and expose RunPod recovery errors

**Finding:** `docs/GOOGLE_COLAB_CLI.md` described the Colab execution lifecycle
as not yet connected even though the PR #70 source candidate has the hosted
Colab adapter and shared owner/run ledger. That stale passage blurred source
readiness, release readiness, and admission. The guide also overgeneralized
the CLI's CI credential path. Separately, missing RunPod account-lease and
provider-job recovery errors were converted to generic `INTERNAL_ERROR`, so an
agent could not tell that an existing run needed recovery rather than replay.

**Change:** updated the guide to distinguish the shared Sites MCP route from
standalone CLI/local MCP runs, and to state that Colab admission remains closed
until release gates pass. The public MCP error contract now preserves the two
bounded RunPod recovery codes while continuing to redact arbitrary provider
messages.

**Validation:** focused error-contract tests pass (3/3) and `git diff --check`
passes. No Colab CLI job, provider call, experiment, credential, deployment,
or admission change was made.

## 2026-11-28 — A3: audit Modal adapter-journal loss paths

**Finding:** Modal has two distinct submit paths, so the missing-record case
must be checked at both boundaries. For the fixed delegated route, Sites D1's
`submit_attempted_at` is the durable dispatch claim; a status/cancel request
reconstructs only the deterministic handle, never retries submit, and maps a
missing Modal Dict claim to `SUBMISSION_OUTCOME_UNCONFIRMED`. For owner-selected
training, D1's `dispatch_claimed_at` prevents a repeated `training_submit` from
dispatching again. A missing adapter record makes status/cancel return
`uncertain` through the existing not-found mapping.

**Evidence:** `worker/delegated_experiment_lifecycle.js`,
`worker/training_submit.js`, `worker/training_tools.js`, and
`modal/provider_adapter.py`. `worker/index.test.js` covers a missing fixed-lane
adapter claim. A new `worker/training_tools.integration.test.js` covers the
owner-selected custom-training path through Sites' D1 state projection and a
missing adapter journal. Status/cancel return
`SUBMISSION_OUTCOME_UNCONFIRMED`, provider allocation and cleanup `unknown`,
and status-only recovery; repeated submit remains local to D1.

**Validation:** the new training-tools integration test and existing source
registration integration test pass (2/2). No provider call, experiment,
deployment, credential, or admission change was made.


## 2026-11-28 — A7: centralize the MCP tool-result projection

**Problem:** `worker/index.js` converted domain return values into the
schema-v2 envelope and separately assembled legacy text-only, structured
content, and current-protocol completion metadata. This made result
compatibility a transport implementation detail and duplicated tool success
and error shape construction in the dispatcher.

**Change:** moved normalization and the success/error projections into
`worker/mcp_tool_result.js`. Domain tools provide values, while the module owns
the stable public envelope and version-specific MCP result shape. The oldest
supported protocol remains text-only; later versions include structured
content; the current version also carries its completion type and server
metadata. Errors accept only the already sanitized code from
`mcp_tool_errors.js`.

**Validation:** focused tests cover envelope normalization, all three protocol
result shapes, and the bounded error projection. All 178 Sites tests pass; the
Worker graph is acyclic across 64 runtime modules. Independent read-only
security review found no actionable findings and confirmed provider/internal
error details remain redacted. No provider call, experiment, OAuth flow, or
deployment occurred.

**Source correction (2026-11-28):** a follow-up check of the official CLI's
current authentication reference found that OAuth credentials moved to the
OS-native keyring on 2026-10-21. `~/.config/colab-cli/` still holds session,
settings, and history files, but is no longer the current OAuth-token store.
The ADRs and user guide now distinguish these paths. CLI execution can run in
CI when an accepted Colab identity is available; ordinary hosted CI does not
inherit a developer's Mac keyring, and a direct CLI job still bypasses the
GPU Control ledger.

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
training_artifact retrieval. Added the MAP account-evidence ADR (now ADR 0013
after resolving a duplicate ADR number) and documented OAuth configuration
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
monthly ceiling is hard-bounded at `$1.00`. ADR 0013 records that this is
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


## 2026-11-28 — A7: isolate the experiment-list read model

**Problem:** the Worker composition root queried and merged the local D1 run
ledger with delegated provider records, interpreted uncertain/prepared and
cleanup states, applied filters/cursors, and projected one shared list
contract. This mixed a provider-neutral read model into transport dispatch.

**Change:** moved list queries, local execution-origin evidence, delegated
state projection, merge/deduplication, filters and cursor output into
`worker/experiment_list.js`. `index.js` now supplies the authenticated owner
and dispatches the existing operation. The tool schema, owner-scoped SQL,
legacy-row handling, ordering, output shape, and provider adapter indicator
remain unchanged. This does not add or activate a provider route.

**Validation:** all 148 Worker tests pass, including delegated and local
experiment listing and cursor/filter behavior; D1 forward migration tests
pass; build and artifact validation pass; the Worker graph remains acyclic
across 41 reachable runtime modules. No deployment or provider operation was
performed.


## 2026-11-28 — A7: isolate the local run-status read path

**Problem:** `experiment_status` and `experiment_result` duplicated row
loading after RunPod synchronization, bounded log projection, cleanup/result
metadata projection, and user-facing next actions inside MCP dispatch.

**Change:** moved the owner-scoped local run query, provider-sync orchestration
through explicit adapter callbacks, and common status/result response
projection into `worker/experiment_status.js`. Delegated plans still route
through `maybeDelegateRunTool` first; their authorization, provider polling,
and persisted observation behavior are unchanged. Modal status rate limiting
and the provider lifecycle implementations remain in their existing modules.

**Validation:** all 148 Worker tests pass, including owner isolation, RunPod
and Modal status synchronization, delegated plan handling, bounded logs and
result readiness; D1 forward migration tests pass; the Worker graph remains
acyclic across 42 reachable runtime modules; build, Site artifact validation,
and `git diff --check` pass. No deployment or provider operation was performed.


## 2026-11-28 — A7: centralize execution-origin evidence

**Problem:** the shared list and status read models both need to distinguish
current Modal Sandbox records from historical local Runner records. Keeping
the validation inside the list module made status depend on an unrelated
reader and left provenance without an explicit authority.

**Change:** moved receipt/lease validation into `worker/execution_origin.js`.
Both the list and status projections import the same function; it still
requires a valid run-bound cleanup receipt before identifying a retired local
Runner and otherwise reports `unknown`.

**Validation:** all 148 Worker tests pass, including valid, unknown and
historical execution-origin cases; Worker build packages 43 reachable modules;
Site artifact validation and `git diff --check` pass. No provider call or
deployment was performed.


## 2026-11-28 — A7: isolate delegated-provider run persistence

**Problem:** lookup of historical delegated plans, validation and persistence
of adapter observations, and removal of internal provider handles from public
responses were mixed with prepare/submit orchestration in `index.js`.

**Change:** introduced `worker/provider_adapter_run_store.js` as the storage
and exposure boundary for delegated run records. It owns supported-workload
lookup, bounded state/handle/response persistence, and public handle redaction.
Provider policy decisions, budget reservations, submit claims and adapter calls
remain in their existing orchestration path.

**Validation:** all 151 Worker tests pass, including three focused tests for
owner-scoped lookup, bounded observation persistence and handle redaction;
D1 forward migration tests pass; build packages 44 reachable runtime modules;
Site artifact validation and `git diff --check` pass. No deployment or
provider operation occurred.


## 2026-11-28 — A7: isolate local run cancellation

**Problem:** `experiment_cancel` mixed owner-scoped local state transitions,
RunPod cleanup dispatch, Modal cooperative cancellation, and response
projection inside MCP dispatch while delegated cancellation had a separate
adapter path.

**Change:** moved local run lookup, queued cancellation, cooperative
`cancel_requested` persistence, and RunPod synchronization into
`worker/local_run_cancellation.js`. The entrypoint continues to route
delegated runs first; provider cleanup semantics remain provider-owned.

**Validation:** all 151 Worker tests pass, including owner-isolated cancel,
queued terminal cleanup, Modal cooperative request, and delegated cancel;
D1 forward migration tests pass; the Worker graph is acyclic across 45 runtime
modules; build, Site artifact validation and `git diff --check` pass. No
provider operation or deployment occurred.


## 2026-11-28 — A7: isolate provider-run reconciliation

**Problem:** the dispatcher queried and advanced one delegated-provider run
and one native RunPod run, then merged their outcomes into the reconciliation
tool response. The policy was separate, but provider recovery selection and
result aggregation were still composition-root responsibilities.

**Change:** moved delegated and RunPod recovery selection, bounded status
updates, failure responses and combined response projection into
`worker/run_reconciliation.js`. The module receives the two provider lifecycle
ports and does not submit new provider work.

**Validation:** all 151 Worker tests pass, including recovery of one active
delegated run and RunPod lifecycle contracts; D1 forward migration tests pass;
build packages 46 reachable Worker modules; artifact validation and
`git diff --check` pass. No provider operation or deployment occurred.


## 2026-11-28 — A7: isolate Modal CPU submission

**Problem:** owner-plan matching, single-use ChatGPT authorization, health
readiness, shared budget reservation, D1 run creation, and recovery of a lost
submit response were inline in `callTool`. This security-sensitive workflow
was difficult to review separately from provider routing.

**Change:** moved the full Modal CPU submit use case into
`worker/modal_cpu_submission.js`. It owns exact plan/authorization checks,
health-gate reuse, budget and state reservation, idempotent run creation, and
provider submit/recovery. The dispatcher retains request validation and
selects RunPod/delegated/Modal CPU routes. Existing provider and authorization
helpers are narrow injected services.

**Validation:** all 151 Worker tests pass, including lost-submit recovery,
one-use authorization, budget exhaustion, health checks and owner-bound plan
matching; D1 forward migration tests pass; build packages 47 reachable Worker
modules; Site artifact validation and `git diff --check` pass. No provider
operation or deployment occurred.


## 2026-11-28 — A7: isolate Modal CPU lifecycle synchronization

**Problem:** Modal CPU status/cancel/submit reconciliation, recovery after an
absent Sandbox, result validation and artifact finalization still lived in the
Worker composition root. This left the provider's cleanup and result trust
rules spread across dispatcher code.

**Change:** moved status-check reservation, bounded missing-run recovery,
provider state synchronization, cancellation finalization, exact result
validation and artifact persistence into `worker/modal_cpu_lifecycle.js`.
`index.js` composes the lifecycle in status and submit routes; the module uses
the existing Modal HTTP and artifact contracts. Removed the now-unused local
tokenizer digest constant from the dispatcher.

**Validation:** all 151 Worker tests pass, including Modal status, lost-submit
recovery, cancellation and artifact verification; D1 forward migration tests
pass; the Worker graph is acyclic across 48 runtime modules; build, Site
artifact validation and `git diff --check` pass. No provider operation or
deployment occurred. Exact-head CI is pending and is tracked separately.


## 2026-11-28 — A7: isolate delegated provider lifecycle

**Problem:** adapter-backed prepare, submit authorization, provider-specific
budget claims, response-loss recovery, cancellation and status/artifact routing
were implemented together in the dispatcher. This made adding or maintaining
another MCP client/provider route require changes in a large composition root.

**Change:** moved the complete delegated-provider plan and run lifecycle into
`worker/delegated_experiment_lifecycle.js`, including free-provider policy
authorization, Modal GPU active lease, exact approved-plan and one-use
authorization checks, budget reservation/submit claim, idempotent recovery,
provider-handle redaction, and existing-run status/cancel/artifact routing.
The Worker dispatcher now passes the small account-evidence and secure-random
ports and selects the native versus delegated lifecycle. Existing tools and
persisted D1 contracts are unchanged.

**Validation:** all 151 Worker tests pass, including owner-scoped training,
Modal GPU reservation, delegated run recovery and artifact routing; the Worker
graph is acyclic across 49 runtime modules. D1 forward migration, Worker build,
Site artifact validation and `git diff --check` pass. Independent Security
Review found no actionable findings. No provider operation or deployment
occurred.


## 2026-11-28 — A7: consolidate provider budget reservation authority

**Problem:** D1 budget policy projection and the generic RunPod reservation
query lived in separate modules. A provider's advertised per-run/monthly rules
and the reservation enforcement were therefore harder to review as one
contract.

**Change:** moved `reserveProviderBudget` into `worker/provider_budget_policy.js`
beside provider budget policy reads and the shared Modal reservation builder.
`index.js` now consumes the canonical reservation function. Added focused
SQLite-backed coverage for policy ceilings, exact retries, conflicting retry
amounts and unknown providers.

**Validation:** all 152 Worker tests pass; the graph remains acyclic across 49
runtime modules; D1 forward migration, Worker build, Site artifact validation
and `git diff --check` pass. No provider operation or deployment occurred.


## 2026-11-28 — A7: isolate multi-client request authentication

**Problem:** MCP principal resolution, ChatGPT identity-header interpretation,
owner allowlisting and OAuth bearer challenges were embedded in the dispatcher.
That made the multi-client identity boundary harder to audit and left the
architecture check enforcing the older entrypoint-only location.

**Change:** moved request identity resolution and `401`/`403` bearer challenge
construction into `worker/mcp_request_auth.js`. The entrypoint now receives a
resolved principal; browser confirmation pages use the same owner resolver.
Updated the architecture check to allow header and allowlist interpretation
only in this dedicated boundary. Added direct tests for owner resolution,
scope projection, malformed bearer handling and challenge responses.

**Validation:** all 156 Worker tests pass; the Worker graph is acyclic across
50 runtime modules; D1 forward migration, Worker build, Site artifact
validation and `git diff --check` pass. Independent Security Review found no
actionable findings. No provider operation or deployment occurred.


## 2026-11-28 — A8: separate MCP schema and GitHub source tests

**Problem:** pure public MCP tool-contract assertions and GitHub source pinning
tests were embedded in the 3,445-line Worker integration test, alongside route,
storage and provider lifecycle scenarios.

**Change:** moved tool schema/description assertions into
`worker/mcp_tool_contract.test.js` and pinned repository/default-branch source
tests into `worker/training_source.test.js`. The integration suite now tests
HTTP routing and D1-backed behavior without owning these module contracts.

**Validation:** all 156 Worker tests pass; the graph remains acyclic across 50
runtime modules. No contract coverage was removed; only test ownership changed.


## 2026-11-28 — A8: isolate owner-selected training registration coverage

**Problem:** the 631-line test for GitHub source registration, owner isolation,
immutable commit checks, plan readiness, and repeatable registration lived in
the same `index.test.js` as MCP transport, provider health, and other lifecycle
contracts.

**Change:** moved that complete test into
`worker/training_registration.integration.test.js`. Its SQLite/D1 adapter,
assertions, and test inputs are preserved. The extracted test uses a small
local environment fixture because it replaces the generic worker test
database, which previously gave it an unrelated shared mock D1 implementation.
The `worker/index.test.js` remains the integration-suite entry for remaining
transport and cross-domain behavior.

**Validation:** all 156 Sites Worker tests pass and the dependency graph is
acyclic across 50 runtime modules. No provider operation or deployment occurred.

**Client portability:** clarified that other chats/agents connect through the
same owner-bound MCP OAuth contract only after PR #70's migration and routes
are deployed and a fresh no-compute handshake passes. This is not yet a live
claim or an anonymous public API.


## 2026-11-28 — A11: centralize owner-selected runtime configuration reads

**Problem:** Owner runtime image, hourly and staging rates, quote expiry,
runtime duration, and run/monthly ceilings were converted from Worker
environment bindings in both `training_runtime_profile.js` and
`training_plan.js`. This allowed runtime policy consumers to interpret the
same values independently.

**Change:** `training_runtime_profile.js` remains the sole parser for these
profile settings. `training_plan.js` now consumes its normalized object for
preview defaults, saved-plan readiness, and submit-time runtime/budget checks.
The architecture check rejects raw reads of those settings outside the
normalization module. Admission remains its separate live gate; no defaults,
ceilings, or persisted plan fields changed.

**Validation:** focused profile tests cover normalized numeric values and
missing settings; the full Sites suite passes with 158 tests and a 50-module
acyclic runtime graph. D1 migration test, Worker build, artifact validation,
and diff check pass. No provider operation or deployment occurred.

**Independent review:** no actionable findings. The review confirmed that
missing settings still fail closed and the normalization preserves existing
runtime/budget semantics.


## 2026-11-28 — A11: normalize the reviewed MAP runtime configuration

**Problem:** the fixed MAP training source SHA, image identity, price quote,
runtime, and monthly budget were read and numerically converted across input
validation, source readiness, planning, and submit checks. This made it harder
to tell which code owned the current fixed execution configuration.

**Change:** added `worker/map_training_configuration.js` as the parser for
those values and migrated each consumer. The architecture check now rejects
raw reads outside that module. MAP admission and the shared control-plane
signing key remain separate settings with different owners.

**Validation:** added tests for normalized values and missing-setting behavior.
All 161 Worker tests pass and the runtime graph remains acyclic across 51
modules; D1 migration, Worker build, artifact validation, and diff checks pass.
No provider operation or deployment occurred.

**Independent review:** no actionable findings. Review confirmed that
source/image pinning, quote validation, runtime limits, and budget checks are
unchanged and malformed or missing settings still block execution.


## 2026-11-28 — A11: centralize training admission flag interpretation

**Problem:** owner-selected admission was interpreted separately in capability
projection and training lifecycle code; the MAP admission flag had several
independent reads in plan preparation, status, and submit paths.

**Change:** the owner profile module and MAP configuration parser now each own
their strict literal-`true` admission parser. Capabilities and training
lifecycle paths consume those helpers. Admission remains an explicit live gate
and is not conflated with profile validity or provider policy.

**Validation:** tests verify only the exact string `true` opens the setting.
All 162 Worker tests pass; the 51-module graph is acyclic; migration, build,
artifact validation and diff checks pass. No provider operation or deployment
occurred.

**Independent review:** no actionable findings. Capability, prepare, status,
and submit retain the same fail-closed literal-`true` admission behavior.


## 2026-11-28 — A11: centralize the shared training authorization identity

**Problem:** the shared control-plane SHA used to bind owner and MAP training
authorization was read directly by capabilities, plan submission, and Site
authorization routes. Its security role was distinct from ordinary execution
profile settings but had no explicit configuration boundary.

**Change:** added `worker/training_security_configuration.js` as the sole
binding reader and migrated those consumers. The architecture check now rejects
direct reads elsewhere. Authorization formats, signing, and identity values are
unchanged.

**Validation:** all 163 Worker tests pass; the 52-module graph is acyclic;
D1 migration checks, Worker build, and artifact validation pass. No provider
operation or deployment occurred.

**Independent review:** no actionable findings. Review confirmed that the
existing control-plane identity and fail-closed validation are preserved across
capability, plan, and confirmation paths.


## 2026-11-28 — A8: isolate MCP request-auth route integration tests

**Problem:** two HTTP-level OAuth authentication tests lived inside the broad
Worker integration test file and depended on its provider-oriented environment
fixture, obscuring the authentication boundary and its minimal requirements.

**Change:** moved the anonymous challenge and OAuth bearer audience/scope route
cases to `worker/mcp_request_auth.integration.test.js`. The new test file owns
a small D1 mock for only token lookup and empty run listing. Production code and
the tested assertions are unchanged.

**Validation:** focused route tests pass (2/2); all 163 Worker tests pass; the
52-module graph remains acyclic. `worker/index.test.js` shrank by 48 lines to
2,636 lines. No provider operation or deployment occurred.

**Review:** test-only extraction; old and new assertions were compared and
focused plus full suites pass.


## 2026-11-28 — A9: enforce the shared Python provider runtime boundary

**Problem:** Gateway retains five historical import paths for provider
adapters whose implementation is owned by the Sites Modal runtime. Without a
direct identity check, a later edit could accidentally restore a second
implementation behind a compatibility module.

**Change:** added a parameterized test proving each Gateway import resolves to
the exact corresponding `gpu_gateway._provider_runtime` module. The provider
runtime CI workflow now runs the contract. The Gateway and worker images both
copy the Sites-owned runtime; existing registry, worker, inventory, and tests
remain valid callers for the compatibility imports.

**Validation:** the full offline provider-runtime CI test selection, including
the five alias assertions, passes locally. Sites remains at 163 passing Worker
tests and 52 acyclic runtime modules. No provider operation or deployment
occurred.

**Decision:** retain the import facades while their in-repository callers
remain. Removing the legacy Gateway service is a separate unresolved decision
under A4 and is not justified by duplicate provider implementations.


## 2026-11-28 — A8: isolate owner-scoped experiment read-model routes

**Problem:** seven HTTP integration cases for owner isolation, run-list
projection, provider provenance, delegated history, terminal cleanup state,
pagination, and historical result provenance were embedded in the broad
`index.test.js` fixture.

**Change:** moved the cases into
`worker/experiment_read_models.integration.test.js` with a small owner allowlist
and per-case D1 query result. The tested HTTP/MCP paths and assertions remain
unchanged; no general-purpose test fixture abstraction was introduced.

**Validation:** all seven focused cases pass, all 163 Worker tests pass, and
the 52-module graph remains acyclic. The entry test file is 2,435 lines, down
201 lines; the new domain integration file is 222 lines. No provider operation
or deployment occurred.

**Review:** checked assertion parity and verified each test declares the D1
rows it returns.


## 2026-11-28 — A9/A12: enforce Python core and migration-source boundaries

**Problem:** `gpu_control` is intended as a host-independent reusable library,
but no automated check prevented it from importing Gateway or the Sites-owned
provider runtime. Separately, the root D1 replay test repeated the full
migration filename catalog, so new valid migrations failed until a second
list was updated.

**Change:** added an AST architecture test that keeps the dependency direction
from Gateway to `gpu_control`, never the reverse. Replaced the duplicated D1
migration filename inventory with a check for sequential, gap-free numeric
prefixes; the migration directory is now the single source for filenames.

**Validation:** `uv run --locked pytest` passes 616 tests and five subtests
(one skipped). The Sites Worker suite remains at 163 passing tests; its module
graph and external runtime packaging checks are unchanged. No provider
operation or deployment occurred.

**Review:** checked current import direction and replayed the complete ordered
migration set against in-memory SQLite.


## 2026-11-28 — A13: exercise external MCP OAuth over Worker HTTP

**Problem:** OAuth protocol functions had focused unit coverage, but no test
followed a remote client through the Worker's published discovery and client
registration routes. Route wiring or HTTP media-type checks could fail while
the protocol module tests still passed.

**Change:** added an HTTP integration case that reads protected-resource and
authorization-server metadata, registers a public DCR client, opens its
owner-consent page with PKCE, and verifies that the token endpoint rejects an
Authorization bearer header. Existing OAuth module tests continue to cover
GitHub subject binding, code exchange, audience, scope, expiry, refresh
rotation/replay, and revocation.

**Validation:** all 159 Worker tests pass; the graph is acyclic across 50
runtime modules; D1 migration, Worker build and artifact validation pass. This
is local source evidence only. No external client, provider, or deployed Site
was contacted.


## 2026-11-28 — A6: isolate MAP-specific plan construction

**Problem:** `training_plan.js` still combined owner-selected Modal planning,
MAP-44M's fixed workload/image/account-evidence rules, and the shared plan
record lifecycle. That made a second compute provider harder to add without
mixing its runtime policy into MAP's reviewed exception.

**Change:** moved MAP-44M-specific execution-spec selection, fixed runtime and
cost validation, image/source pin checks, quote calculation, and Modal account
evidence checks into `worker/map_training_plan.js`. The existing
`previewTrainingPlan` function remains the routing boundary; saved plan shape,
authorization, submit, status, cancellation, and public tool contracts are
unchanged. This is a source organization change, not Colab support.

**Validation:** Sites `npm test` passes all 166 tests, including the existing
owner-scoped training registration/prepare/submit contract; the Worker graph is
acyclic across 55 modules and the generated workload registry is current.
`git diff --check` passes. No provider call, experiment, or deployment occurred.

**Next:** keep shared plan/run coordination separate from provider-owned
admission and accounting. Colab remains unavailable until its quota/cost,
egress, idempotent operation recovery, artifact, and owned-session cleanup
contracts are resolved and implemented.

**Remote state:** source batch `bcb5cfac24c94c030f4ef7a1fec4ca746aac2587` was
pushed to PR #70. GitHub reports the PR open and mergeable, review required,
and all seven exact-head checks queued. No merge or deployment is established.


## 2026-11-28 — A7: isolate the atomic training dispatch claim

**Problem:** `training_plan.js` embedded the transactional D1 claim that
consumes exact owner authorization, reserves the Modal monthly ceiling, blocks
parallel unfinished runs, and prevents duplicate dispatch. This atomic
boundary was difficult to inspect separately from the submit orchestrator.

**Change:** moved the SQL claim and its reservation binding into
`worker/training_dispatch_claim.js`. Migrated the only direct test caller to
the new owner module; production orchestration imports the same function. No
public plan, authorization, or run schema changed.

**Validation:** Sites `npm test` passes all 166 tests; the D1-backed training
registration/dispatch integration case passes; the Worker graph is acyclic
across 56 modules and the workload registry is current. `git diff --check`
passes. No external provider operation occurred.

**Remote state:** code batch `70e0f0d122e640ad76f7383b1b320264987cce48` was
pushed to PR #70. GitHub reports the PR open and mergeable, review required,
and all seven exact-head checks queued. The architecture map now records this
code snapshot; no merge or deployment is established.


## 2026-11-28 — A6: bind Colab disclosure to verified provider evidence

**Finding:** Google's documented Colab API `get_subscription` returns only
`FREE`, `PRO`, or `PRO_PLUS`, not the compute-unit balance. Google's usage FAQ
states that remote control, notebook-UI bypass, and distributed workers are
restricted on managed runtimes in the free tier or without a positive unit
balance. Colab runtime egress is not restricted by the Sites Worker. A
capabilities result showing an eligible runtime therefore does not prove
positive units, a dollar ceiling, or network isolation.

**Change:** updated the Colab ADR, provider specification and backlog to make
the exact-plan positive-unit attestation, fresh eligibility recheck,
`cost_unknown`, no automatic top-up, unrestricted egress, secret/data exclusion,
and explicit run-owned runtime deletion part of the provider's release gates.
The read-only `colab_capabilities` response now exposes these limits to agents.
Google account email in owner-facing capability/status responses is redacted;
the OAuth callback still shows the full address only to the browser owner for
identity confirmation.

**Validation:** Sites `npm test` passes all 166 tests; the capability test
asserts quota and egress disclosures, no full email, and no runtime proxy
credential leakage. The Worker graph remains acyclic across 56 modules and
the registry is current. `git diff --check` passes. No Colab runtime, provider
request, credential, or deployment was created.

**Decision still required:** unrestricted runtime egress and unknown Google
spend are inherent to this provider route. Colab admission remains closed until
the owner accepts those disclosed boundaries. Other independent architecture
work continues.

**Remote state:** code batch `c374df4b5d1ab7b6b76682bc33b3b57949db244c` was
pushed to PR #70. GitHub reports the PR open and mergeable, review required,
and all seven exact-head checks queued. This is a local source capability and
policy improvement only; Colab execution remains disabled and no Site was
deployed.


## 2026-11-28 — A7: isolate saved training-plan state and cleanup projection

**Problem:** `training_plan.js` combined provider-neutral preview/prepare/submit
coordination with persisted status, readiness, cancellation, cleanup receipt
projection, and construction of the canonical authorization URL. These state
read operations are useful independently of the provider-specific submit path.

**Change:** moved saved-plan state/readiness/cancellation and cleanup receipt
handling into `worker/training_plan_state.js`; centralized the authorization
URL in `training_authorization.js`. The existing tool handlers and D1-backed
integration test now call the canonical modules. The public MCP tools, plan
shape, SQL schema, and authorization semantics are unchanged.

**Validation:** `npm test` passes all 166 Sites tests, including the D1-backed
registration/submit/cleanup test; the Worker graph is acyclic across 57
runtime modules and the generated workload registry is current. `git diff
--check` passes. The focused registration test passes. No provider request,
experiment, credential, configuration change, or deployment occurred.

**Remote state before this batch:** PR #70 was open and mergeable, all seven
checks had completed successfully at `c13c962`, and review remained required.
The local refactor is committed as `68a69be`; exact-head CI and review must be
refreshed after push. This does not establish merge, deployment, or Colab
execution support.

**Agent usability correction:** `docs/CHATGPT_SETUP.md` now distinguishes the
legacy MAP-44M Site confirmation from the owner-selected route's native
ChatGPT MCP write confirmation. External MCP clients must use their native
confirmation policy when available; OAuth authentication does not authorize
spending. This removes instructions that could send owner-selected users
through a redundant browser step while preserving the legacy contract.


## 2026-11-28 — A10: make Python fingerprint encoding authoritative

**Problem:** core Python value objects independently implemented the same
sorted compact JSON encoding and `sha256:` digest format. A serialization tweak
could silently make plan, capability, workload, lifecycle, and result identity
drift between types.

**Change:** introduced `src/gpu_control/canonical_json.py` and migrated the
approved plan, provider capability, workload spec, submission receipt, job
observation, result manifest, and provider result capture. The shared helper
rejects non-finite JSON numbers. Added behavioral vectors and an AST
architecture contract to prevent these model methods from reintroducing direct
serializer/hash implementations. Public JSON shapes and digest bytes for valid
existing values remain unchanged.

**Validation:** the full Python suite passes (one existing skip); focused
canonical serialization, plan, lifecycle, capability, workload, result, and
provider-finalization tests pass. `git diff --check` passes. No provider or
deployment operation occurred.

**Independent review:** the read-only security review found no actionable
issues. It confirmed the existing sorted compact ASCII representation is
preserved for validated model values and authorization/budget decisions are
unchanged.

**Limit:** the Sites Worker has its own runtime-local serializer. Persisted
cross-runtime contract fixtures still need a separate audit; this change
centralizes Python behavior only.


## 2026-11-28 — A7: isolate MCP tool-to-domain dispatch

**Problem:** `worker/index.js` mixed HTTP/MCP protocol composition and identity
checks with provider/workload dispatch across GitHub, Colab, training, Modal,
RunPod, Kaggle and Hugging Face routes. The entrypoint also retained unused
provider/workload constants and imports.

**Change:** moved the authenticated tool routing into
`worker/mcp_tool_dispatch.js`. The HTTP entrypoint still validates MCP
metadata, scopes and the authenticated principal, then passes the normalized
call and a small set of run-specific callbacks. Removed unused provider and
workload imports/constants. Tool names, argument schemas, owner checks,
provider gates, public result envelopes and route behavior remain unchanged.

**Validation:** Sites `npm test` passes all 166 tests; static Worker packaging
and dependency checks pass with an acyclic graph of 58 runtime modules. The
generated workload registry is current and both edited modules pass `node
--check`. `git diff --check` passes. No provider request, experiment, or
deployment occurred.

**Independent review:** read-only security review found no actionable issues.
It confirmed owner authentication and scope/schema validation remain before
dispatch, and that provider admission, budget gates, and callback wiring were
not weakened or moved into caller-controlled authority.

**Source snapshot:** code batch `c5c8fe5` reduces `worker/index.js` from 816 to
693 lines and puts provider/workload dispatch behind a 122-line module. This is
an ownership boundary improvement, not proof of deployment or live provider
availability.


## 2026-11-28 — A7: isolate external MCP OAuth HTTP routes

**Problem:** `worker/index.js` composed the OAuth discovery endpoints and
public-client registration, consent, token, and revocation handlers alongside
general MCP transport routing. That made the authentication entry point for
non-ChatGPT MCP clients harder to inspect and change independently.

**Change:** moved the OAuth HTTP contracts into
`worker/mcp_oauth_routes.js`. The module delegates OAuth protocol/state rules
to `mcp_oauth.js` and reuses the shared bounded body parsers and HTML renderer.
The Worker entrypoint now performs route composition only. Invalid consent
submissions also clear the one-time CSRF cookie; previously the call passed
cookie headers to a three-argument HTML helper, so the header was silently
discarded.

**Validation:** `node --check` passes for the changed modules; the focused MCP
OAuth suite passes all five tests, including the CSRF-cookie cleanup case. The
full Sites suite passes all 167 tests and the Worker graph is acyclic across
60 runtime modules. `git diff --check` passes. Independent read-only security
review found no actionable findings and confirmed endpoint, size/media-type,
response-header, consent, token, and revocation contracts. No provider call,
experiment, live OAuth flow, deployment, or admission change occurred.


## 2026-11-28 — A7: isolate shared GitHub OAuth owner-proof routes

**Problem:** `worker/index.js` owned GitHub App installation setup and one
callback that handled two OAuth purposes: linking the GitHub installation to
the Sites owner, and proving the same owner for an external MCP client. The
persisted OAuth state chooses which protocol completes.

**Change:** moved both routes into `worker/github_oauth_routes.js`. It
dispatches to the existing GitHub App connection or MCP OAuth domain functions
after verifying the persisted flow type and its matching PKCE cookie. This
keeps the shared GitHub identity proof together without putting GitHub state
rules into the general MCP dispatcher.

**Validation:** focused route tests cover the setup method restriction and
invalid callback state/cookie clearing. All 169 Sites tests pass; the Worker
graph is acyclic across 61 runtime modules; `git diff --check` passes.
Independent read-only security review found no actionable issues and confirmed
separate PKCE cookies, persisted-state classification, callback validation,
escaping, and route placement before `/mcp` authentication. No GitHub account,
credential, provider, run, deployment, or admission state was changed.


## 2026-11-28 — A7: isolate Google Colab OAuth HTTP routes

**Problem:** `worker/index.js` still owned the Colab setup and OAuth callback
handlers, including provider-specific PKCE cookie processing and callback
validation. This mixed an external provider's connection protocol with the
generic Sites HTTP/MCP composition root.

**Change:** moved those handlers into
`worker/google_colab_oauth_routes.js`. The composition root injects its shared
HTML renderer and escaping helper. Existing routes, response messages, cookie
attributes, callback URL validation, state/code checks, and failure behavior
are preserved. This is an internal boundary change; Colab execution remains
unimplemented.

**Validation:** `node --check` passes for both changed Worker modules;
`npm test` passes all 166 Sites tests, and the Worker graph is acyclic across
59 runtime modules. `git diff --check` passes. Independent read-only security
review found no actionable issues for cookie handling, PKCE/state/code checks,
callback matching, escaping, response headers, or failure paths. No provider
request, experiment, account connection, credential operation, deployment, or
admission change occurred.


## 2026-11-28 — A7: centralize bounded HTTP request-body reading

**Problem:** JSON and URL-encoded form readers duplicated the same bounded
stream loop, UTF-8 decoding, and reader cleanup. Their error codes and default
limits differ by format, but the byte-reading behavior has one authority.

**Change:** moved bounded byte collection and strict UTF-8 decoding into
`worker/http_request_body.js`. JSON and form parsers keep their existing
format-specific size and empty-body errors. MCP OAuth routes import the shared
parsers directly instead of accepting body-reader callbacks from the Worker
composition root.

**Validation:** the focused body-reader suite passes all four tests, including
declared and streamed limits, stream cancellation, format decoding, and strict
UTF-8. The full Sites suite passes all 182 tests; the Worker graph is acyclic
across 65 runtime modules; `git diff --check` passes. Independent read-only
security review found no actionable issues. No provider, run, account,
deployment, admission, or credential state was changed.


## 2026-11-28 — A7: isolate ChatGPT browser authorization routes

**Problem:** `worker/index.js` still contained the browser confirmation
surface for both fixed CPU plans and owner-selected GPU plans. Authentication,
exact plan rendering, challenge issuance, Origin/form checks, and one-use D1
consumption formed one coherent HTTP boundary but were mixed with MCP route
composition.

**Change:** moved the complete `/authorize` and `/authorize-training` flow to
`worker/training_authorization_routes.js`. The composition root supplies the
shared renderer, escaping helper, public origin, and canonical authorization
URL builder. Existing route registration and user-visible contracts remain
unchanged.

**Validation:** full Sites suite passes all 182 tests, including exact owner
binding, sign-in return path, HTML escaping, cross-site/wrong-origin rejection,
duplicate form rejection, single-use challenge consumption, and owner-scoped
training authorization. The Worker graph is acyclic across 66 runtime
modules; `git diff --check` passes. Independent read-only security review
found no actionable issue with owner checks, exact plan binding, control-plane
checks, one-use challenges, POST validation, or HTML protections. No live
provider or deployment operation occurred.

The architecture checker also rejects browser confirmation challenge SQL
outside `worker/training_authorization_routes.js`, preserving that security
boundary as an automated invariant.


## 2026-11-28 — PR #70 exact-head CI refresh

**Source:** the code head at that CI run was `842e30d`; `ddaba89` only
refreshed the architecture snapshot. PR #70 remains open and mergeable.

**Hosted CI:** all seven exact-head checks passed on `ddaba89`: Python 3.11,
3.12, 3.13, Gateway, Sites Worker and D1 contract, Project bridge tests, and
Trusted reference container. This is source/CI evidence only; it does not
establish merge, deployment, external MCP handshake, provider readiness, or a
live experiment.


## 2026-11-28 — A8: isolate ChatGPT authorization route integration test

**Problem:** the exact-plan browser authorization integration case was embedded
in the 2,435-line general Worker suite and depended on its provider-heavy
environment builder, despite having a self-contained D1 behavior fixture.

**Change:** moved the existing case to
`worker/training_authorization_routes.integration.test.js` and replaced the
generic environment dependency with the test's own minimal owner configuration
and D1 fake. Assertions and HTTP route coverage are unchanged.

**Validation:** the focused route integration test passes; the full Sites suite
still passes all 182 tests and the Worker graph remains acyclic across 66
runtime modules. `index.test.js` is now 2,317 lines. No production code,
provider, account, or deployment state changed.


## 2026-11-28 — A8: isolate Modal health-route integration tests

**Problem:** Modal health authorization, credential destination, redirect,
cooldown, result persistence and no-Sandbox guarantees were mixed into the
general Worker integration suite and used its broad environment builder.

**Change:** moved the nine existing health-route integration cases to
`worker/provider_health_diagnostic.integration.test.js`. The new fixture owns
only the plan authorization, workspace cooldown and per-plan result rows that
these cases exercise. The separate status-polling case stays with run lifecycle
coverage.

**Validation:** all nine focused cases pass and the complete Sites suite passes
all 182 tests; the Worker graph remains acyclic across 66 runtime modules.
`index.test.js` is now 2,065 lines. The tests preserve the no-provider-call
checks for unauthorized, unconfigured, admission-closed, redirected and
budget-store-failure paths. No real provider request, account change,
deployment or execution occurred.


## 2026-11-28 — A8: isolate local cancellation route integration tests

**Problem:** four owner-scoped cancellation/status integration cases were
embedded in the broad Worker test and reused its general environment builder.

**Change:** moved queued cancellation, cooperative running cancellation,
cross-owner denial, and terminal-run next-action coverage to
`worker/local_run_cancellation.integration.test.js`. The new fixture models
only run ownership/state transitions and needs no Runner or provider.

**Validation:** all four focused cases pass and all 182 Sites tests pass.
`index.test.js` is now 1,978 lines. No production contract, provider state,
deployment, or experiment behavior changed.


## 2026-11-28 — A8: isolate artifact retrieval route integration test

**Problem:** the owner-bound chunk retrieval case combined D1 lookup, artifact
storage metadata and checksum verification inside the broad Worker suite.

**Change:** moved the existing case to
`worker/run_artifacts.integration.test.js`. Its fixture now includes only the
allowlisted owners, one persisted run row, and the bounded R2 object behavior.

**Validation:** the focused artifact-route test passes and the complete Sites
suite passes all 182 tests. `index.test.js` is now 1,918 lines. Owner denial,
chunk boundaries, immutable metadata and tamper detection assertions are
preserved. No provider, deployment, or experiment action occurred.

## 2026-11-28 — A7/A12: centralize bounded external response reads

**Baseline:** exact source head `996cd4b4d1d0c00c3b4956a28b9a727144acc271`
was open on PR #70 and all seven hosted checks had passed. Repository mode
remains `parked`; no provider, account, production, or admission operation was
performed.

**Change:** added `worker/http_response_body.js` as the only bounded external
response byte reader. Migrated GitHub App, Google OAuth, Colab MCP, training
source/manifest, Modal, RunPod and signed adapter responses. Caller-specific
HTTP status mapping, JSON/text decoding, missing-body behavior, public error
codes, and RunPod abort mapping remain at each provider/domain boundary. Added
direct cases for chunking, declared and streamed limits, optional empty bodies,
stream cancellation and abort. The architecture checker now rejects other raw
response-stream readers.

**Local validation:** `npm test` passes all 186 Sites Worker tests; the graph is
acyclic across 67 runtime modules; generated registry validation and the
architecture guard pass. `git diff --check` passes. The change is committed as
`fec62dd1e1578145bb0b0e904150382f8ad09058` and pushed to PR #70.

**Hosted validation:** GitHub reports all seven exact-head checks successful
for `fec62dd`: Python 3.11/3.12/3.13, Sites Worker and D1 contract, trusted
reference container, Gateway provider-runtime, and Project bridge. No
production deployment, D1 migration, provider setting, credential, admission
flag or experiment changed.

## 2026-11-28 — A4: remove the retired Gateway comment bridge

**Finding:** `gateway/COMMENT_BRIDGE.md` already declared the comment-to-Gateway
workflow retired, its policy disabled, and its CLI/routes retained only as
historical reference. The active Project Checks implementation is separately
owned by `project_control/runner.py` and
`.github/workflows/project-checks-ci.yml`; the legacy bridge was not invoked by
that workflow or the current Gateway provider-runtime CI.

**Change:** removed the unused legacy bridge policy, CLI, FastAPI route module,
submission helper, and two bridge-specific test files (1,111 lines). The local
Gateway compatibility app no longer installs the retired routes. Kept the
independent Project Checks implementation, Sites control plane, provider-runtime
compatibility imports, legacy service, and dated historical records. Updated
Gateway and architecture documentation to identify the active owners.

**Local validation:** root `uv run pytest` passes 619 tests, one skipped, and
five subtests. `git diff --check` passes, and the remaining active Gateway,
`project_control`, and architecture sources contain no imports or paths to the
removed bridge. The change is committed and pushed as
`98db55a111f2a945bce295ea6cc51743d18b2cdd`.

**Hosted validation:** all seven exact-head PR checks pass: Python 3.11/3.12/3.13,
Sites Worker and D1 contract, trusted reference container, Gateway
provider-runtime, and Project bridge. No provider, deployment, D1 migration,
credential, or admission setting changed.

**Remaining A4:** the old FastAPI/PostgreSQL Gateway and deployment templates
remain a local compatibility service. This checkout cannot establish whether
an external operator still uses them; continue with source-level caller and
package-boundary work before deciding their retirement.

## 2026-11-28 — A4: reconcile current Gateway status documentation

**Finding:** the architecture map incorrectly claimed `gateway/README.md` and
ChatGPT setup docs disagreed about Gateway status. The current sources agree:
the FastAPI/PostgreSQL service is local-compatibility code and not a production
dependency. The map now states that consistently and preserves the separate
A4 question about unknown external use. No runtime code or deployment behavior
changed.

## 2026-11-28 — A6: bind Colab runtime deletion to the owned runtime identity

**Finding:** the Colab integration contract requires deleting a runtime created
for one exact run after verified output retrieval, but the fixed hosted-MCP
client rejected `delete_runtime` entirely. Google documents this tool as the
operation that removes the runtime, files, sessions, and state; deleting only a
session leaves the allocated runtime running.

**Change:** the internal Colab MCP client now admits `delete_runtime` only when
the requested runtime name exactly matches an expected run-owned runtime name
supplied by its trusted caller. The call still rejects missing ownership
context, a different runtime, malformed names, or extra arguments. Added
contract and client tests for those cases. No public Sites tool calls this
operation yet; this change enables a future shared-lifecycle adapter without
making arbitrary or owner-existing runtime deletion available.

**Validation:** focused Colab MCP client/contract tests pass (6). No Colab
runtime was created or deleted, no credentials or admission settings changed,
and Colab execution remains unavailable until the persisted shared lifecycle
is implemented.

## 2026-11-28 — A12: include re-exports in the Worker dependency graph

**Finding:** the Worker package graph recognized static imports but omitted
static ES module re-exports. A future module split could therefore hide a
dependency edge from cycle checks and packaging reachability.

**Change:** named and wildcard static re-exports now contribute dependency
edges. Added graph fixtures for both forms and malformed semicolonless syntax;
`npm test` runs these script tests before the architecture, registry, and
Worker checks. Refreshed the repository architecture snapshot from the prior
`129f002` head to current PR head `ad4af125d54b202267998b489de4c1f12c505768`.

**Validation:** local Sites checks pass: 2 graph tests, 187 Worker tests,
acyclic graph across 67 modules, generated registry check, and build copying
all 67 reachable runtime modules. Exact-head hosted CI reports all seven
checks successful. No provider execution or deployment occurred.

## 2026-11-28 — A12: enforce append-only D1 migration history

**Finding:** D1 migration replay and sequence checks proved the current files
could build a schema, but did not prevent a change from editing or deleting an
already deployed migration.

**Change:** the Sites CI job now compares migration files with the event's
base revision and rejects edits, deletions, renames, and newly inserted
versions. New tail migrations remain allowed. The job fetches full history so
the comparison is available for pull requests, pushes, and merge-queue runs.
Five isolated Git-repository tests cover valid append, edit, delete, rename,
and insertion cases.

**Local validation:** all five focused Python tests pass; the guard sees 22
base migrations and 15 branch additions against `origin/main`. The full Python
suite passes 624 tests, one skipped and five subtests; the Sites suite passes
(2 graph and 187 Worker tests), and the Sites build copies all 67 reachable
Worker modules. The workflow YAML parses, and all seven exact-head CI checks
pass on `2adfab9c38bcf1ecdef3ec9901d5ab25f4c9e7b3`. No migration was added or
edited by this change.

## 2026-11-28 — A12: make migration artifact verification source-driven

**Finding:** `validate-artifact.mjs` had a long hand-maintained list of old
migration filenames and SQL regexes that stopped at migration 0028. That list
duplicated schema semantics and failed to establish that the latest migrations
were actually copied into the hosted artifact.

**Change:** artifact validation now compares the source and packaged migration
filename sets and exact bytes. Migration replay tests own schema semantics;
they now exercise cancellation and provider limits, authorization expiry,
health-check scope, active lease requirements, and the Modal budget transition.
The legacy budget fixture checks both the old route-specific policy before
unification and the shared policy afterward. The migration test fixture now
inserts named columns instead of relying on the table's evolving column order.

**Validation:** full Python suite passes 624 tests, one skipped, and five
subtests. Sites build, artifact validation, populated migration replay,
dependency graph checks, generated registry check, and all 187 Worker tests
pass locally. The package validator also confirms the deployed hosting
manifest exactly matches `.openai/hosting.json`; seven exact-head checks pass
on `9ae223dea50f14748b8d627e73e224bfbe4edb78`.

## 2026-11-28 — A12: apply future tail migrations in the replay fixture

**Finding:** the populated D1 replay fixture asserted that migration 0036 had
to remain the newest file. That assertion made every valid append-only
migration require an unrelated fixture edit.

**Change:** removed the latest-filename sentinel. The fixture still applies the
OAuth migration at its explicit semantic checkpoint, then applies every later
append-only migration automatically so future schema changes remain covered by
the populated forward replay.

**Validation:** `python3 sites/gpu-control-sites/scripts/test_migrations.py`
passes against all 36 migrations, and `git diff --check` passes. This changes
only the local replay harness; no migration or live database was touched.

## 2026-11-28 — A12: use the Worker graph as the artifact inventory

**Finding:** `validate-artifact.mjs` listed selected Worker modules by name,
duplicating the dependency graph that the build already uses to reject
unreachable modules and copy every reachable module.

**Change:** removed the hand-maintained module list. Artifact verification
still imports the packaged entrypoint, compares the packaged hosting manifest
with its source, and checks the exact source/artifact migration inventory and
bytes. The dependency graph remains the single owner of Worker module
reachability and packaging.

**Validation:** Sites build, artifact validation, and `npm test` pass (2 graph
tests, 187 Worker tests, acyclic graph across 67 modules, current generated
registry). No runtime, deployment, provider, or credential behavior changed.

## 2026-11-28 — Refresh architecture snapshot after source batches

The map now points to `18311137da1a0801bff863971960585de699f418` and records
the local Worker graph and test measurements. All seven exact-head CI checks
passed for that source head. PR #70 remains open, unmerged, and in parked
repository mode.

## 2026-11-28 — A13: colocate MCP UX contract checks with the contract

**Finding:** the large Worker integration fixture exercised tool schemas,
descriptions, and operation annotations through the HTTP dispatcher. Those
assertions describe `mcp_tool_contract.js`, while transport identity and HTTP
behavior already have dedicated integration tests.

**Change:** moved the client-neutral guidance and read/write annotation
assertions into `mcp_tool_contract.test.js`, which now tests the schema and
annotations directly from their owner module. Removed the duplicate dispatcher
round trip from `index.test.js`; transport authorization coverage is unchanged.

**Validation:** focused contract tests pass (2); the full Sites suite passes
(187 Worker tests, 2 graph tests), and the graph remains acyclic across 67
modules. No public MCP schema, annotation, or runtime behavior changed.

The repository map now points at `bcefd695ef1c20e0c4da3defc52aebd02e5604c2`,
records the reduced `index.test.js` size (1,867 lines), and confirms all seven
exact-head CI checks succeeded. The new contract assertions keep the complete
Worker suite at 187 tests.

## 2026-11-28 — A6: specify Colab long-call recovery against provider limits

**Finding:** the Colab MCP client currently times out every call after 30
seconds, while Google's execution API may continue running after its 600-second
response deadline. Reusing an execution ID reattaches only while its result is
pending; after the result is returned, reusing that ID executes the code again.
Cloudflare HTTP Workers also cancel outstanding work when the client
disconnects, with only a short `waitUntil` extension.

**Change:** documented distinct durable identities and state transitions for
runtime creation, code execution, result persistence, and deletion. The
architecture gate now forbids depending on one long MCP request or an
in-memory promise and requires status recovery to reattach to the same pending
execution before Colab admission can be enabled.

**Evidence:** [Google execute_code contract](https://developers.google.com/colab/api/reference/mcp/tools_list/execute_code)
and [Cloudflare Worker limits](https://developers.cloudflare.com/workers/platform/limits/)
were reviewed on 2026-11-28. No runtime or provider call was made; no
admission, credential, budget, or deployment setting changed. The current
adapter remains read-only and the execution lifecycle is unimplemented.

## 2026-11-28 — A12: make architecture decision identifiers unique

**Finding:** two different decisions used ADR 0007, while the architecture
index linked only one of them. References to the Modal MAP account-evidence
decision were therefore ambiguous.

**Change:** renumbered the MAP Modal account-evidence decision to ADR 0013,
added it to the architecture index, and updated the backlog and historical
progress references. The GitHub installation owner-proof decision remains ADR
0007.

**Validation:** searched the repository for the old MAP ADR reference, checked
the decision index and file numbering, and ran `git diff --check`. This is a
documentation-only change; no provider, runtime, credential, deployment, or
admission state changed.

## 2026-11-28 — A5: centralize Modal training budget decisions

**Finding:** owner capability, training prepare, submit and status each
reinterpreted the same Modal D1 budget projection. The duplicated checks could
disagree about provider policy availability, the per-run ceiling, the lane's
monthly ceiling, remaining reservation, and GPU admission.

**Change:** added `assessModalTrainingBudget` beside the authoritative D1
budget projection and migrated all four consumers. The shared result keeps
capability discovery's positive-remaining check distinct from prepare/status'
exact full-plan remaining-budget check, and submit's current admission check.
Updated the architecture map to state that custom training is Modal-only in
source today; it no longer describes this orchestrator as provider-neutral.

**Validation:** focused provider-budget tests pass (7); full Sites checks pass
(2 dependency-graph tests, acyclic graph across 67 Worker modules, current
generated registry, and 188 Worker tests). No D1 schema, provider, credential,
deployment, or admission state changed.

## 2026-11-28 — A7: split training plan work into cohesive use cases

**Finding:** `training_plan.js` combined source resolution and provider preview,
idempotent D1 plan persistence, and exact-plan authorization/dispatch in one
module. The public tool router imported all three operations through that
mixed module, so a provider-specific change pulled unrelated lifecycle code
into the same edit surface.

**Change:** moved the three operations into `training_preview.js`,
`training_prepare.js`, and `training_submit.js`; migrated the MCP router and
the submission integration tests; deleted the old module. Added an executable
architecture rule that prevents contracts from depending on use cases and
keeps use-case dependencies flowing from preview to prepare to submit.
Updated the architecture map and selected-repository design to match the
current source. Public tool schemas, arguments, authorization, D1 state, and
provider behavior are unchanged.

**Validation:** `node --check` passes for all three modules. The Worker graph
is acyclic across 69 runtime modules; the Sites suite passes 2 dependency-graph
tests, the generated-registry check, and all 188 Worker tests. No D1 migration,
provider, credential, deployment, or admission state changed.

## 2026-11-28 — A6: prioritize Colab on the shared run lifecycle

**Finding:** the current Colab surface only connects a Google account and
reads subscription/runtime eligibility. It explicitly reports
`COLAB_EXECUTION_LIFECYCLE_NOT_IMPLEMENTED`; it cannot prepare, submit, recover,
or clean up an experiment. The official `google-colab-cli` can run locally or
in a credentialed CI environment, but those calls do not use the Sites owner
ledger and cannot be launched from a Sites Worker.

**Decision:** make hosted Colab MCP the next owner-selected provider to join
the existing Sites lifecycle. Keep `google-colab-cli` as a local/CI client,
not a second server-side provider adapter. Keep ordinary PR CI offline. The
backlog now orders the work accordingly and names the hard requirements:
unknown provider quota, open egress, durable long-call recovery, and run-owned
runtime cleanup.

**Validation:** checked the current public tool descriptions and implementation
for the explicit lifecycle blocker, reviewed Google's current official CLI
commands/authentication docs, and ran `git diff --check`. This records scope
and ordering; it does not implement Colab execution or enable a provider.

## 2026-11-28 — A6: bind Colab lifecycle tools to run-owned identities

**Finding:** the provider contract validated the shape of runtime, session, and
execution identifiers, but allowed an internal caller to list sessions or
delete any syntactically valid Colab session. It also allowed `get_runtime`,
`create_session`, and `execute_code` without proving they referred to the
identities persisted for the current run. Google's API explicitly warns that
sessions may belong to user notebooks and that deleting a session interrupts
its active execution.

**Change:** `list_sessions` and `delete_session` now require the exact expected
run-owned runtime/session; `get_runtime`, `create_session`, and `execute_code`
require their exact expected runtime/session/execution identities. The
capability remains read-only and there are still no public Colab run actions.

**Validation:** focused Colab contract tests pass (2), the complete Sites suite
passes 188 Worker tests, two graph tests pass, and the runtime graph remains
acyclic across 69 modules. This establishes identifier fencing only; it does
not validate live Google calls, runtime proxy URL safety, or the full run
lifecycle.

## 2026-11-28 — A6: align bounded Colab execution request sizes

**Finding:** the MCP contract accepted `execute_code` source up to 256 KiB,
but the hosted-MCP client capped the complete serialized request at 64 KiB.
Ordinary larger training entrypoints would pass validation and then fail before
reaching Colab.

**Change:** raised the total serialized-request ceiling to 2 MiB, leaving room
for the contract's maximum source plus JSON/MCP framing and escaping. Responses
remain independently capped at 64 KiB. Added a client test that sends more than
64 KiB through the bounded transport.

**Validation:** the Sites suite passes all 188 Worker tests and two graph tests;
the architecture graph remains acyclic across 69 modules, the registry check
passes, and `git diff --check` passes. No Google runtime was created and no
provider credentials or admission settings changed.

## 2026-11-28 — A6: add the Colab operation journal schema

**Finding:** the shared delegated plan table stores provider observations as a
generic JSON response, which is unsuitable for Colab's runtime proxy URL/token
and exact long-call recovery identities. The runtime token is short-lived and
must not be persisted as ordinary provider output.

**Change:** added forward migration `0037_colab_run_operations.sql`, keyed by
the existing run ID and constrained by owner plus plan fingerprint. It stores
the stable runtime request/execution identities, bounded lifecycle state,
encrypted-connection fields, code digest, and bounded result field separately.
Migration tests verify owner/fingerprint binding, allowed state values, and
foreign-key integrity. No public Colab run operation reads or writes the table
yet; execution remains unavailable.

**Validation:** the D1 migration suite passes against the pre-existing schema;
the complete Sites suite passes 188 Worker tests and two graph tests, the
workload registry is current, and the Worker graph remains acyclic across 69
modules. No live provider call, runtime allocation, secret, admission setting,
or deployment changed.

## 2026-11-28 — A6: validate the Colab runtime proxy origin

**Finding:** Colab's runtime response includes a URL and short-lived proxy
token used together for file transfer. Accepting an arbitrary HTTPS URL would
let an invalid provider response redirect credential-bearing requests to an
attacker-controlled host.

**Change:** runtime connection URLs are restricted to the exact
`https://colab.googleusercontent.com` origin without userinfo, port, query, or
fragment. Added contract coverage for deceptive host suffixes and URL
credentials. The architecture record now requires owner-bound runtime creation
and forbids reuse/deletion of sessions or runtimes not created by that exact
run; it also documents exact-ID recovery for timeouts.

**Validation:** focused Colab MCP tests pass (6); the full Sites suite passes
188 Worker tests, two graph tests, generated registry validation, and the
acyclic import check across 69 modules. This does not enable or live-test
Colab execution.

## 2026-11-28 — A6: add owner-bound Colab operation storage

**Change:** added `google_colab_operation_store.js`. It creates a persisted
operation before runtime allocation, returns the same stable runtime request
ID on exact recovery, scopes reads and compare-and-set transitions by owner,
run and plan fingerprint, constrains state transitions, and prevents runtime
or session identity replacement. Runtime connection data can be encrypted
with AES-GCM additional authenticated data tied to that same owner/run/plan.

**Validation:** 191 Worker tests pass, including owner isolation, duplicate
transition, runtime identity replacement, request ID retry and ciphertext
substitution cases. Migration validation passes; the import graph is acyclic
across 70 modules. The storage module is not yet wired into a public Colab
submit/status route, so execution remains unavailable.

## 2026-11-28 — A6: separate Colab short and long call deadlines

**Change:** the hosted MCP client now keeps capability and ordinary lifecycle
reads at 30 seconds while allowing `create_runtime` and `execute_code` the
Google-documented 600-second call ceiling. Explicit per-call overrides remain
bounded by that ceiling; the client adds no automatic retries.

**Validation:** focused Colab contract and transport tests pass, and the full
Sites suite passes 192 Worker tests with an acyclic graph across 70 modules.
This only aligns the outbound call deadline; a disconnected request is still
not durable by itself, so public execution remains gated on status-driven
recovery using the persisted operation journal. Migration checks also reject
truncated, plaintext-sized connection blobs before any runtime token can be
persisted.

## 2026-11-28 — A6: generate a pinned Colab GPU execution payload

**Change:** added `google_colab_execution_code.js`, which generates a
deterministic runner only for a public immutable GitHub commit, a validated
experiment manifest, an eligible T4/L4 profile and a maximum 360-second run.
The generated code installs the hash-locked dependency file, checks both
`nvidia-smi` and PyTorch CUDA against the selected accelerator before running
the entrypoint, bounds output files and total output size, computes SHA-256
for declared artifacts, and writes a durable run-specific completion receipt
so a transport replay does not run completed training twice. No credential is
embedded, and private repository visibility is rejected.

**Validation:** generated Python compiles; source-contract negative cases
reject invalid source, path, profile and duration. The full Sites suite passes
194 Worker tests, migration validation passes, and the Worker import graph is
acyclic across 71 modules. This generator is not yet wired to public MCP plan,
submit, status, artifact or cancellation tools and has not run on a live Colab
GPU.

## 2026-11-28 — A6: retrieve verified Colab runtime files

**Change:** added `google_colab_runtime_files.js` to fetch one declared file
only from a matching run-owned runtime. It validates relative paths, rejects
redirects, caps the API response at 50 MiB, requires exact receipt size and
SHA-256, and never exposes the short-lived proxy token in returned data.

**Validation:** focused generated-code and runtime-file tests pass; the full
Sites suite passes 196 Worker tests, D1 migration validation passes, and the
Worker graph is acyclic across 72 modules. This does not yet persist bytes to
R2 or expose them through the shared artifact MCP tool; no live Colab runtime
was used.

## 2026-11-28 — A6: bind Colab results to the prepared execution

**Change:** added a bounded parser for one machine receipt, binding run ID,
repository, commit, selected T4/L4 GPU, declared outputs, artifact sizes and
SHA-256 values. Arbitrary stdout is not interpreted as control data. A
successful result requires CUDA evidence, exit code zero and metrics output.
The runner now requires declared metrics and checkpoint outputs and caps the
metrics file at 8 KiB.

**Validation:** focused Colab tests pass and migration checks pass. The first
exact-head CI build found that these four pre-integration modules were placed
inside the production Worker source tree without imports from its entrypoint.
They are now isolated under `colab/lifecycle/`; tests still import those
modules directly, while the Worker bundle includes only reachable production
code. This parser is not yet connected to public MCP execution tools; Colab is
not yet a usable experiment route and no live runtime was started.

## 2026-11-28 — A6: connect Colab to the shared MCP run lifecycle

**Change:** the PR #70 source candidate now routes owner-selected public Colab
plans through the shared experiment MCP contract. The D1 operation journal
persists stable runtime/session/execution identities and encrypted runtime
connection data; the shared status/result/cancel/artifact tools resume the same
run, retrieve checksum-verified outputs into private R2, and record cleanup.
Capabilities and scheduled reconciliation include Colab. The public tool
descriptions state that Colab USD cost/CU balance is unavailable, runtime
egress is unrestricted, there is no paid fallback/top-up, and only the
run-owned runtime may be deleted. Colab tools are described as client-neutral
for any compatible authenticated MCP client; direct CLI jobs remain outside
the shared ledger.

**Validation:** all 201 Sites tests passed; Worker dependency graph is acyclic
across 75 runtime modules; `npm run build`, D1 migration validation, and
`git diff --check` passed. Local mocks only; no Google runtime was allocated.
This is PR source evidence, not deployment or live provider acceptance. Open
release work includes exact-head CI, independent security review, production
OAuth/configuration and migration, a verified positive-CU owner attestation
bound to the exact submit confirmation, and one bounded GPU run with
independent GPU/artifact/cleanup verification.

## 2026-11-28 — A14: persist Colab quota attestation and refresh architecture truth

**Finding:** Colab submit required a positive-Compute-Unit attestation in the
tool call but did not persist it with the owner-bound authorization. Capability
readiness also checked the run/artifact tables without checking that the D1
attestation migration was present. Several current architecture pages still
described Colab as not integrated or described Modal as the only
owner-selected provider.

**Change:** migration `0039_colab_positive_cu_attestation.sql` adds a checked,
false-by-default attestation column to the exact delegated authorization.
Colab submit persists `true` only for an exact confirmed call and rejects old
records without the attestation before runtime creation. Colab capability
readiness now requires the migration column. Regression coverage verifies
default-closed prepare, missing-attestation submit and legacy-row migration.
The architecture index, ADR, provider map, selected-repository guide, chat
operations, backlog, status and release matrix now distinguish the shared
hosted-MCP Colab route from standalone CLI/local-MCP jobs and deployed provider
state.

**Validation:** 203 Sites tests pass; the Worker graph is acyclic across 76
runtime modules; build and D1 forward migration replay pass; `git diff --check`
passes. Code batch is commit `89dc396`. This is source evidence only. PR #70
remains unmerged, hosted migration/configuration and live Colab acceptance are
unverified, and the official diff scanner did not initialize on this linked
worktree. The scanner's failure is not a security review result.

## 2026-11-28 — A3: distinguish the product ledger from provider recovery records

**Finding:** ADR 0002 described the owner-selected Modal journal boundary as if
it covered all routes. Current source has distinct coordination records for
RunPod account-scoped dispatch, Colab runtime operations, the fixed Modal GPU
lease, and custom-training Sandbox recovery. Their transitions and recovery
identities are provider-specific; merging them into one state machine would
hide rather than remove those differences.

**Change:** updated ADR 0002, the repository state-ownership map, and A3's
backlog evidence to name each record and keep the Sites D1 run ledger separate
from provider coordination and provider observations. The ADR now marks
cross-route failure/retention conformance as open instead of implying a
completed universal contract.

**Validation:** checked each named table and operation store against the
migrations and current Worker modules; Markdown links resolve and
`git diff --check` passes. This documentation-only batch changes no runtime behavior,
provider settings, or admission state. Route-by-route response-loss, terminal,
cleanup, and record-loss acceptance remains open.

## 2026-11-28 — A0: synchronize source and release evidence after CI

**Finding:** after commit `2842bd9`, the source, local validation, and all seven
exact-head GitHub checks were current, but STATUS, the release matrix, and the
repository map still named commit `89dc396`, 203 tests, and pending CI. This
made the documented release state contradict the authoritative branch and CI.

**Change:** refreshed the source SHA, 204-test count, seven-check result, and
Colab lifecycle evidence in STATUS, the release matrix, repository map, Colab
provider guide, ADR 0011, and the prioritized backlog. Explicitly preserved
the separate unverified boundaries: deployment and D1 migration application,
independent security review, and live Colab GPU acceptance.

**Validation:** compared the documented SHA with the local and remote branch
head and GitHub PR #70; compared the CI statement with all seven exact-head
check results; checked for stale `89dc396`/203-test/pending-CI claims in active
architecture and release summaries. Documentation-only update; no provider,
deployment, admission, or runtime state changed.

## 2026-11-28 — A1: distinguish Colab source support from production support

**Finding:** `sites-four-provider-control-plane.md` still labeled Colab as a
planned, unavailable target and described lifecycle implementation as work
that had not happened. Its route row and activation gate contradicted the
current PR #70 source and the Colab provider specification. This blurred the
difference between implemented source, deployed capability and live provider
acceptance.

**Change:** updated the provider control-plane record to identify Colab as an
owner-selected route implemented in PR #70 source, while keeping deployment,
OAuth configuration, migration, security review and live GPU acceptance as
separate release gates. Clarified that the four-provider count belongs to the
last verified production Site and that direct Google MCP calls remain outside
the shared Sites ledger.

**Validation:** cross-checked the route and lifecycle claims against the
current Colab provider guide, PR #70 source and release matrix. `git diff --check`
passes. No runtime code, provider configuration, admission or live execution
changed.

## 2026-11-28 — A3: validate Colab deletion receipts before cleanup finalization

**Finding:** the lifecycle treated any object returned by `delete_runtime` as
proof of cleanup. Google's MCP method returns an empty protobuf message on
success; an object such as `{ "deleted": false }` is outside that response
contract and cannot establish that the runtime was removed. The cleanup retry
path also had no end-to-end regression case.

**Change:** added one validator for the empty successful deletion response and
made terminal finalization require that exact shape. Extended the Colab
lifecycle integration test to apply both migrations `0037` and `0038`, lose the
first runtime-create response, return an invalid non-empty deletion response,
and then return an empty success on retry. The test verifies cleanup remains
pending between calls, the same runtime request is reused, and execution is
not repeated. Updated the source status, provider contract, and A3 task record.

**Validation:** all 205 Sites tests pass; the Worker graph remains acyclic
across 76 runtime modules; build and D1 forward migration replay pass; the
focused Colab tests pass; all seven exact-head GitHub Actions checks pass on
`e391116`. No Colab runtime, provider setting, OAuth credential, or admission
was used or changed. This fake-provider test does not prove Google's live
deletion behavior or other providers' terminal-state conformance.

## 2026-11-28 — A3: apply the Colab cleanup contract to cancellation

**Finding:** `advanceGoogleColabRun` validated the empty deletion receipt, but
`experiment_cancel` called the same provider method and finalized the D1 plan
and operation journal without validating its response. The same malformed
`{ "deleted": false }` response could therefore still produce false cleanup
confirmation on explicit cancellation.

**Change:** reused the shared `validGoogleColabRuntimeDeletion` contract in the
cancel path. Extended the lifecycle integration case with a second submitted
run whose runtime is discovered during cancellation: an invalid delete
response leaves the operation in `cleanup_pending`; a later empty success
response records cancellation and terminal cleanup on that same run.

**Validation:** all 205 Sites tests pass; build and D1 forward migration replay
pass; the Worker graph remains acyclic across 76 modules; all seven exact-head
GitHub Actions checks pass on code commit `fc8931a`. No live provider or
account state changed. The fake Colab endpoint does not establish live Google
behavior.

## 2026-11-28 — A3: exercise Colab lifecycle recovery after response loss

**Finding:** Colab had unit coverage for its operation journal and MCP protocol,
but no integration test composed the real lifecycle with persisted operation
state. The most important boundary is recovery when Google creates a runtime
but the response is lost before Sites can persist its runtime identity.

**Change:** added
`sites/gpu-control-sites/worker/google_colab_lifecycle.integration.test.js`.
It applies migration `0037` to in-memory SQLite, invokes the real Colab run
lifecycle, drops the first mocked `create_runtime` response after provider-side
creation, and verifies replay uses the same persisted request ID and resolves
to one mocked runtime. It then verifies a failed execution receipt, deletion
of the run-owned runtime, and terminal journal state.

**Validation:** the focused integration test passes. The full Sites suite
passes (204 tests), including the Worker architecture check and workload
registry check. This does not establish Google's live create-runtime
idempotency behavior, provider terminal-state mismatch handling, durable
journal-loss recovery, or real Colab GPU acceptance; those A3/A6 release gaps
remain open. No live provider runtime or provider setting was touched.

## 2026-11-28 — A3: fail closed when the Colab operation journal is missing

**Finding:** when D1 retained a submitted Colab plan but the corresponding
`google_colab_run_operations` row was missing, status could report the plan as
prepared. That hid uncertainty about provider allocation and could encourage
an agent to submit again. Cancellation also lacked a stable missing-record
outcome.

**Change:** status, cancellation, and repeated submit now return the same
owner-bound `uncertain` result with provider allocation and cleanup unknown.
They do not call Colab or recreate a journal for a submitted plan. A genuinely
prepared plan with no submit attempt retains its pre-run behavior. This is a
fail-closed recovery boundary, not reconstruction: provider evidence lost with
the journal still requires manual reconciliation.

**Validation:** the SQLite-backed lifecycle integration test covers all three
entry points and asserts that the fake Colab endpoint receives no request.
All 205 Sites tests, the 76-module acyclic architecture check, build, D1
forward-migration replay, and `git diff --check` pass. Exact-head CI passed all
seven checks at PR tip `644f507`. Code is in `31bc183`; the latest tip contains
documentation updates only. No live provider/runtime or credential was used.

## 2026-11-28 — A3: preserve cancellation intent through ambiguous RunPod submit

**Finding:** while a RunPod submit response was uncertain and its receipt was
not yet recoverable, `experiment_cancel` returned success even though the run
remained active. The cancellation intent was not durable, so a later status
poll that recovered the provider job could continue without cancelling it.

**Change:** RunPod cancellation now persists `cancel_requested` on the
owner-bound run. Synchronization honors that value after recovering the exact
submission receipt and cancels/cleans that job. Until a terminal cleanup state
is observed, the tool reports `pending`/`uncertain` and exposes status polling
as the next action. A missing run from a concurrent state change returns
`RUN_NOT_FOUND` rather than a false success.

**Validation:** focused cancellation and RunPod lifecycle suites pass 12/12;
all 206 Sites tests pass; the Worker graph is acyclic across 76 modules; build
and D1 forward migration replay pass; `git diff --check` passes. All seven
exact-head GitHub Actions checks pass on code commit `748ac11`. No live RunPod
job, provider credential, or account state was used.

## 2026-11-28 — A0: make release state single-source

**Finding:** PR, CI and validation facts had drifted across STATUS,
RELEASE_MATRIX, the architecture map and the prioritized backlog. Several
documents still cited old PR #70 SHAs and test counts as current. The release
matrix also mixed a stale candidate snapshot with dated production acceptance.

**Change:** made `docs/STATUS.md` the current source/release entry point and
linked volatile GitHub review and exact-head checks to PR #70 as their live
authority. Removed the duplicate candidate table from RELEASE_MATRIX and
explicitly dated its retained production table. The architecture map now
labels measured sizes as checkpoint-specific; the backlog points to STATUS
instead of copying mutable SHA/check facts.

**Validation:** checked references and stale-SHA matches in active release and
architecture summaries; `git diff --check` passes. Documentation-only batch:
no provider call, credential, admission, deployment, or runtime state changed.

## 2026-11-28 — A5/A7: centralize RunPod admission policy

**Finding:** `RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED` and
`RUNPOD_WORKLOAD_ADMISSION_ENABLED` were interpreted separately in provider
capability projection, the MCP dispatcher, and RunPod submit. The dispatcher
was the only guard before RunPod prepare, leaving the domain plan boundary
without its own admission check.

**Change:** introduced `runpod_admission.js` as the single policy decision for
both gates. Capability projection, plan creation, and submit now consume that
decision. Removed admission branching and duplicate input validation from the
MCP dispatcher; the RunPod plan module owns its contract and blocks before D1
or provider access when invoked directly. Added a focused regression case for
both gates and their no-I/O behavior. Source commit: `97584ad`.

**Validation:** 11 focused RunPod tests pass; the full Sites suite passes 209
tests, including an acyclic Worker graph across 77 modules. Worker build and
artifact validation pass, D1 forward migration replay passes, and
`git diff --check` passes. No RunPod API, credentials, admission setting, or
runtime was accessed or changed.

## 2026-11-28 — A12: guard the RunPod admission owner

**Finding:** the shared RunPod admission function fixed current callers, but
the architecture check did not prevent future modules from reading the raw
environment flags and recreating a second policy interpretation.

**Change:** extended `check-worker-architecture.mjs` to reject direct reads of
the RunPod transport-verification and admission bindings outside
`runpod_admission.js`. This turns the newly established single-owner rule into
a local CI invariant.

**Validation:** full Sites `npm test` passes 209 tests; the architecture check
reports an acyclic graph across 77 runtime modules. No runtime behavior,
provider configuration, or admission state changed.

## 2026-11-28 — A3: resume RunPod account cleanup after partial terminalization

**Finding:** RunPod records the owner run's terminal state and confirmed
provider cleanup before releasing its account-scoped lease. If that later D1
lease transition fails, a retry for an ambiguous-submit TTL case found the
terminal row but left an `uncertain` lease stuck. Cancellation had the same
partial-write window from an `active` lease.

**Change:** terminal status recovery now reads the saved RunPod cleanup receipt
and resumes only the legal lease transitions for its exact outcome: confirmed
not-started/rejected creates release directly; provider-terminal or cancelled
jobs advance active/cleanup-pending leases; elapsed Serverless TTL advances
the same uncertain lease using its run-bound synthetic expiry handle. It does
not repeat provider calls. Code commit: `b509923`.

**Validation:** failure-injection lifecycle tests cover both an uncertain
lease after TTL terminalization and an active lease after confirmed
cancellation. Both recover to `released` without duplicate create/cancel. The
full Sites suite passes 211 tests; architecture graph is acyclic across 77
modules; Worker build/artifact validation and D1 forward migration replay
pass. No live RunPod call or state change occurred.

## 2026-11-29 — A13: normalize RunPod provider configuration

**Finding:** RunPod readiness, plan construction, capability projection and
pre-submit pricing each read or validate the same pinned image, endpoint, GPU,
maximum price, pool and source SHA independently. This allowed those call
sites to drift even though they represented one operator-owned profile.

**Change:** introduced `worker/runpod_configuration.js` as the single
validation and normalization boundary. Provider construction, plan validation
and creation, capability projection and the default pre-submit offer now
consume its immutable non-secret profile. The direct API key is retrieved
through a separate accessor in the same module and is never included in the
normalized profile. A static architecture guard prevents future direct reads
of profile bindings outside this owner; the existing `runpodConfigured`
export remains compatible.

**Validation:** Sites `npm test` passes 215 tests; the Worker graph is acyclic
across 79 runtime modules. Worker build, artifact validation, D1 forward
migration replay and `git diff --check` pass. No provider API, credential,
admission value, deployment, or experiment was accessed or changed.

## 2026-11-29 — A14: align Colab connection tools with MCP input validation

**Finding:** `tools/list` advertised `colab_connection_start`,
`colab_connection_status`, `colab_connection_disconnect`, and
`colab_capabilities`, but `validToolArguments()` did not accept any of them.
The Worker rejected every call as `INVALID_ARGUMENTS` before dispatch, making
the advertised Google account connection path unusable from ChatGPT or another
MCP client.

**Change:** added the four exact empty-input tools to the common validator.
The worker-level regression test invokes them through the authenticated MCP
entrypoint, checks owner denial and fail-closed behavior while Google OAuth is
unconfigured, verifies malformed extra fields are rejected, and confirms the
tools remain discoverable. A contract test ties the advertised tools to the
same validator behavior.

**Validation:** focused MCP and Worker entrypoint tests pass (41/41). The
full Sites suite passes 217 tests; the 79-module Worker graph is acyclic.
Worker build, artifact validation, D1 forward migration replay, and
`git diff --check` pass. Exact-head CI will be checked after pushing. No
Google OAuth, runtime, credential, provider setting, or experiment was
accessed or changed.

## 2026-11-29 — A0: refresh the architecture map at the current source head

**Finding:** the repository map still described a 2026-11-28 snapshot and
module sizes from before the owner-selected Colab lifecycle and recent module
extractions. Its flow diagram also omitted the hosted Colab API MCP path.

**Change:** refreshed the map to source checkpoint `ef9df7a`, remeasured the
large modules and test suites, documented generated capability-order
ownership, and added Colab runtime/artifact flow to the dependency diagram.
Updated `docs/STATUS.md` with current exact-head local and GitHub Actions
evidence while keeping release and review limits explicit.

**Validation:** verified listed module sizes with `wc -l`, confirmed the
Worker graph is acyclic across 82 modules, and checked documentation diffs for
whitespace errors. This does not change runtime behavior or claim that Colab
is deployed or live-accepted.

## 2026-11-29 — A0/A20: refresh structure after Colab artifact extraction

**Finding:** the Colab artifact boundary batch reduced the run-state module and
added a dedicated artifact lifecycle contract; the previous architecture map
no longer described the current dependency shape or module sizes.

**Change:** updated the measured map to source checkpoint `b4159bc`, recorded
84 runtime modules and the new Colab artifact owner, documented the single
MCP artifact chunk policy, and refreshed the current source/CI evidence in
`docs/STATUS.md`.

**Validation:** module counts match `wc -l`; the exact-head CI workflows and
the local 221-test, build, artifact, and migration checks passed for
`b4159bc`. This does not establish an independent security review, hosted
deployment, live Colab acceptance, or merge readiness.

## 2026-11-29 — A1: add a client-neutral conversational quickstart

**Finding:** MCP client setup described authentication and capability
verification, but did not give an owner a single natural-language example for
requesting an owner-selected repository run without handling internal IDs.

**Change:** added copyable execution and read-only prompts to
`sites/gpu-control-sites/MCP_CLIENTS.md`. The execution prompt requires current
capability discovery, a genuinely available free route where possible, no paid
fallback, same-run result/artifact/cleanup verification, and explicit reporting
of missing account or quota decisions. The guide states that registration is
not execution support and that the current release, not source code, determines
whether a route can be used.

**Validation:** `git diff --check` passes. This documentation-only change does
not enable new routes or claim that PR #70 is deployed; the MCP release and
live capability response remain authoritative.
