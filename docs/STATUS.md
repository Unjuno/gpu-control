# Project status

## Source/release checkpoint — 2026-11-28

- The current source candidate is PR #70 branch
  `codex/owner-training-workloads`, latest head
  `27372e1e2b73d7ee1faff1bd3e398af4f04f4b9b`. PR #70 remains open and
  unmerged. All seven exact-head GitHub Actions checks passed for this head.
- The candidate implements owner-selected GitHub source selection, immutable
  commit planning and strict `.gpu-control/experiment.json`/lock checks for
  Modal, plus a hosted Colab MCP provider using an owner-scoped Google OAuth
  connection, D1 operation journal, verified R2 artifacts and run-owned
  cleanup. RunPod/Kaggle/Hugging Face custom-repository execution is not
  implied by their fixed-workload routes. Colab's direct CLI remains a
  separate local/CI route outside the shared run ledger.
- `policies/repository-state.yaml` remains `mode: parked` and explicitly keeps
  owner-selected GPU admission disabled. No current claim is made that PR #70
  has been merged, deployed, migrated in hosted D1, or accepted in a new
  ordinary ChatGPT run.
- The D1 source tree includes migrations through `0039_colab_positive_cu_attestation.sql`;
  the deployed D1 migration level has not been re-verified. Colab admission
  defaults closed and the exact-submit positive-CU attestation is persisted;
  its account-level cost is still unknown and runtime egress is unrestricted.
- For module ownership, duplicated contracts, state authority and the next
  refactoring batches, see [the repository architecture map](architecture/repository-map.md)
  and [the prioritized backlog](architecture/refactoring-backlog.md).
- The prior full local validation at `748ac11` passed 206 tests; the Worker
  graph was acyclic across 76 modules, and build and D1 migration replay
  passed. The current error-contract change passes its focused 3-test suite;
  the exact-head GitHub Actions suite passes at `27372e1`. The Colab
  lifecycle integration test covers same-request-ID recovery after lost
  mocked runtime-create and cleanup responses on both status and cancellation.
  A non-empty deletion response leaves cleanup pending; a later exact empty
  success response confirms cleanup without replaying execution. It does not prove Google's live
  idempotency behavior or real Colab execution. The earlier independent Security Review does not
  cover this latest source. The automated diff scanner could not start on the
  linked worktree; no independent scan result is claimed.
- The `31bc183` follow-up also fails closed when a submitted Colab plan has lost
  its operation journal: status, cancel and repeated submit report uncertainty
  without contacting Colab. The `748ac11` RunPod follow-up preserves an
  ambiguous cancellation request and completes cancellation when the same
  receipt is recovered, while returning pending until cleanup is confirmed.
  Commit `27372e1` also exposes the fixed RunPod lease/recovery error codes to
  MCP clients and corrects the Colab CLI guide; it does not change provider
  execution or admission.

The dated entries below are historical snapshots. Their deployment versions,
provider configuration, costs and readiness must not be treated as current
without a fresh live check.

## Sites v46 four-provider control plane — 2026-11-21

- Production Sites v46 deployed successfully at
  `https://gpu-control-sites.unjuno.chatgpt.site` with MCP enabled. The exact
  Site source commit is `b425de54315dedb88a0303d5cce2f47a3e026834`.
- Hosted D1 applied migrations through `0017_free_provider_policies.sql`.
  `provider_free_policies` contains independent Kaggle and Hugging Face rows
  with `max_cost_microusd=0` and `paid_fallback_allowed=0`.
- A live owner-authenticated `experiment_capabilities` call reports exactly
  Modal, RunPod, Kaggle and Hugging Face. Modal CPU is enabled. RunPod is
  unconfigured and closed. Kaggle and Hugging Face are unconfigured and closed
  until the authenticated Modal adapter is deployed.
- Railway, Vercel, Neon, an external PostgreSQL database and a separately
  hosted Gateway are not part of the production execution path.
- GitHub PR #68 head `6bb16a5ed44a0237717e7459d51a98d9372af69a`
  has seven successful exact-head checks. Local root tests at the preceding
  runtime head reported 599 passed, 1 skipped and 5 subtests; the Site Worker
  reported 63 passed and the adapter core reported 5 passed.
- The current independent diff security review is **not complete**. The Codex
  Security scanner rejected both the linked worktree and a normal temporary
  clone with `Review changes requires a non-bare Git worktree with a resolvable
  HEAD`. The older sealed scan does not cover this final head.
- No new provider credential, RunPod Pod, Kaggle run or ZeroGPU run was created
  during this checkpoint. Completion still requires adapter credentials,
  bounded live Kaggle/HF canaries, RunPod completion-transport acceptance and
  canary, cross-account denial, cleanup evidence and exact-head independent
  review.

Operational setup, rotation, removal, emergency stop and the first ChatGPT
verification prompt are in [ChatGPT Sites setup](CHATGPT_SETUP.md).

## Modal asynchronous repeat accepted — 2026-11-15

- Sites Version 39 and the matching Modal `unjuno/main` app were published from
  the asynchronous candidate. The owner-confirmed submit returned normal
  `running` state instead of the previous host `INTERNAL_ERROR`.
- Run `9f2c52912b234888b709c7a04bdeb707` succeeded through Modal, produced a
  digest-verified 931-byte R2 artifact, and finished with cleanup confirmed.
  Modal showed the Sandbox `Done` after 575 ms and zero concurrent Sandboxes.
- Both temporary one-hour deployment tokens were deleted; the Modal API-token
  list returned to zero. Usage still displayed `$0.10 / $1` and `$0` charges,
  subject to billing delay. Evidence:
  [Version 39 asynchronous repeat](acceptance/2026-11-15-sites-v39-modal-async-repeat.md).

## Modal recovery candidate verified offline — 2026-11-15

- The unpublished candidate now returns from Modal submit after provider
  acceptance and leaves capture, validation, termination, and cleanup to later
  status calls.
- Injected recovery coverage includes duplicate reservation, lost submit
  response, status timeout, post-horizon absence, provider failure, image
  mismatch, R2/D1 persistence retry, and cancellation/result races. Sites has
  45 passing tests; build and artifact validation pass. Exact-head PR checks
  pass.
- This is offline evidence only. A repeat live run and a bounded live recovery
  drill are still required before recovery/operations acceptance. Evidence:
  [Modal recovery offline matrix](acceptance/2026-11-15-modal-recovery-offline-matrix.md).
- A later read-only ChatGPT tool refresh still reported the fixed route
  available and found no `queued` or `running` record in the latest 50
  owner-visible D1 runs. This did not contact Modal health and is not a
  provider-side orphan inventory.

## Modal CPU vertical accepted — 2026-11-15

- ChatGPT Sites Version 38 completed owner-confirmed run
  `245d034977e5471aa7ec6d1f80f6232f` through the fixed Modal CPU path.
  The result generated `Once upon`, passed all nine workload/isolation checks,
  used no GPU, and ended with cleanup confirmed.
- The complete 931-byte R2 artifact was retrieved and its SHA-256 was
  independently recomputed as
  `86d88aa2593829f818003288b0d48a86807f2161e88cf6b5dd41af2e582325d7`,
  matching the recorded digest. Modal independently displayed the Sandbox as
  `Done`, lifetime 693 ms, with zero concurrent Sandboxes.
- The submit response was ambiguous (`INTERNAL_ERROR`), but no duplicate was
  submitted. Owner list/status recovery reconciled the original run to its
  terminal result, exercising the lost-response recovery path.
- Post-run Modal billing still displayed `$0.10` credits used, `$0` charges,
  and the `$1` Workspace limit. This display can lag final billing. Recovery
  and stability work is next; RunPod/GPU remains parked. Evidence:
  [Modal CPU success](acceptance/2026-11-15-sites-modal-cpu-success.md).

## Sites Version 35 native plan preparation — 2026-11-15

- A fresh goal turn loaded Version 35's updated `experiment_submit` schema,
  including the exact `approved_plan` fields and destructive-write contract.
  The authenticated owner capability call succeeded with Modal configured,
  admission enabled, and the documented CPU, memory, runtime and Sandbox cost
  bounds.
- `experiment_prepare` created a bounded TinyStories one-token plan entirely
  inside ChatGPT, without the separate browser login. The user was away, so the
  exact destructive-write confirmation was not performed and the plan was not
  submitted. No provider health request, Sandbox, RunPod call, GPU allocation,
  or new provider spend occurred.
- A future execution must prepare a fresh plan because this authorization
  window is only 600 seconds. After the plan expired, owner-authenticated
  status returned `RUN_NOT_FOUND` and the run list contained no matching ID,
  confirming that prepare alone created no execution record or provider job.
  Evidence: [Version 35 native plan preparation](acceptance/2026-11-15-sites-v35-native-plan-prepare.md).

