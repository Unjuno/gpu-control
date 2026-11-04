# Implementation progress

### P1 admission-aware readiness candidate replay on PR #57 — 2026-10-31

- Reconstructed the three-file local CPU readiness/admission delta on an
  isolated worktree at exact PR #57 head `51b88f6`, instead of trying to apply
  the aggregate PR #51 overlay. Candidate patch:
  `/tmp/gpu-control-p1-readiness-on-57.patch`, SHA-256
  `03edebebd511a341272b6cd66bcdd5c597d69a8f7c5ff84bd40d54fe738eb118`.
- Confirmed both `gpu_gateway` and shared `gpu_control` imported from the
  candidate worktree, then ran its complete Gateway suite: **246 passed, 9
  skipped**. Skips are optional Torch/Modal dependencies and unconfigured
  Docker/PostgreSQL integrations. `git diff --check` passed. Details:
  `docs/acceptance/2026-10-31-p1-readiness-review-candidate-on-57.md`.
- This resolves the source-base mismatch for a bounded P1 readiness review
  candidate only. GitHub CI/review, authenticated ChatGPT OAuth/tool use,
  deployed `/readyz`, ChatGPT CPU execution, and result retrieval remain open.
  No PR/ref/deployment/account/provider/policy state changed; preserve parked
  mode.

### Current Gateway offline regression after P4 credit-verifier addition — 2026-10-31

- Re-ran the full Gateway suite from the active dirty source tree:
  **484 passed, 15 skipped**, one existing Starlette deprecation warning.
  Skips are optional Torch/Modal dependencies and Docker/PostgreSQL integration
  fixtures not configured for this invocation. This is regression coverage for
  the current Gateway modules, not the source-matched CPU/PostgreSQL acceptance.
- The focused P4 credit and P5 paid authorization suites passed **52 tests**;
  `git diff --check` passes. The P4 ownership map now covers the current dirty
  overlay exactly: 67 paths, no missing or stale assignments.
- The existing six-group candidate patch set predates the credit-boundary
  addition and must be regenerated before any publication. Current upstream
  divergence is 55 commits ahead / 56 behind. GitHub PRs #57/#58 remain Draft
  with no GitHub reviews. Repository remains parked; live ChatGPT acceptance,
  deployment, and provider execution remain unverified.
- Fresh external-gate check at 2026-10-30 23:07 UTC: the visible ChatGPT tab
  is logged out. GitHub reports PR #57/#58 OPEN/DRAFT with no reviews and
  successful latest workflow runs; their Vercel statuses are successful too.
  PR #51 remains a broad Draft aggregate. These remote checks exclude the
  dirty local source and establish neither runtime readiness nor ChatGPT
  execution acceptance.
- Tested PR #58's schema-v9 changes against exact PR #57 head in a temporary
  detached worktree. Direct application failed across five OAuth/migration
  paths; a three-way replay also conflicted because the #58 base depends on
  PR #51's schema-v8 provider-observation migration and evolved OAuth code.
  Removed the temporary worktree and patch files; primary refs remained
  unchanged. The schema-v9 follow-up must stay after schema-v8 in any split PR
  sequence unless the migration ordering is redesigned and retested.

### Exact current-source candidate reconstruction on PR #51 — 2026-10-31

- Re-read current checkout and GitHub state. Primary HEAD is
  `a794438f42bd7246f463eaaa40d963af0aae9d13`; PR #51 remains OPEN/DRAFT at
  `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`. PRs #52–#59 remain OPEN/DRAFT;
  #52 still requires review, and the reviewed local/source ranges do not
  constitute GitHub approvals.
- Reconstructed the full primary source tree (committed changes plus the 61
  dirty/untracked paths) on an isolated detached worktree at PR #51's exact
  head. All 339 files matched byte-for-byte. The replay patch is
  `/tmp/gpu-control-full-current-on-e3ffcef.patch`, SHA-256
  `c0a4b9e9deb8ecf7fe5b24e401ce6da777291c469845dd3175101d9b94c5f8d7`.
- Exact candidate Gateway suite: **482 passed, 2 skipped**, one Starlette
  deprecation warning; PostgreSQL 16 and real local Docker CPU/MCP integration
  enabled. Exact candidate Core suite: **559 passed, 1 skipped**. The separate
  acceptance record contains image/database inputs and scope.
- A preliminary replay that applied only the 61 dirty paths to PR #51 passed
  Gateway 471/2 and Core 559/1, but omitted committed source differences from
  primary HEAD. That partial run is explicitly superseded by the full 339-file
  reconstruction and is not current-source candidate evidence.
- `git diff --check` passed. No branch/ref, GitHub PR, review, deployment,
  account, provider, or policy state was changed. Repository state remains
  parked. This improves local provenance only; GitHub checks/review, deployed
  readiness, and authenticated ChatGPT acceptance remain open.
- Refreshed GitHub PR range metadata: #51–#59 are all OPEN/DRAFT, each with
  nine successful status entries and zero submitted reviews; #52 reports
  `REVIEW_REQUIRED`. #51 has 100 changed paths from #57; #52 has 43 paths to
  main, followed by stacked #53–#57; #58 is a seven-path schema-v9 follow-up
  to #51; #59 is a 14-path P3 change from #57. #51 and #59 share 13 paths, but
  only two final blobs are identical; reconcile the other 12 before deciding
  how the P3 update should join a reviewed stack. Full map is in
  `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`.
- Compared each PR head's final content on every changed path to the current
  local source. Match counts: #51 64/100, #52 6/43, #53 0/19, #54 1/21, #55
  6/38, #56 12/25, #57 18/54, #58 6/7, #59 5/14. These are byte-match
  provenance counts, not test or review results. Existing PR heads do not
  reproduce the current source as-is; candidate diffs must be rebuilt from
  their intended base and exact current source tree.

current_worktree_systemd_template_revalidation_2026_10_31: Re-ran `gateway/deploy/verify_systemd_units_ci.sh` from the current Gateway tree in cached `mixed-formal-2992-debian:20260920` (Debian 12/systemd 252.39, image digest `sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`). With `--network none`, a read-only source mount, and inert guard variables, it exited 0 without diagnostics for all eight service/timer templates; helper SHA-256 `569261ffcd54de9d921d2d1361fa6deec044598e9ae4bbe3f312ed5bcf683d34`. The `--rm` container was absent after the run and no service started. This advances local P3 syntax/reference evidence only; target-host startup, filesystem mount and permission behavior, alert delivery, and production restore remain unverified. Preserve parked mode.

```text
current_phase: P0 baseline audit, P1 registered CPU/MCP lifecycle, and P2 local recovery have passed their documented local scopes. P1 still lacks a reviewed/deployed readiness endpoint and actual ChatGPT OAuth, CPU execution, and cross-conversation result acceptance. P3 has local deployment/backup/systemd foundations but no selected/accepted host or seven-day operation. P4 selection and candidate receipt contracts are offline only; no real GPU has been accepted. P5 has account-lease and signed-authorization primitives, but no trusted issuer, Worker paid-authorization integration, revocation source, or live RunPod path. Keep all later stages distinct and repository state parked.
current_task: Read-only refresh at 2026-10-31 11:20 JST: PRs #51–#59 remain OPEN/DRAFT; each has nine successful published statuses and no GitHub review, while #52 and #43 report REVIEW_REQUIRED. PR #58 is at 561a6c7. Production deployment metadata remains main SHA 24ecb9b; live probes returned /healthz 200, /readyz 404, /mcp 401, and OAuth metadata 200. The 11:12 JST direct Preview check found PR #58 READY but its /healthz and /readyz redirect to Vercel SSO (302). Latest local tunnel-client v0.0.19 CLI preflight passed, but source inspection shows local built-in DCR points to loopback; external OIDC mode requires an issuer supporting ChatGPT client registration and the exact MCP resource audience. No ChatGPT OAuth/tool/CPU acceptance is established. Preserve mode: parked; keep real GPU and paid execution gates closed.
local_slice_validation_2026_10_30: At temporary detached worktree `f054aebe`, composed the P1, P3, P4, P5, and cross-cutting path slices from `f054aebe..aa681f4`. The initial test attempt imported the editable install from the primary checkout and is invalid evidence. Re-ran with `PYTHONPATH` pointing at the temporary worktree's `gateway/` and `src/`, confirming module paths first. All 117 changed paths matched committed `aa681f4`. Correctly sourced focused tests passed: P1/P3 Gateway 131 passed / 9 skipped; P4 Gateway 135 passed; P4 root/core 167 passed; P5 repository-state policy 4 passed. These reused installed primary-checkout dependencies, not fresh locked installs. No per-slice GitHub CI or full CI matrix was run; no PR refs were created or changed. Updated slice ownership is P1=4, P3=49, P4=49, P5=3, cross-cutting=12, exact 117-path coverage.
candidate_boundary_preflight_2026_10_30: Inspected all 14 proposed foundation/recovery/artifact ranges in temporary detached worktrees. Exact adjacent-range `git diff --check` and path counts matched the plan; representative Gateway modules resolved from each candidate worktree's `gateway/` tree using `PYTHONPATH`, not the primary checkout. For the readiness/cost/heartbeat boundary, grouped `74f004a` with the `0d02058` test correction; do not use the inconsistent `74f004a` intermediate as a PR head. No pytest, migration, Docker, PostgreSQL, or GitHub CI was run for these subdivided candidates. Temporary worktrees were removed; no branch refs were created or changed.
candidate_range_changed_tests_2026_10_30: Re-ran each of the 14 exact adjacent candidate ranges from a temporary detached worktree at the candidate head. For each range, ran only tests changed in that range with `PYTHONPATH` set to that worktree's `gateway/` and `src/`; reused primary Gateway Python 3.12 dependencies and supplied cached CPU image digest `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e` with synthetic all-`a` fixture source SHA for applicable real Docker tests. First pass: 294 passed / 10 PostgreSQL tests skipped. Re-ran the four affected ranges with a fresh PostgreSQL 16 container per range, pinned to digest `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`, bound only to `127.0.0.1:55494`, and with both `GATEWAY_TEST_DATABASE_URL` and `GPU_CONTROL_POSTGRES_CONTAINER` set. Those ranges passed 18, 34, 15, and 47 tests respectively with no skips. Effective total: **304 passed, 0 skipped, 0 failed** across changed-test subsets; range 7 has no changed test files. Each pytest invocation emitted the existing Starlette deprecation warning. All temporary containers and worktrees were removed; primary refs unchanged. This is focused candidate-source behavior with reused dependencies and local fixtures, not clean locked-environment validation, full suite per candidate, GitHub CI, independent review, or PR approval.
candidate_range_fresh_environment_revalidation_2026_10_30: Created disposable Python 3.12.13 venv; installed Gateway `requirements-test.txt` and `requirements-worker.txt` from `gateway/` per the workflow command; `pip check` passed (pytest 9.2.0, Modal 1.5.5). Re-ran all 14 candidate changed-test subsets with candidate worktree `gateway/` and `src/` at the front of `PYTHONPATH`, and dedicated loopback PostgreSQL 16 containers for ranges 5, 8, 12, and 13. Results: 304 passed, 0 skipped, 0 failed; range 7 had no changed tests. The worker unit from range 7 was separately verified using `systemd-analyze verify` on exact candidate `cc1e263` in cached Debian 12/systemd 252.39, `--network none`, read-only source mount, and inert placeholders; no service started. This clean pip environment is not `uv sync --locked` or CI; CPU integration still used the synthetic all-`a` image source SHA. Temporary venv/worktree/containers removed; primary refs unchanged. Candidate-specific CI, review and publication remain open.
gateway_ci_build_runtime_and_full_clean_suite_2026_10_30: Reproduced Gateway workflow package steps locally: `uv build gateway --wheel` succeeded; `UV_PROJECT_ENVIRONMENT=/tmp/.../runtime-venv uv sync --project gateway --locked --no-dev` succeeded; locked runtime imports passed. Installed the built wheel into the disposable runtime venv and verified `gpu_gateway` resolves from site-packages. In a separate new Python 3.12.13 venv, installed `requirements-test.txt` and `requirements-worker.txt` from the Gateway directory; `pip check` passed (pytest 9.2.0, Modal 1.5.5). Full Gateway suite with a disposable PostgreSQL 16 instance on loopback port 55496 and cached CPU image: **424 passed, 1 skipped** in 23.83s; only optional Torch test skipped. This included local Docker CPU/MCP/artifact and PostgreSQL outage recovery. Limits: host is macOS arm64, uv 0.11.17 vs workflow-pinned 0.10.0, CPU image source revision is synthetic, and no new GitHub Actions run was triggered. Temporary wheel/runtime/test venvs and PostgreSQL container were removed. This does not establish ChatGPT, production, real GPU, or paid execution acceptance.
followup_slice_patch_preflight_2026_10_30: Regenerated P1/P3/P4/P5/cross-cutting patches from `f054aebe` to committed HEAD and applied them sequentially in a detached worktree. All five patches applied and all 117 paths matched the target commit's blob/existence exactly (74 modified, 42 added, 1 deleted). This proves patch assembly/coverage only; individual-slice runtime tests and CI remain outstanding. Temporary worktree removed; branch refs unchanged.
local_cpu_container_validation_2026_10_30: On committed control-plane HEAD `aa681f4062dac6b73bcf380a38a4258b96a47e1`, supplied cached CPU image digest `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e` only to Gateway tests. Its OCI source/revision labels match repository `Unjuno/gpu-control` and synthetic fixture SHA `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`. Three real Docker CPU/MCP/lifecycle tests passed. Follow-up created disposable PostgreSQL 16 on loopback port 55493 with the exact cached digest and enabled `GPU_CONTROL_POSTGRES_CONTAINER`; the DB-outage-after-capture same-run recovery test passed (1 passed, 5.35s), and the full Gateway suite passed **423 passed, 2 skipped** (only optional Torch/Modal SDKs; 1 Starlette deprecation warning, 23.08s). The first DB-enabled invocation used the wrong container environment variable and skipped the outage test; it is not counted as recovery evidence. The corrected focused test and full suite both ran successfully. The temporary PostgreSQL container was removed by the exit cleanup; no running containers remained. Source identity is synthetic, and this remains local fixture integration, not ChatGPT, target-host, or production database acceptance.
systemd_template_verify_2026_10_30: All eight service/timer templates passed `systemd-analyze verify` in a disposable Debian 12/systemd 252.39 container with `--network none` and a read-only Gateway mount. Inert placeholder users/groups/files were created inside the container. The GitHub-Actions-only helper was not invoked; no unit started. Template syntax/reference evidence only, not target-host startup.
root_core_validation_2026_10_30: From repository root, `./.venv/bin/python -m pytest -o addopts= -q -rs` on committed HEAD `aa681f4`: 550 passed, 1 skipped in 0.91s. The skip is the Python 3.11-only malformed-RunPod-log recursion reproducer. This is offline/local evidence; no provider request was made.
postgres_outage_recovery_revalidation_2026_10_30: Recreated isolated PostgreSQL 16 from pinned local digest `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`, published only on `127.0.0.1:55493`. With `GPU_CONTROL_POSTGRES_CONTAINER` correctly set, `tests/test_postgres_lifecycle_integration.py` passed 1/1 and the full Gateway suite passed 423/2 skipped (Torch/Modal optional SDKs only). The outage test stopped and restarted the dedicated container while preserving and recovering the same run. Container cleanup ran on exit; follow-up inventory found no matching container. This proves the local PostgreSQL fixture path only, not Neon, production, second-operator restore, or measured RPO/RTO.
latest_verified_turn: On 2026-10-30 14:38 UTC, the current local Gateway source at `aa681f4` registers `/readyz`, while `origin/main` at `24ecb9b` has only `/healthz`. A fresh public alias check returned `/healthz` 200, `/readyz` 404, and `/mcp` 401. The response does not identify the deployed SHA; the result is consistent with an older route table but deployment provenance is unverified. PR #51 remains OPEN/DRAFT at `aa681f4`, review-required; all nine visible checks/statuses were successful at 14:35 UTC. Local full Gateway suite: 426 passed, 2 optional skips. No GitHub writes/deployment; repository mode remains parked.

vercel_source_provenance_recheck_2026_10_30_1718_utc: Vercel read-only deployment record and build events identify the READY PR preview as `Unjuno/gpu-control`, branch `codex/chatgpt-cpu-vertical`, commit `aa681f4062dac6b73bcf380a38a4258b96a47e1d`; latest production deployment remains `main` at `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. Thus the preview covers pushed HEAD only, not dirty local changes. No protected preview runtime request or environment/secret read was made. Public production `/readyz` remains 404, and ChatGPT acceptance remains unverified. See `docs/CHATGPT_ACCEPTANCE.md`.

trusted_reference_container_local_recheck_2026_10_30_1723_utc: Reproduced `.github/workflows/ci.yml`'s trusted reference workload on the current checkout with the same network/read-only/capability/PID/memory/CPU/tmpfs bounds and host-only sentinel check. The local container emitted the expected success result and all isolation assertions passed; image manifest digest was `sha256:feec6366e18bd63ab1c3434312b98066b6e0460bc8a4701ab6ca0c0f8680c52d`. A first harness attempt could not invoke GNU `timeout` on macOS and failed before container start; reran with Python subprocess's equivalent 30-second timeout and verified cleanup. This remains local arm64 evidence, not the Ubuntu GitHub check or a PR-head result. Full record: `docs/acceptance/2026-10-30-current-worktree-source-matched-suite.md`.

required_bridge_workflows_local_recheck_2026_10_30_1726_utc: On the current checkout, Gateway comment bridge tests passed 81/1 skipped (optional Torch) and the workflow's real tiny-LM container passed at 40 steps with `gpu_used=false` and lower final loss; Project bridge unittest discovery passed 19/19 and its real Docker smoke receipt passed with `gpu_used=false` and lower final loss. Built images/containers were cleaned up. These local OrbStack/arm64 runs reproduce bridge payloads only, not required GitHub Actions, Ubuntu, independent PR review, production, or ChatGPT acceptance. Full commands/digests/results: `docs/acceptance/2026-10-30-current-worktree-source-matched-suite.md`.

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

## Cumulative slice validation refresh — 2026-10-30

- Split the two PostgreSQL OAuth race/rollback cases into
  `gateway/tests/test_postgresql_oauth.py`; keep the shared migration test
  module with P4 because it depends on P4 migration helpers. The local review
  inventory is 118 paths (P1=3, P3=49, P4=50, P5=3, cross-cutting=13),
  including one uncommitted test-only decomposition path beyond the committed
  117-path inventory.
- A P1+P3-only full Gateway run produced four artifact capacity/prepare test
  failures because it omitted the cumulative P4 experiment API contract. The
  correctly reconstructed P1+P3+P4 candidate passed the full Gateway suite:
  **419 passed, 6 skipped**, with one existing Starlette deprecation warning.
  It used a dedicated PostgreSQL 16 container and the digest-pinned CPU smoke
  image, with candidate Gateway/core source and CI workflow in the isolated
  worktree. This local run used the installed Gateway venv, not a fresh locked
  environment or GitHub CI.
- The current full root/core suite passed **550 passed, 1 skipped**. Temporary
  candidate worktrees and PostgreSQL containers were removed. `git diff
  --check` passes. Live ChatGPT, production, independent GitHub review,
  selected-host acceptance, real GPU execution, and paid execution remain
  unverified; parked mode remains in force.

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

## Review-slice patch application — 2026-10-30

- Revalidated the follow-up owner map against `f054aebe..aa681f4`: 117 changed
  paths are covered exactly once. Corrected the map: the OAuth evidence record
  already existed at the base, so P1 owns three changed paths; the cross-cutting
  slice owns 13 paths, including that record's later update.
- Applied the P1, P3, P4, P5, and cross-cutting patches in sequence to fresh
  detached worktrees at `f054aebe`. Each cumulative candidate applied cleanly;
  all 117 final paths, including the intentional deletion of
  `gateway/deploy/worker.env.example`, match the current HEAD bytes/state.
- This verifies patch-stack applicability and inventory fidelity only. The
  slices are sequential review units, not independently tested standalone PRs;
  no new per-slice tests or GitHub CI were run. PR #51 remains OPEN/DRAFT with
  review required. Local documentation changes remain unpushed, and paid mode
  remains parked.


## Documentation delta Security Review — 2026-10-30

- The selected read-only Security Review covered only the eight current
  uncommitted documentation files; it found no actionable security issues. No
  tests or runtime/deployment checks were part of this review. It does not
  replace PR #51's required GitHub review or change any product acceptance
  status.

## Public production alias recheck — 2026-10-30 13:41 UTC

- Fresh unauthenticated GETs returned `/healthz` 200
  (`configured=true`, `auth_configured=true`, `auth_mode=local_oauth`),
  `/readyz` 404, and `/mcp` 401 (`invalid_token`, bearer access token required).
  The public alias still lacks the current readiness route; exact deployed SHA,
  OAuth flow, dependency readiness, and ChatGPT-originated execution remain
  unverified. No token, authenticated request, write, or deployment action was
  used. Acceptance remains NOT RUN and paid mode remains parked.

## Full review-stack reconstruction — 2026-10-30

