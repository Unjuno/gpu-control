# ChatGPT Sites / Modal / Runpod delivery plan

## Goal

Make the ChatGPT Site the single public product and control-plane entry point
for registered experiments, while requiring authenticated ChatGPT identity for
every data-bearing or execution tool. Keep D1 for lifecycle state and R2 for bounded
results. Use Modal first for a small, fixed, low-cost compute path; retain Runpod
as the later GPU path behind the existing approval, price, workload, result, and
cleanup gates. Vercel, Neon/PostgreSQL, and the macOS Keychain Runner are not
part of the target runtime.

The Site is the ChatGPT-facing interface and policy boundary. It does not itself
provide model compute. Compute remains an explicitly configured provider.

## Live baseline — refreshed 2026-11-12

- The public Site `gpu-control-sites` is active at
  `https://gpu-control-sites.unjuno.chatgpt.site`, with deployed Version 24,
  source commit `c919b0047b203fb0c22b6dd7755934834e899f8f`, and environment
  revision 22.
- Its current Sites access mode is `public` (access revision 2). A Site-hosted
  plugin exists and is connected for the owner; this does not
  establish that another user's ChatGPT process can install or call it.
- Current ChatGPT capabilities report `provider_ready=true`, `available=false`,
  and `admission_enabled=false` for `modal_cpu`. The successful run previously
  attributed to Modal was executed by the retired local Runner under Sites
  Version 16. Two Modal runs failed with cleanup confirmed before the dashboard
  showed v4; no successful v4 inference is recorded. Admission stays closed.
  Paid execution remains parked.
- D1 and R2 remain the Site's storage bindings. Preserve their current records,
  migrations, artifacts, and historical evidence during provider changes.
- The macOS LaunchAgent and its local runtime were removed, and the two local
  Keychain items used by that Runner were deleted. Do not re-provision or use
  that authentication path.
- The Modal account is Starter. Its live UI showed `$1` of `$30/mo` in free
  credits and `$0.01` usage this cycle. The credits are not a hard billing stop.
- Runpod's console showed `$15` balance. That is not authorization to spend and
  does not satisfy repository activation prerequisites.
- Vercel and Neon are retired from the target runtime. Their historical
  records remain historical evidence and must not become deployment gates.

## Target boundaries

```text
ChatGPT
  -> public ChatGPT Site MCP Worker (authenticated owner-scoped operations)
       -> D1: owner-bound plans, executions, idempotency, lifecycle
       -> R2: bounded result artifacts
       -> Modal: fixed registered function, authenticated, async submit/collect
       -> Runpod: separately gated GPU execution after activation requirements
```

- The Site accepts only a registered workload and bounded parameters; no user
  supplied shell command, Dockerfile, image, provider URL, secret, or owner ID.
- A Modal entry function authenticates the Site request, verifies a
  run-bound request signature, and dispatches only the fixed compute function.
  The compute function receives no provider credentials or signing key. It must
  use bounded inputs, a finite timeout, no retries that can duplicate a run,
  restricted Modal access, and blocked outbound networking where supported.
- Modal's async call ID is opaque provider state. Persist it only after strict
  validation and bind it to the D1 run, plan fingerprint, and workload identity.
  Reconcile ambiguous submission before any retry.
- Runpod remains disabled until its current API contract is verified from the
  authenticated OpenAPI/API surface, and all current live authorization,
  pricing, account occupancy, result transport, cleanup, and control-plane
  integrity gates pass. Do not infer live readiness from offline tests or the
  account balance.
- The requested distribution target is public access through ChatGPT. Public
  hosting alone is insufficient: the Site's generated plugin is a separate
  access-controlled object. OpenAI's current help guidance says personal/Pro
  accounts cannot directly share a Site-hosted plugin with other users; a
  Business/Enterprise workspace can share it within that workspace, while
  general public availability requires the supported public plugin review and
  publication route. Choose and verify the supported route before claiming
  another ChatGPT process can use it.
