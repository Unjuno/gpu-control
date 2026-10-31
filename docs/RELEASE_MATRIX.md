# Release acceptance matrix

This matrix reports evidence on the current working branch. It does not infer
readiness from mocks, source inspection, or a green test suite alone.

| Axis | Status | Current evidence | Remaining acceptance |
| --- | --- | --- | --- |
| `MCP_CONNECTIVITY` | BLOCKED (runtime and workspace acceptance) | Fresh production-alias GETs (2026-10-30): `/healthz`=200, `/readyz`=404, `/mcp`=401. Vercel's read-only deployment record identifies PR preview `dpl_CWs7WJ4hKt2thQtmMZeVabiKV84f` as READY from SHA `144cccebca3351b42cd9261375b012784f3b8715`; project SSO protection is enabled for preview deployments. An unauthenticated preview request redirects to Vercel login, so deployed `/readyz` is still unobserved. PR #51 is OPEN/DRAFT/REVIEW_REQUIRED and all current checks pass; no ChatGPT OAuth grant, tool scan, or tool call has completed. Evidence: [`docs/CHATGPT_ACCEPTANCE.md`](CHATGPT_ACCEPTANCE.md). | Complete PR review, obtain authorized preview access, confirm readiness, configure a persistent deployment, then complete OAuth and tool discovery/calls in the intended ChatGPT workspace. |
| `CHATGPT_TOOL_USABILITY` | BLOCKED (deployment/workspace acceptance) | Canonical experiment tools implement prepare/submit/status/result/artifact/cancel/list contracts. The latest PR CI Gateway job passed **424 tests / 1 optional skip** with PostgreSQL and the digest-pinned local CPU container; root CI passed Python 3.11, 3.12, and 3.13. Coverage includes MCP output, owner isolation, Docker CPU execution, artifact retrieval, v1-to-v8 migration, and PostgreSQL outage recovery. The PR preview is deployed but SSO protected; no intended ChatGPT workspace has completed discovery or a tool call. | Complete PR review and eligible deployment/workspace setup, then run a registered CPU experiment through ChatGPT and retrieve it from a second conversation; record the evidence in [`docs/CHATGPT_ACCEPTANCE.md`](CHATGPT_ACCEPTANCE.md). |
| `CPU_EXECUTION` | PASS (local lane only) | Current PR CI Gateway integration passed **424 tests / 1 optional skip** with PostgreSQL and the digest-pinned CPU container; it includes local MCP/result/artifact retrieval, concurrency, outage recovery, authenticated Docker CPU execution, cross-client retrieval, and v1-to-v8 migrations. Root CI passed **550 tests / 1 skip**. These are CI/local execution results, not ChatGPT or production-host acceptance. Evidence: [`2026-10-28-local-integration-revalidation.md`](acceptance/2026-10-28-local-integration-revalidation.md) and latest CI for PR #51. | Use the reviewed persistent deployment host and complete real ChatGPT acceptance and seven-day observation. |
| `FREE_GPU_EXECUTION` | BLOCKED | No GPU backend has been live-verified with device, quota, additional-cost, cancellation, and cleanup evidence. Official RunPod docs schedule REST v1 retirement for 2026-11-15; the separately named v1 adapter is not eligible for future live activation. Current v2 schema review found and fixed a Network Volume create-body mismatch (`mounts.network`); 56 focused offline v2 payload/adapter/policy and legacy-compatibility tests passed, including exact create-response volume/datacenter/cloud validation and compensating termination; current focused v2/selection/capability modules passed 120 tests; the full root/core suite passed 550 tests with the Python 3.11-specific reproducer skipped under Python 3.12. These are offline checks only. Policy metadata now distinguishes the documented v2 surface from unverified provider behavior; no live compatibility, result, or cleanup acceptance exists. Evidence: [`2026-10-28-runpod-api-v2-revalidation.md`](acceptance/2026-10-28-runpod-api-v2-revalidation.md). | Validate the v2 path under separate bounded authorization, then prove result transport, resource reconciliation, cancellation, cleanup, and bounded cost; preserve `FREE_FIRST` gates. |
| `PAID_GPU_EXECUTION` | BLOCKED | Paid mode remains parked; no current exact human authorization or live provider execution. | Complete P5 controls and obtain separate explicit authorization for a bounded canary before any spend. |
| `RECOVERY` | PASS (local CPU lane only) | The latest PR CI Gateway integration passed **424 tests / 1 optional skip** using PostgreSQL and a digest-pinned CPU container, including worker crash recovery, artifact retrieval, and PostgreSQL outage-after-capture recovery. This is CI-local synthetic evidence, not target-host recovery acceptance. Detailed local drill evidence: [`2026-10-28-local-integration-revalidation.md`](acceptance/2026-10-28-local-integration-revalidation.md). | Exercise the selected deployed host and provider; verify the full crash matrix and no duplicate resources there. Production backup retention, target-host recovery and measured RPO/RTO remain open. |
| `CANCELLATION` | PASS (local CPU lane only) | Existing CPU container was cancelled and removed by the recovery supervisor while execution-worker ticks were stopped. | Repeat against the deployment host and, for GPU, its real provider resource. |
| `RESULT_RETRIEVAL` | UNCERTAIN | A real digest-pinned local CPU smoke run emits a validated JSON report; worker recovery persists it to owner-scoped storage and retrieves its exact bytes. PostgreSQL outage recovery preserves the run; artifact chunk API/storage tests and local shared-volume checks pass. A separate synthetic paired PostgreSQL 16 dump/artifact archive restore retrieved the restored bytes through the owner-scoped application path and rejected an unrelated owner. No deployed API or real ChatGPT conversation was used. | Verify an actual run and exact plan/source binding from a second ChatGPT conversation, including returned artifact digest and bytes; test a deployed persistent volume and set a quota/alert policy. See `docs/acceptance/2026-10-28-artifact-storage.md` and `docs/acceptance/2026-10-28-paired-artifact-restore.md`. |
| `SECURITY` | REVIEWED LOCALLY; GitHub review pending | The user-selected read-only Security Review of the full 117-path uncommitted change set reported no actionable findings; the OAuth slice was also reviewed separately with no actionable findings. The code changes were then committed as `4a05977`; `58f19ed` adds documentation only. Earlier Codex Security scans at `f054aebe` remain narrower historical evidence. Local review does not constitute GitHub PR review or verify deployed configuration, target-host permissions, ChatGPT acceptance, or provider accounts. | Obtain the required independent GitHub review, then verify deployed OAuth/owner boundaries and target-host permissions; perform live provider compatibility and operational security checks. |

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
  `gpu-control-capacity`, and documents a journal consumer command. No
  notification sink or delivery test exists yet. A host-independent
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