- In a fresh detached worktree from `origin/main`, applied seven existing
  checkpoint diffs through `f054aebe`, then the five P1/P3/P4/P5/cross-cutting
  follow-up patches through `aa681f4`. The result matched all 322 tracked HEAD
  files exactly by path, bytes, and executable bit. Temporary worktree removed;
  branch and remote refs unchanged.
- This confirms composition fidelity only. The 79-path `c824b90..7c4454b`
  range and 117-path follow-up still need review-sized PR heads and candidate
  CI/GitHub review. PR #51 remains open/draft and unchanged.

## 79-path foundation review sequence — 2026-10-30

- Specified five sequential source boundaries for `c824b90..7c4454b`: 19, 21,
  38, 25, and 41 changed paths. Their recorded focused changed-test results
  are 30/4 skipped, 24/0, 64/6 skipped, 92/0, and 150/7 skipped, respectively.
  The `74f004a` head remains excluded; use the corrected `0d02058` boundary.
- The full source-stack reconstruction proved that these checkpoint changes
  compose with the later slices to reproduce current HEAD. No PRs were created,
  pushed, reviewed, or merged. Because the repository enforces linear history,
  each successor must be rebased onto the newly integrated `main` and retested
  after its predecessor is accepted. PR #51 remains unchanged.


## Candidate full-suite boundary correction — 2026-10-30

- A fresh Python 3.12.13 environment and exact-SHA Docker CPU image at
  `7c4454b` exposed a candidate-only migration gap: full Gateway/PostgreSQL
  suite **236 passed, 1 skipped, 1 failed**. Commit `7c4454b` added a test that
  drops/requires OAuth `grant_id` and expects schema v7, but the migration code
  there is still schema v6. The v7 migration first appears in `c8172c0`.
- Revalidated at `c8172c0` with fresh pip dependencies, PostgreSQL 16 and the
  exact-SHA Docker CPU image: Gateway **252 passed / 1 skipped**, WebMCP 3/3,
  compilation passed, and candidate-source root/core **515 passed / 1 skipped**
  (the skip is Python-3.11-specific). The PostgreSQL container was loopback-
  only; all temporary containers, image tags, and worktrees were removed.
- Adjusted the proposed stack: do not use `7c4454b` as an independently
  acceptable terminal head. Combine the final 41-path CPU/recovery integration
  interval with the 11-path `c8172c0` migration fix; this is a 52-path
  `311d6a9..c8172c0` candidate with full local-suite evidence. No PR or ref was
  created or changed; local macOS evidence is not GitHub/Linux CI.

## Full Gateway candidate-stack verification — 2026-10-30

Each candidate was checked out from its exact source commit in a disposable
worktree. One fresh Python 3.12.13 venv installed the identical Gateway
requirements-test/worker manifests; each head received its own pinned PostgreSQL
16 container bound to loopback and its own Docker CPU image labeled with that
candidate's exact SHA. Full Gateway results, in stack order:

- `c824b90`: 199 passed / 1 skipped; WebMCP 3/3.
- `6646401`: 204 passed / 1 skipped; WebMCP 3/3.
- `2a6f21a`: 209 passed / 1 skipped; WebMCP 3/3.
- `0d02058`: 219 passed / 1 skipped; WebMCP 3/3.
- `311d6a9`: 221 passed / 1 skipped; WebMCP 3/3.
- `c8172c0`: separately run above, 252 passed / 1 skipped; WebMCP 3/3.

All successful Gateway runs also passed Python entrypoint compilation and emitted
the existing Starlette deprecation warning. Root/core full suites passed at the
first candidate `c824b90` (452 passed / 1 Python-3.11-only skip) and at
`c8172c0` (515 passed / 1 Python-3.11-only skip). The intermediate `7c4454b`
head failed the PostgreSQL v4-to-v7 migration regression (236 passed, 1 skipped,
1 failed); see the candidate-boundary correction above. No candidate GitHub CI,
independent GitHub review, ChatGPT execution, deployment, or provider call was
performed. All temporary containers/images/worktrees/venvs were removed; current
branch and refs remain unchanged.


## External deployment access recheck — 2026-10-30 14:06 UTC

- GitHub's read-only main protection endpoint confirms strict status checks for
  Python 3.11/3.12/3.13, Trusted reference container, Gateway offline tests,
  Gateway comment bridge tests, and Project bridge tests; one approving review,
  approval by someone other than the last pusher, linear history, admin
  enforcement, and force-push/deletion prohibition are enabled.
- Reconciled PR #51's 169-path published diff and the one local-only OAuth test
  split. A path-set check parsed the owner lists and compared them with the
  exact Git diffs: the 118-path follow-up inventory matches exactly, and the
  full local 170-path inventory matches exactly after excluding the reverted
  `gateway/deploy/worker.env.example`. No duplicate or missing paths remain in
  the proposed map.
- A read-only request for Vercel preview variable metadata with `decrypt=false`
  returned HTTP 403. No environment values were requested or read. The mapped
  Vercel CLI fallback is unavailable in this environment, so variable presence
  and names remain unknown.
- The connected Neon integration's read-only project search for `gpu-control`
  returned no matching projects. This is limited to the connection's visible
  scope and does not establish whether another account/project exists. No DB
  or Vercel settings were changed.
- PR #51 remains OPEN/DRAFT at the same pushed head, with required checks green
  and no submitted GitHub review. Local cumulative tests and current uncommitted
  Security Review are recorded above; they do not change deployed readiness or
  ChatGPT acceptance. Repository mode remains `parked`.


## Standalone P1 review-candidate check — 2026-10-30

- Applied only the three local P1 OAuth paths on a temporary detached worktree
  based at `f054aebe`, including the OAuth-only PostgreSQL test split. The base
  already has schema v7 with `grant_id`, so P1 did not require the later P4
  migration. OAuth SQLite/HTTP and PostgreSQL 16 focused tests passed **7/7**;
  one existing Starlette deprecation warning was emitted.
- Re-ran the complete Gateway suite on that standalone P1 candidate, keeping
  P4-owned `test_postgresql.py` at its base version: **273 passed, 6 skipped**
  with one existing Starlette deprecation warning. The candidate used the
  installed Gateway venv on macOS arm64, a dedicated PostgreSQL 16 container,
  and the pinned CPU smoke image; this is not GitHub CI or a fresh locked env.
- This establishes that the P1 ownership slice can be reviewed and tested alone;
  it does not establish a PR head or GitHub CI. Full-suite evidence shows P1+P3
  without P4 previously failed four artifact-capacity/prepare tests, while the
  cumulative P1+P3+P4 candidate passed Gateway 419/6 skipped. The proposed PR
  boundaries are therefore P1 standalone, then P3+P4 combined, followed by P5
  and cross-cutting acceptance updates. Each candidate still requires full CI
  and independent GitHub review. Temporary worktree and PostgreSQL container
  were removed. No branch, PR, or remote state changed; policy remains parked.


## P3 paired artifact backup integrity gate — 2026-10-30 14:20 UTC

- Current source review found that atomic backup publication validated the
  PostgreSQL dump and artifact tar independently but did not check that
  unexpired artifact references in the database were present and byte-correct
  in the paired artifact volume. This could publish a self-consistent pair of
  checksummed files that still loses a live artifact.
- `backup_generation.py` now reads artifact metadata during quiescence, verifies
  the referenced source blobs using the owner/run scope and artifact-ID hash,
  and verifies the corresponding bytes inside the generated tar against size
  and SHA-256. Expired artifacts are skipped because the API returns
  `artifact_expired` for them. Invalid metadata, missing/unsafe blobs, and
  size/digest mismatches abort before publishing the generation.
- Added unit coverage for intact source bytes, expiry, source size mismatch, and
  archive digest mismatch. Focused suite: `./gateway/.venv/bin/python -m pytest
  -o addopts= gateway/tests/test_backup_generation.py -q` — **24 passed**, one
  existing Starlette deprecation warning. `git diff --check` passed. An initial
  attempt with the root venv failed to import `jwt`; the Gateway venv was then
  used successfully.
- Follow-up integration used a dedicated PostgreSQL 16 container on its private
  Docker network (no host port). The real PostgreSQL manifest query and local
  macOS tar generation/verification passed; same-size source corruption was
  rejected without publishing a second generation. The `pg_dump` and
  `pg_restore --list` commands were stubbed, so no real dump or restore was
  tested. This run caught and fixed the archive's `./` member-name normalization
  gap; the focused unit suite was rerun and still passed 24/24.
- Unit and local integration evidence above, including the v8 follow-up below,
  does not establish production or Neon behavior, a selected Linux host,
  independent second-operator recovery, alert delivery, or measured RPO/RTO.
  The new code has no GitHub CI yet. Recovery and ChatGPT acceptance gates
  remain open; repository policy stays parked.
- A review-only patch was assembled from exact current base
  `aa681f4062dac6b73bcf380a38a4258b96a47e1` at
  `/tmp/gpu-control-p3-backup-integrity.patch` (SHA-256
  `e5c05d1fa65a175747673e22a778f8b882cac6eb29ed9681a9ee31e2b16b0375`). It
  applied cleanly in a detached worktree and the three files matched byte-for-byte.


### P3 real PostgreSQL backup and paired restore follow-up — 2026-10-30 14:27 UTC

- On a fresh uniquely named PostgreSQL 16 container pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  created a minimal synthetic Gateway-shaped schema and one succeeded run with
  an artifact manifest. The container had no published host port.
- The current backup implementation ran actual `pg_dump --format=custom` and
  `pg_restore --list`, produced a generation, and passed `verify_generation()`.
  Restored the dump into a separate database, checked the run identity/state,
  extracted the paired artifact to a separate tree, and retrieved exact bytes
  through `ArtifactStore.get`; the digest and size matched.
- The seven-unit systemd state probe was stubbed as inactive for this isolated
  drill. The schema was minimal and unversioned; this does not validate a full
  migrated production schema, target-host services, second-operator RPO/RTO, or
  external/Neon recovery. All temporary DB and filesystem resources were
  removed. Repository mode remains `parked`.


### P3 current schema v8 paired restore revalidation — 2026-10-30 14:28 UTC

- Initialized the current Gateway schema through `Store.initialize()` in a new
  PostgreSQL 16 container pinned to digest
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
  A dynamic port was bound on loopback only. Seeded a synthetic completed run
  and its artifact manifest/blob.
- Generated the backup with real `pg_dump --format=custom`, validated it using
  real `pg_restore --list`, and passed `verify_generation()`. Restored the dump
  into a separate database. Confirmed schema version 8, run identity/state, and
  artifact manifest digest. Restored the paired tar to a separate tree and
  retrieved byte-exact content with `ArtifactStore.get`.
- The systemd stopped-unit gate was stubbed inactive; no service ran. The data
  and database were synthetic. The PostgreSQL container, databases, dump, and
  temporary artifact/backup trees were removed. This remains local v8 recovery
  evidence, not Neon/production, target-host, second-operator, alert-delivery,
  or timed RPO/RTO acceptance. `policies/repository-state.yaml` remains parked.


### P3 PostgreSQL-backed artifact-integrity regression — 2026-10-30 14:32 UTC

- Added `gateway/tests/test_postgresql_backup_integrity.py` for the dedicated
  Gateway PostgreSQL CI database. It initializes the current schema, inserts a
  unique synthetic terminal run and blob manifest, runs the actual artifact
  manifest query, verifies the source blob and `./`-prefixed tar member, and
  rejects same-size content corruption. The unique database row is removed in
  `finally`; no shared PostgreSQL lifecycle module was changed.
- Executed the test against a fresh PostgreSQL 16 container pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`;
  result: **1 passed**, one existing Starlette deprecation warning. The
  container was removed. `git diff --check` passed. This covers DB query and
  integrity helpers in CI-compatible form, but the new uncommitted test has not
  run in GitHub CI. Production recovery remains unaccepted and mode remains
  `parked`.


### P3 full Gateway regression after backup-integrity change — 2026-10-30 14:35 UTC

- Revalidated the current Gateway source with a dedicated PostgreSQL 16
  container pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  published only on loopback port 52993. The suite used the cached CPU smoke
  image `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`;
  OCI source/revision labels were checked against `Unjuno/gpu-control` and the
  synthetic fixture SHA.
- Command from `gateway/`: `./.venv/bin/python -m pytest -o addopts= -q -rs
  tests`. Result: **426 passed, 2 skipped**, one existing Starlette deprecation
  warning. The only skips were optional Torch and Modal SDK coverage. This
  includes the PostgreSQL-backed artifact manifest/integrity regression,
  PostgreSQL outage recovery, OAuth PostgreSQL tests, and real local CPU/MCP
  worker tests.
- First run used `docker run --rm`; the outage integration test removes that
  container on stop and could not restart it (8 failures). This was an invalid
  harness configuration. The corrected run retained the named container during
  the test and cleaned it explicitly afterward; all tests passed. No unrelated
  container was modified. This is local integration evidence, not GitHub CI,
  target-host, Neon, ChatGPT, GPU, or paid-execution acceptance.

### P1 OAuth review-candidate validation — 2026-10-30 14:41 UTC

- Reapplied `/tmp/gpu-control-p1-oauth-review.patch` to a detached worktree at
  exact base `f054aebe96460fe033dde8d91d7e3bbab0255655`; patch application
  check passed. Candidate SHA-256:
  `7a3cd15ac07c222fda75c1cbc868c98e0c4beb62759d46183131d1cf67b8cdea`.
- Ran `gateway/tests/test_local_oauth.py` and
  `gateway/tests/test_postgresql_oauth.py` from the candidate source against a
  disposable PostgreSQL 16 container pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  and bound to `127.0.0.1:55498`: **7 passed**, one existing Starlette
  deprecation warning. This includes refresh-token single-consumption under
  concurrency and transaction rollback after injected replacement-token
  persistence failure. Dependencies came from the primary Gateway venv.
- The read-only Security Review of this exact isolated patch reported no
  actionable findings. Temporary worktree and PostgreSQL container were
  removed; primary branch refs and other dirty changes were preserved.
- This establishes candidate-local OAuth behavior and review evidence only. It
  is not GitHub CI, ChatGPT workspace/OAuth acceptance, deployed-source
  provenance, or an approval/merge. PR #51 and the full roadmap remain open;
  repository mode remains `parked`.

### P1 production-alias recheck — 2026-10-30 14:44 UTC

- Fresh unauthenticated GETs to `https://gpu-control.vercel.app` returned
  `/healthz` 200 (`configured=true`, `auth_mode=local_oauth`), `/readyz` 404,
  and `/mcp` 401 (`Bearer access token is required`). The deployed SHA remains
  unverified; this does not prove readiness, OAuth grant, or ChatGPT execution.
- Read-only GitHub recheck: PR #51 remains OPEN/DRAFT at `aa681f4`,
  `REVIEW_REQUIRED`; all seven required Actions checks and the two Vercel
  statuses passed for that pushed head. Branch protection requires one
  approval and all seven checks. Local uncommitted changes and the P1 OAuth
  review candidate are not included in those checks.
- `policies/repository-state.yaml` remains `mode: parked`. No authenticated
  request, GitHub write, deployment, or ChatGPT setting was changed.

### P3 backup-integrity review candidate revalidation — 2026-10-30

- Reconstructed `/tmp/gpu-control-p3-backup-integrity.patch` byte-for-byte
  from the current `HEAD` diff for `gateway/deploy/backup_generation.py` and
  `gateway/tests/test_backup_generation.py`, plus the untracked
  `gateway/tests/test_postgresql_backup_integrity.py`. SHA-256 remained
  `e5c05d1fa65a175747673e22a778f8b882cac6eb29ed9681a9ee31e2b16b0375`.
- Applied the patch with `git apply --check` in a disposable detached worktree
  at `aa681f4062dac6b73bcf380a38a4258b96a47e1d`. The 24 backup-generation
  tests and PostgreSQL-backed integrity test passed: **25 passed**, one
  existing Starlette deprecation warning. PostgreSQL 16 was pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  and bound to a dynamically assigned loopback port. Candidate source was
  imported from the detached worktree; dependencies came from the primary
  Gateway venv.
- The first disposable DB startup attempt did not reach readiness within its
  wait and was removed before tests began. The retry with a dynamic loopback
  port reached readiness and completed all 25 tests. The worktree and DB
  container were removed; the primary worktree and refs were preserved.
- This is local source/test evidence, not GitHub CI, target-host backup, Neon,
  second-operator recovery, or RPO/RTO acceptance. Repository mode remains
  `parked`.

### P1 Vercel deployment provenance — 2026-10-30 14:49 UTC

- Read-only Vercel API metadata identifies the latest production deployment as
  `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`, `main` at
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. Latest PR preview is READY at
  `dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe`, target `null`, branch
  `codex/chatgpt-cpu-vertical`, exact SHA
  `aa681f4062dac6b73bcf380a38a4258b96a47e1`. Project metadata reports SSO
  protection for all deployments except custom domains.
- Together with the public `/readyz`=404 probe, this confirms production is
  behind the local readiness route. The PR revision exists only as a protected
  preview. No protected preview fetch was attempted because the available
  operation creates/reuses a 23-hour share link and authorization for that link
  was not given. No settings or deployment were changed. ChatGPT acceptance
  remains **NOT RUN**; repository mode remains `parked`.
- A read-only Vercel deployment-file listing for that preview returned
  `404 not_found` (`File tree not found`); source-bundle inspection is
  unavailable through that endpoint. Runtime readiness remains unverified.

### P1 GitHub/Vercel review and build-state recheck — 2026-10-30 14:50 UTC

- PR #51 remains OPEN/DRAFT at `aa681f4062dac6b73bcf380a38a4258b96a47e1`,
  `REVIEW_REQUIRED`, with zero submitted GitHub reviews and zero review-thread
  comments. Its only issue comment is the Vercel deployment status comment.
  Seven required Actions checks and both Vercel statuses pass on the pushed
  head; local deltas remain outside those checks.
- The Vercel comment metadata confirms `rootDirectory: "gateway"` for preview
  deployment `dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe`. The separate setting to include
  source files outside the root directory remains unverified. Preview runtime
  cannot be fetched without a temporary share link; its file-tree endpoint
  returned `404 not_found`. Production remains pinned to `main` at `24ecb9b`.
- Read-only preview build events show Python 3.12, uv 0.13.5, dependency
  installation from `gateway/uv.lock`, and successful build/deployment. That
  lock points `gpu-control` at editable path `../`; this does not establish the
  runtime function can import it or reach DB/OAuth readiness.
- No GitHub write, Vercel configuration change, or deployment was performed.
  `policies/repository-state.yaml` remains `mode: parked`.
- A names-only Preview env query with `decrypt=false` was denied with Vercel
  `403 forbidden`; no env values were fetched. Vercel CLI is not installed, so
  Preview variable names/target scopes remain unknown and no missing-variable
  conclusion is justified from the `configured=false` runtime evidence alone.

### P3 capacity delivery scope correction — 2026-10-30

- Audited the release-matrix statement against the implemented delivery pump
  and its test module. Re-ran
  `./gateway/.venv/bin/python -m pytest -o addopts= gateway/tests/test_capacity_event_state.py -q`:
  **40 passed**, one existing Starlette deprecation warning. This covers the
  durable outbox and fake-sender delivery/retry behavior only.
- Corrected `docs/RELEASE_MATRIX.md`: sink-neutral fake-sender tests exist, but
  no concrete notification sender/sink, real transport test, or target-host
  delivery acceptance exists. No sink or SLO was invented; repository mode
  remains `parked`.

### P1 OAuth clean-environment revalidation — 2026-10-30

- Reconstructed the uncommitted PostgreSQL OAuth tests on a detached worktree
  at the current pushed head `aa681f4062dac6b73bcf380a38a4258b96a47e1` and
  created a fresh Python 3.12 virtual environment with the Gateway CI test and
  worker requirements. Against the workflow's digest-pinned PostgreSQL image,
  `tests/test_local_oauth.py` and `tests/test_postgresql_oauth.py` passed:
  **7 passed**, one existing Starlette deprecation warning.
- An initial attempt used older base `f054aeb`, which predates the current
  `_insert_token` implementation and made the new rollback test fail to load.
  That attempt was not evidence about current HEAD; the test was rerun on the
  correct current head and passed. No source fix was required.
- This verifies local OAuth behavior and DB transaction rollback/concurrency
  under the pinned local PostgreSQL image. It does not verify ChatGPT's live
  OAuth handshake, hosted preview readiness, or production credentials. PR
  checks still cover only the pushed head; dirty local deltas remain outside
  CI, and repository mode remains `parked`.

### P1 full Gateway integration revalidation and Preview configuration access — 2026-10-31

- Re-ran the full Gateway suite with the repository Python 3.12 test
  environment, CI's digest-pinned PostgreSQL 16 image, and cached CPU smoke
  image `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`
  carrying the test fixture's synthetic all-`a` source SHA:
  `426 passed, 2 skipped` in 23.57 seconds; one existing Starlette deprecation
  warning. Skips are the optional PyTorch CI bridge (`torch` absent) and Modal
  backend (`modal` absent), both parked external/provider paths. This is local
  code/integration evidence, not ChatGPT-originated execution or deployed
  service acceptance.
