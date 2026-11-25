# Modal and ChatGPT Sites live state recheck

Checked: 2026-11-12 09:28 UTC

## ChatGPT tool path

Read-only calls to the installed `GPU Control — ChatGPT実験管理` MCP returned:

- `experiment_capabilities`: `provider_ready=true`,
  `admission_enabled=false`, `available=false`, blocker
  `CPU_WORKLOAD_ADMISSION_DISABLED`; provider `modal_cpu`; workload
  `tiny-stories-inference-v1`; max runtime 30 seconds; max inflight 1; paid
  execution parked.
- Sites owner API confirms production version 23 is deployed successfully at
  `https://gpu-control-sites.unjuno.chatgpt.site`, environment revision 22,
  access mode `public`, with the current admission env var explicitly `false`.
  The saved version's source SHA is
  `1352662626d44dee08fd513f4c8886b6f75cb090`; this SHA is not present in the
  current checkout and GitHub could not resolve it, so it is not treated as
  source-provenance evidence for the current PR branch.
- `experiment_list`: latest failed runs were `96d7efef9542463d9fc51f47ffbfd5d7`
  (created 2026-11-12 08:21 UTC) and
  `599473dcc1ed4034a42d849bcb42e261` (created 2026-11-12 08:52 UTC). Both
  report `MODAL_WORKLOAD_FAILED`, `cleanup_state=confirmed`, and no result.
- The latest listed success, `eacc26ff2ad54cf69a1ee7665325b197` (created
  2026-11-12 05:02 UTC), has a validated TinyStories CPU result and confirmed
  cleanup. The Runner environment acceptance identifies it as a local Runner
  execution under Sites Version 16. It is not Modal evidence, predates the
  current Modal deploy, and does not verify the launcher fix.

## Modal dashboard

- Workspace banner: `$0.98` credits; adding a payment method is
  needed to unlock the remainder. This is a credit balance notice, not a hard
  spend-stop guarantee.
- App overview at the time of inspection: deployment shown as 22 minutes old,
  `$0.02` usage this cycle, 0 live containers, 0 live Sandboxes. The function
  deployment timeline identifies the current deployment as v4 at
  2026-11-12 18:06:03 JST. The history row leaves its commit field blank; v3
  shows `740fa98`, so the dashboard alone does not bind v4 to a source commit.
- The `control_api` function showed recent `/v1/health` calls returning HTTP
  200. The app overview does not expose a source commit in the inspected view,
  so the live deployment cannot be tied to the latest Git commit from this
  evidence alone. Both failed runs above (17:21 and 17:52 JST) predate v4; the
  listed successful run at 14:02 JST also predates v4. None accepts current v4.

## Gate disposition

No CPU run was submitted because admission is currently false and the exact
post-fix retry remains separately authorized. The objective remains open:
verify which source is deployed, then run the bounded ChatGPT CPU lifecycle,
retrieve its artifact, validate its provenance, and confirm cleanup. Recovery,
cross-account isolation, Runpod GPU, and paid execution remain separate gates.

## Continuation recheck — 2026-11-12 09:46 UTC

- Local `codex/sites-modal-runner` and its GitHub ref are both at
  `40afe25cba0a48fb9728d58484f87fbaf454422c`; the worktree is clean. PR #58
  remains open and draft, with all six required checks passing.
- The only diff since the previously deployed Modal source commit
  `1c8c30d2270ca2bc7f35f3a988d66b4012be9a27` is additional Sites Worker test
  coverage. `sites/gpu-control-sites/modal/app.py`, the Worker implementation,
  and workload source have no changes requiring a Modal code redeploy.
- A fresh ChatGPT capabilities read reports `provider_ready=true`,
  `admission_enabled=false`, `available=false`, and blocker
  `CPU_WORKLOAD_ADMISSION_DISABLED` for the registered `modal_cpu` workload.
- Modal's signed-in API-token page still shows zero API tokens. A one-hour CLI
  token flow was started but not authorized; it was aborted before token
  creation. No deployment or Sandbox was started in this continuation.
- Modal's deployed function page still shows zero live containers and calls;
  its latest visible health calls returned HTTP 200. The account banner shows
  `$1` of `$30/mo` in credits, which is not a hard spending cap.
- A successful ChatGPT run against the current Modal deployment, artifact
  verification, and cleanup acceptance remain open. The current PR branch is
  not merged to `main`; recovery,
  separate-account authorization, Runpod GPU, and paid execution remain open.

## Deployment credential scope check — 2026-11-12 10:00 UTC

- The user authorized a one-hour deployment token and deployment limited to the
  Modal `main` Environment. The Modal CLI token flow offered a one-hour API
  token for the `unjuno` Workspace, with no Environment restriction. This did
  not match the approved credential scope, so no `modal deploy` command was
  run.
- The temporary Workspace API token was revoked in Modal. Reloading the token
  page showed `API tokens (0)`. The CLI-created local `~/.modal.toml` contained
  only that `unjuno` profile and was removed. No Modal deployment, Sandbox, or
  Site admission change occurred.
- No Modal app source changed since the source currently believed deployed
  (`1c8c30d2270ca2bc7f35f3a988d66b4012be9a27`); the pushed follow-up contains
  documentation and test coverage. Current health and deployment state remain
  as recorded above; a main-scoped deployment credential and the separate
  successful ChatGPT inference against the current Modal deployment remains
  unresolved.

## Deployment credential eligibility recheck — 2026-11-12

- The user authorized reissuing a short-lived credential limited to the Modal
  `main` Environment and deploying. The signed-in Workspace `Service users`
  page states that Starter cannot create service users and requires a Team
  upgrade. No upgrade or Workspace-wide token was authorized, so no credential
  was created and no deploy was attempted. The API-token list remains empty.
- The current uncommitted source delta changes the Sites Worker diagnostics and
  documentation; it does not change `sites/gpu-control-sites/modal/app.py` or
  the Modal workload. There is no Modal code change in this delta to deploy.
- Modal deployment remains gated on an eligible main-scoped credential. No
  Sandbox, admission, payment, or provider settings were changed.

## Current Sites deployment and capability check — 2026-11-12 10:43 UTC

- The authenticated Sites control API reports production Site Version 24,
  source commit `c919b0047b203fb0c22b6dd7755934834e899f8f`, public access, and
  the existing production URL. This supersedes the earlier Version 23 snapshot
  above; it does not change the earlier evidence about the provenance of the
  Modal deployment itself.
- A fresh ChatGPT capability call reports `provider_ready=true`,
  `admission_enabled=false`, `available=false`, provider `modal_cpu`, workload
  `tiny-stories-inference-v1`, and blocker `CPU_WORKLOAD_ADMISSION_DISABLED`.
  Paid execution is parked and no next actions are enabled. No experiment was
  prepared or submitted in this check.
- This confirms the current Sites product route is Modal CPU and remains
  disabled. The separate successful `local_cpu` history is not current Modal
  acceptance. The current Sites Worker has no RunPod provider route; RunPod's
  v2 adapter remains an offline core-library implementation.
- No credential, compute, admission, D1/R2 data, or provider setting was
  changed during this read-only check.
