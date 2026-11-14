# Modal budget and Sites capability recheck — 2026-11-12

Checked at 2026-11-12 11:44 UTC through the authenticated ChatGPT Site and
signed-in Modal dashboard.

## Sites state

- Production Site `gpu-control-sites` is public, active, and owned by the
  current account. The Sites API reports Version 25 from source commit
  `c3077a54888bcb07fd0e42238cc677c5d7c17bd8` at
  `https://gpu-control-sites.unjuno.chatgpt.site`.
- Production environment revision 23 contains
  `CPU_WORKLOAD_ADMISSION_ENABLED=true`, the registered source SHA
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image digest
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`,
  and fingerprint
  `34c63203d132b0a11c9ac68eebb4e27ad27b570fa36017f3beeb7d4d24e3bae8`.
- A fresh ChatGPT `experiment_capabilities` call returned
  `available=true`, `provider_ready=true`, `admission_enabled=true`, provider
  `modal_cpu`, maximum runtime 30 seconds, maximum inflight 1, and
  `paid_execution=parked`.
- Version 25 currently reports Modal CPU as `free=true` and prepared cost
  `$0.00`. Those fields are inaccurate because Sandbox CPU and memory are
  usage-billed. No workload was submitted in this check.

## Modal state and price evidence

- The Modal `unjuno/main` dashboard shows deployed app version v4; its commit
  field is blank. The latest observed deployment time was Nov 12, 18:06 JST.
- The Usage limit page displayed a provider-set Workspace limit of `$1`, usage
  of `$0.03` in credits, and `$0` in charges. The UI offered adding a payment
  method to raise the limit. This is a rechecked account-level usage ceiling;
  it does not establish a per-run price cap or successful workload execution.
- Modal's [official pricing page](https://modal.com/pricing) lists Sandbox
  non-preemptible CPU at `$0.00003942` per core-second and memory at
  `$0.00000667` per GiB-second. At the configured maximum of 1 core, 0.5 GiB,
  and 30 seconds, the compute estimate is
  `30 * (0.00003942 + 0.5 * 0.00000667) = $0.00128265`, rounded up to `$0.0013`.
  This estimate excludes Modal control-function time, image builds, and any
  provider charges outside Sandbox CPU/memory.

## Code state and acceptance boundary

- Commit `31d7d42` adds a fixed root-to-UID/GID-10001 Sandbox launcher. The
  follow-up currently in the worktree includes that launcher in the workload
  fingerprint, so Site health will require a matching environment update.
- The current live Site is available but the current Modal v4 deployment has
  not been bound to the new launcher. The fixed launcher has not passed a live
  inference check. Do not infer Modal acceptance from the readiness call.
- A narrow parked-mode exception is being added for one authenticated,
  registered CPU run (30 seconds, 1 CPU, 512 MiB, no GPU, blocked egress,
  `$0.01` Sandbox CPU/memory ceiling), requiring a live Workspace usage limit
  no greater than `$1`, current user authorization, and confirmed cleanup.
  Separately billed Modal control-function calls are excluded from that
  ceiling; total charges can be higher. The
  RunPod/GPU and paid-training gates remain parked.
- Review found the live D1 plan schema still enforces a historical `$0.00`
  ceiling. An append-only migration is required before new paid Sandbox plans
  can be inserted; verify it preserves historical plan rows and the `runs` FK
  before deploying it.
- No new Sandbox was created as part of this recheck. The earlier successful
  run under Sites Version 16 used the retired macOS Runner; two prior Modal
  runs failed with cleanup confirmed.

## Follow-up live acceptance — 2026-11-12 12:20 UTC

- Published Sites Version 26 (commit `a9f519f1e48b976e569f5674949a77fa51e16f81`)
  with the corrected Sandbox cost disclosures and append-only D1 migration
  `0004_sandbox_cost_ceiling.sql`. The migration was executed in SQLite with
  foreign keys enabled: historical `0.00` plans and existing runs remained,
  the foreign-key check was clean, and a new `0.01` plan was accepted.
- Deployed Sites Version 27 (commit
  `64d2646815be198b0173877b821264cf3efc10a6`) with non-secret health check
  booleans; all provider health checks passed. The live fingerprint is
  `3a2b0992465a3aac53a41a6f1a9cd6b1812b1beb6f13ca3a59eaeddbece55ddc`.
- Deployed the fixed Sandbox entrypoint to Modal `unjuno/main`. A temporary
  one-hour Workspace API token was used only for this deploy and deleted in
  the Modal UI immediately afterward; the token does not enter the Sandbox.
- Rechecked Modal's current Workspace usage guard before execution: `$1` limit,
  `$0.03` credits used, `$0` charges. ChatGPT prepared one plan for
  `tiny-stories-inference-v1`, prompt `Once`, 16 maximum generated tokens, seed
  `61112`, and a 30-second runtime. Its Sandbox CPU/memory estimate was
  `$0.0013` and its Sandbox-only ceiling was `$0.01`.
- Run `b3380814d0854d93a5d978799d670013` reached Modal through ChatGPT and failed
  with `MODAL_WORKLOAD_EXIT_2`. Modal Sandbox
  `sb-01M77TZXQ0D04PVJ52QG6Y8F0E` showed `Failed (code 2)` and no logs. Sites
  recorded `cleanup_state=confirmed`; no successful inference or artifact was
  produced. The current workload returns exit code 2 without identifying which
  guard failed, so the failure cause remains unknown. No automatic retry was
  made.
- After the attempt, Modal Usage showed `$0.04` in credits, `$0` in charges, and
  the `$1` Workspace limit. The `$0.01` increase includes provider control and
  deployment activity and cannot be attributed solely to this Sandbox.
- Sites environment revision 27 now has
  `CPU_WORKLOAD_ADMISSION_ENABLED=false`. A fresh ChatGPT capability call
  confirmed `provider_ready=true`, all health checks true, and
  `admission_enabled=false`. This one-run authorization is consumed; another
  live Sandbox requires a new current authorization after a useful diagnostic
  fix is ready. RunPod/GPU and paid training remain parked.

## Bounded failure diagnostic prepared — 2026-11-12 12:28 UTC

- The Modal entrypoint now traces only the fixed inference `main()` return path
  and writes a non-sensitive source-line marker when that function returns
  preflight code 2. The Modal control API accepts only this exact bounded
  marker; the Sites Worker records it in `failure_code` without exposing
  provider stderr.
- A local synthetic preflight returned code 2 and emitted the expected source
  line marker. The Site Worker suite passed 21 tests, and build/artifact
  validation passed. No provider was called.
- This diagnostic has not been deployed. The live Site remains on Version 27
  with admission disabled, and the previous one-run authorization is consumed.
  Deploying this diagnostic and performing one bounded inference require a
  new explicit authorization. No new Modal token or Sandbox was created.

## Historical run-list reconciliation — 2026-11-12 12:40 UTC

- A fresh read-only ChatGPT `experiment_list` and `experiment_status` check
  also surfaced run `0f2a3ddaa7da40648600bae21ccd9ed1`, created at
  2026-11-12 11:25 UTC. It is `failed` with `MODAL_WORKLOAD_EXIT_2`,
  `cleanup_state=confirmed`, and no result artifact. Its request was bounded
  to 16 generated tokens. The current read did not establish which deployment
  or authorization was in effect at creation; preserve it as a separate failed
  event without inferring its approval provenance.
- The latest run `b3380814d0854d93a5d978799d670013` remains failed with the same
  exit code and confirmed cleanup. No successful Modal inference is recorded.

## Bounded diagnostic deploy — 2026-11-12 12:49 UTC

- With the user's explicit approval, issued a Workspace API token with a
  one-hour lifetime. No Sandbox was authorized or started. The token was kept
  out of the local Modal profile and repository and was revoked immediately
  after deployment.
- The first CLI attempt stopped before deployment because the temporary CLI
  environment did not include FastAPI. The second used Modal CLI 1.6.3 and the
  repository-pinned FastAPI 0.128.2; `modal deploy --env main app.py` returned
  exit code 0 for `unjuno/main`.
- The Modal app overview showed `gpu-control-sites` deployed just now, 0 live
  containers, and 0 live Sandboxes. The API-token list showed 0 tokens after a
  page reload. The dashboard displayed `$0.04` usage this cycle; the `$1`
  Workspace limit was last observed at 12:35 UTC, so no new limit check is
  claimed here.
- This deploy includes the bounded preflight return-line diagnostic added in
  `d1dd4fe`. No health request or inference call was made after deployment;
  diagnostic behavior remains unverified live. Sites Version 27 and
  `CPU_WORKLOAD_ADMISSION_ENABLED=false` remain unchanged. A new live Sandbox
  requires its own current authorization.

## Current continuation recheck — 2026-11-12 13:07 UTC

- Current Sites metadata reports Version 27, source commit
  `64d2646815be198b0173877b821264cf3efc10a6`, environment revision 28, and
  public access. The latest recorded ChatGPT capability call passed every
  Modal health check but correctly kept admission false. No current inference
  has been accepted.
- Modal's API-token page was reloaded and showed zero API tokens. The temporary
  Workspace deploy token is revoked. No Sandbox was started during this
  continuation.
- The installed ChatGPT `experiment_prepare` signature advertises
  `max_cost_usd` as the constant `0.00`; current Worker `tools/list` source
  advertises `0.01`, and the Worker rejects `0.00`. This tool-schema mismatch
  prevents preparation through the currently exposed ChatGPT tool and must be
  resolved before the next authorized inference.
- A recorded Modal cold start took about 6.3 seconds before the health handler
  returned. The Worker previously aborted every provider request after 5
  seconds. The local source now uses a bounded 15-second request timeout. The
  regression suite passed all 22 Worker tests, including a simulated 6.3-second
  cold start; Site build and artifact validation passed. This source change is
  not yet pushed or deployed as a new Sites version.
- A separate one-run CPU authorization is still required before any Sandbox
  starts. RunPod/GPU and paid training remain parked.

## Sites Version 28 and fresh diagnostic plan — 2026-11-12 13:24 UTC

- Published Site Version 28 from source commit
  `237c0bed24277cf7c808f8c0e9946c71d517288c`, environment revision 28. The
  refreshed ChatGPT tool schema now accepts `max_cost_usd=0.01`, and the
  deployed Worker carries the bounded 15-second Modal request timeout.
- A fresh live `experiment_capabilities` call passed all eight Modal health
  checks. Admission remains false and capabilities report
  `CPU_WORKLOAD_ADMISSION_DISABLED`.
- Prepared one fixed TinyStories 15M inference plan against registered source
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`: prompt `Once`, one generated
  token, seed `61112`, 30-second runtime, 1 CPU, 512 MiB, no GPU, blocked
  network. The estimated Sandbox usage is `$0.0013`, with a `$0.01` Sandbox-only
  ceiling; Modal control-function charges are separate. The plan is prepared
  but not submitted, and the Sandbox has not been started. Opening admission
  and submitting require exact-run authorization.

