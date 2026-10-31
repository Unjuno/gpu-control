# Release acceptance matrix

This matrix reports evidence on the current working branch. It does not infer
readiness from mocks, source inspection, or a green test suite alone.

| Axis | Status | Current evidence | Remaining acceptance |
| --- | --- | --- | --- |
| `MCP_CONNECTIVITY` | BLOCKED (runtime and workspace acceptance) | Read-only refresh (2026-10-31 11:12 JST): PRs #51–#59 remain OPEN/DRAFT with nine successful published statuses each and no reviews; #52 and #43 report `REVIEW_REQUIRED`. Production alias points to `main` SHA `24ecb9b` and returns `/healthz`=200, `/readyz`=404, `/mcp`=401, OAuth metadata=200. PR #58 Preview is READY at `561a6c7`, but `/healthz` and `/readyz` redirect to Vercel SSO (302), so candidate readiness is unobserved. No authenticated ChatGPT OAuth or experiment call was exercised. Evidence: [`docs/CHATGPT_ACCEPTANCE.md`](CHATGPT_ACCEPTANCE.md). | Obtain an eligible authenticated ChatGPT workspace and authorized access to a readiness-verified persistent endpoint; complete OAuth, tool discovery, CPU execution, and result retrieval in ChatGPT. |
| `CHATGPT_TOOL_USABILITY` | BLOCKED (deployment/workspace acceptance) | Current dirty Gateway suite passed **513 / 2 skipped** against dedicated PostgreSQL 16 and a digest-pinned CPU image whose OCI labels match immutable HEAD; Core passed **559 / 1 Python 3.11-specific skip**. Local MCP exercised prepare/submit, worker execution, and second-client result/artifact retrieval. Current PR heads remain Draft and do not include this local snapshot; production `/readyz` remains 404. No authenticated ChatGPT run has been accepted. Evidence: [`2026-10-31-current-snapshot-full-suite.md`](acceptance/2026-10-31-current-snapshot-full-suite.md), [`docs/CHATGPT_ACCEPTANCE.md`](CHATGPT_ACCEPTANCE.md). | Obtain authorized deployment and eligible authenticated ChatGPT workspace; run a registered CPU experiment through ChatGPT and retrieve it from a second conversation. |
| `CPU_EXECUTION` | PASS (local lane only) | Current dirty Gateway suite passed **513 / 2 skipped** with dedicated PostgreSQL 16 and the commit-bound CPU image; Core passed **559 / 1 Python 3.11-specific skip**. Real local Docker/MCP integration retrieved the plan-bound result and artifact from a second client and verified the artifact digest. Actual ChatGPT acceptance and production readiness remain separate gates. Evidence: [`2026-10-31-current-snapshot-full-suite.md`](acceptance/2026-10-31-current-snapshot-full-suite.md). | Deploy through an authorized path and complete authenticated ChatGPT CPU/result acceptance, then conduct seven-day observation. |
| `FREE_GPU_EXECUTION` | BLOCKED | No GPU backend has been live-verified with device, quota, additional-cost, cancellation, and cleanup evidence. The current Gateway suite includes one successful synthetic candidate-bound lifecycle with a signed receipt and confirmed test cleanup, but all candidate/device/receipt data are fake. Official RunPod docs schedule REST v1 retirement for 2026-11-15; the separately named v1 adapter is not eligible for future live activation. Current v2 schema review found and fixed a Network Volume create-body mismatch (`mounts.network`); 56 focused offline v2 payload/adapter/policy and legacy-compatibility tests passed, including exact create-response volume/datacenter/cloud validation and compensating termination; current focused v2/selection/capability modules passed 120 tests; the current primary root/core suite passed 559 tests with the Python 3.11-specific reproducer skipped under Python 3.12. These are offline checks only. Policy metadata now distinguishes the documented v2 surface from unverified provider behavior; no live compatibility, result, or cleanup acceptance exists. Evidence: [`2026-10-31-p4-fake-candidate-lifecycle.md`](acceptance/2026-10-31-p4-fake-candidate-lifecycle.md), [`2026-10-28-runpod-api-v2-revalidation.md`](acceptance/2026-10-28-runpod-api-v2-revalidation.md). | Validate a current provider path under separate bounded authorization, then prove result transport, resource reconciliation, cancellation, cleanup, and bounded cost; preserve `FREE_FIRST` gates. |
| `PAID_GPU_EXECUTION` | BLOCKED | Paid mode remains parked; no current exact human authorization or live provider execution. Schema v12 Store primitives persist and reload a verifier-approved envelope against the exact run/owner/plan/browser-approval tuple, checking approval/envelope expiry and cancellation state. The reader remains unused; a cancel arriving after the read can still race a later provider call. No issuer, Worker pre-intent/pre-create verification, revocation source, or provider path is wired. Codex Security scan `95ba8a1a-f608-4f28-9b71-aaf5f97f5e9f` found zero candidates on snapshot digest `codex-security-snapshot/v1:sha256:67e0f386a5b1c494a3e37f30293c98f1b7b2253643f126ed914c398ea948430a`; subsequent state/cancel-flag delta received focused independent review. Evidence and limits: [`2026-10-31-p5-paid-authorization-persistence-foundation.md`](acceptance/2026-10-31-p5-paid-authorization-persistence-foundation.md), [`2026-10-31-current-worktree-security-review.md`](acceptance/2026-10-31-current-worktree-security-review.md). | Complete the trusted issuer, atomically integrate durable authorization and cancellation handling at the Worker/provider boundaries, obtain independent review of the final code, then separately authorize a bounded canary before any spend. |
| `RECOVERY` | PASS (local CPU lane only) | The current dirty Gateway suite passed **513 / 2 skipped**. It includes worker death after Docker starts a real container but before handle persistence; a fresh supervisor adopts that same labelled container, retrieves the exact artifact, cleans up, and releases the slot; PostgreSQL spawned-process lease contention and PostgreSQL outage recovery. The suite used a disposable loopback PostgreSQL 16 container and commit-bound local CPU image, then removed the DB container and volume. These are local checks, not target-host recovery acceptance. Evidence: [`2026-10-31-current-snapshot-full-suite.md`](acceptance/2026-10-31-current-snapshot-full-suite.md), [`2026-10-31-postgres-container-crash-recovery.md`](acceptance/2026-10-31-postgres-container-crash-recovery.md), [`2026-10-30-dirty-source-paired-restore.md`](acceptance/2026-10-30-dirty-source-paired-restore.md), [`2026-10-31-p1-dcr-persistence-schema-v9.md`](acceptance/2026-10-31-p1-dcr-persistence-schema-v9.md). | Exercise the selected deployed host and provider; verify the full crash matrix and no duplicate resources there. Production backup retention, target-host recovery and measured RPO/RTO remain open. |
| `CANCELLATION` | PASS (local CPU lane only) | Existing CPU container was cancelled and removed by the recovery supervisor while execution-worker ticks were stopped. | Repeat against the deployment host and, for GPU, its real provider resource. |
| `RESULT_RETRIEVAL` | PASS (local CPU/MCP only) | The commit-bound CPU image ran through authenticated local MCP; a second client retrieved the exact plan-bound result and artifact, including SHA-256 verification. Worker/container and PostgreSQL outage recovery also retained and retrieved results locally. No deployed API or real ChatGPT conversation was used. | Verify the actual run and exact plan/source binding from a second ChatGPT conversation; test deployed persistent volume and quota/alert policy. See `docs/acceptance/2026-10-28-artifact-storage.md` and `docs/acceptance/2026-10-28-paired-artifact-restore.md`. |
| `SECURITY` | REVIEWED (static source snapshot plus focused follow-up; GitHub approval pending) | Codex Security diff scan `95ba8a1a-f608-4f28-9b71-aaf5f97f5e9f` covered all 18 changed source/policy items at base/head `a794438f42bd7246f463eaaa40d963af0aae9d13`, digest `codex-security-snapshot/v1:sha256:67e0f386a5b1c494a3e37f30293c98f1b7b2253643f126ed914c398ea948430a`: zero candidates, complete coverage, no deferred rows. A focused independent review checked the subsequent Store state/cancel-flag delta. It confirmed already-committed cancellation is rejected and identified the remaining cancel-after-read/provider-call race; Worker is not wired to this reader. No external GitHub/deployment checks were made. Evidence: [`2026-10-31-current-worktree-security-review.md`](acceptance/2026-10-31-current-worktree-security-review.md), [`2026-10-31-p5-paid-authorization-persistence-foundation.md`](acceptance/2026-10-31-p5-paid-authorization-persistence-foundation.md). | Close the cancel-after-read race in Worker/provider integration; obtain independent GitHub review; verify deployed OAuth/owner boundaries and target-host permissions; perform live provider compatibility and operational checks. |