## P0 audit and Sites Version 35 — 2026-11-15 08:00 JST

- The repository-wide Codex Security Standard scan completed and sealed at
  Git revision `26c1deff1f73924a3cf88592bdcc8bedf0970285` with zero
  source-backed findings. Live identity, deployment configuration and provider
  behavior remain runtime acceptance gates rather than source-audit claims.
- The reviewed ChatGPT-native approval candidate was pushed to the Site-owned
  source repository as `0eb4fe4ba7dcdc6035af4bdc89f8751b40716538` and
  published successfully as Sites Version 35. The public audience, owner
  allowlist and environment revision 39 were preserved.
- Hosted D1 now exposes `human_authorizations.authorization_source`, proving
  migration `0011` applied. The connected owner can still read capabilities;
  Modal is configured, authorization storage is ready and CPU admission is
  enabled.
- The current conversation retains the old cached submit schema. A fresh
  conversation must verify Version 35's exact-plan destructive confirmation,
  then one bounded CPU run, result artifact, cleanup and budget. No provider
  request or new spend occurred during this publication checkpoint. Evidence:
  [P0 scan and Sites Version 35](acceptance/2026-11-15-p0-scan-and-sites-v35.md).

## ChatGPT-native approval publication — 2026-11-15

- The active PR #68 branch changes the CPU execution flow so `experiment_submit`
  carries the exact plan fields and is marked as a destructive MCP action. Its
  invocation records a short-lived, one-use authorization for the authenticated
  Site owner, avoiding the separate browser sign-in in the intended chat flow.
- Sites Version 35 now publishes this contract from Site source `0eb4fe4`.
  Hosted D1 includes migration `0011`; no health request or Sandbox was started
  during publication. The publishing conversation cached the Version 34 tool
  schema. A later goal turn loaded Version 35 and prepared a plan; the
  destructive confirmation UI remains unverified before the first live run.
- The Site's platform-injected owner identity provenance and authenticated
  cross-account denial remain unverified. Publication does not satisfy those
  runtime gates: the exact ChatGPT tool confirmation UI and a bounded
  end-to-end result/cleanup still require live verification.

## Live recheck — 2026-11-15 05:17 JST

- Sites Version 34 is active with `access_mode=public`, one owner account on
  the MCP allowlist, and no external viewers. ChatGPT capabilities currently
  report the fixed Modal CPU workload configured, admission enabled, and
  provider health deferred until exact-plan owner confirmation. The plan page
  requires ChatGPT sign-in.
- The five Modal failures in the run history were all created on 2026-11-12,
  before the 2026-11-13 Docker `CMD` correction was deployed. The source-level
  explanation is that the old image `ENTRYPOINT` bypassed the fixed bootstrap;
  this is not live-confirmed. No post-correction Modal inference is recorded.
  The newest historical failure has confirmed cleanup but no result artifact,
  and its Modal log query returned no logs.
- The current registered fingerprint is
  `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`; the
  capability response also reports image digest
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  These registry values do not independently attest the running Modal image.
- Modal billing was checked read-only before deciding not to start another
  provider operation. No budget, payment method, credential, environment
  setting, or provider resource was changed. Control-function charges are not
  included in the per-Sandbox estimate.
- PR #68 head `5b48ba7bd6cfaaf2c361ed0aec909079c2bfb3da` has passing CI and
  Project bridge workflows. The documentation-only diff security scan found
  no issue in changed lines. The separate whole-repository Standard scan is
  still partial, and older public acceptance snapshots and Git history retain
  account-specific billing observations.
- RunPod remains offline-only. No new Sandbox, RunPod call, GPU allocation, or
  training was started during this recheck. A new run still requires owner
  sign-in and confirmation of its exact plan.

## Follow-up status — 2026-11-15 03:29 JST

- Sites Version 34 reports source commit
  `18339d5106ff148d0ec4b3acf8da64791b69d54f`; GitHub's commit API does not
  find that SHA in `Unjuno/gpu-control`. The Site uses a separate Cloudflare
  artifact source branch. Exact parity between the live Worker and reviewed
  GitHub source remains unverified, so the first CPU Sandbox is held pending
  source reconciliation.
- The ChatGPT Sites tool can prepare a registered CPU plan. ChatGPT sign-in
  and exact one-use owner confirmation are still required; no provider health
  request or Sandbox has started. The current confirmation attempt has
  expired, so prepare a fresh plan after sign-in.
- User-authorized testing remains a cumulative allowance through completion,
  not a per-run allowance. The Workspace cap remains `$1`; the per-plan
  Sandbox ceiling is `$0.01`, excluding separately billed Modal control calls.
- No code finding was confirmed in the reviewed Sites authorization, Modal and
  RunPod provider, Python control-plane, or workflow slices. The repository
  scan remains partial. An unauthenticated forged owner-header request
  previously received 401, but authenticated header-spoof resistance remains
  unverified.

## Follow-up status — 2026-11-15 03:27 JST

- The ChatGPT Sites experiment tool successfully prepared a new bounded CPU
  plan. Its confirmation page requires ChatGPT sign-in in the in-app browser;
  no current plan is confirmed, and no provider health request or Sandbox has
  started. Prepare a fresh plan after sign-in if the current one expires.
- The user's testing allowance is cumulative through completion, not per run.
  Keep the existing Workspace `$1` cap and the per-plan `$0.01` Sandbox
  ceiling; separately billed Modal control-function calls remain outside that
  per-plan estimate.
- Local checks passed on source HEAD `ab7124f`: `uv run pytest` reported 588
  passed, 1 skipped, and 5 subtests; Sites `npm test` reported 43 passed;
  `npm run build` and `npm run validate` succeeded. Exact-head CI and Project
  bridge checks for `ab7124f` also passed. This status-only README edit still
  needs its own pushed-head checks.
- Independent source reviews found no confirmed vulnerability in the reviewed
  Sites authorization, Modal/RunPod provider, Python control-plane, or workflow
  paths. Repository-wide scan coverage remains partial. The Sites Worker
  trusts the platform-provided `oai-authenticated-user-id`; an earlier
  unauthenticated forged-header probe received 401, but an authenticated
  forged-header probe or authoritative edge contract remains unverified.
- Exact-owner confirmation is therefore still required before the first fresh
  CPU Sandbox. RunPod/GPU remains parked. Details: [current Site acceptance](acceptance/2026-11-13-sites-v33-live-refresh.md).

## Follow-up status — 2026-11-15 03:06 JST

- Published Sites environment revision 39 with only
  `CPU_WORKLOAD_ADMISSION_ENABLED=true` changed, using saved Site Version 34.
  The deployment succeeded; ChatGPT capabilities now reports `available=true`
  with provider health deferred until exact-plan confirmation. The public Site
  audience and owner allowlist were preserved.
- Prepared the bounded CPU run `aa687747b5474d0192b5cfc6fc6b89a7`; its exact
  plan was not confirmed. This browser required a separate ChatGPT sign-in, so
  the five-minute plan expired without any Modal health call or Sandbox. A new
  plan is required after sign-in; older authorization does not apply to the
  new fingerprint.
- Modal usage immediately before the Site deployment was `$0.10` credits,
  `$0` charges, and a `$1` Workspace limit. RunPod/GPU and paid training remain
  parked; repository-wide P0 security review is incomplete. Details:
  [Sites admission and CPU plan](acceptance/2026-11-15-sites-admission-and-cpu-plan.md).

## Follow-up status — 2026-11-15 02:55 JST

- Deployed candidate `3eb2ab5d218b06c2559fd22088e1a4763fc78521` to Modal
  `unjuno/main` (`gpu-control-sites`). The CLI reported `control_api` deployed
  in 3.268 seconds. No Sandbox, health request, or inference was started.
- The one-hour Workspace API token was deleted immediately after the deploy;
  a fresh Modal token-list page showed **0 tokens**. Modal Usage before deploy
  was `$0.10` credits, `$0` charges, with the `$1` Workspace limit unchanged.
- Admission remains closed. This deploy does not establish post-deploy health
  or successful ChatGPT-to-Modal inference. See the
  [redeploy acceptance record](acceptance/2026-11-15-modal-main-redeploy.md).

## Follow-up status — 2026-11-15 02:39 JST

- The first follow-up docs commit `cc1ee922` exposed one timing-sensitive
  assertion in the Sites confirmation test: it required exactly 300 seconds,
  while the code correctly capped authorization at the plan's expiry and the
  observed integer-second lifetime was 299. The test now checks that the
  authorization expiry equals the plan expiry and is still in the future.