- Read-only Vercel project metadata for `gpu-control`
  (`prj_fMufIBiFDlXtWcuJ0bWpAekEMIAp`) now reports latest deployment
  `dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe` READY for the current branch, with SSO
  protection enabled for non-custom deployment URLs. A names-only Preview
  environment-variable request (`decrypt=false`, branch
  `codex/chatgpt-cpu-vertical`) returned `403 forbidden`; no names or values
  were returned. The CLI fallback is unavailable in this environment. Thus
  Preview runtime configuration remains unknown, and no particular missing
  setting can be asserted from this query.
- No Vercel setting, secret, or deployment was changed. The public endpoint
  probe and ChatGPT OAuth/tool acceptance were not repeated. PR #51 remains
  OPEN/DRAFT and current local deltas remain outside its green checks;
  `policies/repository-state.yaml` remains `mode: parked`.
- Vercel deployment metadata independently confirms the latest Preview is a
  READY `LAMBDAS` deployment from `aa681f4062dac6b73bcf380a38a4258b96a47e1d`
  (`codex/chatgpt-cpu-vertical`), protected by SSO on non-custom URLs. A
  names-only runtime-log aggregation request for that deployment and the last
  30 minutes returned no log rows; this is not a readiness or availability
  probe. Gateway `README.md` documents that the Vercel app does not run the
  persistent worker or recovery supervisor.
- Reproduced the workflow's locked runtime dependency install into a new
  temporary environment with `uv sync --project gateway --locked --no-dev`,
  then successfully imported `gpu_control` and `gpu_gateway`. The imports resolve
  to this checkout's root `src/gpu_control` and `gateway/gpu_gateway`. This
  proves the lockfile and local source layout install correctly; Vercel's
  actual bundle inclusion and runtime imports remain unverified because its
  protected deployment cannot be fetched without creating/reusing a temporary
  share link.
- Inspected the checked-in local execution configuration: the
  `cpu-smoke-v1` manifest template intentionally has blank image digest and
  source identity; `gateway/policies/local-cpu.json` is disabled, expired, and
  allowlists no workload. The default Docker Compose stack registers only the
  demo provider and does not supply the dedicated CPU worker/recovery topology.
  Therefore the repo does not currently contain an enabled or runnable local
  CPU deployment configuration. This is an intentional security/spending gate,
  not a runtime failure to work around. The remaining P1 path needs an operator
  to review and provision the exact workload identity, expiring CPU policy,
  dedicated worker/daemon and shared durable artifact storage before ChatGPT
  can be connected.

### P2 PostgreSQL plus real-container crash recovery — 2026-10-31

- Added a PostgreSQL-backed counterpart to the existing SQLite/local-Docker
  process-crash integration. A child execution worker starts the real
  digest-pinned `cpu-smoke-v1` container and exits immediately before it can
  persist the returned handle. A fresh recovery supervisor reads the durable
  submission intent, adopts the single matching run-labeled container, and
  completes the same run. Assertions bind the original run ID and source SHA,
  require `simulation=false` and `gpu_used=false`, retrieve exact result bytes
  through the artifact store, verify cleanup, confirm the container is absent,
  and require the admission slot to return to zero.
- The new crash test and the existing real PostgreSQL outage-after-capture
  test passed together: **2 passed** against the digest-pinned PostgreSQL 16
  image and local CPU smoke image. The complete Gateway suite after the new
  integration passed **427 passed / 2 skipped** in 23.79 seconds; skips are
  optional PyTorch CI bridge and Modal backend, with one existing Starlette
  deprecation warning. The disposable PostgreSQL container was removed.
- These are local macOS/OrbStack integration tests with synthetic identity and
  a local Docker daemon. They increase crash/recovery coverage across real
  PostgreSQL and Docker, but do not replace a selected Linux host, independent
  second-operator drill, measured RPO/RTO, or seven-day operations acceptance.
  Detailed evidence: `docs/acceptance/2026-10-31-postgres-container-crash-recovery.md`.

### P3 restore-runbook and release-evidence refresh — 2026-10-31

- Audited the isolated restore example against the backup CLI and the paired
  restore evidence. The example previously referenced undefined shell
  variables, omitted an executable passfile permission check, and did not
  enforce the required new artifact path. Added explicit isolated-target
  settings, replacement guards, Linux mode verification, and a fail-closed
  artifact-directory existence check to `docs/OPERATIONS.md`. The procedure
  now also requires private exact table-count comparison against the quiesced
  source snapshot.
- Refreshed `docs/RELEASE_MATRIX.md` from read-only GitHub/Vercel state and the
  current local evidence. PR #51 is OPEN/DRAFT at
  `aa681f4062dac6b73bcf380a38a4258b96a47e1d`; all seven required Actions checks
  and the Vercel status are successful on that pushed SHA. Its latest Preview
  is READY but protected. The pushed-head Gateway CI log reports 424 passed,
  1 skipped; the separate current-worktree Gateway run reports 427 passed,
  2 skipped and includes the new crash test. Neither establishes ChatGPT or
  target-host acceptance.
- `git diff --check` passed for the runbook update. No tests were rerun for
  these documentation-only changes, and no GitHub, Vercel, production, or
  provider configuration was changed. Repository activation remains parked.
- Refreshed the Luna handoff and review-slice inventory to the live worktree:
  16 modified tracked files, 3 untracked files, 172 paths from `origin/main`
  through the complete local diff. The ownership-map parser compared the 120
  follow-up paths (`f054aebe..HEAD` plus untracked files) and found 120 unique
  entries, with no missing, duplicate, or stale paths. `git diff --check`
  passed. This is bookkeeping validation, not a code test or GitHub review.

### P1 OAuth review-candidate exact replay — 2026-10-31

- Regenerated the three-path OAuth candidate patch from the current worktree;
  its SHA-256 remained
  `7a3cd15ac07c222fda75c1cbc868c98e0c4beb62759d46183131d1cf67b8cdea`. Applied
  it to a fresh detached worktree at `f054aebe` and confirmed the imported
  `gpu_gateway.local_oauth` module came from that candidate directory.
- With a fresh disposable PostgreSQL 16 container at the pinned CI image digest,
  `test_local_oauth.py` and `test_postgresql_oauth.py` passed **7 passed, 0
  skipped**. A Starlette deprecation warning remains. The temporary container,
  patch file, and candidate worktree were removed.
- This confirms exact candidate reconstruction and targeted PostgreSQL OAuth
  behavior, not the full Gateway suite, hosted ChatGPT OAuth, or GitHub CI. No
  branch or remote reference was changed.

### P3 backup-integrity review-candidate exact replay — 2026-10-31

- Regenerated the three-path backup-integrity candidate patch from the current
  worktree; its SHA-256 remained
  `e5c05d1fa65a175747673e22a778f8b882cac6eb29ed9681a9ee31e2b16b0375`. Applied
  it to a fresh detached worktree at `aa681f4` and verified both the Gateway
  package and backup utility imported from that candidate path.
- With a fresh disposable PostgreSQL 16 container at the pinned CI image digest,
  `test_backup_generation.py` and `test_postgresql_backup_integrity.py` passed
  **25 passed, 0 skipped**. One existing Starlette deprecation warning was
  reported. The temporary container, patch, and worktree were removed.
- A first standalone import probe omitted `gateway/deploy` from `sys.path`; the
  corrected probe resolved `backup_generation.py` from the candidate, and the
  pytest module's own import path worked during the successful run. No branch
  or remote reference was changed. This is local candidate evidence only.
- Refreshed public deployment evidence at 2026-10-30 15:27 UTC with
  unauthenticated GETs: `/healthz`=200 with configured local OAuth,
  `/readyz`=404, protected-resource discovery=200 with the expected three
  scopes, and `/mcp`=401. The live alias still lacks the local P1 readiness
  route; this does not prove readiness or ChatGPT acceptance. Recorded in
  `docs/CHATGPT_ACCEPTANCE.md`; no token or authenticated request was used.

### Reproducible first-install procedure — 2026-10-31

- Added a first-install runbook to `docs/OPERATIONS.md` for deploying an exact
  reviewed commit from `main`, installing the pinned Gateway lockfile into the
  documented virtual environment, and checking package import paths and clean
  source status. Confirmed the uv pin and project-relative package paths
  against the current CI workflow and project configuration. Clarified that
  checkout and virtual environment remain root-owned and service identities
  receive read/execute access only.
- `git diff --check` passed for the documentation changes. No tests were run
  for this runbook-only update. No host, production, GitHub, provider, or
  credential configuration was changed; repository activation remains parked.

### Live P0 GitHub gate and PR refresh — 2026-10-30 15:31 UTC

- Read GitHub branch protection and PR #51 through the authenticated CLI. The
  protected `main` currently requires a pull request, one approval, dismissal
  of stale reviews, resolved conversations, strict up-to-date status checks,
  linear history, and admin enforcement; force-push and deletion are disabled.
  All seven required Actions contexts match the recorded matrix.
- PR #51 remains OPEN/DRAFT at head
  `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, based on
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. GitHub reports
  `REVIEW_REQUIRED`, zero reviews, and success for all seven required checks
  plus Vercel on that pushed head. The 16 modified tracked and 3 untracked
  local paths are outside those checks; they remain unstaged and uncommitted.
- This closes the current-state readback for P0 branch governance only. It does
  not independently review or integrate the local candidate slices, nor prove
  ChatGPT workspace eligibility, OAuth/tool execution, deployed readiness, or
  P1 acceptance. No GitHub or deployment state was changed. Repository mode
  remains `parked`.

### Review inventory stale-path correction — 2026-10-30 15:34 UTC

- Recomputed the current full review inventory from `origin/main...HEAD`, the
  working-tree diff, and untracked files. The union is 172 paths: 169 tracked
  branch paths plus three untracked files; all 16 modified tracked worktree
  paths overlap the tracked branch diff.
- The owner map had retained `gateway/deploy/worker.env.example` only because
  it is deleted between the historical `f054aebe` checkpoint and final HEAD.
  It is absent from both `origin/main` and final HEAD, so removed it from the
  publishable review ownership set. Updated P3 from 50 to 49 paths and corrected
  the Luna handoff counts.
- A path-set comparison now finds exactly 172 ownership entries for 172 actual
  paths, with no duplicate, missing, or stale entries (P1=3, P3=49, P4=50,
  P5=3, cross-cutting=14, plus 53 foundation-only). `git diff --check` passed.
  This validates bookkeeping, not test behavior, review, CI, or acceptance.
  No tests or external mutations occurred; mode remains `parked`.

### P3 systemd installation and target-host verification command — 2026-10-30 15:37 UTC

- Reconciled `docs/OPERATIONS.md` and `gateway/README.md` with the actual eight
  files in `gateway/deploy/gpu-control-*`: seven services (including the
  read-only DB check and manual capacity bridge) and one timer. The target-host
  `systemd-analyze verify` example now includes all eight; the install example
  already copies all eight and was checked against the file inventory.
- A static comparison confirmed the first-install copy list and target-host
  verify list each match the eight current filenames exactly. `git diff --check`
  passed. No test or systemd service was run; this is documentation validation,
  not target-host acceptance. No host, GitHub, database, or provider state was
  changed; repository mode remains `parked`.

### P3 restore table-count and schema-version evidence commands — 2026-10-30 15:40 UTC

- Made the isolated restore runbook executable for row-count comparison: it
  captures required runs/control tables, an optional schema-version table, and
  every present OAuth table from the quiesced source and restored database to
  private mode-`0600` files, then uses `diff -u` to fail on mismatches. The
  table-count query fails if either required core table is absent.
- Added source/manifest/restore schema-version comparison that handles the
  supported legacy `unversioned` state without referencing a table that may not
  exist. Confirmed the seven current OAuth table declarations match the query's
  `gateway_oauth_*` discovery rule. The embedded shell block passes `bash -n`
  and `git diff --check` passes.
- `psql` is not installed in this checkout environment, so the SQL and
  PostgreSQL execution were not run. No database, host, credentials, or
  services were used or changed; this is runbook static validation only.
  Production/second-operator restore acceptance remains open and mode remains
  `parked`.

### P3 recovery-record alignment — 2026-10-30 15:42 UTC

- Aligned the restore decision text with the executable comparison: the schema
  version table is optional only for a source and restore both identified as
  `unversioned` in the backup manifest; otherwise the version and row count
  must match. Added the source/manifest/restore comparison and private
  table-count evidence references to the recovery drill record template.
- Made artifact extraction explicitly pass GNU tar's `--no-same-owner` and
  `--no-same-permissions` while writing as `gpu-control-worker`. The embedded
  restore shell block passes `bash -n`, and `git diff --check` passes. No SQL,
  test, database, or host execution occurred (`psql` is unavailable here); this
  remains documentation-level validation, not recovery acceptance.

### P3 host-resource reconciliation procedure — 2026-10-31

- Expanded the production recovery runbook with a private, read-only Docker
  inventory capture before daemon changes, per-run lookup using the exact
  run-id label, and restricted inspection of only the container state and
  identity labels already enforced by `local_backend.py`.
- Clarified that zero/multiple/mismatched resources, an unavailable daemon, or
  missing inventory leaves a run unresolved with admissions disabled; operators
  must not manually create replacements, blindly resubmit, or remove resources.
  Remote provider outcomes follow the same no-resubmission rule.
- Static documentation review and `git diff --check` passed. No live host,
  Docker daemon, database, or service was accessed; no test was run. This closes
  a runbook specificity gap only and does not establish target-host recovery,
  measured RPO/RTO, or production acceptance. Mode remains `parked`.

### P3 backup manifest JSON-shape regression — 2026-10-31

- Changed both artifact-manifest SQL predicates to call `json_array_length`
  only inside a `CASE` branch after confirming that the JSON value is an array.
  Added a PostgreSQL fixture containing an object-valued `artifacts` field next
  to a valid artifact manifest; quiescence counting and backup manifest
  selection now exercise that legacy/invalid shape without aborting the backup
  check.
- `gateway/tests/test_backup_generation.py`: **24 passed**. The new
  `gateway/tests/test_postgresql_backup_integrity.py` test passed **1/1** against
  a disposable PostgreSQL 16 container using the CI image digest, bound only
  to `127.0.0.1:55494`. Exit cleanup removed the container. `git diff --check`
  passed. The full current Gateway suite also passed **415 tests**, with 14
  skips: optional Torch/Modal SDKs, unavailable CPU Docker image, and dedicated
  PostgreSQL integrations not configured for that run. This is local backup
  integrity evidence only; production restore, target-host operation, and
  ChatGPT acceptance remain open. Mode remains `parked`.

### Live P0/P1 boundary refresh — 2026-10-30 15:48 UTC

- Read-only `gh pr view 51` confirms PR #51 is OPEN/DRAFT at pushed head
  `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, `REVIEW_REQUIRED`, with no
  reviews; the seven required Actions checks and Vercel passed at 12:39 UTC.
  The worktree has additional uncommitted changes outside that checked head.
- Fresh unauthenticated production-alias GETs returned `/healthz`=200
  (`configured=true`, `auth_mode=local_oauth`), `/readyz`=404,
  protected-resource discovery=200, and `/mcp`=401. The deployed SHA remains
  unknown; this is not OAuth or ChatGPT acceptance. Updated the acceptance and
  release records. No GitHub write, deployment, workspace, or credential state
  was changed; mode remains `parked`.

### Full Gateway integration after backup JSON-shape fix — 2026-10-30 15:55 UTC

- The first full PostgreSQL/CPU-container run surfaced test coupling: the new
  backup regression called the global quiescence gate after earlier integration
  cases had left terminal runs with unknown cleanup state. Removed that unrelated
  gate assertion and exercised the shared JSON-type predicate directly against
  PostgreSQL `VALUES`, while still inserting both valid and object-shaped run
  results and checking backup manifest selection.
- Re-ran the complete Gateway suite on the current worktree with a disposable
  PostgreSQL 16 container (CI image digest, loopback-only port 55495) and the
  digest-pinned CPU smoke image: **427 passed, 2 skipped** (optional PyTorch and
  Modal SDKs), one existing Starlette deprecation warning. The cleanup trap
  removed the PostgreSQL container. This is local source/integration evidence,
  not GitHub CI, ChatGPT acceptance, or target-host recovery.

### P1 stacked review refs materialized locally — 2026-10-30 15:59 UTC

- Created local-only branch refs at the first five existing P1 candidate
  checkpoints: `codex/gpu-control-p1-01-baseline` → `b3cb04d`,
  `...02-mcp-contract` → `195de19`, `...03-admission` → `2440897`,
  `...04-local-backend` → `3e1c31c`, and `...05-recovery` → `c824b90`.
  Their sequential bases and changed-path counts (14/9/14/19/13) match the
  reviewed decomposition plan; each exact range passes `git diff --check`.
- Existing candidate-focused test results are recorded in
  `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`. No tests
  were rerun per candidate in this step. No branch checkout, worktree, remote
  ref, PR, commit, or merge was changed. A fresh read-only `gh pr view 51`
  confirms OPEN/DRAFT at the unchanged pushed SHA, `REVIEW_REQUIRED`, and zero
  reviews. Per-head GitHub CI and independent review remain open; PR #51 remains
  unchanged and repository mode remains `parked`.

### Remaining CPU/recovery review refs materialized locally — 2026-10-30 16:02 UTC

- Added nine more local-only refs for documented stack stages 6–14, from
  `c824b90` through `0d02058`. Their sequential path counts are
  6/5/17/3/5/18/16/18/14; all base/head ancestry checks and exact-range
  `git diff --check` passed. Existing focused-test results (including prior
  PostgreSQL reruns) are recorded in the slice table; tests were not rerun in
  this step.
- The first fourteen review refs now cover the initial CPU/recovery foundation
  through readiness/heartbeat. They remain local only. No worktree/checkout,
  remote branch, PR, commit, or merge was created; PR #51 is unchanged and the
  repository remains `parked`.

### Remaining foundation review refs materialized locally — 2026-10-30 16:04 UTC

- Added six checkpoint refs from `0d02058` through `f054aebe`, covering HTTP
  security, CPU/OAuth migration, paired backup/operations, CI/package checks,
  P4 selection, and the final foundation evidence refresh. Their exact
  sequential changed-path counts are 25/52/13/8/5/15; all ancestry and
  `git diff --check` validations passed.
- Existing evidence includes 92 focused tests for the HTTP security range and
  full Gateway 252/1 skipped plus root/core 515/1 skipped at the combined
  CPU/OAuth migration head. Distinct candidate runs are not recorded for the
  backup/operations, CI/package, P4, and documentation evidence heads; these
  still require candidate validation. No tests were rerun in this step. All
  twenty refs remain local, PR #51 is unchanged, and repository mode remains
  `parked`.

### Latest current-worktree Gateway integration — 2026-10-30 16:07 UTC

- Re-ran the full Gateway test suite from the current working tree using a
  disposable PostgreSQL 16 container pinned to the CI image digest, bound to a
  dynamically assigned loopback-only port, and the existing digest-pinned CPU
  smoke image. The run passed **550 tests with 1 skipped**. This includes the
  current PostgreSQL-backed OAuth refresh concurrency/rollback tests, backup
  manifest and artifact byte-integrity test, and real Docker worker crash
  recovery test, alongside the rest of the Gateway suite.
- The PostgreSQL test container was removed by the command's exit trap; no
  matching `gpu-control-ci-local` container remained. `git diff --check` passes.
  This is current local integration evidence only; it does not satisfy
  GitHub CI/review, deployed ChatGPT OAuth/tool execution, target-host
  operations, live GPU, or paid execution gates. Repository mode remains
  `parked`.
- Separately ran the root/core suite using `./.venv/bin/python -m pytest -o
  addopts= -q`: **550 passed, 1 skipped** in 0.99 seconds. This verifies the
  current branch's root/core tests; the uncommitted code delta remains Gateway
  scoped, and neither local suite is a GitHub check.

### Current uncommitted-diff Security Review — 2026-10-30

- The user-selected read-only review of the current uncommitted diff reported
  one actionable P2 at
  `gateway/tests/test_postgres_lifecycle_integration.py:256`: the crash test
  passes the full PostgreSQL URL in a child-process argument, which can expose
  embedded credentials through argv to local processes with process-list
  access. The new backup-integrity implementation had no actionable finding.
- The finding is not yet corrected or independently re-reviewed. It blocks a
  clean local security result at this recorded time; it did not establish a
  production exposure. Follow-up correction and review are recorded below.
  Preserve parked mode and all execution/spend gates.

### Live P0/P1 runtime and workspace access recheck — 2026-10-30 16:11 UTC

- Read-only unauthenticated requests to the production alias returned
  `/healthz` 200 (`configured=true`, `auth_mode=local_oauth`), `/readyz` 404,
  protected-resource discovery 200, and `/mcp` 401. The alias does not expose
  the current checked-in readiness route; the response does not identify its
  deployed SHA.
- The ChatGPT in-app browser showed Log in / Sign up. No account access, login,
  workspace, OAuth grant, or MCP tool call was attempted. This confirms only
  that the current browser session is unauthenticated, not that an eligible
  user workspace is unavailable. ChatGPT acceptance remains NOT RUN.