### Latest local OAuth/migration evidence — 2026-10-30 17:44 UTC

The current worktree adds consent-bound persistent DCR clients and schema v9.
The full Gateway suite passed **426, 7 skipped** on PostgreSQL 16; CPU/Docker
smoke integration was disabled. The isolated PostgreSQL v8-to-v9 client
preservation test and 17 focused OAuth/migration tests passed. This is newer
than the 550-test source-matched CPU integration evidence above, but exercises
a different scope. The new OAuth/migration source has not yet received the
independent Security Review recorded in the matrix; that review found no
actionable findings. Details:
[`docs/acceptance/2026-10-31-p1-dcr-persistence-schema-v9.md`](acceptance/2026-10-31-p1-dcr-persistence-schema-v9.md).

## Operational gates

- P2 recovery work remains in progress: durable owner-scoped artifact storage
  and local CPU report retrieval are implemented and locally exercised;
  provider-independent recovery review, deployed storage/quota controls, and
  ChatGPT retrieval acceptance remain incomplete. Unsupported artifacts must
  not be represented as retrievable.
- Readiness contract follow-up: the current PR source includes
  artifact-storage readiness when a local CPU workload is enabled; Gateway
  CI exercises the readiness contract and the full PostgreSQL + local CPU
  suite. The production alias still returns `/readyz`=404 because it serves
  an older source revision. The current PR preview deploys from the reviewed
  branch SHA but is SSO protected, so its runtime readiness response has not
  been observed. This is a deployment and acceptance gap; it does not
  establish a source defect.