- The Sites Worker suite passes **43/43** locally. Commit
  `9a8adffa8df1509b05d994a23052a7bd760646bc` is pushed to PR #68; exact-head
  CI and Project bridge tests both pass all six CI jobs plus the bridge
  workflow. PR #68 remains Draft with no submitted independent review.
- The live Modal spend/admission snapshot and P0 scan blocker are unchanged
  from the [02:33 JST recheck](acceptance/2026-11-15-budget-and-local-regression-recheck.md).

## Follow-up status — 2026-11-15 02:49 JST

- Local Gitleaks 8.30.1 scanned the current checkout and Git history with
  findings fully redacted: **5** current-tree matches and **12** history
  matches across 1,150 commits. Review of the matched contexts identified
  pinned TinyStories tokenizer digests and test/idempotency/attack-probe
  literals; no current provider credential was identified. This is a secret
  pattern check, not the repository-wide P0 review.
- GitHub API and the logged-in repository settings page show secret scanning
  and push protection enabled, but the dependency graph and Dependabot alerts
  disabled. Code Scanning has no analysis. Main protection enforces admins,
  requires one approval and last-push approval, and requires all six current CI
  checks. A request to enable only the dependency graph and Dependabot alerts
  is pending; security update PRs were excluded. No setting was changed.
- Daybreak is connected, but its scan status reports unavailable because
  credits are exhausted, and none of its listed environments contains
  `Unjuno/gpu-control`. No Daybreak scan was launched. Its results do not
  replace the required Codex Deep Scan, which remains blocked by the managed
  read-only filesystem profile requirement.
- Detailed evidence: [security and provider status recheck](acceptance/2026-11-15-security-and-provider-status-recheck.md).

## Follow-up status — 2026-11-15 02:33 JST

- Rechecked the Modal Workspace Usage Limit page in the logged-in browser:
  `$0.10` credit usage, `$0` charges, and a `$1` Workspace usage limit. This is
  within the user's `$1` aggregate project-testing budget. No payment method,
  spend setting, provider configuration, or admission setting was changed.
- The live ChatGPT capabilities call still reports
  `CPU_WORKLOAD_ADMISSION_DISABLED`, `available=false`, and defers Modal health
  until an exact plan is owner-confirmed. The one-token plan
  `ade7d8e5ce6a4961b16d847c393fd769` was never confirmed or submitted; its
  authorization window elapsed and status now returns `RUN_NOT_FOUND`. No new
  provider health request or Sandbox was made.
- The latest existing Modal-origin attempt remains failed with
  `MODAL_WORKLOAD_EXIT_2`, cleanup confirmed, and no artifact. This does not
  establish the failure cause for the currently deployed candidate.
- Focused local regressions passed: retired Runner route rejection **1/1** and
  Modal bootstrap tests **7/7**. A tracked-source search found no active
  Keychain launcher or personal-host compute Runner implementation; the code
  matches were limited to the inference secret-denylist and the negative
  retired-route test. These local checks do not establish live provider
  acceptance or a repository-wide security clearance.
- The repository-wide Codex Deep Scan remains unstarted. The coordinator
  returned: `Deep Scan cannot safely start a read-only worker: the parent must
  provide a managed filesystem permission profile.` No scan artifacts or
  security clearance were produced. See
  [the live budget and local regression recheck](acceptance/2026-11-15-budget-and-local-regression-recheck.md).
- PR #68 remains open and Draft at this update. Exact-head GitHub Actions for
  commit `8cb4ea87e9157272aa77391d467fbc078a1dfa87` completed successfully:
  Python 3.11/3.12/3.13, Trusted reference container, Sites Worker and D1
  contract, and Project bridge tests. No PR review has been submitted.

## Follow-up status — 2026-11-15

- PR #68 candidate `66010298af1cad4c40a45c0463f7e31e56db5da4` was redeployed
  to Modal `unjuno/main` (`gpu-control-sites`). The CLI reported success in
  3.328 seconds. No Sandbox or post-deploy health request was started. The
  Modal runtime source has no delta from `6a024f5`; this deploy does not resolve
  the observed exit-code-2 failure.
- Modal Usage after deploy showed `$0.10` in credits used, `$0` in charges, and
  a `$1` Workspace cap. The authorized testing budget is `$1` aggregate through
  completion, not per run. The Workspace API-token list was refreshed to 0
  entries after the deploy token was deleted. One earlier token-creation view
  emitted its secret in automation output; that token was not used and was
  deleted. The credential clipboard was cleared after the deploy.
- ChatGPT capabilities still report `CPU_WORKLOAD_ADMISSION_DISABLED`,
  `available=false`, and defer provider health checks until exact-plan owner
  confirmation. New plan `16fc88de7ef44e88957f58ffd8e88035` is pending that
  confirmation. It binds the registered TinyStories 15M workload, prompt
  `Once`, one token, seed `61112`, 30 seconds, CPU-only, no network, 1 core,
  512 MiB, a `$0.0013` Sandbox estimate, and a `$0.01` Sandbox-only ceiling.
  Control-function costs are separate. No run was submitted.
- The latest Modal-origin run remains failed with `MODAL_WORKLOAD_EXIT_2`,
  confirmed cleanup, and no result artifact; the queried Modal Sandbox log view
  returned no logs. RunPod/GPU remains disabled pending live root-signer,
  result-collection, and cleanup acceptance. The repository-wide P0 scan remains incomplete
  because its managed read-only worker cannot start in this session profile.
- See [the dated deployment and plan record](acceptance/2026-11-15-modal-redeploy-and-cpu-plan.md).

## Follow-up status — 2026-11-14 22:50 JST

- Current candidate is PR #68 head `6a024f5b584e85efa93cf6df3cd0fa827f833bc2`.
  All six exact-head GitHub checks pass. Local Python suite: 588 passed,
  1 skipped; Sites Worker/D1 suite: 43 passed. The branch is clean and pushed.
- Independent review found two concrete reliability issues, both fixed in this
  candidate: RunPod account leases could be released while provider creation
  was ambiguous (`5a7f0aa`), and malformed Modal output/stream errors could
  bypass Sandbox termination (`bc1035d`). See
  [Modal capture hardening](acceptance/2026-11-14-modal-capture-hardening.md).
- A further D1/R2 review found a stale Modal `running` row could block the
  single execution slot forever if the Sandbox stayed missing. The candidate
  now retains the slot through a 300-second post-lease grace and releases it
  only after a fresh authenticated Modal 404, with a conditional D1 update and
  cleanup evidence. This code is live in Sites Version 34.
- The Modal app was redeployed to `unjuno/main` from candidate `6a024f5`.
  Sites Version 34 is live at source commit `18339d5106ff148d0ec4b3acf8da64791b69d54f`,
  environment revision 38. `CPU_WORKLOAD_ADMISSION_ENABLED=false` after a
  prepared plan expired without owner sign-in. ChatGPT capabilities were
  verified available at revision 37 with owner-bound, one-use plan confirmation
  and configured 1-core / 512-MiB limits. No inference has been submitted.
- The Modal dashboard shows `$0.10` in credits, `$0` in charges, and a `$1`
  Workspace usage limit. The project test authorization is `$1` aggregate
  through completion; the `$0.01` Sandbox ceiling excludes control-function
  charges.
- A one-hour Workspace API token was used only through ephemeral process
  environment variables for the Modal deploy; it was not written to local
  Modal config or the repository. Its revocation is awaiting the required
  action-time confirmation. The earlier same-name token also remains listed;
  neither secret is exposed in this record.
- Modal dashboard after deploy: `$0.10` of `$1` usage (shown as credits), `$0`
  charges, and a `$1` Workspace cap. The prepared plan expired while the Site
  confirmation redirected to OpenAI sign-in; the gate is closed. No health
  check or Sandbox execution occurred. Owner sign-in must precede a fresh plan.
- Repository-wide Codex Security scan remains partial at 45/335 files, without
  a final report. Independent Sites review found no actionable issue in the
  inspected paths, but separately authenticated account isolation and trusted
  identity-header provenance remain unverified. RunPod/GPU and paid execution
  remain parked.

## Latest hosted state — 2026-11-14

- ChatGPT Sites Version 33 is active at the published URL. The connected owner
  account can read capabilities and owned run history; the persistent Modal
  Proxy Token configuration is present. The Site is publicly reachable, while
  the Worker still applies authenticated owner checks. Each experiment has a
  separate exact-plan, one-use confirmation.
- Sites environment revision 35 sets
  `CPU_WORKLOAD_ADMISSION_ENABLED=false`. Capability reads report the Modal
  provider configured and the authorization store ready, but execution is
  unavailable while admission is closed.