- PR #51 remains OPEN/DRAFT at `aa681f4062dac6b73bcf380a38a4258b96a47e1d`,
  `REVIEW_REQUIRED`, zero reviews; the seven required checks and Vercel pass
  only on that pushed SHA. Branch protection reads back one required approval,
  seven required contexts, strict checks, enforced admins, and force-push and
  deletion disabled. Local deltas are outside those checks. Repository mode
  remains `parked`.

### PostgreSQL child-process URL fix and current-diff security re-review — 2026-10-30 16:13 UTC

- Removed the database URL from the worker-crash test's child-process argument
  vector. The parent now sends the URL over the child's stdin pipe; the child
  reads it there before constructing its database settings. This avoids
  exposing the URL through ordinary process-argument listings.
- The progress count **550 passed / 1 skipped** originally recorded here is
  not supported as a Gateway result by a preserved pytest transcript. A later
  reproducible full Gateway run is documented in the 2026-10-31 correction
  below; the distinct root/core suite result remains 550 passed / 1 skipped.
- The user-selected read-only Security Review of the full current uncommitted
  diff found **no actionable findings** and confirmed the URL is no longer in
  argv. This is local diff review, not GitHub review or deployed security
  acceptance. `git diff --check` passes; PR #51 remains OPEN/DRAFT and
  `policies/repository-state.yaml` remains `parked`.

### Gateway full-suite result correction — 2026-10-31

- Re-ran the complete Gateway suite from `gateway/` with a fresh loopback-only
  PostgreSQL 16 container pinned to the CI image digest, the digest-pinned CPU
  smoke image, and the synthetic source SHA in the required 40-character form.
  Exact command: `./.venv/bin/python -m pytest -o addopts= -q -rs tests` with
  the integration environment variables recorded in
  `docs/acceptance/2026-10-31-postgres-container-crash-recovery.md`.
- The first attempt supplied a 32-character source SHA and failed five tests at
  input validation; it is excluded as a harness error. The corrected run
  passed **427 tests, 2 skipped, 0 failed** in 24.33 seconds. `-rs` identified
  the skips as the optional PyTorch bridge and Modal backend. An existing
  Starlette deprecation warning remained.
- The 427-test run includes PostgreSQL OAuth, paired backup/artifact integrity,
  the PostgreSQL outage-after-capture recovery test, and the worker-process
  crash-after-Docker-start recovery test. The root/core result of **550 passed,
  1 skipped** was separately rerun from the repository root and reproduced in
  0.88 seconds; it is a distinct suite and count.
  Therefore the earlier 550/1 count labeled as Gateway is superseded. The
  disposable database container was removed by the exit trap. This is local
  integration evidence, not GitHub CI or target-host acceptance.
- A fresh PR #51 read still showed OPEN/DRAFT at `aa681f4`, `REVIEW_REQUIRED`,
  zero reviews, and all seven required checks successful. The subsequent
  branch-protection API call was rate-limited; the same-day successful settings
  read recorded in `docs/BASELINE_AUDIT.md` remains the latest confirmed rule
  state, with no setting change made.

### P0/P1 packaging and browser registration checks — 2026-10-30 16:16 UTC

- Built the Gateway wheel from the current worktree with `uv build gateway
  --wheel`; the wheel contains `gpu_gateway` plus the packaged Web UI/WebMCP
  assets. `python -m compileall -q app.py gpu_gateway modal_worker.py` passed
  in the Gateway directory.
- Ran the checked-in WebMCP registration contract tests from `gateway/`:
  **3 passed**. This verifies browser fallback, shared API invocation, and
  visible registration failure behavior locally; it does not register tools in
  an actual ChatGPT workspace. The successful local package and contract
  checks do not replace the PR's current-head CI or hosted runtime acceptance.

### Final stacked checkpoint test gaps closed locally — 2026-10-30 16:16 UTC

- Revalidated exact existing review heads in temporary detached worktrees.
  Stage 17 (`d794c13`) passed **21** backup/deploy-unit tests; stage 18
  (`cccfcb8`) passed **4** workflow-security and **2** package-metadata tests;
  stage 20 (`f054aebe`) passed **31** HTTP-auth/OAuth/package-metadata tests. Each run
  used `PYTHONPATH` entries for that candidate's own `gateway/` and `src/` and
  the existing Python 3.12 environments. Stage 19 (`f15ab32`) is a five-path
  documentation/evidence-only update and has no runtime tests.
- The temporary worktrees were removed; `git worktree list` shows only the
  primary checkout, and the existing candidate refs remain local. This closes
  their previously undocumented focused-test gaps, not per-head Linux CI,
  GitHub review, or deployment acceptance. `git diff --check` passes.
- The stage-20 run included the existing HTTP auth suite after inspecting the
  candidate's OAuth consent-route changes. It passed with one existing
  Starlette deprecation warning; this broader targeted result supersedes the
  initial six-test subset recorded above.

### P3 host price and region refresh — 2026-10-30 16:20 UTC

- Rechecked official provider documentation. Lightsail currently lists
  2 GiB/2 vCPU at $12/month and 4 GiB/2 vCPU at $24; a 32 GB artifact disk
  adds $3.20/month. Both Tokyo and Singapore regions are available. Its
  documented storage/snapshot prices and the bandwidth caveats are linked in
  `docs/decisions/2026-10-28-p3-deployment-topology.md`.
- DigitalOcean currently lists 2 GiB/1 vCPU at $12, 2 GiB/2 vCPU at $18, and
  4 GiB/2 vCPU at $24 per month; a 32 GiB volume adds $3.20. Singapore is
  listed for CPU Droplets; no Japan CPU Droplet region appears in the current
  availability table. The 2-vCPU 2-GiB plan is a useful current comparison
  missing from the earlier note.
- These are public list-price arithmetic and region lists, not account quotes
  or measured latency. Neon remains in Singapore, and the actual monthly cap,
  whether it includes Neon, domain/DNS, backups, and egress remain unselected.
  Asked the user to choose provider/region and a cap; no cloud resource or
  account setting was created or changed.

### P1 runtime and ChatGPT access refresh — 2026-10-30 16:34 UTC

- Read-only unauthenticated GETs to the production alias returned
  `/healthz`=200 (`configured=true`, `auth_mode=local_oauth`), `/readyz`=404,
  protected-resource metadata=200, and `/mcp`=401. The response does not
  identify the deployed SHA; it establishes liveness and the unauthenticated
  boundary only. The local Gateway source has `/readyz`, so the current alias
  is not proven to serve the reviewed readiness-capable revision.
- A fresh visible ChatGPT in-app browser tab displayed **Log in / Sign up**.
  No account action was taken. The user was asked to identify the authenticated
  target workspace and whether its operator can configure MCP write actions.
  ChatGPT OAuth/tool/CPU acceptance remains NOT RUN.
- `gh pr view 51` still reports OPEN/DRAFT, head `aa681f4`,
  `REVIEW_REQUIRED`, zero reviews, and all seven required checks successful
  on that pushed head. A subsequent branch-protection API read was rate-limited;
  the same-day successful settings read is preserved in `docs/BASELINE_AUDIT.md`.
  No GitHub, deployment, account, database, or policy setting was changed.

### P1 current ChatGPT custom MCP requirements — 2026-10-31

- Re-read the current OpenAI Help Center custom MCP guide. Business and
  Enterprise/Edu have full custom MCP support on ChatGPT web; Business app
  creation/publication is admin/owner-only, and Enterprise/Edu can grant
  selected creators/testers through RBAC while publication stays
  admin/owner-only. The current Plugins flow does not require Developer Mode.
- The guide also calls out OAuth refresh-token issuance and `offline_access`
  advertisement. The local authorization-server metadata advertises
  `offline_access` and refresh-token grant support; live ChatGPT OAuth remains
  unverified. Updated the source-check record in
  `docs/CHATGPT_ACCEPTANCE.md`. No account or workspace was available to test;
  ChatGPT acceptance remains NOT RUN.
- Source: [OpenAI Help Center: Connecting custom MCP servers in ChatGPT](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).

### P1 PR and public endpoint refresh — 2026-10-30 16:38 UTC

- Refreshed PR #51 read-only: still OPEN/DRAFT at pushed head `aa681f4`,
  `REVIEW_REQUIRED`, no GitHub reviews, seven required checks successful. The
  checks exclude all current local changes.
- Fresh public GETs returned `/healthz`=200, `/readyz`=404,
  protected-resource metadata=200, and unauthenticated `/mcp`=401. No deployed
  SHA was exposed; deployed readiness and ChatGPT-originated execution remain
  unproven. Full details are in `docs/CHATGPT_ACCEPTANCE.md`.
- No GitHub or deployment setting changed; `policies/repository-state.yaml`
  remains parked.

### Candidate checkpoint graph and focused revalidation — 2026-10-31

- Inspected actual commit parents for all 20 local candidate refs and checked
  adjacent-ref ancestry. The refs are ancestor-ordered, but several commits
  have intermediate parents; ref names are historical checkpoints, not a
  guarantee of standalone PR boundaries. The exact parent map and explicit
  proposed review ranges are recorded in
  `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`.
- Re-ran changed-test subsets in detached worktrees with candidate-local
  `PYTHONPATH`: `0d02058..311d6a9` passed 92 tests;
  `7c4454b..c8172c0` passed 22; `f15ab32..f054aebe` passed 6. Existing exact
  checkpoint runs for `c8172c0..d794c13` (21 passed) and
  `d794c13..cccfcb8` (6 passed) were reconciled into the same table; the
  documentation-only `cccfcb8..f15ab32` range has no changed test files.
  The new runs reused the primary Gateway Python 3.12 dependencies and emitted
  one existing Starlette deprecation warning each. Temporary worktrees were
  removed.
- This closes only focused changed-test evidence for those ranges. It does not
  replace complete Gateway/Core suites on proposed cumulative PR heads, GitHub
  CI, independent GitHub review, or runtime acceptance. PR #51 remains
  OPEN/DRAFT at pushed `aa681f4`; `mode: parked` is unchanged.
- Exact test modules: checkpoint `311d6a9` ran `test_http_auth.py`,
  `test_worker_recovery.py`, `test_http_security.py`, provider self-test,
  RunPod adapter/current-pricing/v1/v1-adapter/v2/list-pods, and source tests;
  `c8172c0` ran external-auth, local-OAuth, migration, and owner-migration
  tests; `f054aebe` ran local-OAuth and package-metadata tests. The first,
  second, and final invocations passed 92, 22, and 6 respectively. The exact
  invocation lists and scope notes are recorded in the worktree-slices table.

### First P1 review candidate full local suite — 2026-10-31

- Evaluated the exact proposed `origin/main..c824b90` source in a fresh
  detached worktree. Full Gateway suite with PostgreSQL 16 pinned to digest
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  and the digest-pinned real CPU image passed **198 tests / 2 optional skips**
  in 19.82 seconds. Full root/Core suite passed **452 / 1 Python 3.11-only
  skip** in 1.14 seconds. Both had the existing Starlette deprecation warning.
- The Gateway rerun skipped both optional Torch and Modal integrations because
  the reused primary venv contains neither dependency. An earlier exact-head
  run in a fresh Python 3.12.13 environment passed **199 / 1 skipped**, WebMCP
  **3/3**, and `compileall`; the same 200-test Gateway inventory passed.
- Candidate modules resolved from the candidate worktree; dependencies came
  from the primary Python 3.12 venv. Temporary PostgreSQL container and both
  worktrees were removed; port 55613 was confirmed free and only the primary
  worktree remained. Detailed inputs and scope:
  `docs/acceptance/2026-10-31-p1-c824-candidate-suite.md`.
- This is local P1 candidate evidence, not clean locked install, GitHub CI,
  GitHub review, ChatGPT OAuth/tool/CPU acceptance, or production-host
  acceptance. PR #51 remains OPEN/DRAFT; `mode: parked` remains unchanged.

### P3 backup/operations candidate full local suite — 2026-10-31

- Tested proposed candidate `c8172c0..d794c13` from an isolated worktree at
  `d794c13`. Built the CPU image from that same candidate's Dockerfile with
  matching OCI source/revision labels and pinned Python base; image digest is
  `sha256:205561a7ff6d32de0a750485f72613878435f660b90b050c86c789aad876fc2d`.
- With disposable loopback PostgreSQL 16 pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  full Gateway passed **272 tests / 2 optional skips**. Root/Core passed
  **515 / 1 Python-version skip**. The reused Gateway venv lacks optional
  Torch and Modal; one existing Starlette deprecation warning remained.
- The disposable DB container/worktree were removed. Candidate image remains
  only in the local Docker cache. Detailed record:
  `docs/acceptance/2026-10-31-p3-d794-candidate-suite.md`. This is local
  candidate validation, not Linux GitHub CI, independent review, production
  restore/RPO/RTO, second-operator recovery, alert delivery, or ChatGPT
  acceptance. Keep `mode: parked`.

### P3 package/CI candidate full suite and wheel inspection — 2026-10-31

- Tested proposed candidate `d794c13..cccfcb8` from a detached worktree at
  `cccfcb8`. Its source-matched, OCI-labeled CPU image passed the full Gateway
  suite with pinned disposable PostgreSQL 16: **274 passed, 2 optional skips**;
  Core passed **517, 1 Python-version skip**. Torch and Modal are optional
  dependencies absent from the reused Gateway environment.
- Built the wheel from that exact candidate worktree and inspected its archive:
  23 `gpu_gateway` Python modules and four UI/WebMCP assets are present.
  Wheel SHA-256 is
  `a173430733f32f88e33833d938a9a385778d6d08d3722ce42586751f7fc43f7a`.
- Evidence: `docs/acceptance/2026-10-31-p3-cccf-package-candidate-suite.md`.
  Temporary worktree and database were removed. This is local packaging and
  test evidence, not GitHub CI/review or hosted acceptance; keep
  `mode: parked`.

### Current security review and public acceptance boundary — 2026-10-30 16:59 UTC

- A read-only Security Review of the current uncommitted changes reported no
  actionable security findings. The reviewer specifically confirmed the
  worker-crash subprocess receives the test database URL through stdin, not
  argv. No files were changed by the review and no tests were run.
- Refreshed PR #51: OPEN/DRAFT at `aa681f4062dac6b73bcf380a38a4258b96a47e1d`,
  review required, seven Actions checks plus Vercel successful. Those checks
  are for the pushed head only, not this dirty worktree.
- The live `main` protection API confirms strict required checks for Python
  3.11/3.12/3.13, Trusted reference container, Gateway offline, Gateway comment
  bridge, and Project bridge. This gives the exact remote CI gate for a future
  reviewed PR head; current local edits are not yet on that head.
- Refreshed the public alias: `/healthz`=200 with local OAuth configured,
  `/readyz`=404, protected-resource metadata=200, and unauthenticated `/mcp`=401.
  This does not prove deployed revision/readiness or ChatGPT acceptance.
  Detailed record: `docs/CHATGPT_ACCEPTANCE.md`. Keep `mode: parked`.

### Current dirty Gateway source-matched full-suite revalidation — 2026-10-30 17:06 UTC

- Built the CPU smoke image from the checked-out Dockerfile and confirmed the
  in-image `smoke.py` and `supervise.py` hashes match the build context. Image
  digest is `sha256:df0740a1425e47096f2921b57810f40d91ffb59d13b7f85766b21f95d097837a`;
  its synthetic revision label matches the integration fixture SHA.
- Re-ran the current dirty Gateway source with pinned PostgreSQL 16 and the
  source-matched image: **427 passed, 2 optional skips**. Core suite: **550
  passed, 1 Python-version skip**. The outage test uses a restartable
  disposable DB, removed after the run. Full provenance and excluded harness
  attempts: `docs/acceptance/2026-10-30-current-worktree-source-matched-suite.md`.
- Early harness attempts failed because of a wrong image env-var name,
  synthetic source-label mismatch, and an auto-removing PostgreSQL container;
  those results are excluded. The corrected exact-source run passes. This is
  still local evidence only; the changed source is uncommitted, not covered by
  GitHub CI/review or hosted acceptance. Keep `mode: parked`.

### Current dirty paired-backup real PostgreSQL restore — 2026-10-30 17:11 UTC

- Exercised `backup_generation.create_generation()` and
  `verify_generation()` from the current dirty-source fingerprint against
  PostgreSQL 16 schema v8. Created a real `pg_dump` archive, verified it with
  `pg_restore --list`, restored it to a separate database, extracted the paired
  artifact archive, and retrieved the same synthetic 33-byte payload through
  `ArtifactStore.get()` with matching SHA-256.
- PostgreSQL client binaries ran in a task-specific container because the host
  lacks `psql`/`pg_dump`; the source/restore DBs were in a separate disposable
  container. The backup tool's seven-unit systemd probe was stubbed to the
  expected inactive state, so no target host was tested. All temporary
  resources were removed. Exact hashes and limits:
  `docs/acceptance/2026-10-30-dirty-source-paired-restore.md`.
- This strengthens local P3 paired-backup evidence; production/Neon, target
  systemd, second-operator, and measured RPO/RTO acceptance remain open. Keep
  `mode: parked`.

### Review-slice inventory and ChatGPT access refresh — 2026-10-30 17:16 UTC

- Reconciled the current PR/base diff plus untracked local files against the
  P1/P3/P4/P5/cross-cutting and foundation-only ownership lists. The 178-path
  union is covered exactly once: no missing, stale, or duplicate paths. Slice
  counts are P1=5, P3=52, P4=50, P5=3, cross-cutting=15, plus 53 foundation
  paths. The updated map is `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`.
- Opened ChatGPT in a fresh visible browser tab; it displayed Log in / Sign up.
  No authenticated target workspace is available in this browser session, so
  live ChatGPT OAuth/tool acceptance remains unrun. See
  `docs/CHATGPT_ACCEPTANCE.md`.
- PR #51 is still OPEN/DRAFT at pushed `aa681f4`; all seven strict required
  checks pass on that head and review remains required. Local edits remain
  uncommitted and have not received those GitHub checks. No remote or deployment
  state was changed; keep `mode: parked`.

### P1 OAuth DCR persistence and schema v9 — 2026-10-30 17:44 UTC

- Fixed the long-idle reauthorization path: DCR clients are provisional until
  owner consent, then persist so ChatGPT can reuse the client ID after token
  expiry. Expired provisional registrations remain eligible for cleanup.
- Added schema v9 and a v8 migration that preserves clients with historical
  token references. SQLite OAuth/migration tests passed **17/17**; the isolated
  PostgreSQL 16 v8-to-v9 preservation regression passed **1/1**.
- The full Gateway suite against PostgreSQL 16 passed **426**, skipped **7**,
  with **1 warning**. CPU/Docker smoke integration was not enabled. No hosted
  database was migrated; the disposable test container was removed.
- Detailed scope and evidence: `docs/acceptance/2026-10-31-p1-dcr-persistence-schema-v9.md`.
  GitHub review/CI, ChatGPT workspace acceptance, and hosted migration remain
  outstanding. Keep `mode: parked`.

### P1 OAuth/schema v9 Security Review — 2026-10-30 17:45 UTC

- The user-selected read-only Security Review of the current uncommitted diff
  found no actionable findings. It confirmed that only the owner consent path
  makes DCR clients persistent; provisional registrations remain prunable;
  persistence alone does not mint tokens or bypass consent, redirect/resource
  binding, PKCE, or token client/resource checks; and schema v9 migration is
  additive, idempotent, and transactional.
- No files were modified by the review. This does not replace GitHub review or
  hosted ChatGPT acceptance. Keep `mode: parked`.

### P1 schema-v9 source-matched CPU integration — 2026-10-30 17:49 UTC

- Rebuilt the registered CPU smoke image from the checked-in Dockerfile and
  matched its two in-image script hashes to the current build context. Ran the
  complete Gateway suite against pinned PostgreSQL 16 and the real digest-
  identified local CPU container: **431 passed, 2 optional skips, 1 warning**.
  It includes owner-authenticated MCP result/artifact retrieval, OS-worker
  death after container start with same-run recovery, PostgreSQL outage
  recovery, and OAuth schema-v9 migration/tests.
- The Core suite separately passed **550 / 1 Python-3.11-specific skip** under
  Python 3.12. Two excluded Gateway attempts had harness issues: a 65-character
  image identifier and a dynamic DB host port that changed after container
  restart. The passing attempt uses the exact image ID and fixed loopback port.
- Fingerprint, image digests, commands, exclusions, and scope:
  `docs/acceptance/2026-10-31-p1-v9-source-matched-cpu-suite.md`. This is
  source-matched local evidence, not GitHub CI/review or hosted ChatGPT/host
  acceptance. Keep `mode: parked`.

### P4 adapter candidate-receipt signing primitive — 2026-10-30 18:01 UTC

- Added `sign_adapter_candidate_receipt()` in
  `gateway/gpu_gateway/candidate_receipts.py`. It binds the supplied exact
  PlanV2 fingerprint, persisted run, source/image/selected resource, normalized
  success claims, and SHA-256 of a bounded provider-object projection; it then
  checks the signed envelope through the existing verifier before returning.