- The Site is publicly discoverable, but all tool calls that read or mutate
  user/run state require the Sites-injected authenticated user ID. Anonymous
  callers may discover the public shell and tool schema only; they cannot
  prepare, submit, poll, cancel, or read results. Every D1 query remains scoped
  to that verified ID. Never accept an owner ID from tool arguments.
- Public execution adds abuse and cost exposure even when callers are signed in.
  Enforce per-user and global concurrency/rate/cost bounds before enabling Modal;
  Runpod stays parked until separately approved. Provider credentials remain
  server-side and are never returned to a caller.
- Production deployments must use the existing Site ID and preserve D1/R2
  bindings and data. Confirm the native Sites access mode supports the intended
  public discovery plus per-call identity behavior before changing audience.

## Delivery sequence and acceptance

### 0. Repository and account inventory

- Reconcile this checkout, `main`, open PRs, current Site Version 24, D1/R2 bindings,
  deployment state, Modal workspace limits, and Runpod active-resource state.
- Resolve the ChatGPT distribution route for non-owner users and test with a
  genuinely separate ChatGPT identity; a public Site URL or the owner's plugin
  call is not sufficient evidence.
- Retain append-only historical acceptance records; mark superseded operating
  instructions rather than rewriting past observations as if they never
  occurred.
- Completion: a source-of-truth status page distinguishes live state, offline
  implementation, and historical evidence.

### 1. Retire the local Runner

- Remove the Keychain launcher, LaunchAgent manager, and local polling process
  from the supported path. Remove current setup instructions that tell an
  operator to unlock macOS or provide a Keychain password.
- Keep old run/artifact records and D1/R2 data. Close the unused Runner API and
  remove its Site bearer secret only as part of a reviewed Site version cutover.
- Completion: no tracked active instructions or deployed endpoints depend on
  Keychain, local polling, `RUNNER_BEARER_TOKEN`, or the Sites service token.

### 2. Modal CPU vertical slice

- Package the existing pinned TinyStories workload as a minimal Modal app with
  separate authenticated dispatch and restricted compute functions.
- Implement D1-backed idempotent submit/status/result/cancel behavior and
  authenticated result validation before writing to R2. Keep current capability
  disabled until exact endpoint, proxy-token, signature, image/source identity,
  timeout, and cleanup behavior are verified.
- First live probe must be CPU-only, one invocation, a short runtime, and within
  the account's current cap. Record observed usage before considering another
  call.
- Completion: an actual ChatGPT conversation prepares, submits, observes,
  retrieves, and verifies a result through Sites → Modal → Sites/D1/R2, and the
  Modal invocation reaches a terminal state with no lingering compute. An
  anonymous request is rejected, and a second authenticated user cannot read,
  cancel, or retrieve the first user's run. The second user's own ChatGPT
  process must discover/install/connect the plugin and complete the same flow.

### 3. Recovery and operations

- Exercise duplicate submit, lost response after dispatch, stale call ID,
  timeout, provider failure, cancellation race, D1 write failure, R2 write
  failure, and restart between every persisted lifecycle transition.
- Add bounded reconciliation and idempotent cleanup. Preserve failed evidence
  without making it a successful result.
- Completion: each injected failure has deterministic terminal or explicitly
  recoverable state, no blind duplicate submission, no orphaned active compute,
  and a documented recovery procedure.

### 4. Runpod offline and live readiness

- Revalidate Runpod REST/OpenAPI and pricing/availability contracts from current
  official sources. Update the existing provider adapter and policies without
  enabling live calls.
- Complete workload provenance, immutable published image, exact offer/price,
  supported result transport, account occupancy, structured authorization,
  environment isolation, and cleanup acceptance.
- Only after every activation prerequisite is met, conduct one owner-authorized
  bounded GPU canary with a fixed cost ceiling and immediate cleanup. No paid
  workflow or live flag is enabled as a shortcut.
- Completion: the real ChatGPT flow returns independently verifiable GPU
  evidence, actual cost and runtime, authenticated result, and confirmed
  cleanup; a repeat is separately authorized.

## Current blockers