- The Site advertises Modal fingerprint
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`; the
  current candidate fingerprint is
  `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`.
  Candidate hard limits of CPU `(1.0, 1.0)` and memory `(512, 512)` are not
  live-verified. Five latest Modal-origin attempts failed with
  `MODAL_WORKLOAD_EXIT_2`; the newest has confirmed cleanup and no artifact.
- Modal is usage-billed, not inherently free. Modal's general Starter pricing
  advertises `$30` monthly compute, but this Workspace's dashboard says only
  `$1` of `$30/mo` is currently available and its Credits tab says `$1` monthly.
  Usage & Billing shows `$0.10` in credits used, `$0` in charges, and a `$1`
  Workspace usage limit; at most `$0.90` usage headroom remains under that cap.
  The provider remains classified as paid and credit-eligible. The
  `$0.01` Sandbox ceiling excludes control-function charges. No billing setting
  changed.
- PR #68 is still Draft. Exact-head CI passed, but repository-wide security
  coverage, separate-account denial, Modal deployment/fingerprint matching,
  and successful ChatGPT inference remain open. RunPod/GPU execution remains
  parked and is not wired as a live Sites tool.

## Sites Version 33 approval sign-in fix — 2026-11-13

- Production Site Version 33 is live at
  `https://gpu-control-sites.unjuno.chatgpt.site`, source commit
  `c85fdf7da994ab59b8a19bbb42b2998bc9814e69`, deployment
  `appgdep_6af709c728a08191925d228213edbd03`; MCP is enabled and environment
  revision 34 is unchanged.
- The `/authorize` page now links anonymous visitors to the official
  ChatGPT sign-in route and returns them to the same validated run ID and plan
  fingerprint. A signed-in but non-allowlisted identity receives 403 instead
  of a login loop. The POST confirmation stays same-origin and one-use.
- Site Worker tests passed 36/36; build and artifact validation passed. The
  ChatGPT `experiment_capabilities` operation currently reports the registered
  CPU workload available, provider configured, human-authorization storage
  ready, and admission enabled.
- A direct public authorization-page request returned HTTP 401 both without
  identity and with a forged `oai-authenticated-user-id` header. The edge did
  not accept the caller-supplied identity. A genuinely separate signed-in
  account denial check is still open.
- An exact bounded plan was prepared (`run_id` `851a10287ace484d8f4fb404cd2d5795`;
  TinyStories 15M; prompt `Once`; 1 token; seed 61112; 30 seconds; CPU only;
  Sandbox estimate `$0.0013`, Sandbox ceiling `$0.01`). It expired at
  `2026-11-13T13:05:50Z`. Browser sign-in was not completed, no owner approval
  was recorded, and no provider health call or Sandbox was started. A status
  lookup returned `RUN_NOT_FOUND`, consistent with no submitted run.
- Control-function costs are outside the Sandbox ceiling. Existing credits
  may offset eligible compute but are not a guarantee against charges. The
  previous `$1` Workspace limit was a point-in-time observation and must be
  rechecked before a future run.
- The Sites connector can read capabilities in this ChatGPT conversation, but
  the embedded browser opened a separate OpenAI login page. Complete the
  account sign-in there, then prepare a fresh plan if this one has expired.
  PR #68 is Draft. Site sign-in fix commit `f49988a96e4a65657f67041b90862da6d3aa1319`
  passed all six checks. The PR now mirrors the Site Worker source and
  regression test; production publication still uses the separate Sites source
  repository.
- Supplemental local security scans on Site sign-in fix commit: Semgrep 1.161.0
  scanned 277 tracked files
  with 110 rules and reported one SHA-1 compatibility warning at
  `project_control/runner.py:147`; the code reproduces GitHub Git-blob IDs with
  `usedforsecurity=False`, not a signature. Gitleaks 8.30.1 reported five
  generic-key matches: four pinned tokenizer SHA-256 constants (including a
  generated bundle copy) and one forged authenticated-user-ID test example.
  No credential was verified. These are current-tree checks, not the required
  independent repository-wide Deep Security Scan or complete history audit.
  Codex Security requires a managed read-only profile, unavailable in this
  session. Daybreak had no existing repository environment and returned a
  conflicting exhausted-credit status despite a displayed `$500` allowance;
  no cloud scan was launched. See
  [local security scan](acceptance/2026-11-13-local-security-scans.md).

## Sites Version 32, environment revision 34, and current execution gates — 2026-11-13

## Sites Version 32, environment revision 34, and current execution gates — 2026-11-13

- Production Site Version 32 is live at
  `https://gpu-control-sites.unjuno.chatgpt.site` from Site-source commit
  `7aacaac46a0111621d450c89a85fde7ce8cca6a2`; environment revision 34 and MCP
  are active. D1 contains `modal_authorized_health_checks`, the per-plan
  one-use reservation for separately billed Modal health diagnostics.
- The Worker requires the exact owner-confirmed `run_id` and plan fingerprint
  for a standalone Modal health call, checks unexpired unconsumed authorization,
  requires admission enabled, and reserves both a workspace cooldown and a
  unique plan row before calling Modal. No health call is made when admission
  is closed. The exact-plan confirmation remains one-use and expires within
  10 minutes.
- CPU admission is enabled for the fixed registered workload. ChatGPT
  capability read reports `available=true`, `provider_configured=true`,
  `human_authorization_store_ready=true`, and `admission_enabled=true`; provider
  readiness remains deferred until a plan-authorized submission. The runtime
  ceiling is 30 seconds, one in-flight run, estimated Sandbox cost $0.0013,
  and maximum Sandbox cost $0.01. Control-function charges are separate.
