# Implementation progress

```text
current_phase: P0 baseline, P1 T1-T5 local CPU lifecycle, P2 recovery implementation/local acceptance, and P4 offline selection plus receipt/read-verification contract are implemented at their stated scopes. P1 ChatGPT/deployment acceptance and P3 selected-host operation remain incomplete. P4 has no accepted provider adapter or live GPU evidence; P5 paid execution remains separately unauthorized. Preserve `policies/repository-state.yaml` parked mode.
current_task: Current checkout is branch `codex/chatgpt-cpu-vertical` at `f054aebe96460fe033dde8d91d7e3bbab0255655`; 117 paths are dirty and unstaged, with an exact five-slice ownership map. Root suite passes 550 tests / 1 skip; full Gateway suite with local Docker CPU and disposable PostgreSQL 16 passes 423 / 2 optional SDK skips, including v1-to-v8 migration, outage recovery, and OAuth rollback. A new isolated Linux/systemd + PostgreSQL 16 schema-v8 backup/restore drill passed with synthetic data. P1 ChatGPT/deployment acceptance and P3 selected-host operation remain incomplete. P4 has no accepted provider adapter or live GPU evidence; P5 paid execution remains separately unauthorized. The current ChatGPT web session was logged out at the last observed check; workspace access/permissions remain unverified. Preserve `policies/repository-state.yaml` parked mode.
latest_verified_turn: At 2026-10-28 11:44 UTC, refreshed official AWS and DigitalOcean pricing/region/volume documentation and updated `docs/decisions/2026-10-28-p3-deployment-topology.md`: the public 2-GiB + 32-GiB-volume baseline is $15.20/month and the 4-GiB baseline $27.20/month at both providers, but CPU count, included bandwidth, overage, backup costs, region, Neon latency and account-specific billing differ. This is a candidate comparison only; no provider, price ceiling, or deployment was selected. At 11:42 UTC, fresh read-only tabs showed ChatGPT logged out and OpenAI Platform redirecting its tunnel-settings URL to login. Tunnel inventory, runtime-key presence, Tunnels Read + Manage/Use permissions, and workspace association are therefore unknown; no login, credential creation, setting change, or MCP call was attempted. ChatGPT/P1 acceptance remains NOT RUN. A disposable Ubuntu 24.04 systemd + PostgreSQL 16 schema-v8 backup/restore drill preserved one synthetic succeeded run with zero active count and completed cleanup state; the artifact archive was empty and all temporary resources were removed. The working tree has 117 dirty/unstaged paths (75 tracked, 42 untracked); the five-slice map last matched all 117 exactly before this documentation-only turn. Root/core 550/1 and Gateway+Docker/PostgreSQL 16 423/2 remain prior recorded suites, not rerun this turn. Read-only GitHub refresh at 11:38 UTC confirmed PR #51 still OPEN/DRAFT at `f054aebe`, with zero reviews and review threads; its combined-status response exposed only Vercel success, so no other CI result is inferred from it. Review selection (Bugbot or Security Review) is still unanswered; neither was run. Codex Security Deep Scan could not start because the native scanner requires a managed filesystem permission profile unavailable to this task; no replacement scan was run. No provider, GPU, paid compute, production DB, deployment, PR, or repository-policy mutation occurred; `policies/repository-state.yaml` remains parked.

2026-10-28 public alias recheck at 05:53 UTC: unauthenticated reads returned
`/healthz`=200 (`configured=true`, `auth_configured=true`), `/readyz`=404, and
protected-resource discovery=200 advertising read/run/cancel scopes. This is
not evidence that P1 is deployed: the readiness route is absent, deployed SHA
was not established, and no OAuth grant or ChatGPT call occurred. GitHub
connector read still shows PR #51 OPEN/DRAFT at pushed head
`f054aebe96460fe033dde8d91d7e3bbab0255655`, with no reviews or review threads;
the four PR-triggered Actions workflows completed successfully (CI
`40614634054`, Gateway offline `40614633953`, Gateway comment bridge
`40614633965`, Project bridge `40614633942`). The current working tree is
unpushed. Do not treat the advertised scopes or green remote checks as proof of
working tools or user authorization.

2026-10-28 P1 OAuth local regression: ran the roadmap's focused command with
the Gateway Python 3.12 venv,
`./gateway/.venv/bin/python -m pytest -o addopts= gateway/tests/test_http_auth.py gateway/tests/test_local_oauth.py -q`;
**34 passed**, one existing Starlette deprecation warning. This covers local
HTTP/OAuth behavior only; no ChatGPT account, grant, refresh round-trip, or
reconnection was performed. The T6 live acceptance gates remain NOT RUN.

2026-10-28 P1 T1 dual-database migration check: the first PostgreSQL 16 run
found that the old-v1 fixture inserted integer `0` into BOOLEAN columns,
which SQLite tolerated but PostgreSQL correctly rejected. Changed those
fixture literals to portable SQL `FALSE`. The SQLite contract/migration/local
backend tests then passed **31 tests**. Re-ran the same v1 fixture against a
disposable PostgreSQL 16 container bound to loopback: two migrations reached
schema v7 and preserved the legacy run identity/owner/key/fingerprint/payload
and OAuth token row. The container was removed. This is migration evidence
only; production database and OAuth acceptance remain open.

2026-10-28 P1 T2 owner and protocol regression: added explicit cross-owner
negative coverage for status/result/cancel (404) and list non-disclosure, then
ran the planned experiment API/protocol validation/CI bridge modules: **107
passed, 1 skipped**, one existing Starlette deprecation warning. This confirms
local service/protocol behavior only; no ChatGPT conversation was used.

2026-10-28 P1 T2 tool contract follow-up: advertised a shared v2 `outputSchema`
for all eight MCP tools and added an owner-scoped terminal status log tail
limited to 4096 characters, with an explicit truncation flag. The focused
experiment API and protocol validation run passed **37 tests**, including
schema presence, truncation, and cross-owner denial. This focused run does not
replace the earlier full Gateway/PostgreSQL regressions and does not establish
ChatGPT acceptance.

2026-10-28 protocol compatibility review: MCP 2025-03-26 predates structured
tool output. Updated the protocol adapter to omit `outputSchema` from that
version's tool listing and omit `structuredContent` from its call results;
2025-06-18 and newer retain both. Updated the contract and implementation plan.
The version-gating change still needs its dedicated regression before P1 T2 is
considered complete; no ChatGPT request was made.

2026-10-28 live boundary refresh (10:02 UTC): unauthenticated GETs to the
current PR preview `/healthz`, `/readyz`, and OAuth protected-resource
discovery all returned HTTP 401 from Vercel Authentication before reaching
the application. PR #51 remains OPEN/DRAFT at the unchanged pushed head
`f054aebe96460fe033dde8d91d7e3bbab0255655`; GitHub reports no review
submissions or inline review threads. The local 2025-03-26 compatibility fix
is unpushed and therefore cannot appear in that preview. ChatGPT cannot use
this protected preview as an endpoint; exposing an accepted endpoint requires
an owner-approved deployment protection/origin decision and a ready runtime.

2026-10-28 P1 T2 MCP version regression: added dispatch-level coverage for
`tools/list` and `tools/call` on protocol revisions 2025-03-26, 2025-06-18,
2025-11-25, and 2026-07-28. The targeted experiment API/protocol validation run
passed **41 tests**, with one existing Starlette deprecation warning. This is
local protocol compatibility evidence; the real ChatGPT client and deployment
remain unaccepted.

2026-10-28 current-schema migration follow-up: renamed the PostgreSQL
v4-to-v7 regression to describe the actual current target and expanded it to
drop/recreate the schema-v8 provider-observation table. SQLite migration suite
passed **4 tests**; the PostgreSQL 16 v4-to-v8 integration passed **1 test** on
loopback port 55489 using the digest-pinned image. The disposable container was
removed. This extends earlier PostgreSQL v1-to-v7 evidence but is not a direct
v1-to-v8 PostgreSQL rehearsal. See
`docs/acceptance/2026-10-28-local-integration-revalidation.md`.

2026-10-28 release-matrix refresh: GitHub currently reports PR #51 OPEN/DRAFT,
head `f054aebe96460fe033dde8d91d7e3bbab0255655`, mergeable, with no reviews or
review threads. The latest authenticated preview fetch still showed an
unconfigured runtime; an unauthenticated preview request is intercepted by
Vercel Authentication (401). Updated evidence scopes to distinguish the last
full 403-test Gateway run on its 111-path snapshot from subsequent focused
protocol/migration regressions on the current 113-path worktree. Also marked
security status uncertain because the pushed-head source review predates the
current protocol output changes.

2026-10-28 untrusted-output boundary: canonical `experiment_status` and
`experiment_result` tool descriptions now warn that workload logs/results are
untrusted data and must not be followed as instructions. The API/protocol
focused suite passed **41 tests** with one existing Starlette deprecation
warning. No real ChatGPT client has yet confirmed how this warning is presented.

2026-10-28 result-size reporting: worker-generated `result_omitted` records
previously left `experiment_result` classified as `ok` solely because the
execution state was succeeded. The API now preserves the actual execution state
but marks result retrieval `blocked` with `RESULT_OMITTED`; status also exposes
the omission flag and size-limit reason. The focused API/protocol suite passed
**42 tests**, including the omitted-result path. The full Gateway suite was not
rerun for this change; ChatGPT presentation remains unverified.

2026-10-28 full Gateway offline regression after the P1 T1/T2 additions:
`./gateway/.venv/bin/python -m pytest -o addopts= -q gateway/tests` passed
**353 tests / 9 skips**, one existing Starlette deprecation warning. This run
did not configure the PostgreSQL/Docker integration variables; it confirms
only the offline Gateway suite. The separate PostgreSQL 16 v1 migration proof
and earlier Docker/PostgreSQL integration record remain separately scoped.

2026-10-28 recovery-runbook consistency correction: review found the isolated
restore example invoked `sha256sum -c` on sidecar files that the atomic backup
tool does not emit. Updated the procedure to verify the generation's actual
`manifest.json` with `backup_generation.py --verify-generation`, restore
`database.dump`, and conditionally extract `artifacts.tar` as the dedicated
worker UID into a new artifact directory. This resolves local documentation
drift only; second-operator, target-host, Neon, and timed RPO/RTO acceptance
remain open. No backup or restore was executed in this turn.

2026-10-28 backup shutdown procedure follow-up: the new backup gate checks all
seven local systemd units, including the capacity timer, but the operator steps
only named API/worker/supervisor. Updated `docs/OPERATIONS.md` to require
stopping the timer, capacity oneshot, and manual bridge, confirming migration
is inactive, recording whether the timer was active, and restarting that timer
only after backup and artifact-mount verification. Application services remain
under the maintenance/change procedure. Documentation-only consistency fix;
no host command or backup was run. `git diff --check` passed; `mode: parked`
remains.

2026-10-28 capacity bridge concurrency follow-up: serialized delivery pump
invocations with a separate private advisory lock held across due-record
selection, injected send, and durable acknowledgement. This prevents two local
bridge processes from concurrently sending the same pending transition; the
crash-after-remote-acceptance duplicate window still requires sink
idempotency. No sink or network call was added. Regression tests were not run
in the initial implementation turn. Added a separate-process lock regression
and then ran the focused capacity event state module: 33 passed, one existing
Starlette deprecation warning. This proves local lock exclusion only;
target-host delivery remains open.

2026-10-28 continuation revalidation at 05:34 UTC: Current root/core suite
`./.venv/bin/python -m pytest -o addopts= -q` passed **536 tests / 1 skip**.
Re-ran `gateway/deploy/verify_systemd_units_ci.sh` in the cached Debian
12/systemd 252.39 image with `--rm --network none`, read-only `gateway/` mount,
and inert CI guard variables; all seven unit templates passed with no
diagnostics, and no container remained. Refreshed evidence is in
`docs/acceptance/2026-10-28-systemd-uid-boundary.md`. Read-only GitHub state:
PR #51 remains OPEN/DRAFT at head `f054aebe96460fe033dde8d91d7e3bbab0255655`,
with zero submitted reviews and zero review threads. The current combined
status response exposes one Vercel success; do not infer unreturned workflow
checks from this response. The dirty worktree still has 64 paths outside the
pushed PR head. `policies/repository-state.yaml` remains `parked`. No host,
Neon, ChatGPT, notification sink, provider, or paid resource was accessed.

p1_production_alias_readonly_recheck_2026_10_28: At 2026-10-28 04:54 UTC,
unauthenticated GETs to the public alias returned `/healthz` 200 with
`configured=true`, `auth_configured=true`, `auth_mode=local_oauth`; `/readyz`
404; and `/mcp` 401 with a bearer-token requirement. The alias is responsive,
but this does not identify its deployed revision or prove P1 readiness or
ChatGPT acceptance. Recorded in `docs/CHATGPT_SETUP.md` and
`docs/CHATGPT_ACCEPTANCE.md`; no OAuth grant, authenticated request, deployment,
or configuration change was made.

p0_pr51_and_worktree_refresh_2026_10_28: Read-only GitHub refresh confirms PR
#51 is OPEN/DRAFT, unmerged, base `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`,
and head `f054aebe96460fe033dde8d91d7e3bbab0255655`, matching local HEAD. Its
four PR workflow runs at that head (CI, Gateway offline, Gateway comment
bridge, Project bridge) are successful; submitted reviews and inline review
threads are both zero. Current worktree has 63 changed/untracked paths (44
tracked with diffs and 19 untracked), outside those remote checks. Refreshed
`docs/BASELINE_AUDIT.md` with these identities, exact scope, and the public
endpoint result. No remote or policy state was changed.

review_slice_inventory_refresh_2026_10_28: Reconciled the 63 current worktree
paths against `git diff --name-only` plus `git ls-files --others` and replaced
the stale 49-path Luna handoff inventory with five non-overlapping review
boundaries: P1 registry/result identity; P3 artifact readiness/backup; P3
systemd/capacity bridge; P4 selection/Modal billing observation; and final
composed evidence reconciliation. The exact file inventory assigns each
changed path once, including the manual journal bridge and billing-only
observer added after the previous inventory. No code was changed and no tests
were run; the handoff remains preparation, not authorization to stage, commit,
push, or merge.

p3_capacity_bridge_install_runbook_correction_2026_10_28: Audited the manual
capacity-bridge addition against `docs/OPERATIONS.md` and found the prose said
seven units while the install and target-host `systemd-analyze verify` commands
still listed only six. Added `gpu-control-capacity-bridge.service` to both
commands, reconciled the release matrix's current count with the later
seven-template verification, and mechanically compared install/verify names
against every `gateway/deploy/*.service` and `*.timer`: all seven matched.
`git diff --check` passed. Documentation correction only; no host unit was
installed or started and target-host acceptance remains open.
immediate_p3_task: Obtain selected-host authorization and verify the manual journal bootstrap/poll under the bridge identity; separately decide sink, route, credentials, and SLO before connecting a timer to the sender. Preserve parked admission.
latest_github_state: Last read-only refresh confirmed PR #51 OPEN/DRAFT at `f054aebe96460fe033dde8d91d7e3bbab0255655`, zero submitted reviews and inline review threads, and successful then-current workflow runs; these remote results cover that committed head only, not current uncommitted work. Vercel success was for a READY build only; runtime remained unconfigured/unready. Refresh before relying on remote state.
base_sha: 24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e
working_branch: codex/chatgpt-cpu-vertical
implemented: plan/spec copied into repository; PR #43 disposition audited; README canary SHA and completion version reconciled to repository policy; core pytest upgraded from vulnerable 8.4.2 to locked 9.1.1; additive Gateway v2 Plan/Result contracts and explicit idempotent v1-to-v7 migrations added; schema v4 persists submission intent and attempt before dispatch; schema v5 adds the recovery-supervisor heartbeat; schema v6 adds nullable last_observed_at for successful backend observation/reconciliation timestamps; eight canonical MCP tools including owner-scoped artifact chunk retrieval advertised while six legacy names remain callable; canonical owner-scoped envelopes, source/device checks, exact-fingerprint submit, bounded filtered listing with owner-bound cursor, pending/simulation result handling added; bounded artifact blobs are written atomically with opaque owner/run-scoped paths, digest/size/media type/expiry metadata, authenticated chunk retrieval, and hourly retention pruning; compatibility period documented; T3 added fail-closed local CPU admission, disabled-by-default policy, immutable image digest and smoke profile constraints, separate durable local-policy authorization, prepare/submit/worker policy and fingerprint validation, and revocation-before-start behavior; T4 added digest-pinned CPU smoke image, detached local Docker backend with runtime hardening, strict bounded result validation, label-bound reconciliation, cancellation, and trusted supervisor deadline enforcement; T5 separates capture/persist/cleanup, keeps active slots until cleanup proof, fences stale lease writes, and recovers container-start worker crashes; `/readyz` distinguishes liveness and checks DB, exact schema version, worker heartbeat, registry shape, enabled workloads, and authentication; ChatGPT setup/acceptance prerequisites documented against current OpenAI guidance; confirmed existing Compose is demo-provider-only and Docker worker image has no Docker CLI or daemon access; documented dedicated local CPU worker's Docker trust boundary and rejection of API socket mounting; added unverified systemd and environment templates for a dedicated Linux worker; added PostgreSQL backup/isolated restore runbook documenting all DB-resident Gateway/OAuth state and the unmeasured RPO/RTO boundary; performed local PostgreSQL 16 custom dump/restore with exact row parity across all Gateway metadata tables; exercised Gateway readiness and MCP list/result read paths against a second synthetic restored database using generated test auth
latest_work: `experiment_capabilities` distinguishes simulation-only, queue-ready, blocked, and configured-but-unverified workloads and reports cost/quota/approval details, worker/supervisor heartbeat age, active slots, and explicitly unverified physical capacity; control-store read failure and missing singleton row return `CONTROL_STORE_UNAVAILABLE`; heartbeat staleness uses one shared 15-second boundary across recovery, readiness, and capabilities (`age >= 15` is stale); regression tests cover these boundaries; worker artifact-write failure now persists a failed result without publishing partial artifact metadata, keeps the slot while cleanup is pending, and preserves its failure code through worker recovery; independent provider-independent recovery review is complete with FINDINGS: no local source defect identified, but target-host mount/service behavior and production/remote recovery evidence remain unverified; gateway README now distinguishes the separate CPU gateway from the independent RunPod adapter changes in this branch; schema v5 adds supervisor_seen_at and schema v6 adds last_observed_at; `worker --supervise` is a recovery-only role that never claims queued jobs, recovers expired leases, and may take over a submitting run after the execution-worker heartbeat is stale without starting a replacement submission; readiness requires fresh worker and supervisor heartbeats; status/result/list return the owner-scoped last successful backend observation time; systemd recovery unit and ChatGPT/operations deployment instructions added; both hardened systemd templates now provision the private persistent artifact state directory; operations runbook pairs database and artifact snapshots; new `gateway/deploy/backup_generation.py` checks database quiescence and cleanup proof, builds checksummed DB/artifact archives in a private stage, validates them, and atomically publishes one generation; local PostgreSQL 16 drill verified the generation, injected tar failure without publishing a partial generation, restored into a separate database, and retrieved byte-exact artifact data through `ArtifactStore.get`; workers hourly prune expired artifacts and 24-hour-old unmanifested blobs while preserving active runs; registered CPU smoke now emits a bounded JSON report that is validated, persisted as an owner-scoped artifact, and read back after worker crash recovery; missing terminal results fail closed and preserve resources until cleanup proof
latest_validation: on commit `1a4718d`, full Gateway suite with digest-pinned CPU image `sha256:92eefb29cdbe77b66f5381afba946c12e31f5bc4fd4d32e907fa5b0aa9548092` and disposable PostgreSQL 16: 220 passed, 2 skipped, 1 Starlette deprecation warning. It includes v1-to-v6 migration, owner-scoped last-observation timestamps, retention pruning, artifact metadata constraints, artifact-write failure recovery, missing-result cleanup safety, slow-provider lease fencing, real Docker integration and PostgreSQL outage/recovery. Detailed historical integration scope: `docs/acceptance/2026-10-28-artifact-storage.md` and `docs/acceptance/2026-10-28-recovery-supervisor.md`.
latest_reviewability_audit_2026_10_28: Refreshed current worktree at `eff04c508f02c7f8206e23884f281e1edff4ddab` against `origin/main` `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`; porcelain status has 67 tracked modified paths and 28 untracked paths; the branch remains unpushed. Reviewed Gateway/Core GitHub Actions diffs and their requirements-file/root working-directory behavior; no deterministic workflow path/dependency defect was found by static inspection. Added a PR-slice map (HTTP boundary, local CPU vertical, OAuth state/migration, artifacts/host ops, P4 selection, CI/release evidence) and dependencies to the roadmap. `git diff --check` passed. No tests, remote Actions, commit, push, deploy, DB mutation, or paid/provider call was made in this audit; the slices are not yet extracted or independently reviewed.
latest_local_review_slice_2026_10_28: Extracted the shared bounded/no-redirect HTTP transport, GitHub source reads, RunPod REST/pricing/S3 read boundaries, and allocation-time authorization/price/occupancy rechecks with their focused core tests into local commit `311d6a9` (`Harden outbound HTTP and RunPod allocation checks`). The staged diff contained exactly 18 related files and passed `git diff --cached --check`. No test command was run in this turn; the prior documented core run (464 passed, 1 skipped) predates this commit and is not a substitute for current-head CI/review. Commit is local only, not pushed. Live RunPod remains uncalled and paid execution remains parked.
latest_local_cpu_vertical_slice_2026_10_28: Extracted the real local CPU MCP path and its tightly coupled worker recovery, artifact binding/retrieval, exact source/image result contract, local OAuth route addition, and offline workload capability-selection types into local commit `7c4454b` (`Implement local CPU experiment vertical and recovery`), together with the relevant acceptance/runbook/spec docs. The staged diff contained exactly 41 related files and passed `git diff --cached --check`. Historical local acceptance recorded immediately before these slice commits includes the full Gateway suite with labeled Docker CPU image and real Docker integrations (270 passed, 6 skipped) and the core suite (464 passed, 1 skipped); neither GitHub Actions nor independent PR review has run on commits `311d6a9`/`7c4454b`. No test command was run in this turn, and the commits remain local/unpushed. This does not satisfy ChatGPT account OAuth/tool-call, deployment host, seven-day operations, production restore, or real GPU acceptance; mode remains parked.

oauth_example_local_vs_external_2026_10_28: Audited `Auth`, `Settings`, `LocalOAuth`, and deployment examples. Built-in local OAuth uses durable database-backed opaque sessions and does not construct/use Fernet; only external OIDC browser login requires `GATEWAY_COOKIE_KEY`, and it must be a valid Fernet key. Corrected `gateway/deploy/api.env.example`, Gateway README, OPERATIONS, and deploy-unit regression assertions so the key is commented out for local mode and its generation command is explicit for external OIDC. The initial focused pytest attempt was blocked by missing PyJWT; this was resolved by syncing the locked Gateway runtime dependencies offline and restoring pytest from `gateway/requirements-test.txt`. Focused deploy-unit suite: 14 passed; Gateway suite: 289 passed, 9 skipped, one Starlette deprecation warning; root suite: 532 passed, 1 skipped. `git diff --check` and `py_compile` passed. Local non-integration runs do not prove ChatGPT/OIDC, target-host, production restore, or live provider acceptance.

p3_capacity_alert_bridge_contract_2026_10_28: Added `docs/specs/capacity-alert-bridge-contract.md` defining strict journald input validation, durable ordering/deduplication, redaction, independent bridge permissions/failure domain, bounded delivery/retry, and target-host acceptance. Checked current official SNS endpoint requirements: HTTPS subscriber needs a publicly reachable endpoint, signed-message verification, and subscription confirmation, so no SNS push implementation was assumed for the loopback service. No sink, bridge, account, or notification configuration was created. `git diff --check` passed; sink selection and delivery acceptance remain blocked on host, region, cost ceiling, origin/route, recipient, and SLO decisions. The first container availability check used only Docker client `info` and was inconclusive; a follow-up confirmed OrbStack server `29.8.2` is reachable and listed existing historical stopped containers. No new container was created because they are not task-owned and the required verification was achievable locally.

p3_recovery_restore_handoff_audit_2026_10_28: Re-read the systemd UID-boundary and paired-restore acceptance records and checked the live OrbStack inventory. Ran the guarded CI helper in a uniquely named `--rm --network none` container from the already-present Debian 12/systemd 252.39 image, with the repository mounted read-only and inert placeholders. `systemd-analyze verify` accepted all six current service/timer templates, including the capacity probe supplementary group. A first attempt with plain `debian:12` could not install systemd offline and auto-removed; the existing systemd image initially invoked an unrelated entrypoint, then passed with `/bin/bash` override. A post-run inventory found no named container. No service was started. This closes only current template syntax/reference validation; service sandbox startup, target-host mount/permissions, notification delivery, production/Neon restore, second-operator and measured RPO/RTO remain unverified. No production or paid resource was changed.

current_worktree_handoff_slicing_and_runbook_check_2026_10_28: Refreshed `gh pr view 51`: PR #51 remains OPEN/DRAFT with base `24ecb9b` and head `f054aebe96460fe033dde8d91d7e3bbab0255655`; remote checks remain successful on that pushed head only, with no PR review, so they do not cover the 49 current worktree entries. Added exact P3 artifact, P3 systemd, P4 selection, and CI/evidence review boundaries to the Luna handoff; assigned shared `OPERATIONS.md` and progress/release docs to one slice each. Parsed and ran `bash -n` only (no commands executed) for all 17 shell blocks in `docs/OPERATIONS.md` and `gateway/README.md`. Relative-link validation found and fixed the roadmap's recovery-drill-template path from `../acceptance` to `../../acceptance`; revalidation passed all 6 local links across 5 updated planning/acceptance docs. `git diff --check` passed. No files were staged or committed; `mode: parked` remains.
latest_local_implementation_slices_2026_10_28: Continued extraction into four additional review boundaries: `c8172c0` OAuth lifecycle/owner migration (11 files), `d794c13` paired backup/Linux operations (13 files), and `cccfcb8` CI/workflow/package metadata (8 files); preceding core vertical is `7c4454b` (41 files), preceded by HTTP hardening `311d6a9` (18 files). All staged diffs passed `git diff --cached --check`. The commits are local and unpushed. No tests were run after these commits in this turn; earlier local test totals in the entries below are pre-slice evidence, so the commit sequence still needs a fresh full suite and GitHub CI/review. No production migration, deployment, live provider call, or parked-policy change occurred.
latest_full_local_revalidation_2026_10_28: After the five local implementation commits and P4 documentation commit `f15ab32`, core suite passed 517/1 skipped. Gateway suite initially failed four PostgreSQL-backed cases when PostgreSQL was published through OrbStack's dynamic host port and the lifecycle test stopped/restarted its container. The exact outage integration then passed on fixed loopback port 55439; the complete Gateway suite on that same fixed port passed 274, skipped 2 optional Torch/Modal cases, and emitted one Starlette deprecation warning. The run enabled the actual digest-pinned CPU image and disposable PostgreSQL 16; authenticated HTTP/MCP, artifact retrieval, cancellation and recovery paths ran. Evidence and limits: `docs/acceptance/2026-10-28-local-integration-revalidation.md`. No live ChatGPT, Vercel deployment, target Linux host, Neon migration, or provider/GPU call. The first dynamic-port failure is documented as a local test harness issue; do not omit it from future reproduction. Work remains local/unpushed and `mode: parked`.
latest_remote_pr_ci_2026_10_28: Pushed `codex/chatgpt-cpu-vertical` and opened Draft PR #51 against main SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, head `89ea42efd45154e832858d14293cd29bb66cab41` (120 files). Current-head GitHub Actions runs: core CI `40609696199` success; Gateway comment bridge `40609696197` success; Gateway offline including wheel build, CPU image, PostgreSQL and Docker lifecycle `40609696193` success; Project bridge `40609696388` success. Vercel preview `dpl_8297EDuZphLShPAUgHqW8qjmLUCJ` is READY. PR review list and review-thread list are empty. This proves CI/preview build only, not production readiness or ChatGPT connectivity. No merge, production deploy, or policy change.
vercel_preview_runtime_failure_and_fix_2026_10_28: Runtime GET `/healthz` on prior preview `dpl_8297EDuZphLShPAUgHqW8qjmLUCJ` returned 500 `FUNCTION_INVOCATION_FAILED`; runtime logs identified `ModuleNotFoundError: No module named 'gpu_control'`. Build READY had not verified imports. Commit `e67eb72411ed1827dc262c0c16a71113c977cb75` adds `gpu-control` as an explicit PEP 621 dependency with local uv source `../`, commits `gateway/uv.lock`, and adds a locked fresh-environment import check to Gateway CI. Local fresh uv sync imported both `gpu_control` and `gpu_gateway`; packaging regression tests passed (2 passed), wheel build passed, all four GitHub Actions workflows passed, and Vercel preview `gpu-control-cpb08sy93-unjunos-projects.vercel.app/healthz` returned 200 with `configured=false`. Runtime import/liveness is verified; DB/OAuth readiness and ChatGPT acceptance are not.
preview_readiness_probe_2026_10_28: On the same PR #51 preview, `/readyz` returned 503 with `database=false`, `migration=false`, `worker=false`, `supervisor=false`, `registry=false`, and `authentication=false`. OAuth authorization-server discovery and unauthenticated `/mcp` both returned 503 `configuration_required`. These checks confirm preview deployment currently lacks runtime configuration; no environment variable values or secrets were accessed. Production remains untouched.
oauth_consent_boundary_2026_10_28: A focused read-only security review found `GET /oauth/authorize` issued a code to any valid session without an owner-consent step. Added a consent screen that displays client name, requested scopes, and redirect destination; GET now only validates and renders. Code issuance and denial response require a same-origin POST with the persisted session CSRF token; duplicate/reserved form parameters are rejected. Tests cover no code on GET or deny, plus CSRF, wrong Origin, reserved parameter, PKCE, token refresh/revocation and MCP use. Full Gateway suite on the changed tree: 268 passed, 8 optional integrations skipped, 1 Starlette deprecation warning. This fix is not yet re-reviewed on its resulting head and is not live-ChatGPT acceptance.
oauth_consent_fix_remote_validation_2026_10_28: Commit `bf01d12ee9918a99d19f9bf9af95404d818e7601` is pushed to Draft PR #51. Current-head GitHub Actions all passed: CI `40611512259`, Gateway bridge `40611512246`, Gateway offline `40611512283`, Project bridge `40611512244`. Vercel deployment `dpl_7MVQi85qyf9h5ne4AdWTuvgdNRks` is READY and `/healthz` returns 200; `/readyz` remains 503 with DB/migration/worker/supervisor/registry/authentication false. The fix has only local and CI regression evidence; no independent post-fix review or live ChatGPT OAuth has occurred.
external_oidc_http_boundaries: OIDC token exchange and JWKS retrieval now stream at most 65,536 uncompressed response bytes, reject duplicate JSON keys and non-finite numbers, and disable redirects. Regression tests use injected streams and prove oversized bodies are stopped early; they do not establish live identity-provider compatibility. See `gateway/gpu_gateway/auth.py` and `gateway/tests/test_external_auth.py`.
latest_external_oidc_validation_2026_10_28: TDD regression checks first reproduced full-body token reads and PyJWT's unbounded JWKS read; both pass after bounded streaming was added. Full Gateway CI rehearsal with disposable PostgreSQL 16 and digest-pinned CPU image: 258 passed, 2 skipped, 1 Starlette deprecation warning. WebMCP node tests: 3 passed; Python compileall passed. Disposable container/image removed. These are local results; remote GitHub Actions, live IdP, independent review, and deployment remain unverified.
bounded_provider_http_2026_10_28: Shared `src/gpu_control/http_security.py` rejects redirects, compressed responses, invalid/oversized Content-Length, and reads no more than limit+1 bytes. GitHub source verification, RunPod REST v1/v2, pricing GraphQL, and S3 result retrieval now use it; API JSON/error bodies are capped at 2 MiB and S3 uses its per-result limit. Injected transport tests cover upper-bound rejection and redirect handler wiring. Full core suite: 460 passed, 1 skipped; `compileall` and `git diff --check` passed. No live GitHub, IdP, or RunPod call occurred, so provider compatibility is still unverified and parked mode remains unchanged.
runpod_preallocation_freshness_2026_10_28: Adversarial tests first showed the v1/v2 adapters could reach create after authorization/price evidence expired during the occupancy/payload-preparation interval. Both now recheck the live permit, exact price evidence freshness, and the same pre-create occupancy evidence at one shared timestamp immediately before invoking provider create. Injected-clock regressions cover expired price, permit, and occupancy evidence and assert zero create calls. This remains offline adapter evidence; no RunPod request occurred. Full core suite after fix: 464 passed, 1 skipped; Python `compileall` and `git diff --check` passed.
backup_archive_member_validation_2026_10_28: Backup verification now parses artifact tar metadata without extraction and rejects absolute/traversal/nested paths, links, special files, duplicate members, and violations of per-object/per-run artifact limits. A real macOS tar probe exposed AppleDouble metadata entries; archive creation sets `COPYFILE_DISABLE=1` and then passed the real OS-tar layout check. Backup focused suite: 12 passed; full Gateway suite: 258 passed, 8 skipped, 1 Starlette warning. This is local validation and does not replace a second-operator production restore drill.
latest_environment_audit: 2026-10-28 read-only Vercel MCP inspection found project `gpu-control` (`prj_fMufIBiFDlXtWcuJ0bWpAekEMIAp`) with latest deployment `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ` READY for production `main` SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`; this predates the local CPU vertical. Project metadata lists only the verified `gpu-control.vercel.app` project domain and no custom environments; SSO protection is enabled for all deployments except custom domains. The environment-variable metadata API returned 403; no secret values were requested and the Vercel CLI fallback is not installed. Earlier public-alias checks found `/healthz` and OAuth discovery reachable, unauthenticated `/mcp` returning 401, and `/readyz` returning 404 at that deployed SHA. Read-only Neon MCP inspection found project `gpu-control-gateway` (`delicate-smoke-00521013`), ready default production branch `br-raspy-cell-b3l93n46`, Postgres 17 in `aws-ap-southeast-1`; `gateway_schema_version` is absent, `gateway_runs_v1` has 0 rows, and `gateway_control_v1.id=1` has `active_count=0`. Gateway tables match unversioned v1 columns; OAuth admin, login guard, and sessions each contain one row, so existing local OAuth state must be preserved. A loopback-only PostgreSQL 16 rehearsal of current `Store.initialize()` against the v1 shape reached schema v6 and preserved synthetic run/OAuth rows; details and limits are in `docs/acceptance/2026-10-28-neon-first-schema-migration.md`. Neon metadata lists branch protection disabled and 21,600-second history retention. No production schema mutation was performed. No ChatGPT account completed OAuth/tool scan, no CPU job or worker was deployed, and no database/artifact persistence acceptance ran. No Vercel or Neon configuration was changed.
vercel_runtime_assessment: Official Vercel documentation checked 2026-10-28 says Vercel Functions are bounded request invocations and terminate after maxDuration; this repo configures 30 seconds in `gateway/vercel.json`, so that function is not a persistent queue worker. Vercel Sandbox is a distinct candidate: current docs describe up to 24-hour sessions on Pro/Enterprise plus snapshots and Vercel Drives. Actual account plan/eligibility, pricing/quotas, worker scheduling/restart behavior, and storage/backup acceptance are unverified. P3 must compare Sandbox+Drive with the documented dedicated Linux/systemd path before selecting a deployment; no Vercel configuration was changed.
tests_and_commands: Final full Gateway suite with digest-pinned CPU image and disposable PostgreSQL 16 configured: 214 passed, 2 skipped. It includes a real Docker artifact-producing CPU run, worker process-crash recovery with exact artifact byte readback, and PostgreSQL outage/recovery. Focused artifact/contract/API suite: 29 passed; artifact-only prune suite: 4 passed. `docker compose config -q` passed; API and worker images built and both ran as UID 10001 against a unique shared volume, with API write and worker read/write verified, then project volumes removed. Recovery tests cover result persistence outage, supervisor process exit during cleanup_pending, timeout-cancel cleanup intent, slow-start lease fencing, missing-result cleanup, and real Docker/PG recovery. Artifact tests cover worker ingestion, private file mode, chunk digest/bytes, owner isolation, unlisted ID, expiry pruning and safe orphan cleanup. Recovery details: acceptance record.
real_execution_evidence: local OrbStack Docker CPU container ran on linux/arm64; verified non-root UID, network none, read-only root, dropped capabilities, PID/CPU/memory limits, no mounts, source/fingerprint binding, simulation=false, gpu_used=false, deterministic checks/checksum, timeout exit 124, capture before cleanup, and container removal. The validated stdout report was persisted as `cpu-smoke-result.json` and retrieved byte-for-byte from the owner-scoped artifact store after a Worker subprocess exited immediately after Docker start and before handle persistence; a recovery-only supervisor reconciled the single existing container and completed the same run. A separate run was cancelled after local policy disable while execution-worker ticks were stopped; the supervisor removed the container. PostgreSQL 16 was stopped after real terminal capture; the worker retained the resource and slot, then recovered, read the artifact byte-for-byte, and completed cleanup after PostgreSQL restart. No deployed Gateway, provider, or real ChatGPT/MCP call executed.
release_matrix_changes: added `docs/RELEASE_MATRIX.md` with scoped statuses: CPU_EXECUTION and local worker RECOVERY/CANCELLATION pass only for the local lane; MCP_CONNECTIVITY, CHATGPT_TOOL_USABILITY, RESULT_RETRIEVAL, and SECURITY remain uncertain; FREE_GPU_EXECUTION and PAID_GPU_EXECUTION remain blocked
latest_incremental_validation: Python full suite `./.venv/bin/python -m pytest -o addopts= -q`: 220 passed, 2 skipped, 1 warning; WebMCP contract `node --test tests/webmcp.test.js`: 3 passed; `./.venv/bin/python -m compileall -q app.py gpu_gateway modal_worker.py`: passed on the preceding readiness commit; CI-style PostgreSQL outage test stops/restarts the test DB, so it was bound to fixed loopback `127.0.0.1:5432`; its dedicated disposable container was removed after the suite. The separate focused run of health/recovery/readiness/API tests passed 46 tests.
latest_p3_host_research_2026_10_28: Read-only official provider research added to `docs/decisions/2026-10-28-p3-deployment-topology.md`. Lightsail is a candidate with Tokyo/Singapore regions; its listed 2 GB Linux bundle is $12/month and 4 GB is $24/month, with 32 GB separate block storage adding $3.20/month. DigitalOcean lists a 2 GB Basic Droplet at $12/month in Singapore but its current regional availability table does not list Japan. These are candidate prices only; snapshots, transfer overage, tax, DNS, domain and account terms are excluded. No host/provider, cost ceiling or region selected; no paid resources created. User cost-ceiling preference is pending. Live GitHub refresh found PR #43 still OPEN/DRAFT with no reviews or review requests and only 2026-09-07 successful checks; Issue #48 CPU/comment receipts on main do not prove ChatGPT MCP acceptance. Full details: `docs/BASELINE_AUDIT.md`.
latest_workflow_syntax_2026_10_28: Parsed the current four modified Actions workflow files (`ci.yml`, `gateway-ci.yml`, `gateway-bridge-ci.yml`, `project-checks-ci.yml`) with `yq -e`; all parsed. `actionlint` is not installed. This validates YAML syntax only; no GitHub Actions run exists for this unpublished worktree.
latest_task_validation: atomic paired backup generation on 2026-10-28: `./gateway/.venv/bin/python -m pytest -o addopts= gateway/tests/test_backup_generation.py -q` passed 6 tests with 1 Starlette deprecation warning; `git diff --check` passed. Disposable PostgreSQL 16 drill created and verified generation `20261027T222922Z-200fa888523044939615fba871183a5f`; injected tar exit 42 without publishing a partial generation; restored database and artifact archive to separate targets; `ArtifactStore.get` returned exact fixture bytes and digest. A follow-up schema v7 paired backup/restore into separate PostgreSQL 16 source/target containers passed: manifest verification reported schema 7, the succeeded run and 35-byte artifact were preserved, and both synthetic OAuth grant IDs plus revoked states matched. A cross-major restore probe then restored another verified v7 dump from PostgreSQL 16 into disposable PostgreSQL 17.11; schema 7, succeeded run, exact artifact, and OAuth grant/revocation fields were preserved. PG17 dump SHA-256 `d388364560d174f6a53f02924cddd913d657c0234eace998e93f641c63f932d4`; artifact archive SHA-256 `6444d3d5766958f9c207f12e7972d54a6f47cf04a982bbc144bdd21df7105761`. Both drill sets removed disposable containers, networks, and files. Evidence: `docs/acceptance/2026-10-28-atomic-backup-generation.md` and `docs/acceptance/2026-10-28-paired-artifact-restore.md`. Production backup, PostgreSQL 17/Neon parity, timed RPO/RTO, second-operator, and target-host acceptance remain open.
latest_focused_validation: after adding an explicit HTTP readiness test at ages 15 and 14 seconds, `./.venv/bin/python -m pytest -o addopts= tests/test_http_auth.py tests/test_health.py tests/test_recovery_supervisor.py -q` passed 31 tests with 1 Starlette deprecation warning
chatgpt_acceptance: `docs/CHATGPT_ACCEPTANCE.md` now provides the missing T6/T7 evidence record template; status remains NOT RUN, with no real ChatGPT OAuth/tool scan/CPU conversation represented as passed. On 2026-10-28 the official OpenAI connection requirements were refreshed and recorded in roadmap/setup/acceptance docs; actual workspace plan, role, settings, and tool connection remain NOT RUN.
remaining_blockers: T6-T7 and P3-P7; no real ChatGPT OAuth/tool-scan/CPU-run acceptance, target-host deployment, production database recovery, or timed RPO/RTO drill has run; existing Vercel production deployment is for the pre-vertical main SHA and its unique deployment URL is SSO protected; latest PR preview requires Vercel SSO and app readiness has not been observed through an authenticated fetch; environment-variable listing returned 403 and the CLI fallback is unavailable (no values read); live Neon production branch lacks gateway_schema_version and has not been migrated; it contains existing OAuth admin/login-guard/session rows requiring preservation; synthetic PostgreSQL 16 and 17.11 tests now cover unversioned v1-to-v8 and v4-to-v8 migration shapes, while Neon-specific and production migration remain unverified; local paired backup/restore is now verified on synthetic PostgreSQL 16 schema v7, including OAuth grant/revocation state, but Neon-specific behavior, production, and second-operator evidence remain open; systemd templates and paired artifact backup procedure are not validated on a target host; restore evidence is synthetic and isolated only, with simulated OAuth signing and worker heartbeat; no production artifact filesystem quota or host alert sink/delivery route is configured or tested; GitHub main branch protection is now configured and API-verified (one approval and seven required Actions checks); policy defaults remain disabled; no provider/GPU execution or paid authorization; independent provider-independent recovery source review is complete with findings limited to target-host/production evidence gaps and no identified local source defect; preserve parked mode until all activation gates and separate spend authorization are satisfied
security_review_2026_10_28: Codex Security completed full source review of the exact PR #51 base `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` to head `f054aebe96460fe033dde8d91d7e3bbab0255655` range: all 43 changed source/config/workflow inventory paths reviewed, 0 candidates/findings, complete coverage. Report: `/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/f054aebe96460fe033dde8d91d7e3bbab0255655_20261028T013205Z_ztqe0uxv/report.md`. This is source-diff evidence only; deployed runtime, ChatGPT OAuth acceptance, production settings, host permissions, and provider account behavior remain unverified. The review recorded a functional readiness mismatch in PR #51 head: `/readyz` omitted artifact storage although local_cpu capabilities/prepare require it; the local worktree patch now aligns those checks, with module-level tests passing.
readiness_contract_local_change: `gateway/gpu_gateway/app.py` now makes `/readyz` depend on artifact storage only when at least one registered local_cpu workload is enabled, and returns the storage probe status; demo-only deployments do not require artifact storage. This uncommitted change is outside scanned PR #51 head `f054aebe`. `gateway/.venv/bin/python -m pytest -o addopts= tests/test_http_auth.py -k readiness -q`: 6 passed; full `tests/test_http_auth.py`: 29 passed, one Starlette deprecation warning. Full Gateway suite `./.venv/bin/python -m pytest -o addopts= -q`: 271 passed, 9 skipped, same warning; `GATEWAY_TEST_DATABASE_URL` was unset, so database-only tests did not touch a DB. Docker was available; no test containers remained afterward. No deployed-host acceptance yet.
long_term_sequence: Continue P3 host-independent readiness and recovery acceptance preparation; keep PR #51 in reviewable Draft state and obtain GitHub review before integration. Then complete the blocked deployment decisions (Linux host/provider, region, public HTTPS origin, monthly ceiling, alert route/recipient/SLO, and authorized ChatGPT workspace/account); after those are selected, repeat the schema-v7 paired restore with a second operator and validate Neon-specific behavior only in an approved isolated path. Validate the selected host's service/mount/alert behavior; main branch protection is now configured and verified. Deploy the persistent worker/database/artifact storage only through an approved path. Complete paired production backup/restore, OAuth/tool-scan, real ChatGPT CPU run, cross-conversation result retrieval, and seven-day CPU operations observation before GPU milestones. Keep parked mode until separately authorized activation gates pass.
issuer_migration_local_acceptance: added offline preflight/apply command for built-in single-owner OAuth issuer changes; it refuses unsettled runs, nonzero active_count, and idempotency collisions, verifies/copies artifacts before transactional owner rewrite, preserves hidden rollback copies, and revokes local OAuth credentials. Combined migration, experiment API, artifact, and local-OAuth suites: 34 passed, 1 warning; includes migrated/old/unrelated-owner retrieval boundaries and recovery from partial rollback/stage directory fixtures. Disposable local PostgreSQL 16 preflight/apply/readback/token revocation passed. Four local PostgreSQL SIGKILL boundaries passed: partial rollback/stage copy injected through a blocked copytree wrapper; after artifact installation before DB update; and after DB commit with new-owner reads and OAuth revocation intact. Production PostgreSQL, other crash boundaries, and ChatGPT OAuth remain NOT RUN. See docs/acceptance/2026-10-28-owner-issuer-migration.md.
systemd_api_service_template: added `gateway/deploy/gpu-control-api.service`, binding Uvicorn to loopback, sharing the durable DB/artifact environment, and omitting Docker group access; `docs/OPERATIONS.md` documents reverse-proxy/TLS placement alongside worker/supervisor. Debian 12/systemd 252 `systemd-analyze verify` accepts the six current service/timer units with temporary executable paths, service accounts/groups, and environment file. This checks syntax and unit relationships only; actual target-host service startup, permissions, mount behavior, and reverse-proxy behavior remain unverified. The capacity monitor requires a dedicated filesystem, reports free bytes against `GATEWAY_ARTIFACT_MIN_FREE_BYTES`, and exits nonzero on low space or probe failure; a five-minute systemd timer records status to the journal, with external notification routing still required. Python static/behavior tests cover API loopback binding, Docker-group separation, shared worker environment/state, parked provider flags, timer/service wiring, dedicated-filesystem and low-space behavior; these are not a substitute for target-host startup or alert-delivery acceptance.
systemd_manual_schema_migration: added `gpu-control-db-migrate.service`, a manually started restricted oneshot with no boot install target. It reuses the protected worker environment and executes the existing `--init-db` migration path without starting API/worker processes. Operations now requires quiescent ingress and workers, zero nonterminal runs/active slots, reviewed paired backup, migration execution, and explicit failure/restore handling before other units start. `test_deploy_units.py`, `test_migrations.py`, and `test_postgresql.py`: 13 passed, 3 skipped (PostgreSQL tests require a dedicated test database), 1 warning. All six units passed `systemd-analyze verify` under Debian 12/systemd 252 with installation placeholders. Separately built the Gateway Docker image and ran the exact `--init-db` entrypoint twice against disposable PostgreSQL 16: both runs succeeded at schema v6 with zero runs/active slots/heartbeats. Setting the disposable schema version to 99 then made it fail with `UnsupportedSchemaVersion`, leaving version/run/control/heartbeats unchanged. The command was not invoked through systemd and did not use the target service account. All disposable resources were removed; no production migration or target-host start occurred. Evidence: `docs/acceptance/2026-10-28-neon-first-schema-migration.md`.
systemd_artifact_mount_ordering: Only the capacity-check service declares `RequiresMountsFor=/var/lib/gpu-control/artifacts`, matching `capacity.env.example`. API, execution worker, and recovery supervisor remain startable without that mount so they can report the storage failure and recover/cancel tracked resources; capabilities/prepare, the worker pre-start probe, and the capacity monitor fail closed for new local CPU work. `gateway/tests/test_deploy_units.py` asserts this boundary. Host mount activation and boot-time behavior remain unverified.
latest_tree_validation_2026_10_28: Rebuilt `workloads/cpu-smoke/Dockerfile` as `sha256:0b1034d4bd47c6336639d40a4cec077c1dde1c05f8cb0c75b5f9a16641271469`; with a disposable PostgreSQL 16 container bound to `127.0.0.1:55432`, full Gateway suite on the current working tree passed **247 passed, 2 skipped**, one Starlette deprecation warning, in 18.83s. This run includes the owner migration tests, mount-ordering assertions, real local Docker lifecycle/recovery and PostgreSQL outage/recovery. The DB container and temporary image tag were removed. This is local integration evidence; it does not establish GitHub CI, independent review, target-host mount activation, production storage/alerts or ChatGPT acceptance.
ci_workflow_local_validation: `yq` parsed the four CI workflows; structural checks confirm the Gateway, Gateway comment bridge, and Project bridge workflows have unfiltered `pull_request` triggers while retaining path filters for `push` to `main`, and all four accept merge_group checks. Added a root regression test for event coverage and unique required contexts; `tests/test_workflow_security.py`: 3 passed. Earlier in this working-tree cycle, `node --test tests/webmcp.test.js` passed 3/3 and `python -m compileall -q app.py gpu_gateway modal_worker.py` passed; `git diff --check` passed. `actionlint` is not installed, and GitHub Actions has not run this unpushed working-tree revision.
artifact_storage_preflight: `GATEWAY_ARTIFACT_MIN_FREE_BYTES` is parsed into validated settings; `experiment_capabilities` and `experiment_prepare` require the artifact path to be a distinct filesystem, compare free bytes against this headroom floor, and fail closed below it. Prepare performs a fresh probe after policy/backend admission and before run creation, returning `ARTIFACT_STORAGE_UNAVAILABLE` without a run. The worker repeats the probe immediately before local CPU backend start and refuses to create a container when unavailable. The systemd capacity monitor also requires a dedicated fixed-size filesystem. No production quota or alert route is configured; `quota_status=LOCAL_CAPACITY_UNVERIFIED` remains explicit.
latest_incremental_validation: `GATEWAY_ARTIFACT_MIN_FREE_BYTES` is now checked in capabilities and prepare and rechecked by the worker immediately before local CPU backend start; a regression confirms low headroom prevents container creation, clears the reserved slot, and records `ARTIFACT_STORAGE_UNAVAILABLE`. The worker admission tests plus API/recovery tests passed 39 cases before the final full run; the real Docker crash-recovery and PostgreSQL outage/recovery integrations passed 2 cases after updating their fixtures to provision the mounted artifact directory. Current full Gateway suite with the exact CI CPU Dockerfile freshly built as `sha256:9b3a5ff76d08719992dab75f25c0df3bdd03f28fe4d045de97dc389b4b040111` and a loopback-only disposable PostgreSQL 16 container on `127.0.0.1:55432`: 247 passed, 2 skipped (optional Torch and Modal), 1 warning in 18.66s; it includes real Docker smoke/recovery, PostgreSQL parallel admission, lease fencing, migration, and outage recovery. The disposable container and temporary image tag were removed after the run. Root CLI/core suite: 452 passed, 1 skipped (run before the latest Gateway-only changes). The Gateway CI workflow now builds a CPU smoke image, starts a dedicated stoppable PostgreSQL container, and enables real Docker/DB lifecycle integration tests; `yq` parsed the workflow and `git diff --check` passed locally. The branch has not been pushed, so GitHub has no Actions run for these changes; the latest successful main workflow run is 2026-09-25 on `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. These local results do not establish production quota/alert routing, target-host deployment, ChatGPT acceptance, or independent review.
latest_chatgpt_workspace_gate: rechecked the official OpenAI Help Center on 2026-10-28. Full custom MCP with write actions is available on Business/Enterprise/Edu web; Business creation/publication is restricted to admins/owners; Enterprise/Edu may use RBAC for authorized creators/testers, while publication remains admin/owner-only; Pro is read/fetch only. `docs/CHATGPT_SETUP.md` and the acceptance gate table distinguish plan, tester authorization, enabled write actions, and publisher rights. The actual project account, workspace role and action policy remain unverified.
github_release_gate_audit_2026_10_28: Read-only GitHub API/CLI inspection: repository `main` is `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`; current local `codex/chatgpt-cpu-vertical` has no matching remote branch. PR #43 is still an OPEN DRAFT for the unrelated `release-audit-2026-09-08` head `1699b75df8262023501d41279e83bf429dca1be4`, last updated 2026-09-07. `GET /branches/main/protection` returned 404 “Branch not protected”; repository rulesets are empty; `Production` and `Preview` GitHub Environments have no protection rules or deployment branch policies. The connected account reports repository admin permission, but no push, setting change, environment mutation, or secret read was performed. Current local Gateway CI cannot run on GitHub until this worktree is published; no such publication has been authorized. These GitHub controls remain unsatisfied prerequisites for any live paid path.
required_check_workflow_contract: Removed path filters from `pull_request` triggers in Gateway offline, Gateway comment bridge, and Project bridge workflows so required checks are reported on every PR; path filters remain on `push` to `main`. Added `merge_group: checks_requested` to the core, Gateway, and bridge test workflows so merge-queue candidates report the same checks. The current main check-run inventory has duplicate generic `gateway` job names from separate workflows, so the three relevant jobs now have unique display names. The successful main run inventory on SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` was read from CI run `36136508005`, Gateway run `36136508092`, Gateway bridge run `36136508071`, and Project bridge run `36136508002`. Candidate checks are the observed CI names `Python 3.11`, `Python 3.12`, `Python 3.13`, `Trusted reference container`, plus the new distinct `Gateway offline tests`, `Gateway comment bridge tests`, and `Project bridge tests`; the renamed names require confirmation on the first PR run before protection is configured. GitHub documents path-filtered skipped workflows as pending and requires `merge_group` for checks in a merge queue: https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks. No repository settings were changed.
latest_incremental_validation_2026_10_28: Corrected mount ordering so only the artifact capacity-check unit requires the artifact filesystem; API, worker, and recovery supervisor remain startable for diagnostics and cleanup during mount failure. All five service/timer units passed `systemd-analyze verify` after this correction in Debian 12/systemd 252 with temporary executable, account, and environment-file placeholders. Capacity monitor CLI regression tests now check machine-readable success/failure output and corresponding exit codes. The deployment-unit, artifact-storage, and local-admission tests passed (28 tests), root `tests/test_workflow_security.py` passed (3 tests), and `git diff --check` passed. The initial root-venv Gateway test invocation lacked `PyJWT`; rerunning with the Gateway venv succeeded. This verifies unit syntax/references and local probe behavior only; no host systemd boot, alert delivery, or GitHub Actions validation was performed.
latest_revalidation_2026_10_28: On the current uncommitted `codex/chatgpt-cpu-vertical` worktree, root `uv run pytest -o addopts= -q` passed 464 tests with 1 skipped; `gateway/.venv/bin/python -m pytest -o addopts= -q gateway/tests` passed 259 with 8 skipped locally; with disposable PostgreSQL 16 enabled, the full suite passed 262 with 5 skipped and one Starlette deprecation warning. Python compileall and `git diff --check` passed. These local suites do not establish GitHub Actions, independent review, production deployment, external alert delivery, or ChatGPT acceptance. GitHub state was refreshed read-only: PR #43 remains a separate Draft audit branch; this worktree branch has no open PR. Parked mode is unchanged.
latest_full_local_ci_rehearsal_2026_10_28: Reproduced `.github/workflows/gateway-ci.yml` locally with PostgreSQL 16 image `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`, loopback-only disposable database, and freshly built CPU smoke image ID `sha256:6e85b632f1fd342add29717490db5558dc99c8ede103dabac967e3da7c25b779`. Full Gateway suite: 249 passed, 2 skipped (optional Torch and Modal), 1 Starlette deprecation warning, 19.24s; real Docker/PostgreSQL lifecycle cases were enabled. WebMCP contract: 3 passed; Python entrypoint compile passed; root workflow security tests: 3 passed; prior focused artifact/admission/API/migration/deployment/lifecycle set: 59 passed, 2 skipped. The disposable PostgreSQL container and temporary image tag were removed. These local checks do not establish GitHub Actions, production deployment, host alert delivery, independent review, or ChatGPT acceptance.
paired_artifact_restore_2026_10_28: Corrected the backup runbook to disable local admission, stop the API, wait for zero nonterminal runs and `active_count=0`, then keep API/worker/supervisor stopped across both database and artifact snapshots. Executed synthetic paired restores to separate disposable PostgreSQL 16 targets. The original v6 drill verified `experiment_artifact` byte-exact retrieval and unrelated-owner `not_found`; the v7 refresh verified manifest/checksums, succeeded run, exact artifact bytes, and OAuth grant/revocation state. See the acceptance record for both evidence sets. Dump SHA-256 `fd45d698de49b492f1de8d4cbcb59c7c5f823a4d818c10b45a94fbcdf253f21a`; archive SHA-256 `deda7cc36f7bb90a6d3d3ee67acd8b78cfbd4e82953d5a357a7a4472c0ab708a`. `bash -n` passed for all six shell blocks in `docs/OPERATIONS.md`; `git diff --check` passed. Disposable DBs and temporary files were removed. This adds local synthetic paired-restore evidence only; production backups, filesystem quota, second-operator replication, worker/Docker reconciliation, and measured RPO/RTO remain unverified.
neon_first_schema_migration_2026_10_28: Read-only Neon inspection found the production branch on unversioned Gateway v1 with no runs or active slots, but an existing local OAuth admin, login guard, and session. The Gateway columns matched the local v1 migration assumptions. A loopback-only disposable PostgreSQL 16 rehearsal migrated the observed Gateway v1 shape to schema v6, preserving a synthetic terminal run and synthetic OAuth admin/login-guard/session/client/unrevoked-token records; legacy cleanup remained `unknown`. No production schema or config was changed. Evidence: `docs/acceptance/2026-10-28-neon-first-schema-migration.md`. This does not replace the required paired production backup, restore rehearsal, migration review, or controlled production application.
deployment_topology_decision_2026_10_28: Selected the deployment topology as one dedicated Linux host with separate systemd API/worker/recovery processes, managed Neon PostgreSQL, fixed-size persistent artifact filesystem, and loopback API behind TLS proxy. This fits the persistent worker, recovery supervisor, and shared filesystem implementation; Vercel Sandbox was not selected because account eligibility, pricing, quotas, resume scheduling, and shared artifact behavior are unverified. The host/provider, region, public HTTPS origin, and cost ceiling are not selected; no purchase, DNS change, deployment, or production mutation is authorized. Details: `docs/decisions/2026-10-28-p3-deployment-topology.md`.
oauth_revocation_v7_2026_10_28: Added RFC 7009 token revocation to built-in single-owner OAuth and advertised `revocation_endpoint`; public clients must identify themselves, and token hashes are scoped to that client. Access-token revocation is immediate; refresh-token rotation preserves a grant ID and refresh-token revocation invalidates the grant family for newly issued tokens. Additive v6-to-v7 migration adds nullable `grant_id` and preserves legacy token rows without inventing grant relationships; a legacy refresh starts a newly tracked family. TDD regression first failed on missing discovery metadata; OAuth and migration tests passed. The PostgreSQL migration path was exercised in the full suite against a disposable PostgreSQL 16 container using the repository CI image digest; full Gateway suite: 262 passed, 5 skipped, 1 Starlette deprecation warning. The container was removed. Live public endpoint remains pre-vertical, so this is local implementation evidence only. RFC: https://www.rfc-editor.org/rfc/rfc7009.
neon_v1_to_v7_operator_entrypoint_refresh_2026_10_28: Reconstructed the observed unversioned Gateway v1 column shape in a loopback-only disposable PostgreSQL 16 database, seeded synthetic run and OAuth admin/login-guard/session/client/unrevoked-token rows, removed schema-version/v2-v7 columns, then ran the exact `python -m gpu_gateway.worker --init-db` command twice. Both runs exited successfully at schema v7; run identity/state and all OAuth rows were preserved, historical cleanup remained `unknown`, active count and heartbeats remained zero, and the preexisting refresh-token row received nullable `grant_id=NULL`. Setting only the disposable version to 99 made the same entrypoint exit 1 with `UnsupportedSchemaVersion` and no state change. The disposable container was stopped/removed. Evidence: `docs/acceptance/2026-10-28-neon-first-schema-migration.md`. This verifies synthetic PostgreSQL 16 v1-to-v7 local behavior only; it does not validate PostgreSQL 17/Neon production, systemd execution, or authorize migration.
runpod_concurrency_gate_2026_10_28: Static diff review found the v1/v2 submit paths revalidate the same occupancy snapshot, so concurrent calls can still race; this behavior predates the reviewed diff and no non-test in-repository submit caller was found. Before real RunPod enablement, require account-wide cross-process serialization or an equivalent provider-enforced idempotency guarantee. No live provider call or paid allocation was made.
p4_modal_readiness_2026_10_28: Reviewed official Modal Sandbox, networking, and pricing docs against `ModalSandboxBackend`. Existing local code uses a registered immutable Modal image ID/fixed argv, bounds runtime and logs, blocks outbound network, supports cancel and recovery-only lookup, and defaults disabled; this is source-level evidence only. Public docs list included Starter compute credits and pay-as-you-go overage, but no user workspace plan, GPU quota, credit balance, budget, or hard-stop semantics were inspected. Modal is not accepted as a zero-additional-cost GPU route. No API call or compute was started. Evidence and next requirements: `docs/decisions/2026-10-28-p4-modal-readiness.md`.
github_gate_refresh_2026_10_28: Read-only GitHub CLI refresh: the only open PR returned is #43, still the unrelated draft `release-audit-2026-09-08` branch; this local `codex/chatgpt-cpu-vertical` branch has no published PR. `GET /branches/main/protection` returned 404 `Branch not protected`; repository rulesets returned an empty list. No settings were changed. The roadmap changes still need to be organized into reviewable PRs and run current CI before required check names and protection can be finalized.
p4_capability_selection_contract_2026_10_28: Added the initial concrete implementation brief mapping P4 requirements to current `Workload`, `PricingVerificationResult`, `ApprovedExecutionPlan`, registry, and local CPU policy boundaries. It specifies resource/evidence fields, availability separate from cost classification, zero-cost/overage proof, fresh-evidence handling, no provider substitution after approval, structured refusal reasons, and offline versus live acceptance scope. The pure core slice was subsequently implemented; see the following entry and `docs/specs/p4-capability-selection-contract.md` for current status.
p4_core_capabilities_and_selection_2026_10_28: Implemented pure core `WorkloadRequirements`, `CapabilityEvidence`, `CostBreakdown`, and `select_candidate` with explicit unknown values, per-run cost components, freshness, resource/result/cancel/cleanup compatibility, zero-cost proof, deterministic free-first ordering, and stable refusal reasons. RED→GREEN tests: 51 focused passed; root suite `./.venv/bin/python -m pytest -o addopts= -q`: 515 passed, 1 skipped. Review corrected free-first ranking to prioritize only proven all-zero candidates and keeps `MANUAL_ONLY` separate from unknown quota. Gateway registry/read-only capabilities/prepare are not wired to the selector; no account/provider/live GPU evidence exists. `git diff --check` passed. See `docs/specs/p4-capability-selection-contract.md`.
```

Update this record only with observed implementation and validation evidence. Do not describe mock/provider tests as real integration acceptance.

local_systemd_artifact_permissions_and_environment_split_2026_10_28: Corrected P3 Linux service templates after inspection found `ProtectSystem=strict` blocked artifact writes and shared `worker.env` would expose API-only OAuth values to worker/supervisor. API, worker, and supervisor now have only the artifact path in `ReadWritePaths`; API gets common plus API-only environment files, worker/supervisor/migration get common settings, and capacity monitor gets only path/headroom settings. Updated examples, unit regression tests, README and operations runbook. `gateway/.venv/bin/python -m pytest -o addopts= tests/test_deploy_units.py -q`: 10 passed, 1 Starlette deprecation warning. `systemd-analyze verify` accepted all six units in an ephemeral Debian 12/systemd 252 container with placeholder paths, users/groups, executables and env files. This is static unit/reference evidence only: no services were started, installed, or tested on a target host; host mount propagation, ownership, restart/boot behavior and quota alerts remain open. No provider secrets were added and `policies/repository-state.yaml` remains parked.
systemd_environment_upgrade_runbook_2026_10_28: Added steps in `docs/OPERATIONS.md` for moving an existing single-file `worker.env` installation to `gateway.env`, API-only `api.env`, and minimal `capacity.env`. The runbook preserves cookie/database values, requires root-only mode `0600` during cutover/rollback, prevents provider credentials from entering the API-readable common file, and keeps provider integrations disabled until a worker-only secret path is separately reviewed. Documentation-only; no installed host or secret files were modified.
worker_only_provider_secret_path_2026_10_28: Fixed a deployment wiring gap: the README reserved Modal/RunPod credentials for a worker secret store, but the dedicated systemd worker and recovery supervisor had no worker-only environment input. Both now optionally read `/etc/gpu-control/worker-secrets.env`; API, migration and capacity units do not. Added a secret-free example with Modal token variable names, kept provider admission switches disabled, and documented its setup/upgrade/rollback boundary. Source reference for Modal token env names: [Modal config docs](https://modal.com/docs/sdk/py/latest/config). After this change, `gateway/.venv/bin/python -m pytest -o addopts= tests/test_deploy_units.py -q`: 10 passed, 1 Starlette deprecation warning. `systemd-analyze verify` accepted all six current templates in an ephemeral Debian 12/systemd 252 container with placeholder paths/users/env files; no service was started. No provider credentials were created, and parked mode remains unchanged.
systemd_runtime_environment_acceptance_2026_10_28: Added an explicit host acceptance matrix to `docs/OPERATIONS.md` and a gate to `docs/CHATGPT_ACCEPTANCE.md` for validating environment scope after service startup. The procedure checks variable names only and forbids logging values; API/migration/capacity must not receive provider secrets, and capacity must not receive DB/auth values. This closes a documentation gap between unit-file source checks and target-host acceptance. Documentation-only; no host process environment was inspected.
systemd_runtime_environment_check_command_2026_10_28: Added a bounded command to inspect `MainPID` process environment variable names only for API/worker/supervisor, plus an assignment-name-only check for capacity/migration oneshots. It deliberately avoids `systemctl show -p Environment` and never logs values. The runbook now specifies the expected per-unit secret boundaries. Documentation-only; command not executed against any deployed service.
lightsail_instance_pricing_recheck_2026_10_28: Rechecked the P3 shortlist against current official Lightsail bundle, block storage, snapshot, and instance transfer pricing. Existing $15.20/$27.20 compute-plus-32-GB-disk estimates remain unchanged; instance-plan outbound overage remains $0.12/GB Singapore and $0.14/GB Tokyo. Clarified that these are instance rates, separate from object storage/distribution rate tables. Read-only public pricing review only; no provider, region, budget, or resource was selected or created.

lightsail_size_baseline_revalidation_2026_10_28: Re-read current official AWS price/region docs while preparing the P3 decision. The documented candidates now state exact public-IPv4 bundle specs (2 vCPU/2 GB/60 GB/3 TB at $12; 2 vCPU/4 GB/80 GB/4 TB at $24) and separate 32 GB artifact disk estimate (+$3.20). 4 GB remains the safer unmeasured host-size candidate; region and monthly ceiling remain unchosen. No provisioning or paid-resource mutation occurred.
production_recovery_measurement_record_2026_10_28: Added `docs/acceptance/2026-10-28-recovery-drill-record-template.md` with predeclared UTC clock boundaries for RPO and RTO, paired-state checks, independent observer fields, and explicit failure criteria; linked it from the operations runbook. This makes the existing 24-hour/2-hour objectives recordable without treating synthetic drills as production evidence. Template only; no timed or production restore was run, and the P3 gate remains open.
recovery_record_rpo_definition_correction_2026_10_28: Corrected the RPO template definition after reviewing the clock semantics: RPO is the interval from disruption start back to the latest fully recovered acknowledged write at/before disruption, with acknowledged-write loss recorded separately. This avoids claiming loss merely because the most recent successful write preceded an incident. Documentation correction only; no recovery drill was run.
linux_deployment_template_inventory_2026_10_28: Reconciled the Gateway README with the six actual systemd units and documented a staged install path for the three required root-owned 0600 environment files plus all units. The instructions keep worker secrets absent while parked, keep migration manual, and defer capacity timer enablement until the fixed artifact filesystem is verified. Documentation only; no target host was changed and this is not installer acceptance.
current_worktree_gateway_regression_2026_10_28: On the current local worktree at base HEAD `f054aebe96460fe033dde8d91d7e3bbab0255655`, `gateway/.venv/bin/python -m pytest -o addopts= gateway/tests -q` passed 273 tests with 9 skips and one Starlette deprecation warning. The focused artifact-storage, HTTP-auth/readiness, and deploy-unit modules passed 48 tests. This command ran without the disposable PostgreSQL + digest-pinned Docker integration settings, so it is fast local regression evidence only; it does not supersede the separately recorded 279-pass integration run, and proves no ChatGPT, target-host, Neon, or GPU acceptance.
p4_gateway_selection_boundary_2026_10_28: Gateway `experiment_capabilities` now converts explicit operator GPU requirements to `WorkloadRequirements` and invokes the selector in read-only mode. Optional manifest fields stay unknown when absent; complete requirements plus unavailable provider inventory yield `PROVIDER_EVIDENCE_UNAVAILABLE`, not a fabricated `FREE_GPU_UNAVAILABLE`. The response lists registered local CPU alternatives and marks paid GPU unavailable until live acceptance; prepare/submit are unchanged. `gpu-control` is now an editable Gateway dependency; Docker API/worker builds succeeded with imports verified inside both images. `gateway/examples/workloads.json` now states T4/16-GiB OS, architecture, network, result, cancellation, and cleanup requirements while leaving repository/SHA blank; a regression confirms the selection remains blocked until those exact identities are supplied. Current Gateway suite: 263 passed, 8 skipped, 1 Starlette deprecation warning; root suite: 517 passed, 1 skipped; API/worker Docker images rebuilt successfully; `git diff --check` passed. Provider evidence, Vercel deployment packaging, account quota, and GPU execution remain unverified.

local_oauth_failed_login_lockout_2026_10_28: Fixed failed-credential lockout persistence: the rejection was raised inside the transaction, rolling back the increment and preventing the five-attempt lockout. The counter now commits before the error is returned. A regression verifies the fifth attempt is rate-limited, lockout persists across a new Auth facade, and expires after 301 seconds. Targeted test and full Gateway suite passed. This is local security behavior evidence, not live ChatGPT/OIDC acceptance.
real_local_docker_crash_cancel_recheck_2026_10_28: Rebuilt the pinned-base `gateway/workloads/cpu-smoke` image locally as `sha256:8e4e9c5dcf06df280342f8719d883f8ce4278ad27541c749726bbc856802b981` and reran `test_os_worker_crash_after_container_start_reconciles_same_run` against OrbStack with that exact image ID: 1 passed. The test starts a real restricted Docker container, terminates the worker after container start but before handle persistence, verifies recovery adopts the single run-labeled container, retrieves exact artifact bytes, confirms cleanup leaves no matching container, then confirms a queued cancellation is cleaned by the supervisor after the policy is disabled. The test uses synthetic owner/source fixtures and local SQLite; this is real local Docker lifecycle evidence only, not ChatGPT, production host, PostgreSQL, GPU, or provider acceptance. `git diff --check` passed afterward.

chatgpt_endpoint_refresh_2026_10_28: Rechecked the public Vercel alias with unauthenticated GET requests: `/healthz` returned 200 with configured built-in OAuth, `/readyz` returned 404, and `/mcp` returned 401 as expected without a bearer token. Read-only GitHub refresh confirmed main `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` and only open PR #43 remains an unrelated draft. This confirms the live endpoint is still not the reviewed CPU vertical and does not supply ChatGPT acceptance. Added the missing operator sequence for one-time built-in OAuth bootstrap to `gateway/README.md` and `docs/CHATGPT_SETUP.md`; `python -m gpu_gateway.worker --help` exposes the documented command and `git diff --check` passed.

local_cpu_image_source_binding_2026_10_28: Closed an evidence gap in T4: the CPU smoke container output and container labels carried the plan SHA but the worker had not checked that the prebuilt image identified the same source. The image Dockerfile now embeds OCI source/revision labels from build args; the worker requires both to match the exact registered repository/SHA before container creation; the Gateway CI build records its actual repository and commit and supplies those identities to real-image integration tests. TDD: source-provenance regression failed first with an unexpected keyword, then passed with mismatch and missing-label refusals; a backend-start regression confirms an unproven image is rejected before the Docker create command. Built a labeled OrbStack image (`sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`, repository `Unjuno/gpu-control`, fixture revision `a` repeated 40 times); real smoke and worker-crash/cancel recovery integrations passed 2/2; full Gateway suite passed 265, 8 skipped, 1 Starlette deprecation warning. Docker labels bind the operator-provided identity to the image digest but are not a signed supply-chain attestation. `git diff --check` passed.
local_mcp_real_docker_vertical_2026_10_28: Added an authenticated HTTP/MCP integration that executes canonical tools/list, experiment_prepare, same-key idempotent prepare, experiment_submit, the real restricted local Docker worker, then retrieves the result and byte-exact artifact through a second TestClient using the same bearer principal. This first reproduced a lease-fixture clock issue; after advancing the fixture clock, it exposed a real product gap: ResultV2 omitted `image_digest`, although ChatGPT acceptance requires the result to bind run/source/plan/image identity. Added backward-compatible nullable ResultV2 image_digest (legacy schema-v2 records remain readable), made the worker attach the persisted plan digest, and made result binding reject missing/mismatched digest for local_cpu. Updated failure fixtures with the exact PlanV2 digest. The end-to-end real Docker MCP path now passes; Gateway suite with the labeled CPU image and local Docker integration enabled: 268 passed, 6 skipped, 1 Starlette deprecation warning. The live ChatGPT acceptance checkbox remains open; TestClient does not substitute for ChatGPT. `git diff --check` passed.
vercel_gateway_package_preflight_2026_10_28: Reproduced `uv build gateway --wheel` failing because `gateway/pyproject.toml` treated the pip-only `-e ..` monorepo installation line as PEP 621 dependency metadata. Replaced dynamic full-requirements metadata with valid explicit runtime requirements, kept `-e ..` in `requirements.txt` for the shared root `gpu-control` package, and added a regression requiring the pyproject/runtime dependency sets to stay synchronized. Gateway wheel builds and CI now builds it. A Vercel preview for PR #51 head `c1541a8` reached READY, confirming the shared root package resolved in that build. The explicit Vercel include-outside-Root-Directory setting value was not read directly. Full Gateway local suite after this change: 274 passed, 2 optional skips; GitHub Gateway offline workflow also passed. This does not prove production runtime or ChatGPT acceptance.

local_cpu_artifact_storage_readiness_2026_10_28: Completed the local `/readyz` contract for artifact-producing CPU workloads. `inspect_artifact_storage` now performs an exclusive one-byte create, immediate unlink, then write/fsync through the open no-follow file descriptor after filesystem/headroom checks, so read-only mounts and effective write failures fail closed without leaving a visible probe file during the write. Readiness requires this only when an enabled `local_cpu` workload exists and reports null storage status for demo-only configurations. Tests cover injected write failure, unlink-before-write, and no residue. Artifact-storage plus HTTP-auth modules: 38 passed. The current full Gateway suite with disposable PostgreSQL 16 and digest-pinned CPU image passes 279 with 2 optional skips, one Starlette deprecation warning. This is local evidence only; PR review, deployed host mount/quota behavior, and remote readiness remain unverified.

current_worktree_postgres16_revalidation_2026_10_28: Re-ran the complete Gateway suite on the uncommitted current worktree using a dedicated loopback-only PostgreSQL 16 container, the OCI-labeled CPU image `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`, and the stoppable database integration configuration. Result: 279 passed, 2 optional skips (Torch and Modal SDK), one Starlette deprecation warning, 20.49s. This enabled PostgreSQL parallel admission, lease fencing, v4-to-v7 migration, real local Docker/MCP/artifact flow, and PostgreSQL outage-after-capture recovery. The isolated container was stopped/restarted by the test and then explicitly removed; no labeled CPU containers remained. Exact uncommitted diff digest at test time: `22602e3e8cc5ee01c05e63968025efebff93359584885c9ee4f54f6a719408dc`; full environment scope: `docs/acceptance/2026-10-28-local-integration-revalidation.md`. This remains local synthetic evidence, not Neon/production/ChatGPT acceptance.

systemd_distinct_service_uids_and_artifact_read_boundary_2026_10_28: Closed a host-level isolation gap found during review: separated API, worker, migration, and capacity UIDs (worker and recovery supervisor intentionally share credentials/UID); API is writable only in a sticky probe subdirectory, while artifact directories/blobs are group-readable by API/capacity. Added no-follow descriptor probes, stale empty API-owned probe cleanup, tar exclusion for transient probes, new-unit and storage tests, and new install/upgrade guidance. Focused regression command across artifact storage, HTTP auth/readiness, unit templates, and backup generation: 61 passed, 1 Starlette deprecation warning. This does not establish target-host Unix permissions or systemd startup; the broader current-worktree suite has not yet been rerun after this security change. Historical shared-UID Compose evidence is explicitly marked as not validating this boundary. `policies/repository-state.yaml` remains parked.

current_worktree_gateway_suite_after_uid_boundary_2026_10_28: First full run exposed four fixtures that did not create the now-required probe directory; updated those fixtures to represent the deployment contract. Re-run before the migration utility: `gateway/.venv/bin/python -m pytest -o addopts= -q`: 274 passed, 9 skipped, one Starlette deprecation warning. This suite did not configure `GATEWAY_TEST_DATABASE_URL`; it does not supersede the separate PostgreSQL 16 + real Docker integration evidence above and does not validate a live systemd host.

artifact_permission_migration_utility_2026_10_28: Added `gateway/deploy/migrate_artifact_permissions.py` with read-only default audit and explicit root-only `--apply`. It rejects symlinks, hard links, special/nested objects, unexpected root or run-scope entries, and nonempty probe directories; applies worker/artifact group ownership and 02750 directories/0640 blobs, creates the separate 03770 probe directory, verifies postconditions, and deletes no payloads. Initial suite had 7 passing tests; a follow-up added rejection of unknown regular filenames so those cannot become group-readable. `docs/OPERATIONS.md` uses the utility with backup and stopped-service prerequisites. No real artifact tree was migrated; target-host execution and digest parity remain open.

current_gateway_full_suite_after_artifact_migration_tool_2026_10_28: Added a real tar regression proving `.gpu-control-probes` is excluded while a persisted blob remains in the backup archive. Combined migration-tool and backup tests: 20 passed. Full Gateway suite after all current changes: 282 passed, 9 skipped, one Starlette deprecation warning; `git diff --check` passed. This local run did not configure `GATEWAY_TEST_DATABASE_URL`; no target host or existing artifact tree was modified.

systemd_uid_boundary_disposable_linux_validation_2026_10_28: In a disposable, network-isolated Debian 12 container (`systemd-analyze` 252.39; image `sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`), `systemd-analyze verify` accepted all five current service units and the capacity timer with placeholder account/path setup. A real UID/GID mode-bit probe confirmed API read + own probe create/remove while denying artifact-root/blob writes; capacity read without probe-write; worker artifact write; migration artifact-read denial. Evidence: `docs/acceptance/2026-10-28-systemd-uid-boundary.md`. No unit was started and no real host/mount was changed; target-host `ProtectSystem`/`ReadWritePaths`, mount ordering, restart, and alert acceptance remain open.

artifact_permission_migration_linux_execution_2026_10_28: Ran the new migration utility as root against a throwaway tree inside the same pinned Debian 12 image. Dry-run preserved the original 0700 root and did not create the probe directory; apply changed root/scope ownership and modes to worker/artifact-group 02750, blob to 0640, and probe to worker/probe-group 03770. Exact `stat` assertions passed; the disposable container and fixture were removed. This confirms utility behavior with real Linux chown/chmod, not migration of a real artifact volume.

artifact_migration_filename_allowlist_2026_10_28: Tightened the migration preflight to accept only artifact-store 64-hex `.blob` filenames inside 64-hex scope directories. This prevents an unexpected regular file from becoming readable by the artifact group; abandoned `.tmp` files now require manual inspection before migration. The safety suite passes 8 tests. Full Gateway suite: 283 passed, 9 skipped, one Starlette deprecation warning. No production artifact tree was touched.

operations_runbook_identity_and_rwpath_reconciliation_2026_10_28: Reconciled stale deployment text with the current unit files: API has probe-directory-only `ReadWritePaths`, worker/supervisor have full artifact write access, and the manual migration service runs as `gpu-control-migrate`. Confirmed the OAuth restore wording and checked `git diff --check`. Documentation-only; no service or credential state changed.

systemd_sandbox_review_2026_10_28: Offline `systemd-analyze security` on systemd 252 reported 7.6/10 `EXPOSED` for each unit. Following a per-service needs review, added `PrivateDevices`, `ProtectProc=invisible`, `ProcSubset=pid`, empty capability bounding set, native syscall ABI, clock/hostname/kernel-log/realtime restrictions, and socket-family allowlists; the network-free capacity check also uses `PrivateNetwork` and AF_UNIX only. Re-evaluation scores: API/worker/supervisor/migration 3.8 (`OK`); capacity 3.0 (`OK`). `tests/test_deploy_units.py`: 12 passed; systemd `verify` accepted all six current units. This score is a directive heuristic, not a vulnerability assessment or runtime acceptance; Docker socket retains effective host-root authority and target-host startup/behavior remain unverified.

current_gateway_suite_after_systemd_sandbox_controls_2026_10_28: Full Gateway suite on the updated unit/security regression set: 284 passed, 9 skipped, one Starlette deprecation warning, 8.67 seconds. `git diff --check` passed. The suite does not start systemd units; no PostgreSQL integration environment was configured for this run.

systemd_pid1_container_start_attempt_2026_10_28: Tried to boot systemd as PID 1 in a network-isolated unprivileged disposable container to exercise runtime mount restrictions. The container exited 255 without useful journal/stdout; the diagnostic container was removed. No extra container capabilities were granted. This is not service-startup evidence; keep target host runtime acceptance open.

systemd_template_ci_validation_2026_10_28: Added a Linux GitHub Actions-only helper that creates inert account/path/env placeholders and runs `systemd-analyze verify` on all six service/timer units. It refuses to run outside a Linux GitHub Actions runner and never starts a service. The CI helper passed in the disposable Debian 12/systemd 252.39 container; regression test verifies workflow wiring and all unit filenames. Full Gateway suite: 285 passed, 9 skipped, one Starlette deprecation warning; `shellcheck`, YAML parse, and `git diff --check` passed. This worktree revision has not run in GitHub Actions and still does not substitute for a target-host startup test.

p4_gateway_approved_selection_binding_2026_10_28: Added strict optional `CandidateBinding` to persisted Gateway `PlanV2`, pinning workload/provider/resource/evidence fingerprints into the exact approval hash. Unknown fields and plan-provider mismatch fail closed. `plan_payload()` preserves legacy schema-v2 fingerprints/storage by omitting the absent optional field; local plan request hashing and persisted payload now share this canonical form. Contract, local-admission, and experiment API regression tests: 51 passed. This only creates the durable binding contract: Gateway selection population and `revalidate_approved_candidate` calls at submit/worker launch remain outstanding; no provider/account access occurred.

p3_capacity_alert_state_contract_2026_10_28: `check_artifact_capacity.py` emits `status=alert|ok` on each run and `gateway/deploy/capacity-event.schema.json` defines the stable event, rejects extra fields, requires a nonempty reason for alert, and requires a true healthy state for alert clear. The systemd unit sends stdout/stderr to journald under `gpu-control-capacity`; `docs/OPERATIONS.md` gives the exact `journalctl --follow --output=json SYSLOG_IDENTIFIER=gpu-control-capacity` selector and strict JSON handling. Deploy-unit tests: 14 passed, one Starlette deprecation warning; `git diff --check` passed. The CI helper's six unit/timer files also passed `systemd-analyze verify` in a disposable Debian 12 container; no unit was started. No alert sink or host delivery was configured.

p3_capacity_probe_group_correction_2026_10_28: Historical interpretation incorrectly attributed the API readiness write probe to `check_artifact_capacity.py`; its capacity check is mount identity plus `statvfs`. The earlier grant of `gpu-control-artifact-probes` to capacity, worker, and supervisor was unnecessary and widened access. A follow-up source review removed those supplementary memberships; API alone joins the group, while worker accesses the directory as owner. Fresh deploy-unit tests: 14 passed. A fresh network-isolated Debian 12 UID/GID matrix passed API blob-read/probe-create-remove, capacity blob-read/probe-write-denial, worker owner access, migration read denial, and API artifact-root/blob-write denial. A fresh systemd 252.39 verify accepted all six current unit/timer templates. This validates ordinary mode bits and template syntax only; systemd sandbox runtime, selected host, and alert delivery remain unverified.

p1_latest_preview_readiness_recheck_2026_10_28: Read-only Vercel inventory matched PR #51's latest READY preview to head `f054aebe96460fe033dde8d91d7e3bbab0255655` (`dpl_DFmSmWfMKE2Nbox5ufWDxKBa7Y9p`, target `null`). Direct authenticated Vercel fetches: `/healthz` 200 but `configured=false`/`auth_configured=false`; `/readyz` 503 with DB, migration, worker, supervisor, registry, and authentication false; OAuth protected-resource discovery 503 `configuration_required`. Updated `docs/CHATGPT_SETUP.md` and `docs/CHATGPT_ACCEPTANCE.md`. Preview build readiness is not service readiness; no production alias, configuration, database, or service state was changed.

p4_capability_availability_cost_separation_2026_10_28: Added `provider_availability` to read-only capability output, separate from Gateway `availability` (submission readiness) and `cost_classification`. Disabled provider is `UNAVAILABLE`; enabled but live-unverified provider is `UNKNOWN`; local CPU availability follows current queueability checks. Regression coverage includes disabled/enabled GPU inventory states and unavailable local artifact storage. All 23 tests in `gateway/tests/test_experiment_api.py` pass; `git diff --check` passes. No provider discovery/account evidence or submit behavior was added.

p4_modal_billing_controls_revalidation_2026_10_28: Rechecked current official Modal pricing and budgets docs. Workspace usage budget is pre-credit; net spend limit caps out-of-pocket charges, but credit-covered workloads may continue until the usage limit. Added `QuotaEvidence` with remaining usage headroom, eligible credit balance/components, provenance, and expiry; the selector blocks stale/insufficient quota, uncovered storage/egress, or absent hard stop for zero-additional-cost credit-backed runs. Added `revalidate_approved_candidate` to recheck exact workload/provider/resource/evidence fingerprints with no substitution and return `APPROVED_PLAN_STALE` when evidence or requirements changed/expired. Root suite: 532 passed / 1 skipped; Gateway suite: 285 passed / 9 skipped. Gateway evidence ingestion and calls to the revalidator at submit/worker launch are still absent. No Modal account access or provider call occurred; workspace values remain unverified. Sources: `https://modal.com/pricing`, `https://modal.com/docs/guide/budgets`.

p1_p2_current_worktree_postgres_cpu_revalidation_2026_10_28: On base HEAD `f054aebe96460fe033dde8d91d7e3bbab0255655`, current tracked Gateway diff digest `09f57882bc17184533c95f83428a18dfce2c98f65eada9ab5951b71a80a0a23e`. First integration attempt found missing `.gpu-control-probes` in MCP and worker recovery test artifact-root fixtures; fixed all three fixtures to model deployment setup while keeping production readiness fail-closed. Re-ran full Gateway suite with digest-pinned CPU image `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e` and isolated PostgreSQL 16 `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97` on loopback: 296 passed, 2 optional Torch/Modal skips, one Starlette deprecation warning. Explicit worker-crash-after-container-start test passed 1/1 and PostgreSQL outage-after-terminal-capture recovery passed 1/1. Root suite: 532 passed / 1 skipped. Dedicated database container and all test run-labeled containers were absent after cleanup; `git diff --check` passed. This remains local OrbStack/Linux-container evidence only; ChatGPT, target host, Neon, seven-day operations, alert delivery, GPU/provider, and paid acceptance remain open; parked mode preserved.


## Current-turn progress — 2026-10-28

- P4 offline selector review found that credit-backed zero-cost selection did
  refuse candidates without a hard spend cap/stop-on-overage, but did not
  classify the missing stop evidence as `QUOTA_UNKNOWN`. The branch now makes
  this gate explicit; regression cases cover missing/false cap and unknown/
  chargeable overage behavior. This changes diagnosis, not provider activation.
- Validation: root full suite `./.venv/bin/python -m pytest -o addopts= -q` —
  536 passed, 1 skipped; core capability/selection suite — 71 passed; Gateway
  contract/API suite — 39 passed, 1 Starlette deprecation warning; deployment
  and artifact permission utility suite — 22 passed, 1 Starlette deprecation
  warning; `git diff --check` passed. An initial invocation from the root venv
  could not collect Gateway tests because PyJWT is absent there; rerunning with
  the Gateway venv passed. No Docker/PostgreSQL integration ran in this turn.
- This is offline test evidence only. Modal account quota, GPU execution,
  ChatGPT connection, target host, and production recovery remain unverified;
  no external account or paid service was accessed. Parked policy is unchanged.
- Revalidated current ChatGPT custom MCP requirements against the official
  OpenAI connection guide and recorded them in the roadmap, setup, and
  acceptance documents: eligible workspace tiers and roles, current Plugins
  setup flow, HTTPS or Secure MCP Tunnel endpoint, published tool snapshot
  refresh, action controls, and capture of any ChatGPT write-action
  confirmation. These are verified product requirements; actual workspace
  eligibility and connection acceptance remain **NOT RUN**.
- No host, account, alert sink, deployment, production database, provider, or
  paid resource was accessed or changed. Existing parked policy remains in
  force.
- Checks performed: inspected the progress record, recovery drill template,
  operations runbook, alert bridge contract, and roadmap; `git diff --check`
  is the final workspace check for this documentation update.


## P4 exact-candidate integration audit — 2026-10-28

- Re-read the current `PlanV2`, capability response, `ExperimentService`, and
  worker paths after the previous selector change. `PlanV2.selection_binding`
  persists workload/provider/resource/evidence fingerprints and changes the
  plan fingerprint when present; legacy unbound schema-v2 serialization stays
  compatible. GPU capability discovery still calls the selector with an empty
  inventory (`inventory_complete=false`), and no trusted Gateway provider
  evidence ingestion exists. `revalidate_approved_candidate` is core-only and
  is not called from prepare, submit, or worker launch.
- Conclusion at that audit: do not synthesize or infer provider
  quota/availability to fill this gap. The next slice must either connect the
  existing provenance-checked RunPod price/stock source or introduce a source
  for fields it cannot establish, then convert a fully evidenced selection to
  the persisted binding and revalidate provider/resource/evidence before
  submit and worker launch. API-side provider credentials are not acceptable;
  preserve the worker-only secret boundary. Until the capability and lifecycle
  evidence is complete, keep GPU submission blocked and Modal disabled. This
  is not proof of live account values or authority to make a provider call.
- Revalidated current policy `mode: parked`; no policy file changed. GitHub
  read-only refresh still shows PR #51 open/draft at the older committed head,
  without reviews or inline threads; green checks do not cover this worktree.

## P4 provider-source inventory correction — 2026-10-28

- A deeper source audit found an existing provenance-checked RunPod source:
  `src/gpu_control/providers/runpod_current_pricing.py` makes fixed-origin,
  bearer-authenticated GraphQL reads for GPU model/VRAM/price and exact
  datacenter stock, then binds a reviewed contract commit, content digest, and
  at most 300-second validity window. This is real provider observation code,
  not synthetic evidence. The local environment has no RunPod or Modal
  credentials, and this source is not wired into Gateway capability discovery.
- Scope is insufficient for a selectable `CapabilityEvidence`: the response
  does not establish CPU/RAM, OS/architecture/runtime, queue delay, network
  behavior, result transport/size, cancellation/cleanup proof, quota, or a
  bounded all-in run cost. Do not map these missing fields from workload
  requirements or treat `HIGH` stock as a reservation. The prior statement
  that no provider evidence source exists is too broad; the accurate boundary
  is that no complete, Gateway-ingested capability evidence source exists.
- Next implementation slice should assess RunPod as a possible first live
  inventory adapter alongside the existing Modal-first decision, define the
  missing-field policy and credential boundary, then persist an exact
  candidate binding only when all selector requirements are backed by current
  observations. Prepare, submit, and worker launch must revalidate the same
  resource/evidence; expired or changed evidence fails closed. No provider
  credentials or live API calls were used, and `mode: parked` remains intact.

## P4 signed observation persistence — 2026-10-28

- Added schema v8 `gateway_provider_observations_v1` with one latest signed
  envelope per provider, version, observed/expiry timestamps, and envelope
  digest. `Store.write_provider_observation` verifies the Ed25519 envelope
  before an atomic SQLite/PostgreSQL upsert and refuses equal or lower versions;
  `read_provider_observation` checks row/index/digest integrity and
  `read_verified_provider_observation` also verifies signature and freshness.
- Added signature, tamper, expiry, unknown-key, TTL, version rollback, and
  migration coverage. Full Gateway suite: **361 passed, 9 skipped**, one
  existing Starlette deprecation warning. This remains persistence plumbing:
  worker collector, runtime key configuration, API capability mapping, plan
  binding/revalidation, and live provider/ChatGPT acceptance are not connected.
  No provider credentials or paid resources were used; `mode: parked` remains.

## P4 worker key boundary — 2026-10-28

- `Settings` now parses a bounded Ed25519 public-key JSON set from the common
  runtime environment and an optional base64-encoded private PEM/key ID from
  worker-only secrets. If a private key is configured, validation requires
  that its derived public key matches the pinned keyset. Deployment examples
  keep public keys in common settings and private material out of API config.
- `Worker.persist_provider_observation` signs and stores observations only for
  role `worker`; the recovery `supervisor` is rejected. This is plumbing only:
  no collector invokes it and API capability discovery does not yet consume
  verified observations. Focused configuration/deploy/evidence/migration tests:
  25 passed; full Gateway suite: **362 passed, 9 skipped**, one existing
  Starlette deprecation warning. `mode: parked`; no provider was contacted.

## P4 API verified-snapshot selection — 2026-10-28

- `CapabilityEvidence.from_dict` now strictly reconstructs selector contracts
  from JSON, rejecting unknown/missing fields, non-string monetary values,
  unsupported enum values, and invalid nested quota/cost objects. The API
  capability path reads only the observation for the registered workload's
  provider via `read_verified_provider_observation`, then checks the signed
  payload schema, inventory-complete flag, candidate provider/source, and
  candidate timestamps against the envelope before calling the existing
  selector. Invalid/stale snapshots fail closed; no provider inventory still
  yields `PROVIDER_EVIDENCE_UNAVAILABLE`.
- A signed fixture can be selected for capability discovery, but this does not
  mark the resource submission-ready: existing provider live-acceptance gates
  remain authoritative and `submission_available` stays false. Core suite:
  **540 passed, 1 skipped**. Full Gateway suite: **363 passed, 9 skipped**, one
  existing deprecation warning. No collector, provider API, GPU, or paid path
  was activated; mode remains parked.
- Gateway boundary review: `experiment_capabilities` runs in the API service;
  `gateway_runs_v1` currently has no provider-observation relation, the schema
  is version 7, and `selection_binding` is persisted but not consumed by
  prepare/submit/worker candidate validation. Keep collection in the worker
  credential boundary, persist bounded normalized observations additively,
  have API discovery read persisted snapshots only, and revalidate the exact
  evidence fingerprint before submit and worker provider creation. This
  sequence is now recorded in the P4 contract and roadmap. No database schema
  or runtime code changed in this review; `mode: parked` remains.
- Provenance threat review: `gateway/deploy/gateway.env.example` is loaded by
  both API and worker systemd units and contains one shared PostgreSQL URL.
  Thus a worker-only RunPod token does not prove that a stored evidence row was
  written by the worker. The P4 contract now requires either worker-side
  canonical-envelope signing with API-side pinned-public-key verification and
  explicit rotation/rollback rules, or separate DB roles that make the
  evidence table read-only to API. A content hash alone is not provenance
  authentication. No credentials, schema, or runtime behavior changed.
- Added the pure signed-envelope primitive `gateway/gpu_gateway/provider_evidence.py`:
  canonical finite-JSON encoding with a 1 MiB bound, payload SHA-256, Ed25519
  signature over provider/source/revision/version/timestamps/digest/payload,
  key-ID lookup for public-key rotation, maximum 300-second evidence TTL, and
  optional strict high-water-version checking for replay rejection. It makes
  no provider/network/database calls and is not yet wired into Gateway or the
  worker. Schema, selector behavior, credentials, and `mode: parked` are
  unchanged. The file passed Python syntax compilation; no tests were added or
  run.


## Current-worktree integration and Modal evidence refresh — 2026-10-28

- Re-ran current Gateway tests with digest-pinned Docker CPU and disposable
  PostgreSQL 16 on loopback: 296 passed, 2 optional skips (Torch/Modal), one
  Starlette deprecation warning. Container cleanup was confirmed; no
  run-labeled container remained. Exact tracked Gateway diff digest and scope
  are recorded in `docs/acceptance/2026-10-28-local-integration-revalidation.md`.
- Rechecked current official Modal billing docs. The documented
  `Workspace.billing.summary()` output is metered/billed costs, adjustments,
  and cost breakdown; it does not document remaining eligible credit, current
  usage headroom, configured limits, or stop-on-overage state. Updated the P4
  readiness decision: this API cannot alone satisfy `QuotaEvidence`; keep the
  selector blocked until an authorized owner-visible evidence source supplies
  the required current fields. No Modal credentials or calls were used.
- No code activation, provider access, deployment, or paid work occurred;
  parked policy remains unchanged. `git diff --check` passed after recording.


## Modal evidence API contract refresh — 2026-10-28

- Inspected the current official `Workspace` SDK reference. The documented
  read-only billing surface includes `rates()`, resource/time `report()`, and
  cycle `summary()`; this can supply pricing and observed-use inputs for a
  future adapter. `Workspace.settings.list()` returns settings, but its public
  reference does not define fields for remaining usage/eligible credits,
  workspace/environment hard budgets, net-spend limits, or stop-on-overage.
- Updated P4 readiness/roadmap records to separate these known API outputs from
  missing `QuotaEvidence` fields. No Modal credentials were inspected or used,
  no provider API call occurred, and no live quota was inferred. A future
  adapter must fail closed when these fields are absent.
- This turn is documentation/source-contract progress; no code or test result
  changed. Final workspace check: `git diff --check`.


## Modal billing-only observation adapter — 2026-10-28

- Added `gateway/gpu_gateway/modal_evidence.py`, an injected-workspace adapter
  that calls only `Workspace.billing.rates()` and `summary()`. It validates
  UTC timestamps and billing cycles, bounds and normalizes returned values, and
  fingerprints a `billing_only` envelope. It marks quota evidence unavailable
  and the observation ineligible for selection. It does not import Modal, read
  credentials, contact an account, create a Sandbox, or produce
  `CapabilityEvidence`/`QuotaEvidence`.
- Added 12 offline unit cases for read-only method usage, cycle behavior,
  malformed/non-finite/negative data, incomplete summaries, and timestamp
  validation. Focused suite: 12 passed. Full Gateway offline suite: 301 passed,
  9 skipped; skips cover unavailable optional Torch/prebuilt image/Modal SDK and
  unconfigured PostgreSQL integration. One existing Starlette deprecation
  warning remains.
- This confirms local adapter behavior against fakes only. Live SDK compatibility,
  workspace quota/credits/budgets, provider evidence ingestion, selection,
  submit/worker revalidation, ChatGPT connection, and GPU execution remain
  unverified. `policies/repository-state.yaml` remains `mode: parked`; no
  provider, account, credential, paid resource, or container was accessed.


## P1 registered-workload revalidation before local CPU execution — 2026-10-28

- Current local CPU workload identity was already checked during `prepare_local`
  and by the local policy at submit/worker start, but the submit-side stored
  plan was not compared to the current registered manifest, and the worker did
  not reload its configured workload registry. Added shared exact-manifest
  validation for repository/source SHA, image digest, manifest digest, runtime,
  execution profile, and current parameter schema. Submit rejects drift as
  `admission_revoked`; the worker reloads the configured registry immediately
  before local backend start and expires the queued run with
  `local_workload_changed_before_start` if the registry changed. Missing or
  unreadable worker registry configuration now expires the queued run with
  `local_workload_registry_unavailable`; the worker never treats absent
  evidence as a match. Production local CPU workloads require the configured
  workload file/JSON path.
- Focused validation: `./.venv/bin/python -m pytest -o addopts= -q
  tests/test_local_admission.py` — 14 passed;
  `./.venv/bin/python -m pytest -o addopts= -q
  tests/test_experiment_api.py tests/test_local_mcp_integration.py` — 23 passed,
  1 skipped because the optional prebuilt CPU Docker integration was not
  available/configured; one existing Starlette deprecation warning.
- Scope: policy and manifest drift are covered at submit and queued worker start
  with unit/service fixtures. This does not prove ChatGPT connection, deployed
  host configuration reload semantics, production execution, or GPU evidence.
  The repository policy remains parked and provider switches were not changed.


## P1 worker registry absence and corruption fail-closed — 2026-10-28

- A follow-up audit found that the first revalidation patch treated an absent
  workload config as a match. The queued worker now requires an explicitly
  configured workload JSON/file, reloads it before start, and distinguishes
  unavailable/invalid registry (`local_workload_registry_unavailable`) from a
  valid registry whose manifest changed (`local_workload_changed_before_start`).
  Both paths expire the queued run before backend allocation. API/service fixtures
  for the real local CPU path now provide the same registry configuration used
  by deployed worker units (`gateway.env`).
- Focused checks: local admission 16 passed; experiment API, local MCP, local
  Docker lifecycle and PostgreSQL lifecycle modules 23 passed / 3 skipped. The
  three skips are missing prebuilt CPU image (MCP and local Docker lifecycle)
  and missing dedicated PostgreSQL integration container. Existing Starlette
  deprecation warning remains. `git diff --check` passed.
- This verifies fail-closed state transitions with fixtures. No real Docker or
  PostgreSQL integration ran in this command; no ChatGPT, deployment, provider,
  or paid-resource acceptance is implied. Parked policy remains unchanged.


## P3 capacity journal event state core — 2026-10-28

- Added `gateway/deploy/capacity_event_state.py`, a host-independent core for
  the future capacity bridge. It accepts only the capacity unit's fixed
  journald identity, validates bounded JSON fields and alert/clear invariants,
  rejects malformed/unknown fields, deduplicates the current and recent 256
  source cursors, and reports transitions only when state changes. Journal
  ordering comes from resuming after the opaque cursor, never from realtime
  timestamps that can move backwards.
  Cursor plus normalized event are atomically persisted with mode `0600`; the
  writer serializes process mutations with a separate `flock` file and rejects
  symlink/non-regular or group/world-accessible state/lock files. Alert reasons are limited
  to the fixed codes emitted by `check_artifact_capacity.py`; raw journal
  fields, paths, credentials, or exception text are never persisted.
- Every alert/clear transition is added to a bounded 64-record outbox in the
  same atomic state update as its cursor. Delivery attempt timestamps, fixed
  result codes, and acknowledgement timestamps are retained without response
  bodies. Retries exhaust after eight attempts but preserve the failed record;
  a full outbox with no acknowledged entry refuses to advance its cursor.
- `gateway/deploy/capacity_event_delivery.py` adds a bounded 16-record pump,
  fixed five-field notification projection, cursor idempotency key, and
  deterministic exponential retry delay from 5 seconds to a 1-hour cap. Sender
  exceptions and response details are not persisted. Fake-sender regressions
  cover message projection, acknowledgement, retry timing, and exception
  redaction. `delivery_health()` exposes only state and fixed attempt counters,
  never event bodies, cursors, or wall-clock ordering claims. Focused capacity
  suite: 29 passed; full Gateway suite after this addition: 334 passed / 9
  skipped / 1 existing Starlette deprecation warning.
- `capacity_event_bridge.py` adds required `--bootstrap-latest` and
  `--poll-once` actions. Bootstrap is explicit; poll-only mode refuses missing
  state. CLI output contains only the processed count and safe health counters.
  `gpu-control-capacity-bridge.service` is a manual-only oneshot under a
  dedicated UID, with read-only `systemd-journal` group access, private
  `StateDirectory`, no network, no database/environment credentials, no
  artifact access, and no Docker membership. No timer was added because no
  sender/route is selected and pending deliveries must not accumulate on an
  unattended schedule.
  Root suite remains at the prior 536 passed / 1 skipped and was not rerun.
- TDD evidence: the initial focused test failed collection because the
  module did not exist; after implementation,
  `./.venv/bin/python -m pytest -o addopts= -q
  tests/test_capacity_event_state.py` passed 23 cases before the delivery/health
  additions. Tests first exposed
  reason-text leakage, duplicate JSON-key acceptance, corrupt-state acceptance,
  and trust in user-supplied `SYSTEMD_UNIT`; each was made to fail closed.
  Fake-journal tests cover bounded resume arguments, cursor expiry before state
  mutation, explicit first-run bootstrap, a healthy initial baseline,
  concurrent cursor writers, and realtime clock rollback.
  Full-suite verification after the manual CLI/unit slice: Gateway 334 passed /
  9 skipped / 1 existing Starlette deprecation warning; root suite prior result
  536 passed / 1 skipped. Docker/PostgreSQL integrations and a live Linux
  journal were not enabled.
- Scope: poller and pump have fake-source/fake-sender tests only; no selected-host
  journal runtime or systemd-analyze check for the new unit has been exercised.
  A manual oneshot template exists, but there is no timer, concrete sink,
  selected route, or notification acceptance. Retention-gap
  reconciliation remains operator-driven. A crash after a sink accepts but before
  the local acknowledgement is persisted can cause a repeated notification;
  use the cursor as an idempotency key where supported. No target host was changed,
  and `policies/repository-state.yaml` remains parked.

## 2026-10-28 continuation: integrated local revalidation

- Gateway full suite with the digest-pinned CPU image and disposable PostgreSQL
  16 container, fixed to loopback `127.0.0.1:55543`: **344 passed, 2 optional
  skips** (Torch and Modal SDK unavailable), one existing Starlette warning.
  The test container was uniquely named and removed by an exit trap. An initial
  dynamic-port run produced 4 database reconnect failures after the recovery
  test restarted PostgreSQL; the fixed-port run passed. Detailed inputs and
  scope: `docs/acceptance/2026-10-28-local-integration-revalidation.md`.
- P3 capacity bridge/deployment focused modules: **51 passed**. The seven
  current systemd unit/timer templates passed `systemd-analyze verify` in the
  cached Debian 12/systemd 252.39 image, mounted read-only with networking
  disabled. The helper must be invoked through `bash`; direct execution is not
  enabled in the file mode. No unit or live journal was started.
- These are local CPU/Docker/PostgreSQL and static systemd-template results.
  ChatGPT tool-call, target-host, Neon, seven-day operations, alert delivery,
  real GPU, and paid-provider acceptance remain open. Parked policy and
  provider switches remain unchanged.
- Refreshed Modal's official Workspace billing SDK, budgets, pricing, and egress
  documentation. Since October 1, 2026, egress is billable and the documented
  billing APIs expose egress costs; Volume reads/writes are excluded, external
  transfers are included. Billing remains retrospective and does not expose
  component-eligible remaining credits, current quota headroom, or a
  per-run stop guarantee. Updated
  `docs/decisions/2026-10-28-p4-modal-readiness.md`; no account was inspected.
- Re-ran the root/core suite after this continuation: **536 passed, 1 skipped**.
  The offline selector still has no provider inventory/evidence ingestion or
  Gateway submit/worker revalidation, so P4 live-GPU readiness remains open.
- Review correction: `/readyz` now always requires a distinct artifact
  filesystem for enabled local CPU workloads, including when the configured
  free-space floor is zero. This matches the capacity monitor's mount check.
  The regression test was observed failing before the fix; current artifact
  storage/readiness tests pass 40 cases. Gateway offline suite after adapting
  fake-mount integration fixtures: 337 passed / 9 skipped.

2026-10-28 P4 runtime and queue-wait selection follow-up: Added optional
operator-owned `runtime_requirements` and `max_queue_wait_seconds` to registered
GPU workload manifests and `WorkloadRequirements`. Capability evidence now
binds `supported_runtime_requirements` and `estimated_queue_wait_seconds` into
its canonical fingerprint; a required runtime with missing/unsupported
evidence or a missing/over-ceiling wait estimate rejects that candidate.
Complete inventory with no admissible zero-cost GPU returns
`FREE_GPU_UNAVAILABLE`; incomplete inventory remains
`PROVIDER_EVIDENCE_UNAVAILABLE`. Gateway capabilities coverage verifies that
registered local CPU choices are presented separately from the paid GPU path,
which remains unavailable pending live acceptance. Core selector/capability
tests: 74 passed; Gateway experiment API, Modal evidence, and PlanV2 contract
tests: 53 passed. The complete root suite passed 539/1 skipped, and the full
Gateway offline suite passed 353/9 skipped with one existing Starlette
deprecation warning. `git diff --check` passed. No provider/account, GPU, paid
call, deployment, or mode change occurred. All 71 paths remain uncommitted.
Provider inventory ingestion and submit/worker revalidation remain open.
The Modal registration guide now labels provider setup as future-only while
parked, explicitly prohibits enabling the provider in this state, and documents
the operator runtime and queue-wait manifest fields. This documentation change
does not authorize provider setup.

2026-10-28 P4 selection-binding guard: A RED regression showed that a
`PlanV2` carrying `selection_binding` could pass `prepare_local`, even though
the local CPU path does not run P4 candidate-evidence revalidation. Updated
`matches_registered_local_workload` to reject candidate-bound plans; this shared
guard is used by local prepare/submit and the worker's pre-start registry check.
The prepare regression observed RED before the guard; a persisted queued-plan
regression confirms the worker launches zero containers. Local-admission +
PlanV2 tests passed 39; full Gateway offline suite passed 355/9 skipped, one existing
Starlette deprecation warning. This prevents unvalidated selection evidence
from entering the separate local CPU lane. It does not implement the GPU
provider evidence source or revalidation lifecycle. No external provider, GPU,
host, or paid call occurred; 71 changed paths remain uncommitted and parked mode
is unchanged.

2026-10-28 live-state recheck: read-only requests to the production alias at
06:21 UTC returned `/healthz` 200 (`configured=true`, `auth_configured=true`),
`/readyz` 404, and protected-resource discovery 200 with read/run/cancel scopes.
The P1 deployment still lacks the readiness route; no OAuth grant, authenticated
MCP request, or ChatGPT tool call was attempted. GitHub confirms PR #51 remains
OPEN/DRAFT and unmerged at head `f054aebe96460fe033dde8d91d7e3bbab0255655`,
with no submitted reviews. The exposed combined commit status lists only Vercel
success; it does not report the Actions workflows. This is refreshed external
state, not acceptance evidence. No deployment or repository-host mutation was
performed; mode remains parked.

2026-10-28 P4 RunPod catalog collector slice: Added a default-off
`GATEWAY_ENABLE_RUNPOD_EVIDENCE` path that polls only from an idle normal worker,
at most once per minute. Exact operator-owned GPU and datacenter IDs are
required; malformed or ambiguous matches cannot become complete inventory.
The worker persists a signed, 120-second snapshot with a monotonic version.
RunPod read credentials and the Ed25519 signing key now live in an optional
`provider-evidence.env` loaded only by the normal worker; the API and recovery
supervisor do not receive that file. Catalog price is retained only as an
accelerator estimate; all-in costs and runtime/OS/CPU/RAM/network/result/
cancellation/cleanup properties remain unknown, so this source alone cannot
make a candidate runnable or enable submission. Added fake-client and role
boundary tests. Focused collector, signing, and GraphQL tests: 16 passed. Full
Gateway suite: 367 passed, 9 skipped, one existing Starlette deprecation
warning; root suite: 540 passed, 1 skipped. `git diff --check` and Python
compilation passed. Deployment-unit tests passed as part of the Gateway suite.
The repository systemd CI helper intentionally refused local execution because
it is restricted to an ephemeral Linux GitHub Actions runner; `systemd-analyze`
acceptance remains for CI. No provider request, credential use, GPU, paid call,
deployment, host mutation, or policy mode change occurred.
`policies/repository-state.yaml` remains parked. Official API fields were
checked against the [RunPod GraphQL API spec](https://graphql-spec.runpod.io/).

2026-10-28 P4 plan-binding continuation: Moved signed snapshot validation and
workload requirement conversion into shared `provider_selection.py` helpers.
When the full evidence selects a GPU, `experiment_prepare` now creates a
PlanV2 whose fingerprint binds the exact workload, provider, resource, and
evidence fingerprints. Prepare revalidates before persistence; submit locks and
revalidates the signed observation in the queue transaction; the normal worker
revalidates once more before writing submission intent. Changed evidence,
expired evidence, manifest changes, and unknown/incomplete inventory fail
closed without substituting another candidate. Provider registrations default
to `supports_candidate_binding=false`; current Modal and RunPod integrations
therefore cannot queue such plans or reach their backends. Added regressions
for plan binding, stale evidence at submit, stale evidence before worker start,
and unsupported backend queue refusal. Focused suite: 82 passed. Full Gateway
suite: 370 passed, 9 skipped, one existing Starlette deprecation warning; root
suite: 540 passed, 1 skipped. `git diff --check` and Python compilation passed.
No external provider, GPU, paid call, host mutation, or deployment was used.

## P4 candidate-bound backend contract — 2026-10-28

Added a runtime acceptance-shape check for candidate-bound execution. A provider
must be explicitly enabled in the trusted registry and expose a dedicated
`start_candidate_bound` entry point plus `capture`, `cleanup`, and `is_clean`.
Queued candidate-bound plans that fail this contract terminate with
`candidate_backend_contract_unavailable` before creating submission intent or
calling the provider. Accepted candidate-bound plans dispatch only through the
dedicated entry point; legacy `start(run)` adapters cannot silently ignore the
selected resource. Modal and RunPod remain unsupported, provider flags remain
off, and no external provider/GPU/billing call was made.

Targeted Gateway verification: 9 passed (`test_registry.py` and
`test_worker_recovery.py`); `git diff --check` and Python compilation passed.
This verifies the offline contract and existing recovery behavior only. It does
not establish provider device identity, real GPU execution, trusted result
attestation, cleanup acceptance, or paid authorization. Next implement a
provider adapter against the dedicated contract and a signed/validated device
and result receipt; keep `supports_candidate_binding=false` until that full
acceptance is independently evidenced.

## P4 trusted candidate-result gate — 2026-10-28

Strengthened the candidate backend shape: an opted-in backend must expose
`validate_candidate_observation(run, observation)` in addition to its dedicated
PlanV2 start and cleanup lifecycle. Before publishing a terminal candidate
result, the worker invokes that trusted adapter validator; exceptions or any
value other than literal `True` discard the untrusted result/artifacts, record
`candidate_result_evidence_invalid`, and still drive cleanup. A successful
candidate GPU `ResultV2` must report a named device, `gpu_used=true`, exit code
zero, and normalized `candidate_resource_verified` plus
`device_identity_verified` checks. These checks are necessary acceptance
markers; they do not by themselves prove provider-side signature or hardware
identity. Registry opt-in remains false for Modal and RunPod.

The first full Gateway run caught an error-precedence regression where backend
contract rejection masked stale-plan expiry. Reordering preserves evidence and
registered-workload revalidation before checking backend readiness; the full
Gateway suite then passed, as did the full root suite. `git diff --check` and
Python compilation passed. This remains offline contract evidence only. The
adapter must verify a provider-authenticated receipt binding actual
resource/device, run ID, approved plan fingerprint, image, and result before
returning true. No provider, GPU, or billing call was made; parked mode remains.

## P4 execution receipt signer-scope verifier — 2026-10-28

Added a bounded Ed25519 receipt verifier in `gateway/gpu_gateway/candidate_receipts.py`.
Successful candidate GPU observations need a receipt signed under one of two
explicit scopes: a provider key, or a trusted adapter key attesting to an
authenticated provider API projection. Namespaced key IDs
(`provider:<provider>:<id>` and `adapter:<provider>:<id>`) prevent scope
confusion. The verifier binds provider, exact resource, run ID,
approved plan fingerprint, source SHA, immutable image digest, provider
execution ID, device identity/model, GPU use, exit code, and a digest of
normalized result claims. Receipt keys use the distinct
`GATEWAY_CANDIDATE_RECEIPT_PUBLIC_KEYS_JSON` setting; they cannot be confused
with the Gateway worker's provider-observation signing key. The verified signed
receipt is retained in the result, and only then does the worker add normalized
resource/device verification markers. The adapter's authenticated live-object
cross-check remains required.

Added `docs/specs/p4-candidate-execution-receipt-contract.md` with both signer
scopes, trust/key provenance boundary, adapter interface, lifecycle
gates, and acceptance tests. Fake Ed25519 tests cover valid binding, tampering,
wrong resource/fingerprint/result, untrusted key, and expiry. Focused Gateway
modules passed 49 tests; full Gateway suite passed; full root suite passed;
Python compilation and `git diff --check` passed. This is schema/verifier
contract evidence only. No provider or adapter has been shown to emit a
production receipt, key
provenance/rotation are unaccepted, and no hardware/GPU/billing/cleanup evidence
exists. Modal/RunPod candidate opt-ins remain false; provider switches remain
off and `mode: parked` remains. Next: verify current provider APIs/accounts for
receipt or authenticated execution evidence, then implement exactly one
provider adapter only if the evidence source can satisfy this contract.

### Provider evidence source review — 2026-10-28

Refreshed primary provider docs after defining the receipt contract. The
RunPod GraphQL schema exposes authenticated Pod/machine/GPU identity and
runtime telemetry fields, but the reviewed schema does not define a
provider-signed execution receipt. The Modal Sandbox API exposes Sandbox
identity, process polling/streams, and termination, and its runtime environment
includes `MODAL_SANDBOX_ID`; the reviewed interfaces do not expose a
provider-signed hardware/result receipt. References: [RunPod GraphQL spec](https://graphql-spec.runpod.io/),
[Modal Sandbox SDK](https://modal.com/docs/sdk/py/latest/Sandbox), [Modal
runtime environment](https://modal.com/docs/guide/environment_variables).
This is doc review only; no account or provider API was accessed. The receipt
contract now distinguishes provider-signed receipts from Gateway-adapter
signatures over authenticated API snapshots. This distinction still needs
provider-specific implementation and independent key provenance. Do not
conflate those evidence scopes or accept workload self-report. GPU remains
blocked; parked mode remains.

### Receipt signer-scope follow-up — 2026-10-28

Extended the receipt envelope with an explicit `signer` scope (`provider` or
`gateway_adapter`) and a bounded provider evidence source plus provider-object
snapshot digest. The public-key configuration now requires namespaced key IDs
(`provider:<provider>:<key-id>` or `adapter:<provider>:<key-id>`), and the
verifier checks the signer/key namespace matches. For `gateway_adapter`, the
receipt is expressly an adapter attestation over an authenticated API snapshot,
not provider-signed hardware attestation; the trusted adapter's independent
live-object check remains required. Updated the receipt specification and
operator env example accordingly. Focused receipt tests: 9 passed; full Gateway
suite and root suite passed; `git diff --check` and Python compilation passed.
No adapter keys have been provisioned, no provider adapter accepted, and no
provider/API/GPU/billing activity occurred. Keep switches off and mode parked.

### Candidate cleanup success invariant — 2026-10-28

`validate_candidate_gpu_success` now also requires `cleanup_state="complete"`.
The API's persisted-result verifier uses the same invariant, so changing a
successful candidate result's cleanup state to `unknown` or `pending` causes
the response to fail closed and redact the result. A regression mutates both
result metrics and cleanup state after persistence and verifies neither is
reported as successful; focused candidate/read/contract modules passed 29
tests. Full Gateway and root suites, Python compilation, and `git diff --check`
passed. This checks the recorded cleanup state and existing worker
`cleanup`/`is_clean` lifecycle; it is not an independent provider cleanup
receipt or proof of a live resource being absent. Provider adapter, cleanup
attestation, ChatGPT acceptance, and live GPU remain open; parked mode remains.

### Candidate receipt verification on result retrieval — 2026-10-28

The Gateway now re-verifies persisted successful candidate GPU receipts on
`experiment_get`, status/result responses, terminal idempotency reads, and
experiment listings. Read verification checks the persisted plan fingerprint,
ResultV2 identity, GPU success markers, trusted receipt signature and result
digest. It accepts an expired-but-authentic receipt for historical reads while
still enforcing the signature, bounded validity interval, no-future-issued
constraint, and exact run/plan/resource/result binding. Tampered candidate
success is returned as `failed/result_integrity_failed` with the untrusted
result redacted; artifact retrieval therefore cannot use that result manifest.
Focused receipt/read-path tests: 11 passed. Full Gateway and root suites passed;
Python compilation and `git diff --check` passed. This verifies offline receipt
and tamper-handling behavior only; no provider adapter, production key, GPU, or
live retrieval acceptance exists. Mode remains parked.

## P5 Gateway paid-execution separation — 2026-10-28

Added `ProviderRegistration.supports_paid_execution`, independent from the P4
candidate-binding acceptance flag. Candidate plans are treated as requiring
separate paid authorization unless cost evidence proves `LOCAL`, `FREE`, or
`FREE_QUOTA` with an explicit zero additional cost. The Gateway submit path
rejects paid-class plans with `paid_authorization_required` while the registry
has not passed paid execution acceptance. The worker repeats the independent
capability check and, before submission intent/provider invocation, requires a
trusted backend's `validate_paid_authorization(run)` to return literal `True`.
A missing/false/raising permit validator fails before the provider start call.
This is the integration seam for the existing core `LiveExecutionPermit` and
paid-authority evidence; no RunPod/Modal registration opts into it.

Coverage proves paid-plan submit rejection leaves the plan approved and
reserves no slot, and that registry/runtime acceptance distinguishes a
zero-cost class from paid cost. Focused registry/API/recovery tests: 39 passed;
full Gateway and root suites passed; Python compilation and `git diff --check`
passed. No permit, credential, provider call, GPU, billing action, or host change
was made. The next P5 work is a trusted adapter that loads and verifies the
run-specific core `LiveExecutionPermit` against the exact Gateway PlanV2 and
current provider pricing/occupancy evidence; keep registry opt-ins false until
reviewed.

### P5 run-specific permit-before-intent regression — 2026-10-28

Added an integration regression with a current signed candidate snapshot and a
PAID PlanV2. Even when a test registration explicitly enables both candidate
and paid capability, a backend that rejects its run-specific permit is stopped
before submission intent, provider start, or slot retention. Also narrowed the
zero-cost exception: `LOCAL` only qualifies for local provider IDs; remote
providers need explicit `FREE` or `FREE_QUOTA` classification and exact zero
additional cost. Full Gateway and root suites pass; Python compilation and
`git diff --check` pass. The production RunPod core `LiveExecutionPermit` is not
yet loaded/validated by a Gateway adapter; all real provider flags remain off.


### P5 Gateway–RunPod permit bridge design boundary — 2026-10-28

Documented the trust boundary and staged implementation contract in
`docs/specs/p5-gateway-runpod-permit-bridge.md`. The core permit is an unsigned
dataclass whose provenance comes from the GitHub protected workflow/Environment
path; Gateway currently stores only browser approval ID/expiry and has no
durable paid-authorization envelope. Direct JSON conversion or synthesizing
core human/paid evidence from PlanV2/browser approval would weaken the existing
authorization model. The design requires an independently trusted, signed,
run-specific paid-authorization envelope, exact PlanV2-to-
`ApprovedExecutionPlan` mapping, durable storage, worker and pre-allocation
revalidation, revocation/recovery rules, and independent review. No execution
code, registry flag, credential, provider API, GPU, billing, or policy mode
changed.

### P2 recovery regression refresh — 2026-10-28

On the current Gateway diff digest
`f98f3eeb9e6dedb4bce9c9e69fa6e6de68575dfcf286938c6f69d82ff3baea95`, the
focused worker-recovery and recovery-supervisor modules passed **11 tests**
from `gateway/.venv`. The full Gateway suite passed **393 tests**, with 3
optional/unconfigured skips. A dedicated PostgreSQL outage-after-capture test
also passed against the pinned local CPU smoke image and disposable PostgreSQL
container: DB outage retained the run/slot, and restart recovery persisted the
artifact, completed cleanup, and released the slot. `git diff --check -- gateway`
passed. Detailed commands and scope are in
`docs/acceptance/2026-10-28-recovery-regression-refresh.md`. Production recovery,
Neon, and RPO/RTO remain open; mode remains parked.

### P3 capacity bridge and backup regression refresh — 2026-10-28

Re-ran the current worktree's host-independent capacity journal/outbox,
delivery-pump, and backup-generation coverage from `gateway/.venv`: 53 passed;
systemd deploy-unit template coverage: 14 passed. The root virtualenv lacked
Gateway-only PyJWT, so the initial root-environment invocation failed during
conftest import before test collection; the Gateway venv run is the authoritative
result. Evidence: `docs/acceptance/2026-10-28-capacity-bridge-regression.md`.
No live journald, sink, PostgreSQL, host service, provider, or backup restore was
used. Sink/host/SLO acceptance remains open; mode remains parked.


### P4 RunPod REST API v2 source revalidation — 2026-10-28

Read current official RunPod API documentation. REST v1 is deprecated and
scheduled for retirement on 2026-11-15; repository source contains both a v2
HTTP client and a separately named legacy v1 client/adapter. Official v2 docs
expose authenticated Pod identity/status, GPU type/count, cloud/datacenter,
CUDA/runtime and cost metadata, a container/system-log SSE endpoint, lifecycle
actions, and Pod termination. This supports further design of an adapter under
the existing trusted-adapter receipt scope, but does not prove returned result
bytes, actual provider compatibility, provider-signed hardware evidence,
resource absence, pricing/quota, or live cleanup. No account, credential,
provider request, Pod, or billing activity was used. Evidence and remaining
gates: `docs/acceptance/2026-10-28-runpod-api-v2-revalidation.md`. Keep the
legacy v1 path out of live use; keep all provider registrations disabled and
mode parked.

### P4 RunPod REST v2 Network Volume payload correction — 2026-10-28

Comparing the v2 adapter against RunPod's current official v2 create schema
found that the shared Network Volume helper was emitting legacy top-level
`networkVolumeId`/`volumeMountPath` fields. The current v2 API represents this
as `mounts.network: [{volumeId, path}]`. Replaced the helper output, bound placement to the trusted volume datacenter,
required Secure Cloud, and made it reject pre-existing mount/datacenter settings
rather than merge ambiguous storage configuration. The v2 adapter now validates
the exact returned volume ID/path/datacenter/cloud before accepting a Pod and
uses compensating termination on mismatch. Added request, response, and adapter
regressions; they failed against the prior behavior, then passed. Focused v2
payload/adapter/policy plus legacy v1 compatibility tests: 56 passed. No provider
request, credential, resource, or billing activity occurred. Official-source
and scope record: `docs/acceptance/2026-10-28-runpod-api-v2-revalidation.md`.
Real provider compatibility and all GPU/paid acceptance gates remain open;
provider opt-ins stay disabled and mode remains parked.

### Candidate-bound prepare idempotency after evidence expiry — 2026-10-28

Code review found that `experiment_prepare` reselected provider inventory before
checking the idempotency record. An exact retry after the signed observation
expired therefore returned a blocker without the existing `run_id`; a changed
candidate could also make the retry look like different input. Added an
owner-scoped early lookup using a stable hash of the normalized request, and
preserved compatibility with rows written using the prior PlanV2 hash by
matching immutable request fields. Same-key changed inputs still return
`idempotency_conflict`. The regression failed before the fix, then the focused
Gateway experiment API and local-admission modules passed **53 tests**; the
full Gateway offline suite passed **388 tests / 9 skips**. Skips were for
Torch/Modal SDK and unconfigured Docker/PostgreSQL integrations. This is
offline Gateway evidence only; no GPU execution or provider contact occurred.
Candidate backend acceptance, real ChatGPT connectivity, and all live GPU gates
remain open; repository mode remains `parked`.

### RunPod API policy metadata reconciliation — 2026-10-28

Aligned `policies/runpod-v2-policy.yaml`, parked repository state, and their
regression expectations with the current official REST v2 source review. Removed
the stale assertion that v1 is the current official contract and the stale
claim that Pod-log streaming is undocumented/unavailable; v1 retirement remains
recorded for 2026-11-15. The policy still says the implementation is not fully
matched/accepted and requires revalidation before live enablement. Updated the
release matrix to preserve the live-verification boundary. Only policy/docs and
existing assertions changed in this follow-up; tests were not rerun. No provider
contact or live setting changed, and repository mode remains `parked`.

### Docker acceptance after prepare-idempotency fix — 2026-10-28

Re-ran the real local Docker backend, worker-crash recovery, and authenticated
MCP CPU/artifact integration modules on the current working tree using the
existing provenance-labeled CPU image
`sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`:
**3 passed**, one existing Starlette deprecation warning, 7.05 seconds. The
offline Gateway suite is **388 passed / 9 skipped**; skipped integrations
include Docker/PostgreSQL, Torch and Modal because that invocation did not set
their inputs. The separate latest full PostgreSQL 16 result predates the
idempotency fix and was not repeated. One Exited run-labeled container in the
post-run inventory was created before this invocation and was left untouched;
no new run-labeled test container remained. Acceptance details and source hashes
are in `docs/acceptance/2026-10-28-local-integration-revalidation.md`. No
ChatGPT workspace, production host, provider, GPU, or paid resource was used;
parked mode remains unchanged.

### Full Docker/PostgreSQL Gateway revalidation after prepare-idempotency fix — 2026-10-28

The entire Gateway suite passed **395 tests / 2 optional skips** with the
digest-pinned CPU smoke image and disposable PostgreSQL 16 container on fixed
loopback port `55546` (22.47 seconds; one existing Starlette deprecation
warning). This rerun includes the prepare-idempotency changes and the PostgreSQL
outage/recovery path. The first invocation selected the undeclared psycopg2
driver through a generic PostgreSQL URL and failed four cases during database
initialization; rerunning with the declared psycopg 3 driver (`postgresql+psycopg`)
passed. The temporary database container was removed by an exit trap. Exact
inputs and scope are recorded in
`docs/acceptance/2026-10-28-local-integration-revalidation.md`. This is local
CPU/Docker/PostgreSQL evidence only; ChatGPT, deployment, provider, GPU, and paid
acceptance remain open, and repository mode remains `parked`.

### Continuation refresh — 2026-10-28

The current-worktree full Gateway run with digest-pinned Docker CPU and
PostgreSQL 16 passed **395 tests / 2 optional skips**; details are in
`docs/acceptance/2026-10-28-local-integration-revalidation.md`. Codex Security
reviewed the then-current snapshot digest
`codex-security-snapshot/v1:sha256:7e0e8d8cd28422336d2f13fd6520868dc91ef5e9fac2d9a3e85e8004ec272716`
across 36 changed source-like files and eight coverage surfaces with zero
candidate findings. Report:
`/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/f054aebe96460fe033dde8d91d7e3bbab0255655_20261028T081301Z_gcgufipi/report.md`.
This bounded source scan is not a GitHub human review, deployed security
validation, or ChatGPT acceptance. The target ChatGPT workspace remains
unverified; the in-app browser was logged out. PR #51 was last observed
OPEN/DRAFT with no reviews, and `main` had no active branch-protection rule.
No external settings changed; repository mode remains `parked`.

Read-only GitHub status refresh at 2026-10-28 08:25 UTC: PR #51 remains
OPEN/DRAFT at `f054aebe96460fe033dde8d91d7e3bbab0255655`, based on
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`; review requests and submitted
reviews are empty. GitHub reports `main` unprotected. This confirms that the
current 105-path local worktree is still outside the pushed PR head and that
human review/integration gates remain open. No GitHub state was changed.

### P3 capacity-alert delivery boundary recheck — 2026-10-28

Source inspection confirms `capacity_event_delivery.py` is a sink-agnostic
injected sender pump with bounded retries, fixed message projection, and stable
cursor idempotency keys. The installed service template only performs a
manual journal poll into the durable outbox; it has `PrivateNetwork=true` and
does not invoke delivery. No sender, bridge timer, route, or target host is
selected. This is intentional under `docs/specs/capacity-alert-bridge-contract.md`:
sink selection depends on host/provider, region, cost ceiling, route, recipient,
credential storage, and a predeclared SLO. Therefore no honest live-delivery
implementation or acceptance can be completed from repository evidence alone.
The immediate independent work is preserving the sink-neutral contract and
reviewing the uncommitted P3 slice; once operator decisions exist, implement one
bounded sender and service under the bridge-only identity, then perform target-
host alert/clear delivery acceptance. No test, service, or external setting was
changed in this continuation; parked mode remains unchanged.

### P3 capacity delivery ordering follow-up — 2026-10-28

Closed a retry ordering gap in the sink-agnostic capacity pump. The due selector
now stops at the first pending event still in backoff, and a retryable failure
stops the current send batch so a later clear cannot overtake its alert.
Added a fake-sender regression covering failed alert, blocked clear during
backoff, and ordered alert-then-clear delivery after retry. Capacity state
suite: **40 passed**, one existing Starlette deprecation warning;
`git diff --check` passed. Evidence:
`docs/acceptance/2026-10-28-capacity-bridge-regression.md`. No live sink,
journald, host service, or network was used; host alert acceptance remains
open and `policies/repository-state.yaml` remains parked.

### Current integrated local regression refresh — 2026-10-28

Revalidated the current worktree after the capacity ordering change. Root suite:
**550 passed, 1 skipped**. Gateway suite with digest-identified CPU smoke image
and a disposable PostgreSQL 16 container bound to `127.0.0.1:55499`:
**423 passed, 2 skipped** (optional Torch and Modal SDK only). This includes
Docker CPU/MCP lifecycle, worker crash recovery, PostgreSQL v1-to-v8 migration,
OAuth refresh concurrency/rollback, and PostgreSQL outage recovery. An initial
run with a dynamic published port failed after the outage drill restarted
PostgreSQL; fixed-port rerun passed. The test container/image tag were removed.
Exact evidence and limits are in
`docs/acceptance/2026-10-28-local-integration-revalidation.md`. ChatGPT,
Neon/production, selected-host, seven-day, notification, GPU, and paid
acceptance remain open; repository policy remains `parked`.

### Current ChatGPT access preflight — 2026-10-28 11:25 UTC

Opened `chatgpt.com` in a fresh in-app browser tab for read-only access
inspection. The page showed Log in / Sign up, not an authenticated workspace;
no login or workspace mutation was attempted. The target workspace plan, role,
custom-MCP permissions, and tunnel association therefore remain unverified and
all live ChatGPT gates remain NOT RUN. Re-read current official OpenAI docs:
Secure MCP Tunnel can carry OAuth discovery, while the authorization server is
not automatically tunneled. Corrected the setup guide to distinguish those
paths. Evidence: `docs/CHATGPT_ACCEPTANCE.md` and
`docs/CHATGPT_SETUP.md`. No OAuth grant, Platform API call, tunnel, deployment,
or provider action occurred.

### P3 capacity journal retention-gap recovery — 2026-10-28

Closed an implementation gap in the manual capacity bridge: retention loss
previously failed closed but offered no safe operator rebaseline path. Added
`JournalPoller.reconcile_latest()` and explicit CLI `--reconcile-latest`. It
requires an initialized state and a missing saved cursor, rechecks retention
after reading one latest trusted event, preserves pending outbox entries, and
queues the latest status even when unchanged. It does not infer or recover
intermediate events removed from journald. The Operations runbook and bridge
contract now explain the operator command and evidence boundary. Red/green
regressions plus capacity-state, backup-generation, and systemd-unit suites:
**71 passed**, one existing Starlette deprecation warning; `git diff --check`
passed. Evidence: `docs/acceptance/2026-10-28-capacity-retention-reconciliation.md`.
No live journal/host/sink was used; P3 host acceptance and alert delivery remain
open, and parked mode remains unchanged.

The independent review of this retention-reconciliation slice found one
runbook invocation issue: the example used unsupported `sudo -G`. Removed that
option; the documented setup already adds the bridge identity to
`systemd-journal`, and sudo initializes the target identity's supplementary
groups. The focused 71-test suite was rerun after the correction and passed.
This platform-specific command itself was not executed on a Linux host.

### P3 capacity bridge read-only health inspection — 2026-10-28

Added CLI `--show-health` so an operator can inspect pending/acknowledged/
exhausted outbox counters without polling journald. It emits only the fixed
local health projection and omits event reasons, cursors, exception text, and
sink responses. A regression failed before implementation because the option
was unsupported; after the change, the source factory was proven not to run and
redaction assertions passed. Capacity-state, backup-generation, and systemd
unit suites: **72 passed**, one existing Starlette deprecation warning;
`git diff --check` passed. Evidence:
`docs/acceptance/2026-10-28-capacity-bridge-health-cli.md`. This reports local
outbox state only and is not host/journal/notification acceptance. Parked mode
is unchanged.

### P3 health CLI review fix — 2026-10-28

Independent review found `--show-health` read the private state file outside the
CLI's fixed-error handler, so corrupt JSON/permissions could expose traceback and
path details. Moved the read into the guarded action and added a corrupt-state
regression requiring only the fixed error output and no journald access. The
review finding was fixed; capacity-state, backup-generation, and systemd-unit
suites passed **73 tests**, one existing Starlette deprecation warning;
`git diff --check` passed. Updated evidence:
`docs/acceptance/2026-10-28-capacity-bridge-health-cli.md`. No live host or
journal was used; parked mode remains unchanged.

### P1 OAuth refresh-token rotation atomicity — 2026-10-28

A RED regression exposed that invalid scope expansion revoked the old refresh
token before returning `invalid_scope`. Refactored refresh rotation to validate
scope before mutation and commit old-token revocation plus replacement access/
refresh insertion in one transaction. Replacement-pair insertion failure now
rolls the entire transaction back. Added fault-injection coverage proving the
old pair remains usable and no partial new pair survives. OAuth modules passed
**37 tests**; the complete Gateway offline suite passed **395 / 9 skipped**
with explicit Docker/PostgreSQL/CPU integration inputs unset. One existing
Starlette deprecation warning. Follow-up PostgreSQL 16 concurrency regression
started two refreshes simultaneously and passed **1/1**: exactly one refresh
rotated the token and the other received `invalid_grant`; the dedicated DB
container was removed. `git diff --check` passed. Evidence:
`docs/acceptance/2026-10-28-oauth-refresh-atomicity.md`. The concurrency check
does not simulate a PostgreSQL insert failure or establish live ChatGPT
acceptance; parked mode remains unchanged.

Read-only external gate refresh at 2026-10-28 08:42 UTC: PR #51 remains
OPEN/DRAFT at `f054aebe96460fe033dde8d91d7e3bbab0255655`, based on
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`; submitted reviews and review
requests remain empty. Listed CI/Gateway/project/Vercel status checks are
successful for that pushed head only. GitHub still reports `main` unprotected.
The current 110-path local worktree is not covered by those checks. No GitHub
state changed.

### Current-worktree full Gateway revalidation — 2026-10-28

Revalidated all 110 current modified/untracked paths on base
`f054aebe96460fe033dde8d91d7e3bbab0255655` using digest-pinned local CPU and a
dedicated PostgreSQL 16 container: **403 passed, 2 skipped**, one existing
Starlette deprecation warning. This includes the simultaneous OAuth refresh
regression and existing PostgreSQL outage-after-capture/CPU container recovery.
The first invocation used `docker run --rm`; the recovery test intentionally
stopped PostgreSQL, which auto-removed that container and invalidated the run.
The corrected invocation omitted `--rm`, then removed the dedicated container
with an exit trap and passed. Full worktree content/status digest:
`61134cb0665c99cd8e3673e506b6a753ee60193a10df200f5a2a5f4b013be075`.
`git diff --check` passed; `mode: parked` remains. Evidence:
`docs/acceptance/2026-10-28-local-integration-revalidation.md`. This remains
local synthetic evidence; no ChatGPT workspace, Neon production database,
target host, provider API, GPU, or paid execution was used.

The full root/core suite then exposed one policy-fixture mismatch: PyYAML had
parsed the RunPod v1 retirement date as a native `date`, while the policy
contract and regression expect an ISO string. Quoted the date in
`policies/runpod-v2-policy.yaml`; the full root suite now passes **549 tests / 1
skip** in 0.90s. Current 110-path content/status digest after that fix:
`13be54a0d5ad50f0e0e666367bd7ca96b7bf97accf11b91e287e616fed6957f9`.
`git diff --check` passes. The one skip is an optional integration; this is
repository test evidence, not live RunPod acceptance.

### P3 systemd template revalidation — 2026-10-28

Re-ran `gateway/deploy/verify_systemd_units_ci.sh` in the cached Debian
12/systemd 252.39 image with network disabled and `gateway/` mounted read-only.
It verified all seven current service/timer templates with inert placeholders;
exit status 0, no diagnostics. Current helper and capacity bridge unit hashes
match the prior evidence snapshot. The `--rm` test container was removed; no
unit was started. Evidence:
`docs/acceptance/2026-10-28-systemd-uid-boundary.md`. This is static syntax and
reference validation only, not target-host acceptance.

### P3 operational command syntax audit — 2026-10-28

Ran `bash -n` on all fenced `bash`/`sh`/`shell` blocks in
`docs/OPERATIONS.md`, `gateway/README.md`, and `docs/CHATGPT_SETUP.md`: **19
blocks checked, 0 syntax failures**. No commands were executed. This confirms
shell syntax only; it does not validate host-specific paths, unit state, or
operational effects.


authenticated_preview_runtime_readiness_recheck_2026_10_28: Used Vercel's protected-URL fetch to perform read-only GETs against the PR #51 preview. `/healthz` returned 200 but `configured=false` and `auth_configured=false`; `/readyz` returned 503 with database, migration, worker, supervisor, registry, and authentication false; protected-resource discovery returned 503 `configuration_required`. The preview runtime is reachable but unconfigured and not ready for ChatGPT. The temporary Vercel share link was used only for the read-only requests; no app credentials, OAuth grant, ChatGPT connection, deployment/configuration change, or paid resource was used. Acceptance remains NOT RUN and `policies/repository-state.yaml` remains parked. Evidence: `docs/CHATGPT_ACCEPTANCE.md`, `docs/CHATGPT_SETUP.md`.

### P1 OAuth refresh current-worktree revalidation — 2026-10-28

Reviewed the current OAuth refresh diff and re-ran the focused OAuth/auth modules:
37 passed, one existing Starlette deprecation warning. Re-ran the PostgreSQL 16
concurrent one-time refresh regression with the digest-pinned image and the
repository's psycopg 3 URL dialect: 1 passed. The initial invocation omitted the
`+psycopg` dialect and failed before test execution because psycopg2 is not
installed; corrected invocation passed. The loopback-only disposable database
container was removed. The P1 scope and evidence are recorded in
`docs/acceptance/2026-10-28-oauth-refresh-atomicity.md`. No production database,
ChatGPT OAuth client, or deployed host was contacted; those acceptance gates
remain open.

### P3 artifact, capacity bridge, and systemd current-worktree revalidation — 2026-10-28

Re-ran artifact storage, backup generation, capacity event state, artifact
permission migration, and deployment-unit regression modules: **91 passed**,
one existing Starlette deprecation warning. Re-ran the seven-unit systemd
verification helper inside the cached Debian 12/systemd 252.39 image with
network disabled and the Gateway tree mounted read-only: exit 0, no diagnostics.
The initial attempt used plain Debian 12 without systemd and correctly stopped at
the helper preflight; the corrected run used the previously recorded systemd
image and `/bin/bash` entrypoint. See
`docs/acceptance/2026-10-28-systemd-uid-boundary.md`. This is focused local
regression and unit-reference evidence only; no services, target host, alert
sink, production backup, or live deployment were used.

### Current core/P4 contract regression — 2026-10-28

Ran the complete root/core test suite on the current worktree after the OAuth
and P3 focused checks: **549 passed, 1 skipped** in 0.84s. This validates the
repository's local core contracts and selector/provider policy tests. It does
not provide live provider evidence, real GPU execution, cost/quota verification,
or paid authorization; candidate-bound GPU execution remains unavailable and
`policies/repository-state.yaml` remains parked.

### Full local Gateway integration rerun — 2026-10-28

Re-ran all Gateway tests on the current dirty worktree with digest-pinned
PostgreSQL 16 and the existing digest-pinned CPU smoke image, using loopback-only
port 55548 and the stoppable database container expected by the recovery test.
Result: **403 passed, 2 optional Torch/Modal skips**, one existing Starlette
deprecation warning, 22.31 seconds. This includes MCP/HTTP, local CPU execution,
PostgreSQL lifecycle, artifact retrieval, refresh-token concurrency and outage
recovery. The disposable database container was removed by an exit trap and no
run-labeled test containers remained. `git diff --check` passes and parked mode
is unchanged. Scope and environment are in
`docs/acceptance/2026-10-28-local-integration-revalidation.md`; live ChatGPT,
Neon, target-host, GPU and paid acceptance remain unproven.

### Secure MCP Tunnel setup prerequisite refresh — 2026-10-28

Rechecked the current official OpenAI Help Center and Secure MCP Tunnel guide.
The guide explicitly requires a Platform `tunnel_id`, a runtime API key for
`tunnel-client`, an MCP server reachable over stdio or HTTP, Platform Tunnels
Read + Manage to create/edit, Tunnels Read + Use to run/select, and association
with the intended ChatGPT workspace. The official setup includes the current
client release, named profile, `doctor --explain`, and a continuously running
client during discovery/calls; it documents the 120-second request deadline and
10 MiB serialized envelope limit. Updated `docs/CHATGPT_SETUP.md` to include
these prerequisites without recording credentials. Local preflight found no
`tunnel-client` binary or running Gateway/tunnel process; no tunnel, app, key, or
workspace configuration was created. Evidence remains documentation-only; real
ChatGPT acceptance is NOT RUN.

### PR #51 preview runtime recheck — 2026-10-28 09:26 UTC

Read-only Vercel fetch of the latest READY preview for pushed head
`f054aebe96460fe033dde8d91d7e3bbab0255655`: `/healthz` 200 with
`configured=false` and `auth_configured=false`; `/readyz` 503 with database,
migration, worker, supervisor, registry, and authentication false; protected-
resource metadata 503 `configuration_required`. This confirms a build artifact,
not a configured P1 runtime. No Vercel settings, secrets, database, or deployment
were changed. Real ChatGPT and deployed CPU acceptance remain NOT RUN.

### P4 Gateway evidence and candidate-bound result contract slice — 2026-10-28

Reviewed the current P4 Gateway selection and receipt boundaries and ran the
targeted provider evidence, RunPod inventory, Modal billing-only, registry,
candidate receipt/result-read, local admission, and experiment API modules:
**90 passed**, one existing Starlette deprecation warning. These tests cover
offline evidence validation and exact-plan/result binding only. No live
RunPod/Modal account, provider API, GPU, quota, or billing path was accessed;
candidate-bound GPU execution remains blocked and paid execution remains
parked. PR #51 remote checks do not cover this dirty worktree.

### P4 zero-cost quota boundary review — 2026-10-28

A manual audit questioned whether current `FREE_QUOTA` evidence should offset a
positive gross run estimate for a zero-dollar request. The roadmap's explicit
invariant requires every charge component to be known and zero; quota balance
alone must not turn positive provider charges into a zero-cost claim. Kept the
selector behavior and added a regression that rejects a positive gross estimate
even when current quota evidence covers it and overage stops. The focused case
passed, followed by the complete core selector module: **54 passed**. This is
offline contract evidence only; no provider quota or live GPU was inspected.
The complete current root/core suite then passed **550 tests / 1 skip**
in 0.99 seconds. The skip is the Python 3.11-specific real decoder recursion
reproducer, not an optional provider SDK test. This is the first full-core rerun after the regression was
added; Gateway and deployed acceptance scopes were not rerun by this change.

### P1 Secure MCP Tunnel client preflight — 2026-10-28

Prepared the official OpenAI `tunnel-client` container without adding a native
binary to macOS. Pulled immutable image digest
`sha256:486321616c197fed2d3fbe7d44f22433ce9a1e6c1ee434c0d6652868a5fda5c1`,
and `gh attestation verify oci://ghcr.io/openai/tunnel-client:v0.0.18 -R
openai/tunnel-client` exited successfully. In the isolated container, version
was `0.0.18+274a5588414819f063d27100a4fb1096aae3830f`; `help quickstart` ran with
network disabled, read-only rootfs, dropped capabilities, and no-new-privileges.
Homebrew was unavailable because Xcode's license has not been accepted; that
system license was not accepted and Gatekeeper was not bypassed. No tunnel ID,
runtime key, Platform API request, local Gateway, ChatGPT workspace setting, or
OAuth grant was used. The pinned client is locally runnable, but tunnel and
ChatGPT acceptance remain NOT RUN. Full preflight record:
`docs/CHATGPT_ACCEPTANCE.md`.

### P1 OAuth reachability boundary for Secure MCP Tunnel — 2026-10-28

The official Secure MCP Tunnel guide distinguishes MCP transport from OAuth
authorization-server reachability: tunneling the MCP endpoint does not by
itself tunnel a private authorization server. Updated the setup guide and
acceptance table to require checking the discovered issuer, authorization,
token, and advertised revocation endpoints through the OAuth flow before
counting ChatGPT authentication as accepted. No tunnel, OAuth grant, or
workspace setting was used; this is a documented acceptance gate, not live
OAuth evidence.

### P0 GitHub main protection — 2026-10-28

The baseline API probe found `main` was unprotected (GitHub returned 404
`Branch not protected`). Configured and re-read branch protection: PR required,
one approval including a different approver from the latest pusher, stale
approvals dismissed, conversations resolved, linear/up-to-date history, admins
enforced, and force-push/deletion disabled. Required checks are the seven
current GitHub Actions check runs observed on PR #51, scoped to Actions app
15368. Afterward PR #51 remained OPEN/DRAFT with `REVIEW_REQUIRED`; its pushed
head's four workflow runs are successful. These do not cover the 111 dirty
local paths. No merge, push, deployment, provider call, or paid execution
occurred; repository policy remains parked. Full baseline: `docs/BASELINE_AUDIT.md`.

### Direct PostgreSQL v1-to-v8 migration regression — 2026-10-28

Added a PostgreSQL integration regression that creates a unique schema, builds
the actual unversioned v1 fixture, migrates it twice to current schema v8, and
verifies historical run identity/result, OAuth token preservation, and v8
provider-observation columns. The focused PostgreSQL 16 test passed **1/1** on
loopback using the pinned database image; its schema and disposable container
were removed. This closes the direct v1-to-v8 local regression gap only.
PostgreSQL 17, Neon behavior, production data, operator rollback, and production
migration remain unverified. See
`docs/acceptance/2026-10-28-local-integration-revalidation.md`.


## Final PostgreSQL compatibility rerun after URL fixture correction — 2026-10-28

- The v1 migration regression's secondary Store engine was receiving a
  password-masked SQLAlchemy URL (`***`). Updated the test to render with
  `hide_password=False`; production code was unchanged.
- Full Gateway/Docker CPU suite passed **416 tests, 2 optional skips** on
  PostgreSQL 16 and PostgreSQL 17.11. The tests ran against pinned disposable
  databases bound to loopback; containers and explicit volumes were removed.
- `git diff --check` and review-slice inventory are being refreshed for the
  resulting 115-path worktree; ownership-map inventory matched all 115 dirty paths
  exactly and `git diff --check` passed. This evidence remains local only.

## Live review-gate and local worktree refresh — 2026-10-28 10:45 UTC

- Current worktree remains `codex/chatgpt-cpu-vertical` at
  `f054aebe96460fe033dde8d91d7e3bbab0255655`, with 115 dirty paths. The
  sequential review-slice map matches every dirty path exactly. Local tests
  after the PostgreSQL URL fixture correction passed 416/2-skipped on
  PostgreSQL 16 and 17.11; `git diff --check` passed.
- Refreshed GitHub PR #51 through the connected GitHub API: OPEN, Draft,
  unmerged, mergeable, base `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`,
  remote head `f054aebe96460fe033dde8d91d7e3bbab0255655` (same as local HEAD),
  121 remote files. Reviews and inline review threads remain empty. All eight
  PR checks on that remote head are successful; they do not include the 115
  local dirty paths.
- Current Vercel preview check is build/check-status evidence only. It does not
  supply configured runtime, database, workspace, or ChatGPT acceptance for
  this local worktree. No deployment, OAuth grant, production migration,
  provider call, paid execution, commit, or push occurred. Parked mode remains.
- The next review gate is choosing between a general bug review and a security
  review, then reviewing the assigned slices against this exact worktree before
  considering any integration action.

## Roadmap dependency audit — 2026-10-28 10:47 UTC

- Re-read the current P0–P5 roadmap checkboxes against the worktree and
  acceptance records. P2 local lifecycle/recovery items are marked complete;
  that evidence is synthetic/local and does not close production recovery.
- The current critical path is external acceptance: verify the intended
  ChatGPT workspace's write-enabled custom MCP eligibility and connection;
  complete a real ChatGPT CPU run and cross-conversation result retrieval;
  choose and authorize a persistent host, region, public origin, budget ceiling,
  and alert route/SLO; then perform target-host and production-shaped recovery
  acceptance. P4 live GPU work follows CPU acceptance. P5 remains a separate
  paid-authorization gate.
- Local full Gateway/Docker/PostgreSQL suites and passing remote-head checks do
  not satisfy those gates. No selection or authorization was inferred from the
  existing shortlist. The machine policy remains `parked`.

## Capability heartbeat admission regression — 2026-10-28 11:04 UTC

- Added direct local coverage for the T6 rule that capabilities must not claim
  the CPU lane is runnable while either required background process is stale.
  With both heartbeats fresh, the registered local CPU workload is queue-ready;
  aging only `worker_seen_at` yields `WORKER_OFFLINE`, and aging only
  `supervisor_seen_at` yields `RECOVERY_SUPERVISOR_OFFLINE`.
- This records existing behavior; no production code changed. Focused experiment
  API tests: **39 passed**, one existing Starlette deprecation warning. Full
  Gateway offline suite: **409 passed, 11 skipped**, one existing warning;
  skips were optional Torch/Modal SDKs and unconfigured Docker/PostgreSQL
  integration inputs. Prior PostgreSQL-backed full integration evidence remains
  separately documented and did not include this new test.
- This does not establish process uptime, deployed readiness, ChatGPT tool
  acceptance, or seven-day operations. Parked mode remains unchanged.

## Security review finding adjudication — 2026-10-28

- The read-only review of the uncommitted diff reported that
  `GET /oauth/authorize` issues authorization codes without owner consent.
  This finding does not match the checked-out code: `GET` only validates the
  request and renders the consent form; authorization-code creation occurs in
  `POST /oauth/authorize` after same-origin and persisted-session CSRF checks
  and an explicit `decision=approve`.
- The consent implementation is already present in base `HEAD`
  `f054aebe96460fe033dde8d91d7e3bbab0255655`, so it is not a regression or
  omission in this uncommitted diff. The existing targeted regression passed:
  **1 passed**, one Starlette deprecation warning. It asserts that GET creates
  no code, deny creates no code, and missing-CSRF/wrong-origin approvals fail.
- Adjudication: false positive for the current checkout; no code fix or repeat
  review was performed. The reviewer reported no additional actionable issue
  in the other changed security-sensitive areas it checked. This local review
  does not replace a GitHub review of a pushed head or ChatGPT/production
  acceptance.

## OAuth protocol regression revalidation — 2026-10-28

- Re-ran the current local OAuth and HTTP-auth contract suites with the Gateway
  virtualenv: `gateway/.venv/bin/python -m pytest -o addopts= gateway/tests/test_local_oauth.py gateway/tests/test_http_auth.py -q`.
  Result: **35 passed**, one existing Starlette deprecation warning.
- Covered local protocol cases include PKCE authorization, redirect/client
  binding, explicit consent and CSRF/origin checks, refresh-token rotation and
  revocation, scope enforcement, invalid audience/issuer/subject/time claims,
  and local owner/session boundaries.
- The first attempt used the repository-root `.venv`, which lacks Gateway's
  `jwt` dependency and failed during test collection; the Gateway environment
  is the correct one and the complete targeted rerun passed.
- Scope remains local tests only. This does not verify ChatGPT's live OAuth
  flow, deployed issuer/revocation endpoints, workspace action permissions,
  or production owner isolation. The roadmap OAuth acceptance item remains
  open pending live acceptance.

## Paired backup generation contract revalidation — 2026-10-28

- Re-ran `gateway/.venv/bin/python -m pytest -o addopts=
  gateway/tests/test_backup_generation.py -q`: **20 passed**, one existing
  Starlette deprecation warning.
- This is the focused backup-tool contract suite, including stopped-service
  attestation, database quiescence and unsettled-run refusal, atomic generation
  publication, manifest/checksum/archive validation, and unsafe artifact
  archive rejection. It does not perform a database or filesystem restore.
- Existing PostgreSQL 16/17 paired restore drills remain synthetic local
  evidence in `docs/acceptance/2026-10-28-paired-artifact-restore.md` and
  `docs/acceptance/2026-10-28-atomic-backup-generation.md`. Neon behavior,
  production backup, target-host permissions, independent second-operator
  reproduction, and measured RPO/RTO remain unverified. The P3 recovery gate
  stays open.

## Full Gateway Docker/PostgreSQL revalidation — 2026-10-28

- Ran the complete Gateway suite with the digest-pinned local CPU image and a
  disposable loopback-only PostgreSQL 16 container. Result: **418 passed, 2
  skipped**, one existing Starlette deprecation warning. Skips were optional
  Torch/Modal SDK checks.
- The run covered actual local Docker CPU execution, artifact retrieval, worker
  crash recovery, PostgreSQL-backed lifecycle behavior, and database outage
  recovery. Exact environment, base SHA, diff digest, and cleanup observations
  are in `docs/acceptance/2026-10-28-local-integration-revalidation.md`.
- The dedicated database container was removed. Two run-labeled exited CPU
  containers found afterward predated this run by hours and were left
  untouched. This remains local integration evidence, not ChatGPT or
  production acceptance; parked mode remains in force.

## Deployment preflight recheck — 2026-10-28 11:02 UTC

- Read-only Vercel listing still points the READY PR preview at HEAD
  `f054aebe96460fe033dde8d91d7e3bbab0255655`. Authenticated `/readyz` on that
  preview returned 503 with database, migration, worker, supervisor, registry,
  and authentication all false.
- Public alias probe: `/healthz` and both OAuth discovery documents returned
  200, unauthenticated `/mcp` returned 401, and `/readyz` returned 404. The
  public alias therefore does not expose the current readiness route; the
  preview has the route but lacks runtime configuration.
- No deployment or environment configuration changed and no ChatGPT OAuth or
  tool call occurred. This is deployment-preflight evidence only. Details are
  recorded in `docs/CHATGPT_ACCEPTANCE.md`; P1 external acceptance remains
  open.
- Reconciled `docs/RELEASE_MATRIX.md` with the current 418-test PostgreSQL 16
  integration run and this live deployment observation. MCP connectivity and
  ChatGPT tool usability are now explicitly BLOCKED at the deployment/workspace
  acceptance boundary; local CPU and recovery remain PASS only for their local
  lanes. Relative links and `git diff --check` pass. PR #51 remains
  OPEN/DRAFT/REVIEW_REQUIRED; no push or external configuration change was
  made.

## Root/core regression revalidation — 2026-10-28

- Current root/core suite: `./.venv/bin/pytest -o addopts= -q -rs` — **550
  passed, 1 skipped** in 0.83 seconds. The skip is
  `tests/test_runpod_log_results_malformed.py:71`, whose real decoder recursion
  reproducer is Python 3.11-specific; the suite ran under Python 3.12.
- This suite covers the offline P4 capability, selection, pricing-evidence,
  RunPod v2 payload/adapter, and repository-policy contracts. Skipping the
  Python 3.11-specific reproducer does not imply a provider account, live
  quota, GPU device, provider cleanup, or paid execution.
- No implementation files changed for this run. The P4/P5 release statuses
  remain BLOCKED on current live provider/GPU and separate paid-authorization
  evidence; parked mode remains unchanged.

## P3 artifact/capacity/systemd revalidation — 2026-10-28

- Focused artifact storage, backup generation, capacity-event state, artifact
  permission migration, and deployment-unit tests: **92 passed**, one existing
  Starlette deprecation warning.
- The guarded systemd helper passed for all eight current service/timer units
  in the cached Debian 12/systemd 252.39 container with networking disabled
  and the Gateway tree mounted read-only. No service ran; the `--rm` container
  was absent in the follow-up inventory.
- Two initial harness invocations stopped before verification due to local
  image-name/working-directory mistakes; the corrected invocation passed.
  Evidence and exact inputs are recorded in
  `docs/acceptance/2026-10-28-systemd-uid-boundary.md`. Target-host runtime,
  mount filtering, notifications, quota, and production recovery remain
  unverified.

## P4 RunPod v2 and selection regression — 2026-10-28

- Re-ran current v2 payload/policy, adapter, selection, and capability modules:
  **120 passed**. Command and module list are in
  `docs/acceptance/2026-10-28-runpod-api-v2-revalidation.md`.
- This is offline schema/policy/adapter evidence only. No provider account,
  credentials, API request, live quota, GPU device, allocation, or cleanup was
  exercised. Free GPU remains BLOCKED on live evidence; paid execution remains
  separately parked.

## P1 public endpoint recheck — 2026-10-28 11:13 UTC

- Read-only unauthenticated requests to `https://gpu-control.vercel.app`:
  `/healthz`=200 with configured local OAuth, `/readyz`=404, protected-resource
  and authorization-server discovery=200 (authorization code, refresh token,
  PKCE S256 and revocation advertised), and `/mcp`=401 requiring a bearer
  token. This confirms only liveness, discovery metadata, and the unauthenticated
  boundary; deployed SHA, database/worker readiness, OAuth grant, ChatGPT tool
  discovery, and tool calls remain unverified.
- No local Gateway/worker/tunnel process or port-8000 listener was present.
  No token, authenticated request, ChatGPT workspace setting, deployment, or
  runtime service was changed. P1 ChatGPT acceptance remains NOT RUN; the
  endpoint evidence is recorded in `docs/CHATGPT_SETUP.md` and
  `docs/CHATGPT_ACCEPTANCE.md`.
- Vercel project/deployment metadata confirms the latest READY preview remains
  PR #51 head `f054aebe96460fe033dde8d91d7e3bbab0255655`, while the production
  alias is a separate configured-OAuth deployment without `/readyz`. A
  read-only environment-variable metadata request was denied with HTTP 403;
  the local Vercel CLI is not installed, so no environment names or values
  were retrieved. The preview's DB/OAuth/worker configuration cannot be
  diagnosed from this account permission, and no environment setting was
  changed.

## P3 backup publication fault-injection follow-up — 2026-10-28

- Added failure-injection coverage for `pg_dump` and `pg_restore --list` in
  `gateway/tests/test_backup_generation.py`. Both cases verify that the
  private staging directory is removed and no partial backup generation is
  published. Focused suite: **22 passed**, one existing Starlette
  deprecation warning. No database, target host, or real backup was used.
- Evidence: `docs/acceptance/2026-10-28-atomic-backup-generation.md`.
  Production/second-operator recovery, encrypted off-host retention, and
  measured RPO/RTO remain open; repository policy remains `parked`.

## P3 artifact permission migration retry follow-up — 2026-10-28

- Added a mid-apply ownership failure regression for
  `gateway/deploy/migrate_artifact_permissions.py`. After root/scope ownership
  is changed and blob ownership fails, payload bytes remain intact; rerunning
  the idempotent operation completes the exact root/scope/blob/probe mode
  contract. Focused suite: **9 passed**, one existing Starlette deprecation
  warning. This is a local filesystem fixture only, not target-host
  permissions or migration acceptance.
- Evidence: `docs/acceptance/2026-10-28-artifact-storage.md`; `mode: parked`
  remains.

## Long-term goal continuation and snapshot reconciliation — 2026-10-28 11:49 UTC

- The active Codex goal remains the complete ChatGPT-native experiment path:
  real registered CPU execution and result retrieval first, then recovery and
  operations, real GPU validation, and paid execution only under a separate
  explicit authorization. The detailed long-term sequence and current gates
  are in `docs/superpowers/plans/2026-10-28-gpu-control-roadmap.md`.
- Re-counted the current worktree: 75 tracked modified/deleted files plus 42
  untracked files, 117 unique paths total, zero staged. The exact path ownership
  map is `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`.
  `git diff --check` passes. Remote PR checks cover only pushed HEAD
  `f054aebe96460fe033dde8d91d7e3bbab0255655`; they do not cover these local
  changes. Prior Codex Security scans are bound to earlier snapshots and do not
  establish coverage of this exact current worktree.
- The current ChatGPT and Platform browser session is logged out. Workspace
  write-action eligibility, tunnel association, and live OAuth remain
  unverified; no account setup or authenticated request was attempted. The
  earlier review-mode choice (Bugbot or Security Review) is still unanswered,
  so that workflow has not been started.
- No code, runtime, deployment, database, GitHub, provider, or spending state
  changed in this continuation. `policies/repository-state.yaml` remains
  `mode: parked`. The Luna handoff now records the exact continuation snapshot
  and dependency order.

## PR and review-gate revalidation — 2026-10-28 11:51 UTC

- Refreshed PR #51 through the connected GitHub API: still OPEN, Draft,
  unmerged, and mergeable; base remains `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`
  and pushed head remains `f054aebe96460fe033dde8d91d7e3bbab0255655`.
  Submitted reviews and inline review threads both remain empty. The PR body
  itself says independent review and real ChatGPT/host acceptance are
  incomplete. Its remote checks cannot cover the uncommitted 117-path local
  diff.
- The resulting next action remains to review the exact local diff before
  publishing any reviewable slice. The previously presented Bugbot vs Security
  Review choice is still unanswered; no review workflow or PR write was
  triggered by this read-only refresh.

## Public MCP endpoint recheck — 2026-10-28 11:52 UTC

- Unauthenticated read-only GETs to the public Vercel alias returned
  `/healthz` 200 with configured local OAuth, OAuth authorization-server
  discovery 200, `/mcp` 401 (`invalid_token`), and `/readyz` 404. The preview
  hostname returned Vercel Authentication 401 to unauthenticated requests;
  this probe did not refresh authenticated preview state. Evidence is recorded
  in `docs/CHATGPT_ACCEPTANCE.md` and `docs/RELEASE_MATRIX.md`.
- This confirms the public alias is not exposing the current readiness route;
  it does not identify which revision is deployed or prove ChatGPT acceptance.
  No credentials, workspace, deployment configuration, OAuth grant, database,
  provider, or paid resource was changed. P1 live acceptance remains NOT RUN.

## P1 OAuth slice independent Security Review — 2026-10-29 02:40 UTC

- After the user selected Security Review, one read-only independent review was
  completed for the uncommitted P1 OAuth refresh-rotation, scope-validation,
  and PostgreSQL concurrency slice: `gateway/gpu_gateway/local_oauth.py`,
  `gateway/tests/test_local_oauth.py`, `gateway/tests/test_postgresql.py`, and
  `docs/acceptance/2026-10-28-oauth-refresh-atomicity.md`. The reviewer found
  no actionable findings in that slice. This is not a review of the entire
  117-path worktree or the pushed PR head; no tests were run and no files were
  changed by the reviewer.
- Fresh browser inspection showed ChatGPT displays Log in / Sign up; the
  Platform tunnel-settings URL redirects to Platform login. No account,
  workspace, tunnel, permissions, key, or setting was accessed or changed.
  Real ChatGPT acceptance remains NOT RUN; this does not prove the user lacks
  an eligible workspace.
- `git diff --check` passes and `policies/repository-state.yaml` remains
  `mode: parked`. No deployment, GitHub write, provider call, or paid action
  occurred.

## Public endpoint recheck — 2026-10-29 02:41 UTC

- The public Vercel alias again returned `/healthz`=200 with configured local
  OAuth, OAuth authorization-server discovery=200, unauthenticated `/mcp`=401,
  and `/readyz`=404. The readiness-route gap persists. Exact status was added
  to `docs/CHATGPT_ACCEPTANCE.md` and `docs/RELEASE_MATRIX.md`.
- No authenticated ChatGPT/Platform session, OAuth grant, deployment setting,
  or runtime was used or changed. End-to-end ChatGPT acceptance remains NOT
  RUN; this probe does not establish the deployed source revision.

## Continuation regression and live-state refresh — 2026-10-30

- Revalidated the current 117-path uncommitted worktree: `git diff --check`
  passes, the root suite passes **550 tests / 1 skip**, and the full offline
  Gateway suite passes **413 tests / 12 skips** with one existing Starlette
  deprecation warning. The Gateway run did not configure PostgreSQL/Docker
  integration variables; it is not a repeat of the separately recorded
  PostgreSQL 16 + local Docker integration run.
- A current read-only GitHub query confirms PR #51 is still OPEN/DRAFT at
  pushed head `f054aebe96460fe033dde8d91d7e3bbab0255655`, with review required.
  Its successful checks completed on 2026-10-28 and cover the pushed head, not
  these uncommitted changes.
- Fresh unauthenticated requests to the production alias returned `/healthz`
  200, `/readyz` 404, and `/mcp` 401. Current source contains the readiness
  route; the production alias still serves a revision without it. This does
  not establish ChatGPT acceptance or production readiness. No GitHub write,
  deployment, OAuth grant, provider call, or paid action occurred.

## PR CI and preview source verification — 2026-10-30

- Pushed `4a0597782da50eb90697bb280f036dcd26c446d7` to Draft PR #51. All
  required workflow checks passed on that SHA. The Gateway workflow ran the
  Linux systemd template verifier and the real local CPU + PostgreSQL lifecycle
  suite (**424 passed, 1 skipped**, one Starlette deprecation warning). Root
  CI passed Python 3.11, 3.12, and 3.13; trusted reference container and both
  bridge suites also passed. This is CI evidence, not deployed production or
  ChatGPT acceptance.
- Vercel's read-only deployment record identifies preview deployment
  `dpl_A3SApn6Ry5Ys9UN3vZSQWqw6GWQj` as READY from the exact PR SHA above.
  Project metadata says SSO protection is enabled for previews. An unauthenticated
  HTTP fetch of the preview is redirected to Vercel login, so its runtime
  `/readyz` response remains unobserved. Asked the owner whether a temporary
  (up to 23-hour) Vercel share link may be created/reused solely to GET
  `/healthz` and `/readyz`; no share link has been created.
- PR #51 remains OPEN/DRAFT with `REVIEW_REQUIRED` and no submitted reviews.
  Production alias still returns `/healthz`=200, `/readyz`=404, `/mcp`=401.
  Repository paid-execution policy remains `mode: parked`.

## Production source comparison and preview access boundary — 2026-10-30

- Read-only Vercel deployment metadata resolves `gpu-control.vercel.app` to
  production deployment `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`, source `main` at
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. This predates the PR #51 CPU
  vertical. The current PR branch remains OPEN/DRAFT with
  `REVIEW_REQUIRED`; its CI is green and the corresponding preview is READY.
- Direct unauthenticated requests to production still return `/healthz`=200,
  `/readyz`=404, `/mcp`=401. Vercel project metadata confirms preview SSO
  protection (`all_except_custom_domains`); direct preview requests redirect
  to Vercel login. Thus the preview deployment exists, but its app-level
  readiness response has not been observed.
- A names-only Vercel environment-variable inventory request
  (`decrypt=false`, preview branch filter) was denied with HTTP 403. The local
  `vercel` CLI is not installed. No environment values were requested or read;
  this is an access boundary and does not prove that runtime variables are
  absent. No protection setting, deployment, secret, OAuth grant, provider, or
  paid resource was changed. Temporary share-link authorization remains
  unanswered; no link was created. ChatGPT acceptance remains **NOT RUN**.