1. The fixed Modal CPU adapter and authenticated dispatch are deployed. Current
   Sites health reports Modal ready. ChatGPT run
   `eacc26ff2ad54cf69a1ee7665325b197` returned a verified R2 artifact, but it
   was executed by the retired local Runner and is not Modal acceptance. Two
   Modal runs failed as `MODAL_WORKLOAD_FAILED` with cleanup confirmed before
   the dashboard's v4 deployment; the v4 source commit was not exposed and no
   successful v4 inference is recorded. Site Version 24 records bounded Modal
   exit-code failure codes without provider stderr, but this diagnostic has not
   been observed on a live run. Admission stays disabled until failures are
   diagnosed and recovery behavior is adequate for another bounded run.
2. The local Runner is retired. Modal recovery and operational failure
   coverage remains incomplete; no successful inference after the current
   Modal dashboard deployment has been accepted.
3. Runpod live use remains parked. The canonical API and pricing path now use
   REST v2, with current public OpenAPI and catalog contracts reviewed offline.
   Live account, result, cleanup, concurrency, security, and spend acceptance
   remains required.
4. The Modal account UI showed `$0.01` usage this cycle and a free-credit
   banner. Recheck its current state before another run. Runpod balance is not
   a spend target.
5. Public Site hosting does not currently prove public plugin distribution. The
   account's eligible sharing/publication route and a separate-user ChatGPT test
   remain unresolved.

## Continuation refresh — 2026-11-12

- GitHub branch `codex/sites-modal-runner` is at `ea2cf5894a77dedd9e4a9d4b1f00a90dbf51c364`.
  The Site Worker accepts Modal Proxy Token ID/secret prefixes and reports
  provider health failure separately from disabled admission. Its 17-test
  Worker suite, build, artifact validation, and `git diff --check` passed before
  the change was committed and pushed.
- Modal's temporary one-hour deployment API token was revoked through the
  signed-in sidebar browser; reloading the API-token page showed no API tokens.
  The persistent Site Proxy Token remains configured in the hosted Site
  environment. Its capabilities response has not been rechecked against the
  corrected Worker version.
- The repository's machine policy still says `mode: parked` and forbids
  provider-secret references and live paid execution until the listed GitHub,
  prompt/context, workload, provider-contract, result-transport, and cleanup
  prerequisites are satisfied. Therefore no Site deployment, admission change,
  Sandbox start, or Runpod action was performed in this refresh.
- Remaining objective evidence: publish the corrected Site Worker only after
  resolving the repository activation-policy conflict; verify provider health
  and owner authorization from the ChatGPT tool path; diagnose the two recent
  failed Modal runs and add bounded failure diagnostics; complete operational recovery
  evidence; then independently satisfy and authorize Runpod GPU and paid-canary
  gates. The overall goal remains incomplete.

## Modal launcher fix refresh — 2026-11-12

- Repository branch `codex/sites-modal-runner` is pushed through
  `1c8c30d2270ca2bc7f35f3a988d66b4012be9a27`. The fix removes the root-required
  launcher from `modal/app.py` and lets Modal execute the image's fixed
  `python -I /work/inference.py` entrypoint as Dockerfile user 10001. Python
  compilation and `git diff --check` passed; the repository suite passed 559
  tests with 1 skipped; the Sites Worker suite passed 17/17. Independent code
  review found no actionable issue in this change.
- Modal CLI deploy returned exit code 0. The sidebar overview showed the app
  deployed just now and zero live Sandboxes. The temporary one-hour deploy
  token was deleted after deploy; the token-list page showed zero API tokens.
- The Site still reports Modal ready, admission disabled, and no available
  execution. No post-fix Sandbox was run in this refresh. Modal UI displayed
  `$0.01` usage this cycle. The overall goal remains open until authorized
  post-fix inference, recovery evidence, cross-account acceptance, Runpod GPU,
  and paid-execution gates are verified.

## Sites failure-diagnostic refresh — 2026-11-12