- Tests cover valid signature/digest round-trip, overlong/future timestamps,
  wrong provider evidence namespace, wrong plan fingerprint, unsuccessful GPU
  claims, and invalid projection root/key/value/cycle cases. TDD RED for the
  missing signer: **4 failed, 9 passed**. GREEN initially passed **15/15**.
  Independent review found Python JSON coercion ambiguity; four strict-
  projection regressions failed before fix (**4 failed, 15 passed**), then the
  focused suite passed **20/20** after recursive JSON validation.
- Final full Gateway suite with digest-identified local CPU image and pinned
  PostgreSQL 16 passed **442 / 2 skipped / 1 warning**. Core passed **550 / 1
  Python-3.11-specific skip**. Optional Torch and Modal tests were skipped.
  Independent re-review of `3d82405..a794438` found no Critical, Important,
  or Minor issues. Review identified that authenticating and cross-checking the
  supplied provider object remains the future adapter's responsibility.
- Local commits `3d824053612be93a56c96142c7662c1a551d6a91` and
  `a794438f42bd7246f463eaaa40d963af0aae9d13` contain the signer, its strict
  projection fix, tests, and task plan; neither has been pushed. This helper
  does not implement a RunPod/Modal candidate backend or establish real GPU,
  quota, result transport, or cleanup acceptance. Detailed evidence:
  `docs/acceptance/2026-10-31-p4-adapter-receipt-signer.md`. Keep
  `mode: parked`.

### Current ChatGPT, deployment, and PR gate recheck — 2026-10-31 03:34 JST

- A new visible ChatGPT tab is logged out. Read-only production probes confirm
  liveness and OAuth metadata but `/readyz` remains 404 and unauthenticated
  `/mcp` remains 401. The protected PR preview redirects to Vercel SSO, so its
  readiness could not be inspected without authenticated preview access.
- PR #51 remains OPEN/DRAFT at remote head
  `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, with zero reviews or inline
  comments. Its seven required Actions checks passed on that remote head at
  2026-10-30 12:39 UTC. Local HEAD is `a794438f42bd7246f463eaaa40d963af0aae9d13`
  (68 commits ahead of local `origin/main`, 2 ahead of the PR head), with 40
  modified/untracked paths outside those checks and reviews.
- This recheck ran no authenticated request, OAuth flow, MCP action, provider
  call, GPU allocation, or deployment. `mode: parked` remains unchanged.
  ChatGPT-originated CPU execution and cross-conversation result retrieval are
  still NOT RUN. Evidence: `docs/CHATGPT_ACCEPTANCE.md` and
  `docs/RELEASE_MATRIX.md`.

### Current-source PostgreSQL artifact-manifest integration — 2026-10-31 03:37 JST

- Ran the focused backup-integrity PostgreSQL integration against the current
  dirty source at HEAD `a794438f42bd7246f463eaaa40d963af0aae9d13`, using a
  disposable PostgreSQL 16 container pinned by digest and bound to loopback:
  **1 passed**, one existing Starlette deprecation warning. It verifies
  manifest query shape, owner/run artifact binding, and blob/archive size and
  digest checks, including malformed manifests and corrupted bytes.
- Removed the uniquely named disposable database container; verified port
  55471 has no listener. No existing container, host service, or production
  database was changed. This is focused current-source integration evidence,
  not a fresh paired `pg_dump`/`pg_restore` drill or target-host acceptance.
- Detailed command, image digest, tested file hashes, scope, and exclusions:
  `docs/acceptance/2026-10-30-dirty-source-paired-restore.md`. Keep
  `mode: parked`.

### Current-source PostgreSQL OAuth and migration rerun — 2026-10-31 03:38 JST

- The current dirty-source PostgreSQL integration set passed **7/7** on a
  disposable loopback PostgreSQL 16 instance pinned by digest. It covers
  schema v1/v4/v8 upgrades through v9, preservation of token-referenced DCR
  clients, concurrent single-use refresh rotation, and rollback after an
  injected token-row insertion failure.
- Removed the test database container and confirmed ports 55471/55472 have no
  listener. This strengthens local OAuth/migration evidence only; it is not
  ChatGPT OAuth, GitHub review/CI, hosted migration, or production acceptance.
  Full command and tested-file hashes:
  `docs/acceptance/2026-10-31-p1-dcr-persistence-schema-v9.md`.

### Current-worktree P2 worker-crash recovery rerun — 2026-10-31 03:41 JST

- Re-ran `test_postgres_worker_crash_after_docker_start_recovers_same_run`
  against current HEAD `a794438f42bd7246f463eaaa40d963af0aae9d13`, the current
  digest-identified CPU smoke image, and a disposable loopback PostgreSQL 16
  container: **1 passed**. The supervisor recovered the same run after worker
  death, returned its exact artifact, recorded cleanup, removed the container,
  and released the admission slot.
- Removed the uniquely named DB container and verified port 55473 had no
  listener. Full command, image/source hashes, and limits:
  `docs/acceptance/2026-10-31-postgres-container-crash-recovery.md`. This is
  local recovery evidence, not target-host or ChatGPT recovery acceptance.

### Continuation status reconciliation — 2026-10-31

- Re-read the current checkout and PR #51 instead of relying on older status
  text. HEAD is `a794438f42bd7246f463eaaa40d963af0aae9d13`, 68 commits ahead of
  local `origin/main` and 2 ahead of the pushed PR head. The worktree has 25
  modified tracked paths and 15 untracked paths, none staged. PR #51 remains
  OPEN/DRAFT at `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, with zero reviews;
  its green checks cover only that pushed SHA.
- Corrected the latest-state sections in the roadmap, review-slice inventory,
  and Luna handoff. Historical `aa681f4`/427-test snapshots are now explicitly
  labeled historical; the current 480/2 Gateway and 550/1 Core results and
  focused PostgreSQL reruns point to their current-source evidence records.
- Recomputed ownership for the exact dirty overlay: P1=10 paths, P2=2, P3=11,
  P4=1 evidence record, P5=5, and cross-cutting=11. A path-set comparison
  against `git diff --name-only` plus untracked files found 40/40 entries,
  with no missing, stale, or duplicate assignments. The current `test_postgresql.py`
  migration delta stays with P1; P3 artifact-manifest checks are isolated in
  `test_postgresql_backup_integrity.py`.
- This documentation repair does not close GitHub review/CI for the current
  source, production readiness, ChatGPT OAuth/tool/CPU acceptance, P3 host
  operations, or GPU/paid gates. Repository mode remains `parked`.

### P1 DCR/schema-v9 candidate overlay on PR #51 head — 2026-10-31

- Built a six-file P1 code/test patch on a detached worktree at the exact
  pushed PR #51 head `aa681f4062dac6b73bcf380a38a4258b96a47e1`. It applies
  cleanly. The candidate's six code/test files match the current worktree
  byte-for-byte. Patch artifact:
  `/tmp/gpu-control-p1-dcr-v9-review.patch`, SHA-256
  `1a0e4bafe567caf240b8aa8623280c8ae6a32ff6251d985d8bd73669a1c7fb27`.
- Candidate-source OAuth/migration unit tests passed **17/17**. Candidate
  PostgreSQL migration, DCR preservation, refresh-token concurrency, and
  rollback tests passed **7/7** against a disposable digest-pinned PostgreSQL
  16 container on loopback. The container was removed and port 55474 closed.
- This validates a review-sized overlay atop the existing pushed PR head; it
  does not establish a mergeable P1 series based on `main`, GitHub CI/review,
  deployed readiness, or live ChatGPT acceptance. No commit or push was made;
  repository mode remains `parked`.

### P3 backup-integrity candidate overlay on PR #51 head — 2026-10-31

- Rebuilt the current three-file P3 backup-integrity patch from the dirty
  checkout and applied it to a detached worktree at pushed PR #51 head
  `aa681f4062dac6b73bcf380a38a4258b96a47e1`. The candidate files are byte
  identical to current source. Patch:
  `/tmp/gpu-control-p3-backup-integrity.patch`, SHA-256
  `d36b3a575a7f9944bfcf7718cfe3d827d7619365f8897adbd940591967d3768a`.
- Candidate-source backup-generation and PostgreSQL manifest-integrity tests
  passed **25/25** against disposable digest-pinned PostgreSQL 16 on loopback;
  the container was removed and port 55475 closed. This current patch replaces
  the older P3 fingerprint `e5c05d1f...`.
- This validates the P3 code/test overlay on the pushed PR head. It does not
  establish GitHub CI/review, production backup, or target-host recovery
  acceptance. No commit or push was made; repository mode remains `parked`.

### P1/P2/P3 overlay composition — 2026-10-31

- Composed the three tested overlays in sequence on a detached worktree at
  pushed PR #51 head `aa681f4062dac6b73bcf380a38a4258b96a47e1`: P1 schema-v9
  OAuth, P2 worker-crash recovery, then P3 backup-integrity. All three patches
  apply in order; the cumulative candidate has 11 changed paths (10 code/test
  files plus the P2 acceptance record), all 10 code/test files byte-identical
  to the current working tree. Candidate `git diff --check` passes.
- Standalone candidate tests have passed: P1 **17 unit + 7 PostgreSQL**, P2
  **1 real-container/PostgreSQL crash-recovery**, and P3 **25 backup / manifest
  integrity**. The cumulative candidate then passed the full Gateway suite:
  **431 passed, 2 optional skips, 1 warning** in 25.24 seconds with the
  digest-pinned PostgreSQL 16 container and current digest-identified CPU
  image. The first full-suite attempt incorrectly used Docker `--rm` and
  failed 10 PostgreSQL cases after outage injection removed the DB container;
  the corrected run kept the stopped container restartable, passed, then
  removed it and verified the port closed.
- This stacked overlay still sits atop PR #51's old 68-commit branch rather
  than forming independent PRs based on `main`. Do not treat this composition
  as merge-ready. No commit, push, PR edit, deployment, or spending action was
  made; `mode: parked` remains.

### Main-based current-source reconstruction and MCP CPU rerun — 2026-10-31

- Rebuilt the complete current source snapshot in a fresh detached worktree at
  `origin/main` (`24ecb9b`), including the tracked SDD ledger file. Applied the
  candidate boundary deltas through PR #51 head `aa681f4`, the two later local
  commits through `a794438`, and the exact dirty overlay. The cumulative tree
  passed `git diff --check`; a direct replay patch from `origin/main` also
  applied cleanly. Compared path set, bytes, and executable bits against the
  primary worktree: **338 paths, zero mismatches**.
- Confirmed `gpu_gateway.__file__` resolves inside the reconstructed candidate,
  then ran `tests/test_local_mcp_integration.py` there against the real
  digest-pinned CPU image. Result: **1 passed**, one existing Starlette
  deprecation warning. This supplements the captured run/artifact receipt in
  `docs/acceptance/2026-10-31-p1-v9-source-matched-cpu-suite.md`.
- Then ran the full Gateway suite from that candidate with an exact import-path
  check, the digest-pinned CPU image, and disposable PostgreSQL 16 on loopback:
  **480 passed, 2 skipped, 1 warning**. The first attempt used nonexistent DB
  `gateway` and failed 10 DB-backed tests; after inspecting the test contract,
  using `gateway_test` made the focused outage test pass 1/1 and the full suite
  pass. The exact DB container was removed and the port closed.
- The replay artifact is a cumulative source candidate, not a small review
  slice or GitHub PR head. GitHub CI/review, deployment, authenticated
  ChatGPT calls, and target-host operations remain open. PR #51's green checks
  still cover only its pushed head; parked mode remains.

### Current working-tree Security Review — 2026-10-31

- Completed a read-only Codex Security diff scan of the exact working-tree
  snapshot based on `a794438f42bd7246f463eaaa40d963af0aae9d13` (snapshot
  digest `codex-security-snapshot/v1:sha256:32c101e1830d4d539d66eb053509a53af42f18c9986b142c30c2e6f4442644bc`).
  The changed-source inventory contained five files: artifact backup
  generation, Gateway key configuration, local OAuth, schema-v9 migration,
  and the signed paid-authorization verifier. Sequential source review found
  **zero reportable candidates**. Delegated workers were unavailable in this
  session, so this is not an independent second-reviewer result.
- The review specifically found the P5 verifier remains a pure, unintegrated
  helper: no worker caller, durable one-use admission, or provider side effect
  is in this diff. These are future implementation/acceptance requirements,
  not evidence of live paid-execution readiness. ChatGPT OAuth/tool/CPU,
  target-host operations, production recovery, GPU, and paid execution remain
  open; `mode: parked` is unchanged.
- Readable report:
  `/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/a794438f42bd7246f463eaaa40d963af0aae9d13_20261030T192001Z_9ead4udf/report.md`.
- Refreshed GitHub state read-only after the local review: PR #51 is still
  OPEN/DRAFT at `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, marked
  `REVIEW_REQUIRED` and `BLOCKED`. Its seven required Actions checks and
  Vercel statuses succeeded on that pushed head (last completed 2026-10-30
  12:39 UTC); they do not cover the local source snapshot or current dirty
  worktree. Main branch protection currently requires one approval and those
  seven named checks. No GitHub state was changed.
- Refreshed deployment/runtime provenance: production `gpu-control.vercel.app`
  is deployment `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ` at old `main` SHA
  `24ecb9b`; the READY PR preview is at `aa681f4` but remains SSO-protected.
  Public production `/healthz` and OAuth discovery respond, `/mcp` rejects an
  unauthenticated request with 401, and `/readyz` is 404. Thus the current
  source is not deployed on the public alias, while the preview's readiness is
  not observable through unauthenticated access. No share link, configuration,
  deployment, or account state was changed; live ChatGPT acceptance remains
  **NOT RUN**.
- Rechecked the local Secure MCP Tunnel prerequisites by variable names and
  path presence only: no Gateway origin/OAuth client or tunnel config, native
  `tunnel-client`, tunnel ID/runtime key, or running Gateway/tunnel container
  is available. No values were read and no service/tunnel was started. The
  bounded ChatGPT smoke therefore cannot begin from this environment yet.

### P4 receipt signer exact-range Security Review — 2026-10-31

- Completed a read-only Security Review of the two commits between PR #51's
  pushed head `aa681f4062dac6b73bcf380a38a4258b96a47e1` and local HEAD
  `a794438f42bd7246f463eaaa40d963af0aae9d13`. The exact snapshot digest is
  `codex-security-snapshot/v1:sha256:754fa41162a07de319b5250427ba94c55be9ea36c8c8bd7a70dcc77788f7c065`.
- The scan reviewed the new receipt signer, its direct tests and acceptance
  record, plus the worker and registry trust gates. It found **zero reportable
  findings**. Projection-to-claim correlation and key isolation proof are
  deferred to any future concrete provider adapter; no registered candidate-
  bound provider adapter currently invokes this helper. This was a sequential
  source review, not an independent second-reviewer result.
- Report:
  `/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/a794438f42bd7246f463eaaa40d963af0aae9d13_20261030T192803Z_s456uisd/report.md`.
  No provider credentials, runtime, GPU, or account actions were used.
- This closes the local review gap for the two commits, not P1 ChatGPT
  acceptance. Local work can continue. To run real ChatGPT acceptance, an
  authenticated eligible ChatGPT workspace and approved, reachable,
  readiness-verified Gateway endpoint are needed; the checked session has
  neither. The local tunnel preflight also lacks Platform Tunnels Read + Use
  access/configuration. Keep parked mode.

### Current source revalidation and ChatGPT gate refresh — 2026-10-31

- Re-ran the entire Gateway suite from the current dirty working tree with the
  repository-owned CPU image and a dedicated PostgreSQL 16 container bound
  only to loopback: **480 passed, 2 optional skips, 1 warning**. The run
  exercised real local CPU/MCP execution, OAuth/schema migration, artifact
  integrity, and PostgreSQL outage recovery. Core suite: **550 passed, 1
  Python-version-specific skip**. The disposable DB container was removed and
  its port closed. Full command and inputs:
  `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`.
- Completed a read-only Security Review of the exact then-current working-tree
  snapshot (`codex-security-snapshot/v1:sha256:d332334f41caf2e150bcbac547639307710aeb004e1ccddd7c675191b19404e6`).
  It covered all five changed runtime-source inventory rows and found zero
  reportable candidates. The review was sequential, not independent; tests,
  documentation, and external/runtime behavior were outside that scan.
  Report:
  `/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/a794438f42bd7246f463eaaa40d963af0aae9d13_20261030T194335Z_xyd5avew/report.md`.
- Fresh GitHub readback: PR #51 is OPEN/DRAFT at remote head
  `aa681f4062dac6b73bcf380a38a4258b96a47e1`, `REVIEW_REQUIRED`; seven checks
  pass on that head only. At the time of readback, the local tree was at
  `a794438` with 40 dirty paths, outside those checks and reviews. This new
  acceptance record was added afterward. A separate branch-protection read
  confirms `main` still requires one approval, dismissal of stale reviews,
  strict successful status checks from GitHub Actions app 15368, conversation
  resolution, and admin enforcement; force pushes and deletion are disabled.
  PR #51 has zero submitted reviews, so the required review is still open.
- Fresh Vercel readback: production alias deployment
  `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ` is still `main` at
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. The latest PR preview
  `dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe` is READY at `aa681f4` and protected by
  SSO. The public alias returned `/healthz`=200, `/readyz`=404, OAuth
  discovery=200, and unauthenticated `/mcp`=401. The in-app ChatGPT browser
  remains logged out. Vercel denied environment-variable listing with 403; no
  values were requested or read. No share link, deployment, GitHub write, or
  account state was changed.
- These results strengthen local source/runtime evidence but do not close P1
  ChatGPT acceptance. An authenticated eligible workspace and authorized
  access to a readiness-verified endpoint are still required. P3 target-host
  operations, P4 live GPU, and P5 integrated paid authorization remain open;
  preserve `mode: parked` and all spending gates.


### P1 OAuth DCR schema-v9 follow-up PR #58 — 2026-10-30 21:02 UTC

- Published Draft PR #58, `P1 OAuth follow-up: preserve consented DCR clients`,
  head `cb37a630e1609b6166bc0122f3aba86a759beb50`, based on PR #51 head
  `3346d0818dd1dd195d8105c348f00b51e2879daa`. The focused seven-path change
  makes DCR clients persistent after owner consent, retains cleanup of expired
  provisional registrations, and adds the additive schema-v9 migration that
  preserves clients referenced by historical tokens. The schema-v8 parent is
  why this follow-up is stacked after #51 rather than isolated on schema-v7 PR #57.
- Clean local Python 3.12 candidate-source OAuth/migration/PostgreSQL modules:
  **17 passed, 7 PostgreSQL-dependent tests skipped**, with one Starlette
  deprecation warning. `gpu_gateway.__file__` and `gpu_control.__file__` resolved
  inside the exact candidate worktree.
- GitHub CI on the exact PR merge candidate passed all seven standard Actions
  contexts and Vercel. Gateway CI passed **428 passed, 1 skipped, 1 warning**
  against its PostgreSQL 16 service and digest-identified CPU container; WebMCP
  and Project bridge checks passed. This exact current-base run supplies the
  PostgreSQL migration evidence that was skipped in the local host run.
- The same schema-v9 source change has a prior read-only Security Review with
  no actionable findings. PR #58 remains Draft with no GitHub review. PR #51
  is still an unmerged aggregate based on #57 and its earlier checks are stale
  after retargeting, so #58 is not independently mergeable.
- Production readiness and authenticated ChatGPT acceptance remain open:
  latest public `/readyz` is 404; no authenticated OAuth/tool/CPU run was made.
  No hosted database was migrated. Keep `mode: parked`; provider and paid
  execution remain separately unauthorized.

- Re-reviewed the exact current PR #58 head `561a6c7` against PR #51 base
  `e3ffcef` with a separate read-only Security Review. No actionable findings
  were reported in `local_oauth.py`, the schema-v9 migration, or the associated
  OAuth/PostgreSQL migration tests. The review confirmed that only the
  owner-consent path promotes DCR clients to persistent status; migration is
  additive and transactional; and existing client/resource/revocation/expiry
  checks remain in force. This was static source review only: no tests or live
  PostgreSQL run were performed as part of the review. GitHub still reports PR
  #58 OPEN/DRAFT/CLEAN with no submitted review decision; hosted ChatGPT
  acceptance remains NOT RUN.

### PR #51 merge-conflict repair — 2026-10-31

- Refreshed the live PR #51 base/head refs. GitHub reported `CONFLICTING`; an
  exact `git merge-tree` identified only `.github/workflows/gateway-ci.yml` and
  `.github/workflows/gateway-bridge-ci.yml` as conflicted.
- In isolated worktree `/private/tmp/gpu-control-pr51-rebase-20261031`, merged
  the current PR #57 base (`51b88f6`) into PR #51 (`3346d08`). Kept PR #51's
  PostgreSQL, real CPU, wheel, Vercel-style install, and systemd CI jobs while
  retaining the PR #57 editable root-package install in both Gateway jobs.
  For the bridge job, the package install runs with `working-directory:
  gateway` and `pip install -e ..`.
- Ruby/Psych parsed all three resulting workflow YAML files and `git diff
  --cached --check` passed. The conflict-only merge delta adds the package
  installation steps in the two workflows; it does not alter application
  source. Published merge commit `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`
  to the existing PR #51 head branch. The primary dirty checkout remains
  untouched.
- Fresh GitHub readback reports PR #51 OPEN/DRAFT at `e3ffcef`, with
  `MERGEABLE` / `CLEAN` against base `51b88f6`. All seven required Actions
  contexts pass (runs `41128262008`, `41128262048`, `41128261906`,
  `41128261918`) and Vercel is successful. This validates the resolved head's
  workflows and aggregate candidate on GitHub; it is not a reviewer approval
  or product acceptance. PR #51 has no submitted review and remains Draft. No
  review or merge was requested; keep parked mode and spending/security gates
  unchanged.

### PR #58 parent-head refresh — 2026-10-31

- PR #58 previously named `codex/chatgpt-cpu-vertical` as its base but its
  recorded base/head ancestry still pointed to pre-repair PR #51 head `3346d08`.
  `git merge-tree` confirmed the current #51 head `e3ffcef` could be integrated
  without conflicts.
- In isolated worktree `/private/tmp/gpu-control-p1-dcr-v9-rebase-20261031`,
  merged `e3ffcef` into the schema-v9 OAuth candidate and pushed the resulting
  head `561a6c7ac697dfdf22f304b60e313fccb2c806a4` to PR #58. The merge adds the
  same two Gateway workflow package-install steps already verified on PR #51;
  the focused OAuth code delta remains unchanged.
- GitHub now reports PR #58 based on #51 head `e3ffcef`, `MERGEABLE`/`CLEAN`.
  All seven standard Actions contexts and Vercel passed on exact refreshed
  head `561a6c7` (Actions runs `41128668613`, `41128668623`,
  `41128668609`, `41128668619`; Vercel deployment
  `3QtLZEQudmfXMHexbmmUc46mVivv`). The former `cb37a63` results were not used
  as evidence. PR #58 remains Draft with no review. No hosted database or
  ChatGPT connection was touched.

### Current ChatGPT access and P5 authority-source audit — 2026-10-31

- Opened `https://chatgpt.com/` in the available in-app browser and observed
  `Log in` / `Sign up` controls. Selecting the running ChatGPT native app was
  rejected by the computer-use safety boundary. This directly confirms that
  this execution session has no authenticated ChatGPT workspace to use for
  OAuth/tool/CPU acceptance. No login or workspace setting was attempted.