## Diagnostic plan expiration — 2026-11-12 13:30 UTC

- The prepared plan expired without submission while exact-run authorization
  was pending. No Sandbox started and production admission remained false.
- Recheck the Modal Workspace usage limit, prepare a new plan, and bind any
  submission to fresh explicit authorization for that plan's run ID and
  fingerprint.

## Authorized one-token diagnostic execution — 2026-11-12 13:46 UTC

- Before submission, the signed-in Modal dashboard showed a `$1` Workspace
  usage limit, `$0.05` credits used, and `$0` charges. The plan fingerprint was
  `c3bcd8133d6ca7f39f055e564e8f68095790029c49f55451543d1757037ccc2f`; its
  Sandbox-only estimate was `$0.0013` with a `$0.01` ceiling. Modal control
  function costs are separate.
- The explicitly authorized run
  `e9330c5bb5454f42bb3dabe058091dc0` used the fixed TinyStories 15M workload,
  prompt `Once`, one output token, seed `61112`, 30 seconds, 1 CPU, 512 MiB,
  no GPU, and blocked network. It failed with `MODAL_WORKLOAD_EXIT_2`.
- Modal Sandbox `sb-01M77ZZRFC1090CXA2W3MHDH7V` failed after 247 ms. The
  dashboard showed no Sandbox logs. ChatGPT `experiment_status` was reread:
  state `failed`, cleanup `confirmed`, result and artifact absent. The bounded
  preflight line marker was not returned, so the exact failing guard remains
  unknown. A local simulation of the deployed entrypoint and marker regex
  correctly captured a synthetic preflight return; this does not explain the
  missing live marker.