- Read-only ChatGPT tool calls verified the successful historical run
  `eacc26ff2ad54cf69a1ee7665325b197`: four generated tokens, 142 ms,
  `gpu_used=false`, identity/isolation checks passed, cleanup confirmed, and a
  verified 962-byte R2 artifact. The Runner acceptance record shows that this
  run used the local Runner under Sites Version 16, not Modal. It does not
  establish Modal inference success.
- Two subsequent runs failed with cleanup confirmed. The former Worker
  discarded the provider exit code, and the Modal log view for the later
  Sandbox had no entries. The cause remains unverified.
- Added bounded Worker failure codes for Modal exit status without exposing
  provider stderr. Site tests: 19 passed; build and artifact validation passed.
  Published Site Version 24 from source commit
  `c919b0047b203fb0c22b6dd7755934834e899f8f`; D1/R2 environment revision 22
  and public audience were preserved. Post-publish ChatGPT capabilities still
  report provider ready, admission false, and unavailable. No new Sandbox was
  started; live behavior of the new diagnostic remains to be verified during a
  separately authorized run.

## Current deployment and integration follow-up — 2026-11-12

- The authenticated Sites API currently reports production Version 24 from
  source `c919b0047b203fb0c22b6dd7755934834e899f8f`, public access, and the
  existing D1/R2-backed Site URL. A fresh ChatGPT capability call identifies
  the route as `modal_cpu`, with provider health ready but admission disabled
  and `available=false`.
- The current Sites Worker has a fixed Modal CPU path. RunPod REST v2 exists in
  the offline core library, but no RunPod provider route is exposed through the
  Sites MCP tools yet. Live RunPod, result transport, and cleanup gates remain
  open.
- The Modal Starter account cannot create Service Users without a Team upgrade.
  The approved main-scoped deployment credential was therefore unavailable;
  no plan change or Workspace-wide token was used. The latest source delta
  changes the Sites Worker, not the Modal app, so it had no Modal code to
  redeploy.
- Remaining work: diagnose the two historical Modal failures before reopening
  CPU admission; verify the new diagnostic on a bounded live run; complete
  recovery, cross-account, and backup/restore acceptance; build and review a
  separately gated RunPod route through Sites; then satisfy live GPU, cleanup,
  and spend evidence. The goal remains incomplete.

## Latest source and runtime follow-up — 2026-11-12 12:35 UTC

- Repository branch `codex/sites-modal-runner` is clean and pushed through
  `d1dd4fe2bbaf220e24fe1c1f97f958491a3d5674`. Its preceding commit
  `d2969a4` corrected Modal Sandbox cost disclosure and added the D1 cost-ceiling
  migration; `d1dd4fe` adds a bounded preflight line diagnostic that never
  returns provider stderr to ChatGPT. Worker tests passed 21/21; Site build,
  artifact validation, and synthetic diagnostic trace passed. The focused
  security diff review reported no findings; its scan warned that the worktree
  changed during review, so the final trace-scope narrowing was also manually
  inspected.
- Production is still Sites Version 27, source
  `64d2646815be198b0173877b821264cf3efc10a6`, environment revision 27.
  Capability reports Modal ready, admission disabled, and unavailable. The
  latest live run `b3380814d0854d93a5d978799d670013` failed with exit code 2;
  cleanup was confirmed, no artifact was produced, and the exact failed check
  remains unknown. The new diagnostic commit is not deployed.
- The previous one-run authorization was consumed by that failed attempt.
  Repository policy requires current explicit authorization per run. A request
  is pending for one 30-second CPU-only diagnostic run, with admission closed
  immediately afterward and the temporary deploy token revoked. Until approved,
  do not issue a token, deploy the diagnostic, change admission, or start a
  Sandbox.
- GitHub's connected status and workflow-run reads returned no checks for
  `d1dd4fe`; the local `gh` Actions query was blocked by GitHub API rate limit.
  Do not treat this push as having passed remote CI.
- RunPod REST v2 remains offline library functionality only; the Sites Worker
  exposes no RunPod route. RunPod GPU and paid execution remain parked behind
  the activation prerequisites in `policies/repository-state.yaml`. Separate
  account isolation, recovery, paired D1/R2 restore, and the approved public
  plugin distribution route also remain unaccepted.