- Read the current public `Unjuno/orbitune` `main` at
  `44a1b806160ab5bc721a370d034a6dfcb28f27a8` and inspected its RunPod-related
  workflows. `publish-runpod-canary.yml` is a manually dispatched exact-SHA
  GHCR image publisher with `contents: read` and `packages: write`; it does not
  issue Gateway paid-authorization envelopes or declare a protected GitHub
  Environment. `runpod-canary-smoke.yml` is CPU contract/integration CI.
  `continuous-train.yml` is a legacy CPU reference-training workflow gated by
  local data files and a marker. This confirms the existing Orbitune workflows
  do not supply the independent paid-authority issuer contract required by
  `docs/specs/p5-gateway-runpod-permit-bridge.md`.
- Consequently, the signed-envelope verifier remains an offline primitive; do
  not connect it to worker admission by treating the image publisher, ChatGPT
  OAuth consent, or Gateway browser approval as paid authority. A separately
  reviewed issuer and actor/spend-consent semantics are still required. No
  provider API, workflow dispatch, secret, container, or paid action was used.
  Repository mode remains `parked`.

### P3 backup and Linux operations extracted as PR #59 — 2026-10-31

- Built a focused P3 candidate from the current PR #57 base (`51b88f6`) using
  the exact `c8172c0..d794c13` backup/operations change set. The candidate has
  13 changed paths (1,122 additions): atomic PostgreSQL/artifact backup
  generation, capacity checks, hardened API/migration/capacity units, a
  registered local-CPU workload example, and direct tests/evidence.
- Published Draft PR #59 at
  `9617d56f7dd189ba7660976e8a384a39662d454a`, based on PR #57. GitHub reports
  the exact expected 13 paths. Its seven standard Actions contexts and Vercel
  passed. This exposed a coverage gap: that head had no PostgreSQL-backed
  artifact-manifest regression.
- Extended the same P3 slice with strict live/archived artifact manifest
  digest-and-size verification, an explicit stopped-systemd-unit backup
  precondition, updated backup unit tests, and a PostgreSQL-backed integrity
  regression. The existing Gateway workflow already provisions PostgreSQL 16
  and exports `GATEWAY_TEST_DATABASE_URL`, so the new test joins that exact CI
  suite without introducing another workflow. Exact current PR #59 head is
  `76c2a1a1b4439cf093c4e6efdd39d5121eb08959`, with 14 paths and 1,634
  additions / 10 deletions. All seven GitHub Actions contexts and Vercel pass
  on this exact head; Gateway offline CI run `41130137786` ran against
  PostgreSQL 16 and reported 282 passed, 5 skipped, 1 warning. PR #59 is OPEN,
  Draft, and CLEAN, based on PR #57 at `51b88f6`; it has no independent GitHub
  review yet. Results from `9617d56` were superseded by checks on `76c2a1a`.
- `git diff --check` passed for both candidates. Target-host restore, installed
  services, alert delivery, and measured RPO/RTO remain open. No host or
  provider operation was performed; mode remains `parked`.

- A separate read-only Security Review of the exact PR #59 branch diff
  (`51b88f6..76c2a1a`) found no actionable security findings. Coverage included
  the backup/capacity scripts, systemd units, environment example, workload
  template, and supporting artifact-store behavior. The reviewer did not run
  tests or verify permissions and service behavior on a production host. This
  source review is not a submitted GitHub PR review or target-host acceptance.

### P4 execution boundary revalidation — 2026-10-31

- Re-read the current P4 plan, candidate receipt contract, Gateway worker, and
  existing RunPod v2 core adapter. The core adapter requires a validated
  `LiveExecutionPermit` at construction and before provider operations; the
  Gateway candidate path separately requires `start_candidate_bound`, an
  authenticated candidate observation, receipt validation, capture, and
  cleanup. Therefore the existing paid adapter cannot serve as the P4
  free/credit-backed lane, and the offline paid-envelope verifier must not be
  used to manufacture its permit. The next P4 implementation must be a separate
  candidate-bound backend with exact resource binding and current cost/quota
  checks; keep registration disabled until owner-account evidence and
  independent acceptance exist. No provider API or account was contacted.
- Rechecked `https://chatgpt.com/` in the in-app browser. It displayed `Log in`
  and `Sign up`; no authenticated workspace was available, and no login or
  setting change was attempted. P0 workspace eligibility and P1 ChatGPT
  acceptance remain NOT RUN.

### P4 capability contract state correction — 2026-10-31

- Compared `docs/specs/p4-capability-selection-contract.md` with the current
  provider-evidence store, RunPod worker collector, Gateway selection helper,
  prepare/submit revalidation paths, and worker pre-intent check. The spec
  still described those integrations as unimplemented and claimed RunPod
  inventory was not wired, contradicting the current code and roadmap.
- Corrected the spec to record the implemented offline path and its actual
  boundary: the RunPod catalog can confirm a configured GPU/datacenter row, but
  unknown runtime, CPU/RAM, result, cleanup, quota, and full-cost fields still
  make it non-runnable; Modal billing observations do not establish quota.
  Candidate-bound GPU execution remains disabled and unaccepted. `git diff
  --check` passed. No tests, provider calls, account access, or GPU allocation
  were performed; repository policy remains parked.
- Added the typed `CandidateBoundBackend` lifecycle contract and tightened
  registry readiness to require candidate-bound start, authenticated
  observation validation, capture, cancel, no-create reconcile, cleanup, and
  clean-state confirmation. Existing registry fixtures now implement cancel
  and reconcile to match the required contract. `git diff --check` passed;
  tests were not run. Provider registrations remain disabled for candidate-bound
  execution and `mode: parked` is unchanged.

### P4 provider lane comparison refresh — 2026-10-31

- Rechecked current official RunPod Pod lifecycle docs and Modal Sandbox SDK,
  pricing, and budget docs. RunPod documents GPU release on Pod stop while
  persistent volume storage remains billable; termination is needed to release
  that retained storage. The Gateway RunPod catalog collector does not observe
  complete CPU/RAM/runtime/result/cleanup/quota or storage/egress cost evidence,
  and the existing RunPod core adapter requires `LiveExecutionPermit`.
- Recorded the technical implementation order as Modal candidate-bound,
  credit-backed P4 first and RunPod only through the separate P5 paid gate.
  Modal Sandbox exposes GPU/CPU/memory/network/runtime controls and terminate
  lifecycle, but its public starter credits and billing APIs do not prove the
  selected workspace has sufficient eligible credit or full component coverage.
  Account evidence and actual device/release proof remain required before
  registration. See `docs/decisions/2026-10-28-p4-modal-readiness.md` and the
  P4 roadmap. No provider call, account inspection, or allocation was made;
  policy remains parked.
- Read the current Modal Sandbox SDK reference for device and lifecycle
  evidence. It documents the requested GPU, Sandbox object ID/tags, exit code,
  logs, and waited termination, but no provider-side physical GPU ID/model
  field was identified. `gpu_smoke.py`'s CUDA device name is therefore
  workload-produced evidence, not independent provider attestation. Recorded
  this acceptance boundary: the Modal receipt must not claim verified hardware
  identity until an immutable-image/source chain plus provider-object/result/
  release binding is independently accepted. No provider SDK/account call was
  made and no adapter was enabled.

### P4/P5 credit authorization mismatch correction — 2026-10-31

- Traced `CREDIT_BACKED` through `candidate_plan_requires_paid_authorization`
  and `verify_paid_authorization`. The registry intentionally requires the
  paid gate for this class, but the verifier accepts only `PAID`; therefore
  there is currently no executable Modal credit-backed route. The earlier
  provider comparison's proposal to treat Modal credits as a P4 lane was
  incorrect and has been superseded.
- Corrected the P4 Modal readiness decision and roadmap: Modal may remain the
  adapter target, but credit use requires a separate signed authority claim for
  max gross credit debit, zero out-of-pocket limit, quota fingerprint/coverage,
  owner/actor and exact run/plan/resource. Updated the P5 spec to require that
  contract while keeping rejection fail-closed. No code enables credit use,
  no tests/provider calls/account inspection were performed, and policy remains
  parked.

### P4/P5 credit authorization boundary separation — 2026-10-31

- Added an explicit authorization-kind classifier for candidate plans. Exact
  zero-additional-cost `FREE`/`FREE_QUOTA` (and local provider `LOCAL`) retain
  their no-extra-authority path; `PAID` and malformed/unknown cost evidence
  retain the P5 paid gate; `CREDIT_BACKED` now routes to an independent P4
  credit-authority gate.
- Provider registrations must separately opt in to `supports_credit_execution`
  and expose `validate_credit_authorization`. The worker fails closed with
  credit-specific unavailable/invalid codes, and the API refuses queueing when
  the credit gate is absent. No current provider is opted in and no credit
  verifier exists, so this separates the contracts without authorizing credit
  consumption. Paid execution remains independently gated.
- Focused Gateway checks: registry, experiment API, paid authorization bridge,
  Modal backend, candidate receipt and candidate result-read suites passed
  **107 tests**, with **1 optional Modal SDK test skipped** and one existing
  Starlette deprecation warning. `git diff --check` passed.
- No provider credential/API, credit, GPU, deployment or external state was
  accessed; repository mode remains parked.

### P4 signed credit-consumption verifier — 2026-10-31

- Added `gateway/gpu_gateway/credit_authorization_bridge.py`, a pure Ed25519
  verifier for an independently issued, short-lived, exact-run credit-use
  decision. Claims bind owner, actor, decision, run, Gateway PlanV2 fingerprint,
  provider/resource/image/runtime, current capability-evidence fingerprint,
  maximum gross credit debit, and a literal zero out-of-pocket ceiling.
- Verification requires current CREDIT_BACKED capability and quota evidence,
  a known all-component gross cost, complete eligible-component coverage,
  sufficient current usage headroom and credits, an enforced hard spend cap,
  stop-on-overage behavior, a trusted issuer/key namespace, and a live
  revocation lookup. Added matching default-empty trust settings for a future
  issuer. No settings are consumed by worker admission; no issuer is configured.
- Focused verifier and existing paid-bridge tests passed **50 tests** with one
  existing Starlette deprecation warning. Test coverage uses synthetic signed
  data and proves verifier logic only.
- This advances the offline authority contract but does not establish live
  Modal quota or provider-enforced spend caps. Durable one-use storage, exact
  owner/actor provenance in the Gateway workflow, worker and provider pre-create
  revalidation, independent security review, account evidence, and adapter
  acceptance remain open. No provider call, credit use, GPU allocation,
  deployment, or policy change occurred; keep repository mode parked.

### Current-checkout contract fixture and local suite refresh — 2026-10-31

- Re-ran the core suite on current checkout `a794438` plus the dirty overlay:
  **550 passed, 1 skipped** (Python 3.11-only reproducer).
- The candidate-bound/paid-authorization focused Gateway selection initially
  exposed an outdated test backend double: it omitted `cancel` and no-create
  `reconcile`, both now required by the candidate lifecycle contract. Updated
  only that test double; the focused authorization, registry, receipt, and API
  set then passed **100/100**.
- Re-ran the complete Gateway suite: **467 passed, 15 skipped, 1 warning**.
  Skips were expected in this invocation because the optional Torch and Modal
  packages, digest-pinned CPU smoke image, and dedicated PostgreSQL test
  database/container were not configured. Then reran against the pinned local
  CPU smoke image and a dedicated PostgreSQL 16 container on loopback port
  55484, using the repository-declared `postgresql+psycopg` driver. The exact
  current Gateway source passed **480 tests, 2 optional skips, 1 warning**;
  PostgreSQL OAuth/migrations, real CPU container, and recovery integrations
  were enabled. The dedicated database container was removed, and no listener
  remained on port 55484. Core remains **550 passed, 1 skipped**.
- `git diff --check` passed after the fixture update. No provider/account,
  deployment, ChatGPT, or paid execution was performed. Repository policy
  remains `mode: parked`.

### GitHub candidate checks and review refresh — 2026-10-31 06:46 JST

- Re-read PR state and required checks from GitHub. PR #52 head
  `bc9b0305e6b2e86f9d8c214161b10511ce9f012c`, #57 head
  `51b88f6110e2fc12de1c475e6e3d07c5438eaa3b`, #58 head
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4`, and #59 head
  `76c2a1a1b4439cf093c4e6efdd39d5121eb08959` each report all seven standard
  GitHub Actions contexts successful, plus successful Vercel deployment and
  preview-comment status.
- PR #52 remains OPEN/DRAFT with `REVIEW_REQUIRED`; its current GitHub review
  list is empty. PRs #57–#59 remain OPEN/DRAFT, stacked on unmerged bases, and
  also have empty GitHub review lists.
  These check results do not cover the 47-path local overlay, do not constitute
  GitHub review, and do not establish hosted ChatGPT acceptance.
- A branch-protection API refresh was rate-limited during this check, so the
  earlier protection snapshot was not treated as newly verified. No remote
  branch, PR, deployment, provider, or policy setting was changed.

### PR #52 workflow Security Review — 2026-10-31

- Completed the source-only Security Review for the exact workflow diff from
  `c824b9018ea9dfd3d9f8b45f65b7b3fd60c4fb01` to
  `bc9b0305e6b2e86f9d8c214161b10511ce9f012c`. The three reviewed files are
  `gateway-ci.yml`, `gateway-bridge-ci.yml`, and `project-checks-ci.yml`.
  The change removes PR path filters and gives each job an explicit name so
  the expected checks run consistently. No reportable candidate was found.
- The reviewed jobs use `contents: read`, disable checkout credential
  persistence, have bounded timeouts, and do not enable paid provider
  integrations. Untrusted PR code still executes on hosted runners; this
  review found no new credential or spend path in the scoped changes. GitHub
  organization/repository Actions settings and branch protection remain
  unverified. The formal completed scan is
  `4925b03c-d6ea-49e9-b80b-0892cc69d6ed` (0 findings; source-only).
- This closes only the three-workflow security review. It does not establish
  authenticated ChatGPT use, deployment acceptance, or readiness for paid GPU
  execution. Repository policy remains `mode: parked`.

### P0 live GitHub gate refresh — 2026-10-31

- Re-read live `main`, branch protection, rulesets, GitHub Environments, and
  PRs #52–#59. `main` is still `24ecb9b`; protection requires the seven named
  Actions contexts, one PR approval including approval after the last push,
  strict up-to-date history, resolved conversations, and linear history.
  Admin enforcement is on; force pushes and deletion are disabled. Rulesets
  are empty and Production/Preview Environments have no protection rules or
  branch policy.
- PR #52 and PRs #57–#59 still have no GitHub reviews; #52 is
  `REVIEW_REQUIRED`. Their remote checks pass on their current heads, but this
  does not cover the 47-path local overlay. #57–#59 remain stacked on
  unmerged bases. The live-state correction is recorded in
  `docs/BASELINE_AUDIT.md`.
- The refreshed check output supersedes the prior note that branch protection
  could not be refreshed. No repository setting, PR, deployment, or provider
  state was changed. `mode: parked` remains in force.

### P0 paid-environment prerequisite hardening — 2026-10-31

- The live GitHub API reports both `Production` and `Preview` Environments
  with no protection rules and no deployment-branch policy. Added three
  explicit prerequisites for any future paid activation:
  `paid_environment_required_reviewers_configured`,
  `paid_environment_prevent_self_review_enabled`, and
  `paid_environment_deployment_branch_policy_restricted`. Updated repository
  state regression coverage to require them.
- `python3 -m pytest -q tests/test_repository_state.py
  tests/test_prompt_context_security.py` passed **14/14**; `git diff --check`
  passed. The normative policy remains parked and records the missing
  Environment controls as unsatisfied activation prerequisites. No GitHub
  Environment, secret, workflow, provider, or paid execution setting changed.
- Scope correction: repository search confirms `activation_prerequisites`
  currently supplies governance/configuration state and test assertions; there
  is no runtime reader that checks GitHub Environment settings. These entries
  describe a release/activation prerequisite but do not enforce it at runtime.
  Updated the P5 bridge spec to require fresh trusted GitHub policy evidence
  and fail-closed behavior in any future activation/issuer integration.
- Corrected `docs/PARKED_MODE.md`, which still said `main` was unprotected.
  It now records the verified branch-protection state and missing Environment
  protections, distinguishes the governance gate from runtime enforcement, and
  requires fresh GitHub evidence in any future activation path. Refreshed the
  ownership map to 57 paths and verified exact one-to-one coverage.
- Isolated the exact three-file policy/test patch on a temporary detached
  worktree at live `origin/main` (`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`);
  the same two test modules passed **14/14** there. The candidate is 3 files,
  9 insertions, patch SHA-256
  `72eae8c19547cd089a9bd71116b31ea19769a04ec99e0db302296639c5f886c2`.
  Removed the temporary worktree afterward; the primary dirty worktree and
  refs were preserved. This establishes a small reproducible review candidate,
  not published CI or an independent GitHub review.

### P1 production deployment provenance refresh — 2026-10-31

- GitHub's latest `Production` deployment record is deployment `6660954255`;
  Vercel independently reports active `READY` deployment
  `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`. Both map to `main` SHA
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` on
  2026-09-25 12:43 UTC. A fresh production-alias probe at 2026-10-30 22:03 UTC
  returned `/healthz`=200, `/readyz`=404, OAuth discovery=200, and unauthenticated
  `/mcp`=401. This confirms production still runs the pre-P1 baseline and
  cannot satisfy readiness acceptance. Details are in
  `docs/CHATGPT_ACCEPTANCE.md`.
- This identifies the next dependency: a review-approved P1 candidate and
  authorized deployment path must precede authenticated ChatGPT acceptance.
  No deployment, GitHub setting, OAuth grant, or provider action was performed.

### P5 repository-security policy parity — 2026-10-31

- Compared the live `main` branch-protection API with both the repository and
  bundled paid-execution policies. GitHub requires seven checks, while both
  policies listed only four; this would have allowed incomplete CI evidence to
  satisfy `RepositorySecurityEvidence` for the future paid path. Added the
  three Gateway checks (`Gateway offline tests`, `Gateway comment bridge
  tests`, `Project bridge tests`) to both policy copies and the regression
  assertions.
- The same policy audit found `prevent_self_review: false` in both paid-policy
  copies. Changed it to `true` and updated the regression assertion. Paid mode
  remains disabled and there is no paid workflow or `paid-runpod` Environment.
- Updated `docs/REPOSITORY_SECURITY.md`, `docs/STATUS.md`, and
  `docs/PARKED_MODE.md` to reflect the verified seven-check branch protection,
  missing Environment protections, and the fact that the repository
  prerequisite list alone does not verify live GitHub settings at runtime.
  Future activation must obtain fresh trusted Environment evidence and fail
  closed; no runtime environment verifier was added in this policy-parity fix.