- Sites runtime values now advertise fingerprint
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec` and
  registered digest
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  The digest has not been reconciled with the locally rebuilt image or an
  authenticated Modal response. No current inference is accepted.
- Modal browser state shows the `gpu-control-sites` app with one inactive CPU
  control function, zero live function calls, and zero live Sandboxes. The app
  Details view exposes its resource configuration but not a trusted current
  OCI digest. Authentication/readiness and digest parity are still unverified.
- The current ChatGPT connector metadata still exposes the previous empty
  input schema for the separate provider-health diagnostic. Normal preparation
  and exact-plan submission remain the primary path; connector schema refresh
  for the optional diagnostic is unverified.
- The latest recorded Modal workload attempts failed with exit code 2 and
  cleanup confirmed, but predate the current Modal deployment. No inference
  has been run since that deployment.
- Modal Usage & Billing currently shows a $1 Workspace usage limit, $0.10 in
  credits used, $0 in charges, and an “Add payment method” action. This is a
  snapshot, not a durable no-charge guarantee. Modal documents the Workspace
  usage limit separately from the net spend limit and describes automatic
  monthly and incremental billing; see
  [Modal budgets](https://modal.com/docs/guide/budgets) and
  [Modal billing](https://modal.com/docs/guide/billing).
- Modal's API-token inventory is empty; the named main-environment Proxy Token
  remains available to the Site. No temporary Workspace API token is retained.
- PR #68 remains open and Draft. CI reruns on each push; preceding head
  `3e31de5` passed all six checks. The D1 migration test includes migration
  0008.
- Security diff review of this change found no source-level candidate
  vulnerability. Coverage is partial: live Sites identity-header provenance,
  cross-account denial, provider image/readiness, payment limits, and the
  connector's health schema remain unverified. Report:
  `~/.codex/state/plugins/codex-security/scans/gpu-control-pr58-current-candidate/d119bd791f26775b9887c79ec7315db7cda9f16a_20261113T121318Z_e9aj3n3p/report.md`.
- Next gates: obtain one-use owner confirmation for a fresh exact plan; verify
  the authenticated Modal preflight, inference artifact, provenance and
  cleanup; reconcile the deployed image digest; then complete independent
  cross-account denial and P0 security review. The live Modal UI showed the $1
  Workspace usage limit, $0.10 credit usage, $0 charges, and a prompt to add a
  payment method to raise the limit. Preserve that limit and the $0.01 Sandbox
  ceiling. RunPod GPU and paid training remain parked.
- Evidence: [Sites Version 32 and environment 34 acceptance](acceptance/2026-11-13-sites-v32-admission-enabled.md).

## ChatGPT Sites and Modal fingerprint refresh — 2026-11-13

- Reconciled the live Sites fingerprint environment key to the fixed Modal
  workload fingerprint and redeployed existing Site Version 31. Sites
  environment revision 33 is active; MCP remains enabled and admission remains
  `false`.
- ChatGPT capabilities now return the matching fingerprint, but still report
  `provider_ready=null`, `CPU_WORKLOAD_ADMISSION_DISABLED`, and
  `paid_execution=parked`. No provider health request or new Sandbox was
  started during this refresh.
- The two newest owned Modal Sandbox runs remain failed with
  `MODAL_WORKLOAD_EXIT_2`; cleanup is confirmed and neither produced an
  artifact. They predate the current fingerprint refresh and do not validate
  the refreshed path. Modal currently shows zero concurrent Sandboxes.
- Current Modal Usage Limit snapshot: `$1` Workspace usage limit, `$0.10`
  credit usage, `$0` charges. Recheck before any run. See
  [`ChatGPT Sites and Modal fingerprint refresh`](acceptance/2026-11-13-chatgpt-sites-modal-fingerprint-refresh.md).

## Authenticated Modal health diagnostic and Site publish — 2026-11-13

- Added the owner-allowlisted `experiment_provider_health` MCP operation. It
  makes an authenticated GET to Modal `/v1/health`, compares readiness, source,
  workload, digest, fingerprint and runtime limit, and explicitly reports that
  no Sandbox or inference was started. Its description discloses separately
  billed control-function requests; the MCP annotation does not mislabel this
  billable/stateful diagnostic as read-only or idempotent.
- A D1 atomic workspace-wide cooldown permits at most one health request per
  60 seconds. Migration `0007_modal_health_check_limit.sql` adds one shared
  limiter row without storing user IDs. D1 migration replay passed, Site Worker
  tests passed **32/32**, and Site build plus packaged-artifact validation
  succeeded. `git diff --check` passed.
- The candidate is on GitHub PR #68 and deployed as Sites Version 30 from
  Site-source commit `b97c5ceaad1d509c262d66a07015f74bb4e17546`; Version 31
  then republished the corrected source README from
  `7be42adca5306a7cd3d7ecd84718af47969dd9b0`. Both deploys succeeded with MCP
  enabled and environment revision 32; Version 31 has the same packaged
  Worker archive hash as Version 30. Live D1 now lists
  `modal_health_check_limits`; live admission remains false and the previously
  registered digest/fingerprint remain unchanged.
- The existing ChatGPT GPU Control connector still exposes its prior tool
  schema in this session, so the new diagnostic has not yet been invoked through
  ChatGPT. An anonymous public `tools/list` request received HTTP 401; no
  authentication was fabricated. No Modal health call or Sandbox was started
  from this change.
- Full deployment evidence and the exact remaining acceptance are recorded in
  [`Sites Version 30 acceptance`](acceptance/2026-11-13-sites-v30-modal-health-diagnostic.md).
- A follow-up failure-path regression now also proves a D1 limiter-write error
  prevents any Modal request. The worker suite is **33/33** after this addition;
  this changes tests only and does not alter the deployed Worker archive.

## Modal candidate deployment update — 2026-11-13

- PR #68 head `496e28cdb1b257c2a508e56a11fcdb07f6aa8028` is deployed to
  Modal `unjuno/main`. The first attempt exposed an image build-order error
  (`add_local_dir` after a non-copy local source); the fix copies the bootstrap
  into the API image. Full Python verification passed **573 tests, 1 skipped**;
  `git diff --check` passed. All six exact-head GitHub checks pass.
- Modal created API image IDs `im-4K01UJNs0MRcjkglisct1w` and
  `im-Z63nygRSH8lcUALSM2Pfrn`. This is deployment evidence only: unauthenticated
  `/v1/health` returned HTTP 401, and authenticated health/readiness and
  inference have not been verified. The imported source fingerprint is
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`;
  Sites still advertises `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`
  and digest `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  No trusted rebuilt OCI digest has been registered, so admission remains
  disabled and no Sandbox was started.
- Modal UI showed a `$1` Workspace cap, `$0.10` cycle usage, `$0` charges,
  `$1 of $30/mo` free credits, and zero live containers/Sandboxes. The temporary
  Workspace token was revoked; token inventory showed zero API tokens and its
  temporary config was deleted. During the first UI issuance, the token value
  appeared in tool output; it was not used and was immediately revoked. The
  subsequent CLI config had mode `0644`, but its token was also revoked and the
  config removed. No credential is retained.
- Details: [`Modal deployment and credential cleanup`](acceptance/2026-11-13-modal-main-deploy.md).

## Sites production reconciliation — 2026-11-13

- Sites Version 29 is now deployed from the GitHub candidate's synchronized
  source. The Site-only source commit is
  `6144d58acf6de609c8ac42d0b06542e29d89b1ab`; production environment revision
  remains 32. The publish applied D1 migrations 0005–0006; the live schema
  overview now includes `authorization_challenges`, `human_authorizations`,
  `provider_account_leases`, and `provider_account_lease_events`.
- Fresh ChatGPT capabilities confirm the exact-plan authorization flow is
  present and the owner authorization store is ready. Admission remains
  `false`; capabilities report unavailable with
  `CPU_WORKLOAD_ADMISSION_DISABLED`. Worker error logs were empty in the
  five-minute post-deploy window. No inference or D1 row read/write was made.
- The synchronized archive SHA-256 is
  `e1a7a2666e895df1133a7ef1690e8ac1a54fff9ec67cc81c8fd8a0ad21b0092a`.
  Site-source `npm test` passed 30/30, and build and validation succeeded.
  Modal showed zero live Sandboxes and zero running control calls; no provider
  compute was started. See
  [`Sites Version 29 production acceptance`](acceptance/2026-11-13-sites-v29-production-deploy.md).
- PR #68 remains Draft at GitHub head `496e28cdb1b257c2a508e56a11fcdb07f6aa8028`;
  all six exact-head checks pass. The Site-only deploy commit is separate from
  GitHub history. Modal's rebuilt
  OCI image digest and fingerprint still do not match the current candidate,
  and the independent-account browser check, independent PR review, repository
  P0 audit, Modal image readiness, and post-deploy authorized inference remain
  open. Keep admission closed.
- Recomputed the Modal candidate fingerprint by importing the checked-out
  `app.py` under its pinned Modal/FastAPI dependencies: current source yields
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`.
  Earlier current-state notes listed `0fc60d18…`; that value is stale for
  this exact checkout. Live Sites still advertises `3bf90f4c…`.

## Build backend dependency pin — 2026-11-13

- PEP 517 requirements now pin setuptools and wheel, and `build-constraints.txt`
  pins and hashes their build dependencies. CI verifies the build before
  syncing the locked environment. Local verification on uv 0.11.17 passed:
  `uv lock --offline`, hash-checked `uv build`, locked offline sync, and the
  complete Python suite (**573 passed, 1 skipped**). At code commit `cc076b8`,
  all six exact-head CI checks passed using the repository-pinned uv 0.10.0;
  the exact-range Codex Security diff scan reported zero findings. This is not
  the repository-wide P0 audit.
- See [`build backend lock acceptance`](acceptance/2026-11-13-build-backend-lock.md).

## Current goal recheck — 2026-11-13 05:46 UTC

- PR #68 remains open as Draft, with no independent GitHub review. Current
  source update is the migration replay test; subsequent commits only update
  documentation. The latest full six-job CI run passed Python 3.11, 3.12,
  3.13, Sites Worker/D1 contract, Project bridge tests, and trusted reference
  container. No independent review is recorded.
- A fresh Semgrep 1.161.0 `p/security-audit` scan reported one warning at
  `project_control/runner.py:147`, the documented SHA-1 use for Git blob object
  ID compatibility with `usedforsecurity=False`.
- A fresh redacted, worktree-only Gitleaks scan found five
  `generic-api-key` matches: four `TOKENIZER_SHA256` checksum occurrences in
  source/generated code and one test-only completion-key fixture. No live
  credential was verified. This scan did not cover Git history; the earlier
  full-history scan's 11 reviewed matches is recorded above.
- The Sites source reconciliation and read-only D1 overview found production
  Version 28 source drift and missing human-authorization tables. The live
  submit route remains unsafe to call; production environment revision 32
  explicitly keeps admission `false`. Modal secret values were not returned by
  the environment reader. See
  [`2026-11-13 Sites source reconciliation`](acceptance/2026-11-13-sites-source-reconciliation.md).
- Static scans of the separately fetched deployed Version 28 source completed:
  Semgrep `p/security-audit` reported 0 findings; redacted Gitleaks reported
  three `TOKENIZER_SHA256` 64-character hex checksums and no verified provider
  credential. These scans cover the deployed source snapshot only and do not
  close the P0 audit.
- Added a SQLite replay regression covering migrations 0000–0005 and synthetic
  existing D1 rows; `uv run --locked pytest` passes 573 tests with 1 skipped.
  This proves migration compatibility on local SQLite, not on live D1.