- P3 remains pending: systemd units are templates only; there is no selected
  deployed Gateway/worker host, real ChatGPT connection, seven-day observation,
  or timed production restore drill. The local synthetic paired restore in
  `docs/acceptance/2026-10-28-paired-artifact-restore.md` does not establish
  production backup controls, owner/OAuth parity, or worker reconciliation.
  The atomic backup generation drill in
  `docs/acceptance/2026-10-28-atomic-backup-generation.md` is also local-only;
  encrypted off-host retention, second-operator restore, and timed production
  recovery are still required.
  The existing Neon production branch has no schema-version table and has not
  been migrated; only zero aggregate run/active-slot counts were queried. Review
  the migration and production backup/restore plan before any database change.
  Current P3 templates limit artifact writes under `ProtectSystem=strict` to
  API/worker/supervisor, isolate API-only OAuth values in `api.env`, omit DB
  credentials from capacity checks, and optionally pass `worker-secrets.env`
  only to worker/supervisor. After this wiring change, the deploy-unit module
  passed 14 tests. A fresh network-isolated Debian 12 UID/GID mode-bit probe
  confirmed the capacity identity can read a mode-0640 blob but cannot create
  or unlink in `.gpu-control-probes`; API can perform its probe and worker can
  access it by owner UID. The expected 2750/3770/640 ownership layout also
  denied API artifact-root/blob writes and migration blob reads. The six
  templates present at that verification point, including the journald identifier
  and output directives, passed `systemd-analyze verify` in a disposable
  Debian 12 container using the guarded CI helper. No service was started and
  target-host behavior remains unverified; this does not change the P3 release
  status. The current local worktree also defines capacity alert/clear JSON
  events, requires a reason for alerts, pins their schema, selects them through journald identifier
  `gpu-control-capacity`, and documents a journal consumer command. The
  durable outbox and sink-agnostic delivery pump have fake-sender coverage;
  `gateway/tests/test_capacity_event_state.py` passed 40 tests on 2026-10-30.
  No concrete notification sender/sink is selected, and no real transport or
  target-host delivery test has run. A host-independent
  [`capacity alert bridge contract`](specs/capacity-alert-bridge-contract.md)
  now defines allowlisting, schema validation, event ordering/deduplication,
  redaction, identity separation, bounded retries and target-host acceptance.
  No sink is selected: host/provider, region, cost ceiling, origin/egress route,
  recipient, credential store and alert SLO remain open. A source audit found
  that the capacity timer runs only `statvfs` and does not call the API's
  write-probe function. Removed the unnecessary `gpu-control-artifact-probes`
  membership from capacity, worker and supervisor; API alone needs that group,
  while worker owns the probe directory. A fresh disposable Linux UID/GID mode-
  bit matrix confirmed API probe/read, capacity blob-read/probe-write-denial,
  worker owner access, migration read denial, and API root/blob write denial.
  Focused deploy-unit tests pass 14/14. The current
  prior run passed the complete ordinary local suites (Gateway 289 passed / 9
  skipped, root 532 passed / 1 skipped). The newer current-worktree full
  PostgreSQL + Docker Gateway run passed 296 tests with 2 optional skips, and
  the root suite passed 532 with 1 skip. The then-current six unit/timer
  templates also passed the guarded CI helper in a uniquely named
  `--rm --network none` Debian 12/systemd 252.39 container using the existing
  local pinned image and inert placeholders; no service was started and the
  container was removed. After the manual capacity bridge was added, all seven
  current templates passed the same helper; see
  `docs/acceptance/2026-10-28-systemd-uid-boundary.md`.
  Updated systemd sandbox runtime behavior and target-host alert delivery
  remain unverified. The host-independent alert bridge contract is documented
  at `docs/specs/capacity-alert-bridge-contract.md`.