- After execution, Modal Usage still showed `$0.05` credits used and `$0`
  charges. These totals include prior deployment/control activity and cannot be
  attributed to this Sandbox alone. The temporary admission was closed again;
  environment revision 32 has `CPU_WORKLOAD_ADMISSION_ENABLED=false`. A fresh
  ChatGPT capability read reports all eight health checks true,
  `provider_ready=true`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`.
- This one-run authorization is consumed. Do not retry without a new exact-run
  authorization and a diagnostic change that can distinguish the failure.
  RunPod/GPU and paid execution remain parked.

## Offline regression evidence — after the live attempt

- `uv run --locked pytest`: 565 passed, 1 skipped. This covers repository unit
  and contract tests, not Modal live inference or the repository-wide P0
  security audit.
- `npm test` in `sites/gpu-control-sites`: 22 passed. `npm run build` and
  `npm run validate` both passed; the Site Worker artifact was complete.
- No provider call or Sandbox was made during these checks. The P0 scan remains
  unstarted because the current Codex thread does not have the managed read-only
  filesystem permission profile required by its scanner.

## Ambiguous-submit recovery regression — 2026-11-12 14:06 UTC

- Added a Sites Worker regression for a run persisted as `running` after a
  possibly accepted Modal submit. When the subsequent provider status lookup
  returns 404, repeated `experiment_status` calls retain the occupied run and
  do not issue a second `/submit` request.
- `npm test` in `sites/gpu-control-sites`: 23 passed. This is an offline mock
  of the Worker's fail-closed reconciliation rule; it does not prove Modal API
  consistency, a live lost-response recovery, or independent background
  reconciliation. No provider call was made.

## Continuation recheck — 2026-11-12 14:15 UTC

- The stronger ambiguous-submit regression is pushed as `0838bd392316adc895b833f0c6f483563c1ca1a2`;
  the remote branch matches and the worktree is clean. The Sites Worker suite
  passes 23/23 tests.
- A read-only status reconciliation of the latest five failed runs found three
  `MODAL_WORKLOAD_EXIT_2` failures and two `MODAL_WORKLOAD_FAILED` failures.
  All five have confirmed cleanup and no result artifact. The Modal Logs page
  for the latest Sandbox showed no logs. These records do not identify the
  failing workload check or establish a common root cause.
- Modal Usage currently shows the `$1` Workspace limit, `$0.05` in credits
  used, and `$0` in charges. The current Sites capability response still has
  provider health ready but `admission_enabled=false`; no Sandbox was started.
- The previously approved run ID `96ad1246cf744ea3b3eac326f673e547` is absent
  from Sites (`RUN_NOT_FOUND`). Do not substitute a new run ID or fingerprint
  without fresh authorization. The Codex environment also still reports the
  filesystem profile as disabled, so the required managed read-only P0 scan
  remains unstarted.

## GitHub integration recheck — 2026-11-12 14:17 UTC

- GitHub branch `codex/sites-modal-runner` resolves to
  `d5983d5e029eb24ca4295d3f9e7844e6a2861100`, matching the local HEAD. The
  commit-status endpoint returned no checks, the PR-triggered workflow-run
  query returned none, and an open-PR search for this branch found no PR.
- Local `npm test` evidence remains 23/23, but this exact pushed head has no
  GitHub CI or PR review evidence. The branch is not merged; checks from PR #58
  or its neighbouring PR cannot be applied to this candidate.

## PR #68 and live execution continuation — 2026-11-12 14:43 UTC

- Draft PR #68 is open against the PR #58 head. At the start of this recheck,
  its exact head was `51bd76707b88fa2f15eab6453a26d01f40fd3391`, matching
  `origin/codex/sites-modal-runner`; the worktree was clean before this note.
- Exact-head GitHub workflow runs `43236078547` (CI) and `43236084008`
  (Project bridge tests) both completed successfully. These are code checks,
  not provider acceptance or a repository-wide security audit.
- The exact PR diff Security scan completed with six changed source/config
  items reviewed and zero reportable findings. One authorization/spend
  candidate remains deferred: the Worker lacks structured current-human
  authorization evidence and a Modal account-usage recheck; product-side
  confirmation and provider hard-stop behavior are not established by this
  repository. The scan is not the P0 full-repository audit.
- A fresh ChatGPT Sites `experiment_capabilities` call again reports all eight
  Modal health checks ready, `admission_enabled=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`. The latest run
  `e9330c5bb5454f42bb3dabe058091dc0` is failed with `MODAL_WORKLOAD_EXIT_2`,
  cleanup confirmed, and no result or artifact. Its Modal Sandbox log view has
  no logs. Do not retry: its one-run authorization is consumed and the failed
  preflight remains unidentified. The earlier authorized run ID
  `96ad1246cf744ea3b3eac326f673e547` remains absent (`RUN_NOT_FOUND`).
- The OpenAI custom MCP server guidance says ChatGPT *may* request confirmation
  for write/modify actions based on app permissions and action context; it does
  not establish that every submit is confirmed. This cannot substitute for the
  repository's required trusted authorization binding. Source:
  <https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt>.
- A repository-wide Deep Scan was attempted and did not start because the
  parent session did not provide a managed filesystem permission profile. The
  same requirement is still unmet; the P0 audit remains open. No source,
  admission, credential, or provider setting was changed in this recheck.

## Live execution comparison — 2026-11-12 14:53 UTC

- The fresh authenticated Sites run list shows older successful TinyStories
  runs and recent failures. The success `eacc26ff2ad54cf69a1ee7665325b197`
  occurred before the Modal v4 deployment and is documented as executed by the
  retired local macOS Runner; it is not Modal acceptance. Run metadata does not
  expose provider provenance, so do not attribute other historical successes
  to Modal without separate evidence. No successful inference has been
  observed on the current Modal deployment.
- Current Modal failures include `e9330c5bb5454f42bb3dabe058091dc0` (prompt
  `Once`, one token) and `b3380814d0854d93a5d978799d670013` /
  `0f2a3ddaa7da40648600bae21ccd9ed1` (16-token limits). They failed with
  `MODAL_WORKLOAD_EXIT_2`, confirmed cleanup, and no artifact. Other recent
  runs have `MODAL_WORKLOAD_FAILED`. Historical local-Runner successes cannot
  be used as a Modal comparison or to isolate parameter sensitivity. The exact
  Modal failure cause remains unknown. No new execution was submitted and
  admission remains disabled.
- Modal's current `Sandbox.create` reference documents network policy, volumes,
  and experimental options, but no read-only-root-filesystem parameter. Modal's
  filesystem guide documents sandbox filesystem writes. This means the current
  `read_only_rootfs` result should be interpreted narrowly as the workload's
  `/work/write-probe` check, not proof that the entire root filesystem is
  mounted read-only. Since successful runs return the same check list, this
  observation alone does not explain the recent exit-2 failures. Sources:
  <https://modal.com/docs/sdk/py/latest/Sandbox>
  <https://modal.com/docs/guide/sandbox-files>.
- The fresh capability read remains `provider_ready=true`,
  `admission_enabled=false`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`. The exact one-run authorization remains
  consumed, so the next live attempt requires fresh authorization bound to a
  new run plan and a diagnostic improvement that identifies the failing guard.