- `PYTHONPATH=src python3 -m pytest -q tests/test_paid_authorization.py
  tests/test_paid_execution_policy.py tests/test_repository_state.py
  tests/test_prompt_context_security.py` passed **43/43**. `git diff --check`
  passed. No GitHub setting, secret, deployment, provider, or paid execution
  state changed. The ownership map now covers 57 paths exactly once.
- Isolated the six-file P5 policy/security-doc change on a disposable detached
  worktree at exact live `origin/main` SHA
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. The P5 authorization and policy
  suites passed **29/29** there. Patch SHA-256:
  `ffcf59b1bfcaf797569286b39382a4fd02233cae17195838bb04f02ef0eb96e7`.
  Removed the temporary worktree; this remains a local candidate without
  published CI or independent GitHub review.

### P5 repository-security evidence completeness — 2026-10-31

- Extended `RepositorySecurityEvidence` to carry and validate the live main
  branch controls confirmed by GitHub: at least one approving review,
  approval after the last push, strict/up-to-date checks, conversation
  resolution, linear history, and administrator enforcement. The policy must
  require each control, and the evidence must prove it; missing/weak values
  fail closed. Bumped the evidence schema to v2 and reject old, boolean, and
  unknown schema versions. This is still a pure evidence validator: it does
  not query GitHub or establish that supplied evidence is fresh or authentic.
- Updated both paid policy copies and the paid-authorization/policy regression
  tests. `PYTHONPATH=src python3 -m pytest -q tests/test_paid_authorization.py
  tests/test_paid_execution_policy.py` passed **38/38**, including strict schema-v2 evidence-version rejection. `git diff --check`
  passed and the bundled/repository policy files are byte-identical.
- The ownership inventory now contains 58 paths (42 modified tracked, 16
  untracked), with the new validator assigned to P5. Paid execution remains
  disabled; fresh GitHub API acquisition, authenticity/freshness binding,
  worker integration, issuer/revocation persistence, and provider
  revalidation are unfinished.

### P1 current OAuth candidate reconciliation — 2026-10-31

- Refreshed GitHub read-only state. PR #58 is OPEN/DRAFT at
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4`, based on PR #51 at
  `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`; its seven required Actions
  contexts and Vercel status succeed, but it has no GitHub review. PR #52 is
  also OPEN/DRAFT at `bc9b0305e6b2e86f9d8c214161b10511ce9f012c`, targets
  `main`, passes its required checks, and remains `REVIEW_REQUIRED`.
- Compared the six changed P1 DCR/schema-v9 implementation and test files in
  the primary worktree byte-for-byte with PR #58's exact head using the local
  git object for that commit. All six matched. This establishes the current
  local P1 OAuth delta is already present in the review candidate; creating a
  duplicate patch/PR would fragment the same change. Existing PostgreSQL 16
  migration/refresh evidence is recorded in
  `docs/acceptance/2026-10-31-p1-dcr-persistence-schema-v9.md`.
- The ChatGPT browser is logged out, and the latest production probe still
  returns `/readyz`=404. Thus independent GitHub review, a P1-ready deployment,
  and authenticated ChatGPT acceptance remain separate required gates. No
  PR, review request, deployment, account setting, or branch was changed.

### P1 local CPU readiness admission gate — 2026-10-31

- `/readyz` previously treated an enabled `local_cpu` provider registration as
  ready when artifact storage and heartbeats were healthy, even if the workload
  had no source repository/SHA or the enabled local CPU policy did not
  allowlist that workload/profile. Such a deployment could look healthy while
  every real CPU prepare was blocked. Added a read-only admission probe that
  requires exact workload source identity and validates current policy enablement,
  expiry, allowlist, profile, positive runtime window and zero provider charge.
- `/readyz` now fails closed and returns `local_cpu_admission_ready` plus
  per-workload `local_cpu_admission_blockers`; demo-only readiness is unchanged.
  Updated setup/README instructions to require the new admission evidence.
- `./gateway/.venv/bin/python -m pytest -o addopts= -q
  gateway/tests/test_http_auth.py` passed **32 tests**, with one existing
  Starlette deprecation warning. `git diff --check` passed. No host, database,
  policy activation, ChatGPT account, or deployment was changed.
- Worktree is now 61 paths (45 modified tracked, 16 untracked). The updated
  ownership table assigns all 61 paths once; verify its one-to-one match before
  using the table to compose review candidates. This local readiness fix still
  requires reviewed CI, a deployed target with configured worker/supervisor,
  and authenticated ChatGPT acceptance.
- Candidate replay check: the focused readiness patch cannot be applied to
  PR #52's `bc9b030` head because that review slice predates `/readyz`. A
  three-way application to PR #55's `dc109cb` head conflicts in `app.py` and
  `test_http_auth.py`. PR #51's current `e3ffcef` head is the correct
  compatible base: its three target files match the patch's exact base blobs,
  `git apply --check` and application succeed, and the focused HTTP suite passes
  **32 tests** there. The reproducible three-file patch is
  `/tmp/gpu-control-p1-local-cpu-readiness.patch`, SHA-256
  `3bda11219156f57ffe58ceaec9bd43177d612794cee6a0d2c23ce04d61e8429d`.
  This is an overlay on an OPEN/DRAFT aggregate PR, not independently reviewed
  or GitHub-CI-tested. A fresh read-only GitHub query confirms PR #51 is still
  OPEN/DRAFT at exact base head `e3ffcef`; its seven required checks and Vercel
  status pass, with no review decision. No patch was pushed or PR changed.
- A separate read-only Security Review of this exact patch SHA found no
  findings. It is a local review of the three-file overlay; it is not a
  submitted GitHub review or CI result for a pushed head.

### Current acceptance gate recheck — 2026-10-31 07:42 JST

- Fresh read-only production requests returned `/healthz`=200, `/readyz`=404,
  and unauthenticated `/mcp`=401. The live production alias still cannot meet
  the current P1 readiness contract.
- `gh pr list` reports PR #58 at `561a6c7` and PR #52 at `bc9b030` OPEN/DRAFT;
  no submitted review decision is present and #52 reports
  `REVIEW_REQUIRED`. `gh pr checks` reports all seven required Actions
  contexts and Vercel successful on both exact heads. Those runs do not cover
  the dirty local candidate. A fresh branch-protection API request was
  rate-limited (HTTP 403); branch-protection settings were not reasserted.
- Re-ran the current checkout's focused P1 readiness suite:
  `./gateway/.venv/bin/python -m pytest -o addopts= -q
  gateway/tests/test_http_auth.py` — **32 passed**, one existing Starlette
  deprecation warning. `git diff --check` also passes.
- The six-slice exact-source replay and local test evidence are already
  recorded in the worktree slice map and acceptance record. Remaining P1
  blockers are a reviewed candidate, a deployed readiness-verified Gateway,
  an eligible authenticated ChatGPT workspace, and real execute/status/result
  plus cross-conversation retrieval evidence. No GitHub write, deployment,
  OAuth grant, host provisioning, or provider action was performed.

### P3 current schema-v9 paired backup and restore — 2026-10-31 07:50 JST

- On the exact-source local candidate at PR #58 base `561a6c7`, initialized
  PostgreSQL schema v9 and seeded one terminal run, one persistent OAuth DCR
  client, and one 36-byte artifact. `backup_generation.create_generation()`
  made a real custom-format PostgreSQL dump and paired artifact tar;
  `verify_generation()` accepted the output.
- Restored the database into a separate database in the same disposable
  PostgreSQL 16 container, restored artifacts into a separate directory, and
  verified schema v9, run state/cleanup, persistent DCR client, and exact
  `ArtifactStore.get()` bytes. The database was bound only to loopback. Its
  container, network, scratch files, and port were removed after the drill.
- The macOS systemd stopped-unit probe was stubbed to inactive; this closes
  current-schema local restore evidence only. Target-host quiescence, Neon,
  off-host retention, second-operator restore, alerting, and timed RPO/RTO are
  still open. Full hashes and scope are in
  `docs/acceptance/2026-10-28-atomic-backup-generation.md`.

### P1 readiness integrated on OAuth schema-v9 review base — 2026-10-31

- Rechecked published PRs #52 and #57–#59: all seven required Actions checks
  and Vercel passed on each published head. PRs remain Draft; PR #52 is still
  `REVIEW_REQUIRED`, and PR #57 has no submitted review. These results do not
  cover local overlays.
- Rebased the fail-closed local CPU `/readyz` admission gate onto exact PR #58
  head `561a6c7ac697dfdf22f304b60e313fccb2c806a4`, which contains OAuth DCR
  schema v9. The direct patch did not apply; a three-way merge was resolved in
  the isolated candidate worktree. Updated two existing storage-readiness test
  fixtures with valid source identity and an enabled, expiring zero-cost policy
  so those tests continue to isolate storage behavior without bypassing the
  admission gate.
- The exact-source Gateway suite passed **418/418**, with 13 optional Docker,
  PostgreSQL, Torch, and Modal skips and one existing Starlette warning. Both
  app and core package imports resolved from the candidate worktree;
  `git diff --cached --check` passed. Candidate patch:
  `/tmp/gpu-control-p1-readiness-on-58.patch`, SHA-256
  `8437253e113d0bf8f81fc3a27721b0157c02f5ddfef7aa081646fe1933fb6918`.
- A read-only Security Review of the exact #58-based integrated patch found no
  issues in its three changed files. The patch SHA remained unchanged during
  review. It has no published CI or submitted GitHub review. No push, PR update,
  deployment, OAuth grant, or provider action occurred. P1 runtime and
  authenticated ChatGPT acceptance remain open; retain `mode: parked`.

### P1 + P2 ancestry + P3 integration candidate on PR #58 — 2026-10-31

- Refreshed the public PR graph. PR #52 → #53 → #54 → #55 → #56 → #57 →
  #51 → #58 is the main review stack; #59 is a P3 sibling based on #57.
  Verified #53–#57 are ancestors of #58; #59 is not.
- The PR #59 branch has 14 changed paths relative to #57. Compared with #58,
  two of those paths are byte-identical and 12 differ; the direct branch patch
  treats files already present on #58 as additions and is not safe to apply
  wholesale. Built the P3 overlay instead from the exact-source P3 ownership
  slice already based on #58, after the reviewed P1 readiness patch.
- The complete 14-path P1+P3 candidate on #58 passed the full Gateway suite:
  **420 passed, 14 skipped**, one existing Starlette warning. Import paths
  resolved inside the candidate worktree and `git diff --check` passed. The
  first export omitted four untracked P3 test/evidence files; rebuilt from the
  complete staged candidate as `/tmp/gpu-control-p1-p3-on-58-complete.patch`,
  SHA-256
  `5c0acf229ccc0f07a32155ab5498c4685a8c9791c1a31fc4f5d7848b144319b8`.
  Applied that patch to a second fresh #58 worktree and compared the full tree:
  328 paths, zero missing/extra/content/mode mismatches.
- PostgreSQL-backed artifact-manifest test was skipped in the full run because
  no DB was configured, then passed **1/1** against a fresh pinned PostgreSQL
  16 container bound only to loopback. The test-owned unique rows were removed;
  the task-created container was stopped and confirmed absent. This is targeted
  DB integrity evidence, not a full DB-backed Gateway suite or target-host
  acceptance. Schema-v9 paired dump/restore evidence exists separately.
- A separate read-only Security Review of the complete staged 14-path P1+P3
  overlay found no actionable issues, including the four added P3
  test/evidence paths. Review was static and ran no tests. The candidate has
  no GitHub CI or submitted GitHub review. No branch/PR update, deployment, or
  provider action was made. Preserve `mode: parked`.
- The candidate's `tests/test_local_mcp_integration.py` then passed **1/1**
  against the digest-pinned local Docker CPU image after matching the fixture
  source SHA to the image's OCI revision. A first run correctly rejected the
  mismatched default fixture SHA and is excluded. The successful local run
  completed prepare/idempotent replay/submit, real CPU execution, and
  cross-client result/artifact retrieval; run ID and artifact hash are recorded
  in `docs/acceptance/2026-10-31-p1-p3-integration-on-58.md`. The test used
  synthetic in-process OAuth and local SQLite, so ChatGPT and deployment
  acceptance remain open.
- Static unit verification for the same candidate passed on all eight systemd
  service/timer templates using a disposable network-isolated Debian 12 /
  systemd 252.39 container with the candidate `gateway/deploy` mounted
  read-only. Only inert placeholders were created; no unit ran. This is not
  target-host mount, restart, database, worker, or alert-delivery acceptance.
  Details are recorded in `docs/acceptance/2026-10-31-p1-p3-integration-on-58.md`.

### P3 candidate systemd validation and production gate refresh — 2026-10-31

- On the exact #58 P1+P3 candidate, all eight service/timer units passed
  `systemd-analyze verify` in a network-isolated Debian 12/systemd 252.39
  container. Unit source was mounted read-only; only inert users/groups,
  environment placeholders, and executable placeholders existed inside the
  disposable container. No service started. This is syntax/reference evidence,
  not target-host mount/restart/runtime acceptance.
- Read-only production probes at 2026-10-31 08:30 JST returned `/healthz`=200,
  `/readyz`=404, OAuth authorization-server metadata=200, and unauthenticated
  `/mcp`=401. Production remains on a revision without the current readiness
  contract.
- PR #58 is still OPEN/DRAFT at `561a6c7`; all seven required Actions checks
  and Vercel pass on that published head, with no submitted review. The full
  local P1+P3 overlay is not on that head and is not covered by those checks.
  ChatGPT OAuth/CPU/result acceptance remains unrun; P3 host, alert sink/SLO,
  seven-day observation and timed recovery targets remain open. Preserve
  `mode: parked` and spending gates.
### Current acceptance and P4 fake-lifecycle refresh — 2026-10-31

- Added `test_free_candidate_backend_success_requires_bound_receipt_and_confirmed_cleanup`, exercising the fake candidate-bound success path through prepare, approval, submit, Worker capture, signed receipt validation, persisted result read, cleanup confirmation, and slot release. The full Gateway suite on the tested worktree passed **498 tests, 2 optional skips** with PostgreSQL 16 and the digest-pinned local CPU image. A fresh read-only reviewer found no issues in this test and its directly relevant receipt/worker code. The candidate/provider/device/signing material is synthetic; this is not live GPU evidence. Records: `docs/acceptance/2026-10-31-p4-fake-candidate-lifecycle.md` and `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`.
- Refreshed GitHub and production gates at 2026-10-31 08:44 JST: PR #51 (`e3ffcef`), #58 (`561a6c7`), and #59 (`76c2a1a`) remain OPEN/DRAFT with no reviews; their published checks are green but do not cover the current local dirty candidate. `https://gpu-control.vercel.app` returned `/healthz`=200, `/readyz`=404, unauthenticated `/mcp`=401. ChatGPT was last observed logged out at 08:35 JST. Thus no authenticated ChatGPT call, deployment, P1 acceptance, or live GPU result is established. Repository mode remains parked.
- Updated the release matrix and acceptance snapshot with the current suite count and live-gate boundary. `git diff --check` passes. No provider, host, paid resource, deployment, GitHub write, or credential was used.

### Working-tree source diff security review — 2026-10-31

- Sealed Codex Security scan `6d5f661c-55fa-4c58-af82-ad5907bd39cb` for the exact dirty worktree snapshot on base `a794438f42bd7246f463eaaa40d963af0aae9d13` (digest `codex-security-snapshot/v1:sha256:772b8d70382aca205750a9afbe61eaa6115950ffc84ac1b82ba0c088c1abfbf6`). Coverage is complete across all 16 generated changed source/policy review items and five review surfaces; the sealed scan has zero findings and no deferred coverage rows.
- This is static diff evidence only. It did not run tests or the application and does not establish authenticated ChatGPT, deployment/host, live provider/GPU, billing, cleanup, or GitHub PR review acceptance. Keep `mode: parked` and all spending gates closed. Record: `docs/acceptance/2026-10-31-working-tree-security-diff.md`.
- Reconciled `docs/PARKED_MODE.md` with `policies/repository-state.yaml`, `README.md`, and `docs/STATUS.md`: the selected Orbitune source is `fc131174…`, protocol v3, and the recorded workflow is explicitly a CPU contract smoke, not live RunPod execution. GitHub read-only checks confirmed both recorded runs succeeded on that exact SHA. This resolves a historical documentation discrepancy without changing the parked policy.
- P5 concurrency audit: the current RunPod adapter rechecks short-lived occupancy before and after `create_pod` but has no shared durable account lease. Added the required state/transaction/recovery contract and competing-process acceptance cases to P5.3a in `docs/specs/p5-gateway-runpod-permit-bridge.md`; the roadmap remains unchecked because implementation and acceptance are still outstanding. Provider flags and repository mode remain disabled/parked.
- Current P1 gate recheck at 2026-10-31 08:59 JST: production `/healthz`=200, `/readyz`=404, unauthenticated `/mcp`=401. PR #52 is OPEN/DRAFT at `bc9b030`, based on `main`, with seven required checks plus Vercel successful but `REVIEW_REQUIRED` and no review; #51/#58/#59 are also OPEN/DRAFT without reviews. The dirty local candidate is outside those published checks. No authenticated ChatGPT call or deployment occurred; see `docs/CHATGPT_ACCEPTANCE.md`.

### P5 durable account lease store foundation and conflict guard — 2026-10-31

- Added additive schema v10 and SQLite/PostgreSQL Store methods for durable
  provider account reservation, identity/token-fenced state transitions, and
  release only after confirmed cleanup for the exact provider job ID.
- Reservation now begins in `reserved`; a compare-and-set transition to
  `submitting` lets only one retry holder proceed to the next state.
- Added a standalone HMAC-SHA256 account-scope derivation helper; it is not yet
  connected to operator secret configuration or the Store call path.
- Security review identified that a concurrent insert-conflict branch could
  return a row with mismatched provider or plan fingerprint when run ID and
  owner matched. Added a deterministic SQLite trigger regression test, then
  made the branch reject any provider/run/owner/fingerprint mismatch. A fresh
  independent reviewer verified the explicit comparisons and test path.
- Added tests for competing runs, safe release, stale identity/state, schema
  migration, and two independent Store instances sharing one SQLite database.
  The focused scope/lease/migration run passed 19 tests. The latest complete
  Gateway suite passed 494 tests with 15 skips. PostgreSQL-specific cases were
  skipped because no dedicated test database was configured.
- This is only a persistence foundation. Wiring HMAC scope to live operator
  configuration, atomic coupling to run intent,
  authorization/challenge/core-plan binding, RunPod create and
  reconcile, worker cleanup, and multi-process crash/recovery acceptance are
  still missing. Keep roadmap P5.3a unchecked and all RunPod switches disabled.
  Evidence: `docs/acceptance/2026-10-31-p5-account-lease-store-foundation.md`.

### P5 lease authorization and create-challenge persistence — 2026-10-31

- Added schema v11 columns for core-plan fingerprint, authorization ID, the
  bounded provider create challenge, and a digest used to distinguish an
  actually-bound challenge from SQL/JSON null. The v10-to-v11 migration keeps
  existing lease rows and their states intact.
- Store reservations and transitions now bind to the exact core plan and
  authorization. A challenge is write-once, limited to 16 KiB, recursively
  rejects credential-like keys, and must be bound before `reserved ->
  submitting` can succeed.
- Focused lease/migration verification passed 16 tests, including preserving a
  held v10 lease during upgrade. This is still not atomic with run submission
  intent and is not wired into the worker or provider adapter. No provider was
  contacted; RunPod remains disabled and parked.

### P5 atomic account lease and submission-intent primitive — 2026-10-31

- Added one Store transaction that reserves the exact account lease, stores the
  provider create challenge and digest, and persists the linked run intent.
  It is fenced by the current worker lease token, owner, Gateway/core plan
  fingerprints, authorization ID, run state and expected attempt.
- Account contention or stale/mismatched run state rolls back both records.
  A barrier test using two independent Store instances/connections on one
  SQLite database confirms one winning lease and one matching intent.
- Focused lease/migration tests passed **20 tests**. This primitive has no
  Worker caller yet; it does not establish PostgreSQL process competition,
  provider challenge correctness, ambiguous-create recovery, or cleanup. Keep
  P5.3a unchecked and the repository parked.
- After this change, the complete Gateway suite passed **499 tests with 15
  skipped**; skips include PostgreSQL/provider integration requiring external
  test services. `git diff --check` passed. The earlier sealed Security Review
  predates this atomic primitive and does not cover it.
- Added a PostgreSQL acceptance case using two spawned processes and separate
  Store connections to race the atomic reservation. On a task-created local
  PostgreSQL 16 instance, `tests/test_postgresql.py` passed **6 tests** and the
  full Gateway suite passed **508 tests with 7 skipped**. The PostgreSQL race
  is now verified at the Store layer; Worker wiring, actual provider create,
  ambiguous-create recovery, and cleanup remain open. Exact source hashes,
  environment and skip reasons are recorded in
  `docs/acceptance/2026-10-31-p5-account-lease-process-postgresql.md`.

### P1 ChatGPT gate recheck — 2026-10-31 09:15 JST