- Paid and GPU paths stay parked until their separate evidence and authorization
  gates are satisfied. Local CPU evidence does not satisfy either gate.

Update this table only when new evidence is produced. Link acceptance artifacts
and state the scope of each PASS.

Latest working-tree security evidence (2026-10-28): Codex Security scanned the
snapshot digest
`codex-security-snapshot/v1:sha256:7e0e8d8cd28422336d2f13fd6520868dc91ef5e9fac2d9a3e85e8004ec272716`
covering 36 changed source-like files across eight surfaces and reported zero
candidate findings. This does not constitute GitHub human review, deployed
security validation, or ChatGPT acceptance. PR #51 was last observed
OPEN/DRAFT with no reviews; target workspace access remains unverified. Report:
`/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/f054aebe96460fe033dde8d91d7e3bbab0255655_20261028T081301Z_gcgufipi/report.md`.

Latest full-worktree security diff review (2026-10-28): Codex Security completed
scan `f9f8d84d-05bd-40d6-a241-d2856e841475` against base/head
`f054aebe96460fe033dde8d91d7e3bbab0255655`, snapshot digest
`codex-security-snapshot/v1:sha256:d706e1d36e6e99c8408c5bd474fca42dbb7b9236d27f1304453c5408d02f82f7`.
All 37 changed source inventory rows were closed; 0 candidates/findings, complete
coverage. Scope is source/config/workflow review plus directly relevant deploy
templates. Documentation and tests were excluded; no tests, application runtime,
deployment, credentials, live provider calls, or paid resources were used. This
does not replace GitHub review or target-host/ChatGPT/provider acceptance.
Report: `/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/f054aebe96460fe033dde8d91d7e3bbab0255655_20261028T090359Z_6ikse4y1/report.md`.

Current-worktree slice revalidation (2026-10-28): P1 focused OAuth/auth modules
passed 37/37 and the PostgreSQL 16 concurrent refresh-token consumption
regression passed 1/1 using the declared psycopg 3 dialect. P3 artifact storage,
backup generation, capacity event state, permission migration, and deployment
unit modules passed 91/91; all seven systemd templates passed the guarded helper
in the cached Debian 12/systemd 252.39 container with network disabled and the
repository mounted read-only. Details and the initial harness invocation
corrections are in the P1/P3 acceptance artifacts and `docs/IMPLEMENTATION_PROGRESS.md`.
These are local checks; they do not close ChatGPT, selected-host, notification,
or production acceptance.

Earlier core/P4 regression on 2026-10-28: root/core suite passed **549/1
skip**. This was superseded by the later 550-test rerun recorded in
`docs/IMPLEMENTATION_PROGRESS.md`; the skip is Python 3.11-specific. This is offline contract/policy evidence only; no live provider,
GPU, quota, cost, or paid execution was exercised. P4/P5 release gates remain
open.

Full current-worktree Gateway integration rerun on 2026-10-28: **403 passed,
2 optional Torch/Modal skips**, using PostgreSQL 16 and the digest-pinned CPU
container on loopback-only networking. This includes local MCP/lifecycle,
artifact retrieval, PostgreSQL refresh concurrency, and outage recovery; it
remains local integration evidence. See
[`2026-10-28-local-integration-revalidation.md`](acceptance/2026-10-28-local-integration-revalidation.md).

### Independent local slice reviews (2026-10-28)