- Read-only Modal UI follow-up for this failure found the control API call
  `fc-01M77X3HT87A1YYX5A5SM7WDQJ` completed successfully in 127 ms after a
  6.34-second cold start. Its Logs tab and the linked Sandbox Logs view were
  empty; the Execution and Call Graph tabs did not expose the function return
  payload. This confirms only that the control function call completed, not
  why the workload exited 2. No provider state was changed.

## Continuation verification — 2026-11-12 16:03 UTC

- The current ChatGPT `experiment_capabilities` call reports all eight Modal
  health checks true and the deployed fingerprint
  `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`, while
  `admission_enabled=false`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`. No provider execution was started.
- The authenticated ChatGPT run list and status tool confirm the newest run
  `e9330c5bb5454f42bb3dabe058091dc0` is failed with
  `MODAL_WORKLOAD_EXIT_2`, cleanup confirmed, and no result/artifact. A newer
  successful historical record (`360e6ee7bb664bea80ec9846bf1d8b6c`) contains a
  valid result and artifact digest, but the Site tool response does not expose
  provider provenance. It is not counted as Modal acceptance; this preserves
  the provenance rule above.
- Local `tests/test_modal_bootstrap.py` passed 3/3; the Sites Worker suite
  passed 23/23. These verify the synthetic bootstrap marker and mocked Worker
  lifecycle only. The host's OrbStack Docker daemon is stopped and the Modal
  SDK is absent, so no local image/container reproduction was possible.
- A direct external probe with no identity and with a synthetic non-owner
  identity was blocked by the Cloudflare edge with HTTP 403/error 1010 before
  reaching the Worker. It proves neither Worker authorization nor spoof
  resistance. No real owner identity was sent. Separate-account isolation
  remains open.
- The exact current PR head remains `6b4a56492071abe75be6558f9c1cb80a9b736756`
  on Draft PR #68, with its six exact-head checks previously observed passing.
  No source, deployment, credential, admission, or provider state changed.

## Modal UI provenance cross-check — 2026-11-12 16:06 UTC

- The signed-in Modal `gpu-control-sites` app's Sandboxes view, filtered to
  2026-11-11 15:48 through 2026-11-12 15:48 UTC, reports exactly five
  Sandboxes created. All five rows match the known failed run IDs
  `96d7efef9542463d9fc51f47ffbfd5d7`,
  `599473dcc1ed4034a42d849bcb42e261`,
  `0f2a3ddaa7da40648600bae21ccd9ed1`,
  `b3380814d0854d93a5d978799d670013`, and
  `e9330c5bb5454f42bb3dabe058091dc0`; each shows Failed (code 2).
- Successful Site record `360e6ee7bb664bea80ec9846bf1d8b6c` was created at
  2026-11-12 04:26 UTC, inside that window, but no Sandbox with its deterministic
  `gpu-control-<run_id>` name appears in the complete five-row app list. It is
  therefore not evidence of execution by this Modal app. Site responses do not
  expose another provider identity, so its actual origin remains unverified.
- This cross-check strengthens the finding that no successful run is evidenced
  for this Modal app. It does not resolve the exit-2 cause, prove behavior from
  a different Modal environment, or authorize another run. No provider or app
  state was changed.

## Modal exit-code diagnosis patch — 2026-11-12 16:19 UTC

- The pinned workload exits with code 2 for eight concrete preflight guards at
  source lines 43, 47, 56, 58, 62, 69, 72, and 76. The bootstrap now encodes
  only those registered return lines into reserved process exit statuses; the
  Modal endpoint maps those statuses back to legacy `exit_code=2` while
  returning a bounded diagnostic such as `PREFLIGHT_RETURN_LINE_76`. The map is
  included in the workload image fingerprint. Unknown exit codes retain their
  previous value and produce no decoded line.
- Added regressions cover actual guarded source lines, mapping boundaries,
  legacy exit-2 normalization, bootstrap fallback behavior, and Worker result
  normalization. The new fingerprint calculated from the manifest inputs is
  `0fc60d1890c26a646330a0d848750a0dedc03ff8a56a6e6dd214dba1e3471560`; it is
  not the currently deployed fingerprint, so the deployed service remains
  unchanged until separately authorized.
- Verification: targeted bootstrap tests 4/4; Sites Worker tests 23/23;
  Python compile, full `uv run --locked pytest` (569 passed, 1 skipped), and
  `git diff --check` passed.
- Focused Codex Security diff review `7a64ba0b-8a16-4d72-b213-5246ae84e24c`
  completed with four reviewed surfaces, zero findings, and complete patch
  coverage. Report:
  `/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control-pr58-current-candidate/c2f6ef965bdac545cc113edd3ee2dc7bd2466420_20261112T161410Z_qscsqa_4/report.md`.
  This is a patch review, not the unavailable managed-read-only full Deep Scan.
- No Modal deploy, Sandbox execution, admission change, or provider state change
  was performed. A deployed-image run and end-to-end ChatGPT acceptance remain
  open and require a new exact one-run authorization after deployment.

## Execution-origin reconciliation and ChatGPT history labeling — 2026-11-12

- Fresh Sites owner inventory confirms project `gpu-control-sites` is the active
  public Site at `https://gpu-control-sites.unjuno.chatgpt.site`; its D1 binding
  contains `plans`, `runs`, and `runner_heartbeats`. The public Site audience is
  separate from MCP access: the Worker requires the authenticated Sites user ID
  and enforces `GPU_CONTROL_ALLOWED_USER_IDS` before touching D1.