- Sites applies hosted D1 migrations before Worker upload; failed deployments
  may leave the schema advanced. Migration 0005 is additive, and the runbook
  now requires deployment/schema reconciliation before retry instead of manual
  reapplication or rollback.
- Repository-wide Codex Deep Scan and independent review remain incomplete.
  Local scans and green CI are not substitutes for either.

## Dependency audit and remediation — 2026-11-12 17:31 UTC

- PR #68 is open as Draft. The dependency fix at code head
  `7b16186cd35c621a33f550efded78aabe63a64d4` passed all six required
  exact-head checks, including the new audit step in Python 3.12. No independent
  review is recorded.
- Fresh ChatGPT capabilities still report Modal health ready but
  `admission_enabled=false`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`. Run `e9330c5bb5454f42bb3dabe058091dc0`
  remains failed with confirmed cleanup and no artifact. Earlier successful
  records predate retirement of the local Runner and do not establish current
  Modal success.
- The signed-in Modal UI shows a `$1` Workspace limit, `$0.07` credits used,
  `$0` charges, and zero deploy API tokens. No app deployment, setting change,
  or provider run occurred in this refresh.
- Dependency audit found 10 advisory records (five distinct advisories) for
  Starlette in the previous Modal API image dependency resolution
  (`fastapi==0.128.2` selected `starlette==0.50.0`). The candidate API image
  now installs a hash-locked dependency
  set from `sites/gpu-control-sites/modal/requirements.txt`, generated from
  `requirements.in` with FastAPI `0.162.2` and Starlette `1.10.0`. A fresh
  pip-audit scan of 42 development and Modal API packages found no known
  vulnerabilities. CI now audits both locked dependency sets in the required
  Python 3.12 job. The findings correspond to Starlette's [advisory list](https://github.com/Kludex/starlette/security/advisories);
  the fixes are documented in its [release notes](https://github.com/Kludex/starlette/blob/main/docs/release-notes.md).
  This candidate change has not been deployed.
- The whole-repository Codex Deep Scan remains incomplete because the current
  host still lacks its required managed read-only filesystem profile. Do not
  treat dependency scanning or local Semgrep/Gitleaks checks as a replacement.

## Local security-tool refresh — 2026-11-13

- PR #68 already exists as a Draft and currently points at this checkout's
  exact head `9cdb8eb88e6eca9c8384045ce87ea269a65ba848`; creating another Draft
  would duplicate the same candidate. The GitHub API confirms the PR is open,
  based on `codex/gpu-control-p1-dcr-v9-review`, and its six required exact-head
  checks are green.
- A local Gitleaks scan across the full Git history reported 11
  `generic-api-key` matches. All 11 were inspected without treating their
  strings as credentials: they map to pinned SHA-256 checksums, test-only
  fixtures/idempotency values, or synthetic encoded test data. No live
  credential was verified. This is a reviewed false-positive set, not proof
  that all secret exposure risks are absent.
- A local Semgrep `p/security-audit` scan parsed about 100% of 254 tracked
  files (50 excluded by `.semgrepignore`) and produced one warning for SHA-1
  in `project_control/runner.py`. That code reproduces GitHub Contents API's
  Git blob object ID solely for source-integrity matching; it is not used for
  signatures, credentials, or security tokens. The official API example links
  `sha` to the Git blob endpoint. The code now sets `usedforsecurity=False` and
  documents the purpose. Semgrep still reports the rule because it does not
  account for that flag; the warning remains visible and reviewed rather than
  suppressed. All 19 Project Control unit tests pass.
- GitHub Code Scanning has no analysis recorded, and Dependabot alerts are
  disabled. The Codex Security repository-wide P0 scan remains unstarted
  because the active session lacks its required managed read-only filesystem
  profile. These local checks do not replace that audit or an independent PR
  review.

## Live refresh — 2026-11-13 17:05 UTC

- PR #68 is open as Draft at head
  `e816eae970f9fe04443c1e56708a4f3a3a8ae9d5`, stacked on
  `codex/gpu-control-p1-dcr-v9-review`. All six required exact-head GitHub
  checks passed. It still has no independent approval and remains Draft.
- Current PR changes include historical execution-origin labels, bounded Modal
  exit-2 preflight diagnostics, a D1 cancellation/finalization guard, and
  regression coverage for the real workload's missing-identity guard.
  Local verification passed: Sites Worker 25/25, Modal bootstrap 5/5, build,
  Site artifact validation, and `git diff --check`.
- The focused Codex Security diff scan
  `ce9035fb-329e-4b5d-a51b-d5a00c895286` reviewed the Worker, its tests, and
  the acceptance record; it reported zero findings. It is not the P0
  repository-wide audit and does not cover the latest PR changes. A new diff
  scan attempt did not start and returned no scan ID.
- The `gpu-control-sites` Site remains public at Version 28, source commit
  `237c0bed24277cf7c808f8c0e9946c71d517288c`, environment revision 32. The
  current PR patch has not been deployed to Sites, and live `experiment_list`
  responses still omit `execution_origin`. Production remains on the prior
  response contract.
- A fresh ChatGPT capability read reports Modal provider health ready, but
  `admission_enabled=false`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`. Recent live run history still includes
  five Modal failures and older successes attributed to the retired local
  Runner. The latest run `e9330c5bb5454f42bb3dabe058091dc0` remains failed
  with `MODAL_WORKLOAD_EXIT_2`, cleanup confirmed, and no artifact. The live
  fingerprint is `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`;
  the current PR Modal candidate computes
  `0fc60d1890c26a646330a0d848750a0dedc03ff8a56a6e6dd214dba1e3471560`.
  The candidate is not deployed; no deployment, D1 write, or provider run was
  performed in this refresh.
- The Sites runtime environment inventory has no `RUNNER_BEARER_TOKEN` or
  `RUNNER_SERVICE_TOKEN` key; Sites masks secret values, so this records key
  names only. The current checkout has no tracked macOS Keychain launcher or
  LaunchAgent manager, and the host has no matching GPU Control launchd job or
  Runner process. Historical D1 `runner_heartbeats` and run records are kept as
  data evidence. `project_control/runner.py` is a separate GitHub Project
  bridge component, not the retired personal-host compute Runner.
- The P0 Deep Security Scan remains unstarted because this active session does
  not provide the required managed read-only filesystem profile. Cross-account
  Sites identity isolation, D1/R2 restore and retention, and current Modal
  execution acceptance remain open. RunPod/GPU and paid execution remain
  parked under `policies/repository-state.yaml`.

## Main branch protection refresh — 2026-11-12 15:56 UTC

- GitHub owner settings show a classic protection rule for `main`. It requires
  pull requests, one approval, dismissal of stale approvals, and approval of
  the latest reviewable push by someone other than its pusher. It requires
  these six checks: `Python 3.11`, `Python 3.12`, `Python 3.13`,
  `Trusted reference container`, `Project bridge tests`, and
  `Sites Worker and D1 contract`.
- The rule also requires the branch to be up to date, all review conversations
  to be resolved, and linear history; it applies to administrators and
  prohibits force pushes and branch deletion. The rulesets API returned an
  empty list, so the protection is the classic branch rule visible in the owner
  UI. The API's 403 did not establish that protection was absent.
- PR #68 is stacked on `codex/gpu-control-p1-dcr-v9-review`, not directly on
  `main`; the main rule describes the eventual merge gate. PR #68 remains Draft
  and has no independent review submissions, so it does not yet satisfy the
  one-approval rule.

## CI compatibility refresh — 2026-11-12 15:52 UTC

- PR #68 code branch head `2ca43d18d364213d4aa74b996d746bd643b7966a`
  upgrades the pinned `actions/setup-node` from v6.0.0 to official immutable
  v7.1.0 commit `949feb2413d6458794dcd2491c4babbbce0c15c1`, addressing the
  GitHub Actions Node 20 deprecation warning.
- Exact-head CI and Project bridge tests both passed on `2ca43d1`; all six
  reported checks succeeded and the prior Node runtime warning was absent.

## Current checkout and live capability refresh — 2026-11-12 15:48 UTC

- At the 15:48 UTC observation, PR #68 was at head
  `ac8efc265021e4dfe6d9169ef0c4a3b7e417229a` on `codex/sites-modal-runner`,
  matching `origin`; that commit updates only operations documentation. The
  latest code commit is
  `504e492ec2e03f79a94cfad41729d6e30531f598`, which adds
  `gpu_control_modal_bootstrap` to the Modal API image after the earlier
  `67f60a2` bounded Sandbox exit-marker change. PR #68 remains open as a Draft
  against `codex/gpu-control-p1-dcr-v9-review`.