- Fresh public requests returned production `/healthz`=200, `/readyz`=404,
  unauthenticated `/mcp`=401. PRs #51 through #59 remain OPEN/DRAFT; review
  decisions are empty except #52, which requires review. Published checks do
  not cover the current dirty working tree. No authenticated ChatGPT call,
  deployment, GitHub write, provider action, or credential change occurred.
- P1 ChatGPT acceptance remains NOT RUN; repository remains parked. Details:
  `docs/CHATGPT_ACCEPTANCE.md` and `docs/RELEASE_MATRIX.md`.

### Current P5 working-tree Security Review — 2026-10-31

- Completed Codex Security diff scan `11bb8173-3acc-48d9-a5c8-7ad7224ec691`
  against base `a794438f42bd7246f463eaaa40d963af0aae9d13`, exact snapshot
  digest `codex-security-snapshot/v1:sha256:d2022938ed5090477b9aec71d643b6040250ac8fff71b12bacbf75a2924f955b`.
  All 18 generated source/policy items and related changed tests were reviewed;
  the sealed static report has zero reportable findings.
- A candidate in the provider-account lease insert-conflict branch was
  suppressed because the helper has no production caller and later challenge
  binding/atomic-intent paths enforce the missing core-plan and authorization
  identity. Recheck the branch when connecting P5.3a to Worker/provider
  dispatch. Full scope and limitations:
  `docs/acceptance/2026-10-31-p5-working-tree-security-diff.md`.
- This scan did not run tests or the application and does not establish
  ChatGPT, production/host, provider/GPU, billing, or cleanup acceptance. Keep
  `mode: parked` and all spending gates closed.

### Current working-tree Gateway revalidation — 2026-10-31 09:46 JST

- Re-ran the complete Gateway suite against current HEAD `a794438f` plus the
  current 48-path dirty/30-path untracked worktree: **499 passed, 16 skipped**
  in 11.13 seconds. `git diff --check` passed. The SQLite provider-account
  lease cases ran; optional Torch/Modal, CPU image, and dedicated PostgreSQL
  cases were skipped because their external test dependencies were not set up.
- Re-ran the Core suite at the same source checkpoint: **559 passed, 1
  Python-3.11-only skip** in 1.01 seconds.
- This revalidates only the local Gateway snapshot. Durable account lease
  persistence remains unconnected to Worker/RunPod dispatch and does not prove
  PostgreSQL competition, provider recovery/cleanup, or paid execution. Full
  source hashes and command are recorded in
  `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`. Parked mode and
  spending gates remain unchanged.

### P5 recovery lease reload primitive — 2026-10-31 09:58 JST

- Added `Store.read_provider_account_lease_for_run`. It resolves the scope only
  from durable submission intent, requires the current unexpired Worker claim,
  verifies run/owner/plan/attempt/authorization/challenge identity, and locks
  the provider lease before the run row. The API returns no released or
  malformed active lease.
- The new TDD regression failed before implementation because the method was
  absent, then the provider lease module passed **11 tests**. An independent
  PostgreSQL worker process reloaded its winning lease while the competing
  process received none: **1 test passed**. Full Gateway suite on dedicated
  PostgreSQL 16 plus the commit-bound CPU image passed **514 tests / 2 optional
  skips**. The temporary DB container/volume were removed.
- This is recovery-store groundwork. Worker/RunPod dispatch, paid authorization
  persistence, HMAC scope identity, provider reconciliation, and independent
  cleanup are still open. Details and source hashes:
  `docs/acceptance/2026-10-31-p5-account-lease-recovery-read.md`. Parked mode
  and all spending gates remain unchanged.

### P1 real local CPU vertical — 2026-10-31 09:48 JST

- Ran the real Docker CPU backend, lifecycle, and authenticated MCP integration
  tests with a digest-pinned repository-owned `linux/arm64` image: **3 passed**
  in 7.00 seconds. This covers MCP prepare/submit, Worker CPU execution,
  separate-client result and artifact retrieval with digest verification, and
  lifecycle recovery/cleanup in the selected test cases.
- The image and source identity are synthetic (`aaaaaaaa…`), and MCP is called
  by in-process authenticated test clients. This is useful P1 local runtime
  evidence, not actual ChatGPT OAuth/tunnel/deployment acceptance or provenance
  of a real workload commit. Evidence and exact command are in
  `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`; keep mode parked.
- Follow-up at 09:48 JST: rebuilt the CPU image from a clean `git archive` of
  exact HEAD `a794438f42bd7246f463eaaa40d963af0aae9d13`, with the pinned
  base-image digest. Local `linux/arm64` image ID/digest is
  `sha256:e82806277a195971ba3a0fc443650f47e4e15ddd913df6fb26a9ef7f07348922`;
  OCI source/revision labels match that repo/commit. Repeated the three backend,
  lifecycle, and MCP integration tests with this commit-bound image: **3
  passed**. Thus the workload-image provenance gap is closed for local P1; the
  dirty Gateway source, in-process MCP clients, actual ChatGPT connection,
  deployment, and remote host acceptance remain separate gates.
- Latest full Gateway revalidation at 09:51 JST used both the commit-bound CPU
  image and a fresh PostgreSQL 16 container bound to loopback: **513 passed,
  2 skipped** in 26.19 seconds; only optional Torch and Modal SDK tests skipped.
  It includes spawned-process lease contention, PostgreSQL migration/OAuth and
  outage recovery, plus real Docker CPU/MCP result and artifact retrieval.
  Container and anonymous volume were removed. Exact command, hashes, runtime
  and skip scope are in `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`.

### P5 Worker cleanup and lease release transaction — 2026-10-31

- Added a Worker-claim-fenced Store transition and an atomic terminal cleanup
  commit: the exact RunPod lease becomes `released` in the same transaction
  that marks the run/result cleanup complete and returns the active slot.
- Connected both normal and recovery cleanup paths. For runs with durable
  account-lease intent, the Worker requires the adapter to map its handle to
  the exact persisted provider job ID, moves the lease to `cleanup_pending`
  before cleanup, and accepts only literal `True` from `is_clean(handle)`.
  Failed proof leaves the lease held for recovery. Legacy runs without the
  account-lease intent keep their existing completion path.
- Fake-provider Worker tests pass normal cleanup and retry after an
  unconfirmed cleanup under a successor claim. The focused provider-lease
  suite passed **13 tests**; the full Gateway suite passed **507 / 16 skipped**.
  Full command and scope are recorded in
  `docs/acceptance/2026-10-31-p5-worker-cleanup-lease-commit.md`.
- This still does not create the lease or durable paid authorization in the
  Worker submission path, and does not prove PostgreSQL behavior for this new
  terminal transaction or live provider cleanup. Keep RunPod candidate
  execution disabled and repository mode `parked`.

### P5 RunPod candidate lease contract gate — 2026-10-31

- Added the typed RunPod account-lease adapter contract for preparing a
  non-network challenge, creating with the persisted challenge, reconciling
  without create, and extracting the exact provider job ID.
- Candidate readiness now fails closed for RunPod adapters missing any of
  those methods. The existing Worker readiness check occurs before submission
  intent, so legacy adapters cannot bypass the account-lease requirement.
- TDD regression first showed the legacy-shaped candidate backend was
  accepted; it now passes only with the full lease contract. Full Gateway suite
  passed **508 / 16 skipped**. Evidence:
  `docs/acceptance/2026-10-31-p5-runpod-lease-contract-gate.md`.
- The Worker does not yet call the new prepare/create/reconcile methods or
  derive/reserve the account lease. There is no implementing RunPod adapter or
  durable signed paid authorization. Keep RunPod disabled and mode `parked`.

### P5 Worker account-lease dispatch wiring — 2026-10-31

- Connected the RunPod candidate Worker path to HMAC account-scope derivation,
  atomic lease plus submission-intent reservation, persisted create challenge,
  no-create reconciliation after ambiguous outcomes, provider-handle binding,
  and lease-aware cleanup. Paid and credit-backed RunPod candidate plans fail
  closed before provider create until signed authorization can be durably
  persisted, reloaded and revoked by the Worker.
- PostgreSQL 16 integration found that comparing a JSON column to SQLAlchemy's
  JSON-null sentinel fails because PostgreSQL `json` has no equality operator.
  Replaced that predicate at submit and recovery handle persistence with a
  cross-dialect SQL-NULL/JSON-null check. Local outage/recovery and worker-crash
  tests then passed **2/2**.
- Current dirty-source full suites passed: Gateway **524 passed / 2 skipped**
  with PostgreSQL 16 and a commit-bound local CPU container; Core **559 passed /
  1 Python-3.11-specific skip**. Full details and exact source hashes:
  `docs/acceptance/2026-10-31-p5-worker-account-lease-dispatch.md`.
- These results establish offline/fake-provider lifecycle wiring and local
  PostgreSQL/Docker CPU behavior only. There is still no accepted live RunPod
  adapter, real provider allocation/cleanup, durable signed paid authorization,
  ChatGPT Workspace acceptance, or selected production host. Keep P5.3a
  unchecked, preserve `mode: parked`, and keep spending gates closed.

### P5 RunPod scope stability across credential rotation — 2026-10-31

- Worker scope derivation now uses operator-configured
  `GATEWAY_RUNPOD_ACCOUNT_SCOPE_ID`, not the provider API key. Rotating the key
  therefore keeps old and new workers on the same account lease namespace.
- The scope ID is hidden from Settings representations and validated for
  bounded, whitespace-free text. Fake Worker and config tests use the stable
  ID while keeping the API credential solely for provider authentication.
- This closes the account identity precondition for P5 lease dispatch. Actual
  provider configuration, secret rollout discipline, live allocation, and
  production recovery remain unaccepted; keep mode `parked` and all spending
  gates closed.

### P5 Worker lease Security Review — 2026-10-31

- Completed Codex Security diff scan `2087f03f-3369-44bf-af49-0eea97eefb67`
  against frozen worktree digest
  `codex-security-snapshot/v1:sha256:68c2ace3c86596fe7c7547fafac24ee328320ce0ae6380b3d4edc0598a8b2f20`.
  All 18 generated source/policy review items and five security surfaces were
  covered; no plausible candidates were identified. Full scope and limits:
  `docs/acceptance/2026-10-31-p5-account-lease-security-review.md`.
- The review confirmed that paid/credit verifier modules still have no direct
  Gateway caller and RunPod paid/credit plans fail closed pending durable
  authorization persistence. No provider call or paid execution occurred.
- This is static evidence for the recorded digest only. GitHub approval,
  deployed ChatGPT acceptance, selected-host operation and real provider/GPU
  behavior remain open. Keep mode `parked` and spending gates closed.

### P5 paid authorization persistence foundation — 2026-10-31

- Added additive schema v12 for signed paid-authorization envelopes and Store
  write/reload primitives. Persistence is tied to the current exact browser
  approval ID, owner, run, and plan fingerprint; reload rejects a mismatched
  identity or envelope digest. A replacement browser approval makes the old
  record ineligible.
- The Store write method requires a prior verifier result and independently
  checks its run/owner/Gateway-plan claims. It is an internal primitive; no
  HTTP/MCP/browser path accepts an envelope. Evidence and limits:
  `docs/acceptance/2026-10-31-p5-paid-authorization-persistence-foundation.md`.
- Added four Store boundary cases and ran them in the Gateway dedicated venv:
  **4/4 passed**. Existing additive migration tests passed **10/10**. These
  used SQLite; PostgreSQL and verifier-to-Store integration are still open.
- The issuer, revocation source, worker pre-intent reload/reverification,
  provider pre-create recheck, and RunPod paid registration remain unwired. The
  worker's fail-closed refusal remains active. No authorization/provider call
  occurred; keep mode `parked` and all spending gates closed.

### P5 paid authorization read-time approval revalidation — 2026-10-31

- Strengthened `Store.read_paid_authorization` to re-lock and recheck the live
  run approval, exact owner/plan/approval tuple, browser approval expiry,
  cancellation flag, envelope identity/expiry, and digest on every read. It
  permits `submitting` because `Worker.claim` transitions queued jobs before
  pre-intent validation; canceled, uncertain, and other states remain
  ineligible. A follow-up independent review confirmed that a cancellation
  committed before the read is rejected, but the Store lock ends before any
  provider call; cancellation after the read remains a Worker integration race
  to close with a submission-boundary recheck and post-acceptance cleanup.
- The five focused Store tests passed, including expired browser/envelope
  authorization, the Worker `submitting` state, and a previously committed
  cancel flag;
  `git diff --check` passed. The official static diff review completed on the
  immediately preceding snapshot with zero security candidates. Focused
  independent review found and corrected the state-flow mismatch and identified
  the remaining cancel race; see
  `docs/acceptance/2026-10-31-p5-paid-authorization-persistence-foundation.md`.
- This is still an unused Store primitive. The issuer, revocation lookup,
  Worker verification, provider recheck, and RunPod paid registration remain
  absent. Keep mode `parked` and all spending gates closed.

### Submission cancellation boundary — 2026-10-31

- Made non-RunPod dispatch-intent persistence conditional on the current run
  claim and `cancel_requested = false`. RunPod's atomic account-lease and intent
  reservation now has the same cancellation condition, and its reserved to
  submitting transition checks the flag again. If cancellation lands between
  reservation and transition, the unused reservation is released and the run is
  finished as cancelled. Store intent validation also checks bounded identity,
  provider syntax, and exact integer attempt/timestamp fields.
- Added Store regressions for canceled non-RunPod intent and canceled RunPod
  reservation. The first broader run exposed two stale assertions expecting
  schema version 11 while the current migration reports 12; updated those
  migration checks to the current version and reran the complete focused
  provider-lease/recovery subset: **23 passed**. `git diff --check` passed.
- Cancellation can still arrive after the final database transition and while
  the external provider create call is in flight. The worker persists any
  returned handle and the next lifecycle tick observes the cancel flag and
  performs cleanup. This cannot guarantee that a provider never briefly accepts
  a create after a concurrent cancel; the provider call and database cannot be
  made atomic. No provider call was made in this work.
- Independent review confirmed the validation and pre-check behavior and the
  residual transition-to-provider-call window. It found no current reachable paid path:
  RunPod paid/credit remains refused and candidate execution is not enabled in
  the default registry. Keep `mode: parked` and all spending gates closed.
- Re-ran the full Gateway suite and root CLI/Core suite successfully after the
  change (Gateway's configured optional tests skipped; Core also reported one
  configured skip). Read-only acceptance refresh at 11:02 JST confirmed `main`
  protection, but all tracked PRs remain draft/unreviewed, production
  `/readyz` remains 404, and ChatGPT web is logged out. Detailed evidence:
  `docs/acceptance/2026-10-31-cancel-dispatch-boundary.md`.

### Current worktree Security Review — 2026-10-31

- Completed Codex Security diff scan
  `59df3764-a62a-4b0b-96d6-46278862151c` against the frozen worktree digest
  `codex-security-snapshot/v1:sha256:4a92afc39317e7d2fe18724ffa27fccffb92cab622f642546058c6f870957936`.
  All 18 changed source and policy review items were covered across seven
  surfaces. Discovery identified zero candidates; the sealed report has zero
  findings and no deferred coverage rows.
- This was static source review only. It did not verify a deployment, external
  GitHub controls, ChatGPT OAuth, provider behavior, GPU, billing, or cleanup.
  The review reconfirmed that paid/credit verifiers have no Gateway caller and
  RunPod paid/credit execution remains fail-closed. Keep mode `parked` and all
  spend gates closed. Full scope:
  `docs/acceptance/2026-10-31-current-worktree-security-review.md`.

### P0/P1 GitHub and public endpoint refresh — 2026-10-31 10:55 JST

- Read-only `gh pr list` still shows PRs #51–#59 as OPEN/DRAFT; #52 and #43
  have `REVIEW_REQUIRED`, and the other listed PRs have no review decision.
  These heads do not contain the complete current dirty worktree.
- Public endpoint probes returned `/healthz` 200, `/readyz` 404, unauthenticated
  `/mcp` 401, and OAuth authorization-server metadata 200. This confirms the
  older deployment is alive and challenges unauthenticated MCP; it does not
  prove current-source readiness or a ChatGPT experiment call. No OAuth grant,
  deployment, provider action, or GitHub write was made.
- P1 remains blocked on a readiness-verified deployment and authenticated
  eligible ChatGPT workspace. Exact current evidence is summarized in
  `docs/RELEASE_MATRIX.md`; keep the overall goal active.

### P1 current ChatGPT OAuth registration contract — 2026-10-31 11:07 JST

- Rechecked OpenAI's current custom MCP and authentication guides. ChatGPT
  continues to support DCR; CIMD is preferred when the authorization server
  advertises it and the app creator chooses it. The Gateway currently advertises
  DCR, public token authentication (`none`), exact resource binding, and PKCE
  S256; it does not advertise CIMD support. Recorded the selected DCR acceptance
  path, the separate future CIMD requirements, and the distinction between an
  OpenAI transport client certificate and Gateway user OAuth in
  `docs/CHATGPT_SETUP.md` and `docs/CHATGPT_ACCEPTANCE.md`.
- Focused OAuth and HTTP-auth suite passed **39 tests**; `git diff --check`
  passed. This confirms local OAuth contract only. The fresh ChatGPT web tab
  remains logged out, and no OAuth exchange or tool call was made. Keep
  `mode: parked` and the full goal active.

### P0/P1 GitHub and Vercel gate refresh — 2026-10-31 11:12 JST

- Read-only GitHub status: PRs #51–#59 remain OPEN/DRAFT with nine successful
  published status entries each and no submitted reviews. PR #52 remains
  `REVIEW_REQUIRED`; PR #43 is still open with `REVIEW_REQUIRED` and five
  successful entries. Published status does not cover the current dirty
  worktree.
- Vercel metadata confirms production alias `gpu-control.vercel.app` still
  resolves to READY deployment `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ` from `main`
  SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. Probes returned `/healthz`
  200, `/readyz` 404, OAuth metadata 200, and unauthenticated `/mcp` 401.
- PR #58 head `561a6c7ac697dfdf22f304b60e313fccb2c806a4` has READY deployment
  `dpl_3QtLZEQudmfXMHexbmmUc46mVivv`; direct unauthenticated `/healthz` and
  `/readyz` requests redirect to Vercel SSO (302). No share link was created;
  candidate readiness remains unobserved. Full evidence and remaining gates:
  `docs/CHATGPT_ACCEPTANCE.md`, “Current GitHub and Vercel gate refresh.”
- No GitHub/Vercel setting, deployment, OAuth grant, provider call, or paid
  operation was made. Repository mode remains `parked`; P1 ChatGPT acceptance
  remains NOT RUN.

### P1 Secure MCP Tunnel client refresh — 2026-10-31 11:17 JST

- Read-only GitHub release metadata identified official `openai/tunnel-client`
  v0.0.19 (2026-10-30). The OpenAI repository attestation command completed
  successfully. Pulled the multi-architecture image by index digest
  `sha256:dcae53be336c062ffdc3f250a287b2a07724c344b8c370a50f54ad033af43151`;
  Docker identified ARM64 manifest digest
  `sha256:e38276d38eff1b962be792920a9374d86f5931792b70da6f1e14af43a21d4b9f`.
- Isolated `--network none`, read-only-rootfs CLI checks reported version
  `0.0.19+01d67bb4da0d8359b808b4761f8db171ab682cd7`, and successfully ran
  `help quickstart` and `help oauth`. The release documents an HTTP+DCR sample
  and the metadata sequence required for tunnel readiness. Refreshed
  `docs/CHATGPT_SETUP.md` and `docs/CHATGPT_ACCEPTANCE.md`; detailed digests and
  command are recorded there.
- No tunnel ID/key, Platform API request, workspace setting, Gateway process,
  OAuth grant, or provider action was used. This advances only client
  supply-chain/CLI preflight; actual tunnel, OAuth, ChatGPT tool, and CPU-run
  acceptance remain NOT RUN. Keep `mode: parked`.

### P1 local tunnel OAuth reachability boundary — 2026-10-31

- Compared the v0.0.19 `sample_mcp_with_dcr` contract with the current Gateway
  source. Both the built-in authorization-server issuer and the MCP resource
  are derived from `GATEWAY_PUBLIC_URL`, whose non-Vercel default is
  `http://127.0.0.1:8000`. Secure MCP Tunnel does not automatically tunnel the
  authorization-server endpoints, so that local default cannot be treated as
  a working browser-facing ChatGPT OAuth route. The DCR profile validates the
  HTTP discovery shape only; it does not solve issuer reachability or token
  audience binding.
- Recorded this boundary in `docs/CHATGPT_SETUP.md` and
  `docs/CHATGPT_ACCEPTANCE.md`. The remaining choices require a reachable,
  independently supported OAuth issuer, the ChatGPT-selected registration
  method (DCR or CIMD), and an exact MCP resource audience. The Gateway's
  external-OIDC mode only validates tokens: its local authorization-server
  discovery and DCR routes return 404, so those capabilities must come from the
  external issuer. No production OAuth state is shared with the local test. No
  tunnel, OAuth grant, server, or provider action was used; keep the acceptance
  NOT RUN and `mode: parked`.