- The ChatGPT `experiment_list` contains historical `succeeded` rows, including
  `360e6ee7bb664bea80ec9846bf1d8b6c` and `eacc26ff2ad54cf69a1ee7665325b197`.
  Their D1 cleanup receipts record a `gpu-control-<run_id>` container name,
  container ID, local lease ID, and `absent=true`; the `runner_heartbeats` table
  records `local-cpu-1` at 2026-11-12 05:07:41 UTC. The result artifact for
  `eacc26ff2ad54cf69a1ee7665325b197` was also returned by Sites with its D1
  SHA-256 verified. These are retained successes from the retired local Runner,
  not evidence of Modal execution.
- Independent Modal UI checks over the matching period still show five Sandbox
  executions, all failed with code 2. Filtering the `gpu-control-sites` app for
  the successful `gpu-control-360e6ee7bb664bea80ec9846bf1d8b6c` Sandbox name
  returns no row; the Modal control API call list also has no call in that run's
  creation interval. The two systems agree once the D1 rows are attributed to
  their recorded local Docker receipts.
- The previous note that the historical Site success had an unknown provider is
  superseded by this D1 receipt and heartbeat cross-check. No currently deployed
  Modal inference success is evidenced. Capabilities still report
  `provider_ready=true`, `admission_enabled=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`.
- The Worker history endpoint previously omitted execution origin, so successful
  local Runner records could be mistaken for Modal successes. The pending PR
  patch adds `execution_origin` labels to run list and status responses:
  `retired_local_runner` for matching legacy Docker cleanup receipts,
  `modal_sandbox` for recorded Modal Sandbox IDs, and `unknown` otherwise. Raw
  cleanup receipts remain private. Worker regression tests cover all three
  cases and status labeling. This patch has not been deployed; no D1 rows or
  provider state were changed.