- The code commit's exact-head GitHub runs passed: CI `43249691251` and Project
  bridge tests `43249691590`. No checks were created for the documentation-only
  head `ac8efc2`. A Security Review of the one-line image-packaging change found
  no issue; this is not an independent review of the full PR. No full-PR review
  is recorded.
- The ChatGPT Sites capability tool reports Modal provider health ready,
  admission disabled, and availability false with
  `CPU_WORKLOAD_ADMISSION_DISABLED`. Live Sites still expects fingerprint
  `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`; the
  current Modal candidate computes
  `0fc60d1890c26a646330a0d848750a0dedc03ff8a56a6e6dd214dba1e3471560`.
  The candidate has not been deployed and the Sites environment has not been
  updated to the candidate fingerprint.
- Latest run `e9330c5bb5454f42bb3dabe058091dc0` is still failed with
  `MODAL_WORKLOAD_EXIT_2`, cleanup confirmed, and no result or artifact.
  Modal's app overview shows 0 live containers and 0 live Sandboxes (5 Sandbox
  creations in the last 24 hours); no Sandbox was started during this refresh.
- Modal Usage & billing shows `$0.07` in credits, `$0` in charges, and a `$1`
  Workspace usage limit. The API-token page shows 0 tokens. The earlier `$0.05`
  snapshot is superseded; no token was created in this refresh.
- The repository-wide P0 Deep Security Scan did not start: the scanner requires
  a managed read-only filesystem permission profile, which was unavailable in
  the current session. Do not treat the one-line diff review as the P0 audit.
- Deployment and another Sandbox run remain unperformed. Modal admission is
  still closed; RunPod/GPU execution remains parked.

## Live branch refresh — 2026-11-13

- PR #68 remains open as a Draft, based on `codex/gpu-control-p1-dcr-v9-review`;
  head `67f60a2b39fd08840173e07fe6a049a1b3a66bec` adds a fixed Modal bootstrap
  marker for `SystemExit(2)`. Its PR-triggered CI (`43246512972`) passed the
  Python 3.11–3.13 matrix, trusted reference container, and Sites Worker/D1
  contract jobs; Project bridge tests (`43246512950`) also passed. No PR reviews
  are recorded yet.
- A Codex Security diff review of the four tracked code changes reported no
  findings. The new Python bootstrap test was manually inspected but was
  untracked and omitted from that scan's inventory. This is not the repository-
  wide P0 audit; that audit still requires a managed read-only filesystem
  profile, which this active session does not provide.
- Current ChatGPT capabilities remain `provider_ready=true`,
  `admission_enabled=false`, and `available=false`. Live Site registration
  advertises Modal fingerprint `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`;
  PR #68's bootstrap source computes `0fc60d1890c26a646330a0d848750a0dedc03ff8a56a6e6dd214dba1e3471560`.
  The Modal deployment and Site environment have not been updated to the new
  fingerprint, and no new Sandbox was started.
- Latest run `e9330c5bb5454f42bb3dabe058091dc0` remains failed with
  `MODAL_WORKLOAD_EXIT_2`, confirmed cleanup, and no result artifact. The new
  bootstrap marker has not yet been deployed or validated end to end.
- Modal's current Workspace cap is `$1`, with `$0.05` credits used and `$0`
  charges; API token inventory is empty. These facts do not authorize a run.
- The current checkout contains no tracked Keychain Runner implementation or
  active Sites Worker route for RunPod. A local process query found no matching
  Runner process. RunPod/GPU and paid execution remain parked.
- The GitHub integration returned 403 for branch-protection details and the
  rulesets API returned an empty list in that API read. A later owner-UI read
  confirmed the classic `main` protection rule documented above.

The full delivery objective remains open: complete the repository-wide P0
audit, obtain independent PR review, deploy and verify the fixed Modal
diagnostic, secure the exact-plan CPU run, complete recovery and cross-account
acceptance, then separately implement and validate the RunPod GPU path.

## Hosted Sites and provider status — refreshed 2026-11-12

Latest verified capability — 2026-11-12 13:46 UTC: the public ChatGPT Sites MCP Worker is
deployed as Version 28 from Site source commit
`237c0bed24277cf7c808f8c0e9946c71d517288c`, with production environment
revision 32 and D1/R2. The live ChatGPT capability read reported
`provider_ready=true`, all provider identity/health checks true,
`admission_enabled=false`, and `available=false` for `modal_cpu`. Paid
execution remains parked. The owner's ChatGPT connection has called the Site;
cross-account plugin access remains unverified.

The refreshed ChatGPT tool signature accepts
`experiment_prepare.max_cost_usd=0.01`, matching the usage-billed Sandbox
ceiling. The 15-second bounded Modal request timeout is deployed. The one
authorized one-token run `e9330c5bb5454f42bb3dabe058091dc0` failed with
`MODAL_WORKLOAD_EXIT_2` after 247 ms; Modal Sandbox
`sb-01M77ZZRFC1090CXA2W3MHDH7V` had no logs. Sites confirmed cleanup, but no
result or artifact was produced and the expected preflight line marker was
absent. Environment revision 32 has admission false; capabilities are ready but
unavailable. Another attempt needs a new exact-run authorization after a useful
diagnostic change.

An earlier 16-token ChatGPT-initiated Modal Sandbox run
`b3380814d0854d93a5d978799d670013` failed with exit code 2; cleanup was
confirmed and no artifact was produced. A fresh read-only history check also
found an earlier failed run `0f2a3ddaa7da40648600bae21ccd9ed1` at 11:25 UTC
with the same exit code and confirmed cleanup; its deployment/authorization
provenance is unknown. Modal Usage last showed a `$1` Workspace limit,
`$0.04` credits used, and `$0` charges at 12:35 UTC. The bounded preflight
diagnostic from `d1dd4fe` was deployed to Modal `unjuno/main` at 12:49 UTC;
the CLI returned success and the dashboard showed the app deployed just now
with zero live containers and zero live Sandboxes. The later authorized
diagnostic attempt and current admission state are recorded in the current
operational snapshot above. The one-hour Workspace deploy token was deleted
immediately after deployment; reloading the API-token page showed zero tokens.

The Modal dashboard's deployment timeline showed v4 at 2026-11-12 18:06 JST,
but its history row did not identify a source commit. The successful ChatGPT
run `eacc26ff2ad54cf69a1ee7665325b197` generated four tokens in 142 ms and its
complete R2 artifact was verified, but the run was performed by the local
Runner under Sites Version 16; it is not Modal evidence. Two Modal runs
(`96d7efef9542463d9fc51f47ffbfd5d7` and
`599473dcc1ed4034a42d849bcb42e261`) failed with cleanup confirmed before v4.
No successful inference after v4 is recorded. Site Version 24 now stores a
bounded Modal exit-code failure code without provider stderr, but no live run
has tested that diagnostic. A fresh ChatGPT capability read reports provider
health ready, admission disabled, and unavailable. Modal's account page
previously showed `$0.01` usage this cycle. The earlier temporary deploy token
was deleted; Modal's API-token page showed zero tokens after each revocation.
The Sites Worker has no
RunPod route; live RunPod and paid GPU execution remain parked.

The personal-host CPU Runner and its Keychain authentication path are retired.
Do not restore them. Older TinyStories successes remain historical evidence;
they do not establish current Modal execution success.