Three completed reviewer-agent reports were retrieved for the dirty worktree
based on `f054aebe96460fe033dde8d91d7e3bbab0255655`. P1 Gateway source scope
(`app.py`, `admission.py`, `artifacts.py`, `backends.py`,
`candidate_receipts.py`, `config.py`, `contracts.py`, `experiment_api.py`,
`local_oauth.py`, `registry.py`, `service.py`, `store.py`, and `worker.py`):
no findings; tests and documentation were outside this agent's scope. P3
capacity-event, artifact backup/permission migration, CI verification, and
modified systemd unit scope: no findings. P4 provider evidence/selection,
RunPod inventory and policy, and core capability/workload/pricing adapter
scope: no findings. No changes were made by these reviews. These reports are
local source-review evidence; they are not GitHub PR reviews, do not cover
ChatGPT or target-host runtime behavior, and do not replace the PR #51 review
required by the newly configured `main` protection. PR #51 remains
OPEN/DRAFT/REVIEW_REQUIRED with no submitted GitHub review.

## Current-session recheck — 2026-10-31 19:32 UTC

Fresh `gh pr view 51` reports OPEN/DRAFT, `REVIEW_REQUIRED`, no reviews, and
seven required Actions contexts plus Vercel successful on pushed head
`aa681f4062dac6b73bcf380a38a4258b96a47e1d` only. The current checkout is two
commits ahead and contains uncommitted changes. A new ChatGPT web tab displays
Log in / Sign up; the desktop app is unavailable to this CUA session and Chrome
is not an available browser surface. Thus actual ChatGPT workspace access and
all MCP/CPU acceptance steps remain NOT RUN. A fresh GitHub branch-protection
API read was rate-limited; the previous recorded configuration is not refreshed
by this turn. No GitHub or hosting state was changed.

## Current-session gate refresh — 2026-10-31 08:44 JST

Fresh read-only GitHub reads show PR #51 OPEN/DRAFT at `e3ffcef` based on
`51b88f6`, PR #58 OPEN/DRAFT at `561a6c7` based on `e3ffcef`, and PR #59
OPEN/DRAFT at `76c2a1a` based on `51b88f6`. All nine published status contexts
per PR succeeded; each has zero submitted reviews. The local checkout is at
`a794438` with uncommitted changes, which are outside those published checks.
Fresh public alias requests returned `/healthz`=200, `/readyz`=404, and
unauthenticated `/mcp`=401. ChatGPT was last observed logged out at 08:35 JST.
Repository mode remains parked; no external write or deployment occurred.

## Current continuation evidence — 2026-10-31 11:02 JST

The cancellation-before-dispatch delta passed the full local Gateway suite and
the root CLI/Core suite; the focused lease and Worker recovery suites passed
23/23. The two lease migration assertions that had hard-coded schema v11 now
assert the current v12 schema constant. Independent review confirmed the
pre-dispatch checks and documented the unavoidable race if cancellation
arrives while the external provider create call is already in flight. Current
RunPod paid/credit execution remains refused.

Read-only GitHub verification confirmed one required approval, strict required
checks and stale-review dismissal on `main`. PRs #51–#59 and #43 remain
OPEN/DRAFT; #52 and #43 report `REVIEW_REQUIRED`, others have no review
decision. Production probes returned `/healthz`=200, `/readyz`=404,
unauthenticated `/mcp`=401, and OAuth metadata=200. ChatGPT web is logged out.
Thus runtime readiness and authenticated ChatGPT acceptance remain NOT RUN;
the dirty local candidate is not covered by remote PR checks. No GitHub write,
deployment, grant, provider call, or policy activation occurred. Keep mode
`parked`. Details:
[`2026-10-31-cancel-dispatch-boundary.md`](acceptance/2026-10-31-cancel-dispatch-boundary.md).
Read-only `gh pr checks` also returned all seven required Actions checks plus
Vercel and Vercel Preview Comments as successful on remote heads #51, #52,
#58, and #59. These results do not cover local uncommitted changes.

At 11:07 JST, a fresh ChatGPT web tab showed Log in/Sign up. OpenAI's current
custom MCP/auth guidance still supports DCR and recommends CIMD when advertised
and selected. The Gateway advertises DCR, `none`, resource binding, and PKCE
S256 without CIMD; local OAuth/auth tests passed 39/39. This is protocol
regression evidence, not ChatGPT OAuth acceptance. Record the exact test gate
and limits in `docs/CHATGPT_ACCEPTANCE.md` and `docs/CHATGPT_SETUP.md`.