Before retirement, a ChatGPT-originated TinyStories 15M inference completed on
Sites Version 15 after a Runner process-loss recovery test.
Run `aa45b7d899de4c9aaff2ee73fa985cc6` used the registered workload source commit
`3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288` and image
`sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
With prompt `A little bird found a bright blue feather.`, seed `719243`, and an
8-token limit, it generated 8 tokens in 291 ms, passed identity/sandbox checks,
returned `gpu_used=false`, and confirmed cleanup at `$0.00`. Its complete
999-byte R2 artifact was retrieved through ChatGPT; its locally computed
SHA-256 matches D1 metadata. A separate active-run process-loss probe expired
after 180 seconds and recovered as `runner_lost_recovered` with cleanup
confirmed, no retry, and no leftover container. A follow-up inference proved
the free CPU slot was available again.

This does not establish general model quality, repeated crash-window coverage,
cross-owner isolation, or GPU capability. The local Runner result is historical;
the two Modal failures predate v4, and there is no accepted post-v4 inference.
Modal recovery and real RunPod GPU acceptance remain open. Full evidence and gates are tracked in
[`decisions/2026-11-11-sites-d1-architecture-pivot.md`](decisions/2026-11-11-sites-d1-architecture-pivot.md).
The current staged plan is [`SITES_MODAL_RUNPOD_DELIVERY.md`](SITES_MODAL_RUNPOD_DELIVERY.md).
Run evidence: [`Modal and CPU inference chronology`](acceptance/2026-11-12-modal-and-cpu-inference-chronology.md).

The rest of this document records standalone CLI and provider-adapter status on
`main`; it does not supersede the hosted Sites acceptance snapshot above.

This document describes what `gpu-control` on `main` can do today. It deliberately distinguishes implemented offline/control-plane contracts from live paid GPU execution.

## Readiness summary

| Capability | Status | Notes |
| --- | --- | --- |
| Installable standalone CLI | Ready | Python 3.11+, locked dependencies, offline self-test. |
| Request/resource-policy validation | Ready | `gpu-control validate`; no network or GPU required. |
| Public GitHub source verification | Ready | `gpu-control verify-source`; verifies public repository, exact 40-character SHA, and Dockerfile path. |
| Synthetic provider contract self-test | Ready | `gpu-control provider-self-test`; no network or billing. |
| Trusted repository-owned container isolation fixture | Ready | CI exercises a bounded, secret-free reference container. |
| Generic external workload container execution | Not enabled | External Dockerfiles are not generally executed by this repository yet. |
| Decision/context security policy | Ready at policy/CI level | Action constitution, source-to-sink trust policy, failure catalog, and adversarial fixtures are present. |
| Approved execution plan contracts | Ready offline | Immutable/fingerprinted plans, pricing evidence, durable lifecycle state, cleanup state, and bounded result manifests are implemented. |
| Structured exact human authorization | Ready for RunPod adapter boundary | Runtime validator and expiring `LiveExecutionPermit` exist; RunPod adapter construction/submission requires the exact unexpired permit. End-to-end paid workflow wiring remains absent. |
| Current RunPod REST v2 transport layer | Ready offline | Fixed `api.runpod.io/v2` client, cursor-paginated List Pods with bounded complete inventory, v2 create/get/delete, trusted Network Volume attachment, and response identity checks are mock-tested. |
| Current RunPod pricing/availability evidence | Ready offline | Fixed REST v2 GPU catalog, secure price/capacity, VRAM, exact Network Volume datacenter, HIGH stock, 300-second maximum TTL, and content-digest binding are mock-tested. |
| RunPod REST v2 provider adapter | Ready offline for selected canary | Canonical v2 adapter requires current pricing evidence, exact Network Volume DC, unexpired live permit, and v2-backed occupancy/reconciliation before create. |
| RunPod ambiguous create/cleanup reconciliation | Ready offline on REST v2 transport | Bounded occupancy/reconciliation consumes every cursor page and remains fail-closed. Provider behavior and cleanup remain unverified live. REST v1 is retained for offline compatibility only and is forbidden for live calls. |
| Authenticated Orbitune completion v3 | Ready offline | Root signer binds exact result bytes and the observed process exit code into HMAC-SHA256 evidence; legacy v2 remains only during migration. |
| RunPod Network Volume/S3 result transport | Ready offline | Fixed RunPod S3 origin, trusted `/outputs` mount, exact two-object bounded collection, and v3 authentication are mock-tested. Live verification and real credentials/volume are pending. |
| Orbitune paid-canary result acceptance | Ready offline | Workload-specific acceptance accepts authenticated log-v2 or durable volume-v3 evidence and remains separate from provider cleanup/finalization. |
| Pre-cleanup result capture/finalization | Ready offline | Provider-neutral ephemeral-result capture is durable and bounded. |
| Production Pod-log SSE | Officially documented, not live verified | Current RunPod REST v2 documentation exposes `GET /pods/{id}/logs` as SSE. It is not used as the result path because its account behavior and terminal semantics have not been live verified. |
| Paid GitHub Actions workflow | Not present yet | `main` contains CI and dry-run workflows only. It must not be added/enabled until external GitHub gates and initial live provider verification are complete. |
| Live paid GPU execution | Disabled | Repository state is `parked`; paid/provider/result live flags remain off. |

## Current selected canary

The repository currently records this canary workload:

- repository: `Unjuno/orbitune`
- source SHA: `fc131174a9b529a9825f54fccf1a7df4c63c9a1a`
- Dockerfile: `workloads/runpod-training-canary/Dockerfile`
- workload id: `orbitune-runpod-training-canary-v1`
- GPU profile: `cheap-24gb`
- maximum runtime: 30 minutes
- maximum cost ceiling: USD 0.30
- completion protocol: `gpu-control-hmac-sha256-v3`
- exact-main full pytest run: `33313993621` — passed
- exact-main RunPod canary smoke run: `33313993623` — passed

The source CI, signer isolation, current REST v2 adapter contract, current v2 price/DC-stock contract, and central offline volume-transport tests have passed in earlier candidate runs. The selected image now separates a root-owned signer from training UID/GID 10001. The control plane supplies a per-run key only to that digest-pinned wrapper and requires authenticated volume result transport before submission. That does **not** mean the control plane is authorized to spend money today.

## Durable result transport

The Pod-log limitation has a candidate durable-transport implementation and an offline-connected completion path:

1. a pre-existing RunPod Network Volume is mounted at trusted path `/outputs` when the Pod is created;
2. the root wrapper captures the per-run key, removes it before launching the unprivileged training process, and writes `completion-v3.json` over the exact `result.json` bytes and effective process exit code;
3. the Pod may exit and be cleaned up without destroying the Network Volume;
4. the control plane can read bounded objects through RunPod's S3-compatible API;
5. the control plane verifies the v3 HMAC, source, image, plan, execution nonce, result digest and signed exit code before mapping an exited Pod to `SUCCEEDED` or `FAILED`;
6. this boundary protects against the unprivileged training process, while the RunPod host and account administrator remain outside the signer threat model.

The transport is implemented and mock-tested, but not yet live-verified. Network Volume creation/resizing is deliberately not automated because it is a persistent billable resource.

## Provider-control and pricing path

The selected RunPod path has offline/mock components from price selection through result collection, but end-to-end result acceptance is gated:

- current GPU price and VRAM come from the fixed-origin REST v2 GPU catalog;
- exact per-datacenter stock is checked for the Network Volume datacenter;
- current price/DC evidence is short-lived and content-digest bound;
- the approved plan carries the exact price/reference/time window;
- `RunPodV2CurrentAdapter` rechecks that evidence and the Network Volume DC immediately before submission;
- current REST v2 creates the Pod and cursor-paginated v2 List Pods backs account occupancy/reconciliation;
- durable Network Volume/S3 collection and the root-signer contract are connected offline, while live injection and collection remain disabled pending provider acceptance;
- cleanup remains explicit and reconciliation-backed.

No live provider call is enabled. Provider acceptance must still prove the exact image receives the challenge, the training UID cannot read it, the bounded result is collected, and cleanup is reconciled before activation.

## Why live paid execution is still disabled

`policies/repository-state.yaml` remains the source of truth. Important remaining activation requirements include:

- protected `gpu-control/main` with required CI checks;
- control-plane context integrity and prompt/context gates;
- an owner-only protected `paid-runpod` Environment;
- Environment-scoped `RUNPOD_API_KEY` plus separate RunPod S3 credentials;
- a pre-existing Network Volume in a supported S3 datacenter;
- immutable published canary-image identity;
- live read-only verification of current pricing, exact-datacenter stock, and account occupancy;
- live verification of ambiguous-create, result collection, and cleanup reconciliation;
- protected paid-workflow wiring that constructs the exact current `LiveExecutionPermit` from trusted runtime evidence.

The 2026-10-31 GitHub API audit confirms `main` is protected with the seven
required Actions checks, one approval including approval after the last push,
strict/up-to-date checks, conversation resolution, linear history, and admin
enforcement. This satisfies the branch-protection prerequisite only; P1 PR #52
still awaits its independent approval. The same audit found no Environment
protection rules or deployment-branch policy on `Production` or `Preview`, and
no dedicated `paid-runpod` Environment. Do not treat repository access, a
successful dry-run, or available budget as authorization to spend money.

## What "ready" means here

A feature marked **Ready** is usable from `main` for the stated offline/read-only purpose. It does not imply that a downstream live provider action is enabled.

**Offline/mock only** means executable code and tests exist but no real provider credential or billable action was used to verify it.

**Live disabled** means policy intentionally prevents provider calls even if local code could otherwise construct them.

## Source of truth

When documentation and machine state differ, prefer:

1. `policies/repository-state.yaml` for current activation state;
2. `policies/paid-execution-policy.yaml` for paid-path identity/security requirements;
3. `policies/runpod-v2-policy.yaml` for the current Pod-control and pricing contract;
4. `policies/runpod-rest-v1-policy.yaml` for legacy offline compatibility state;
5. tests and current `main` implementation for executable behavior.
