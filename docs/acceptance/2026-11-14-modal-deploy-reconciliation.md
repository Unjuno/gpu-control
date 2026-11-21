# Modal deploy and exact-plan authorization checkpoint — 2026-11-14

## Scope and outcome

- Deployed the current `codex/sites-modal-runner` candidate to Modal `unjuno/main` in app `gpu-control-sites` after explicit user approval for a one-hour Workspace API token. The initial CLI attempt stopped before contacting Modal because its ephemeral CLI environment lacked `fastapi`; retrying with the locked `sites/gpu-control-sites/modal/requirements.txt` succeeded. No Sandbox was started by the deployment.
- Revoked the temporary Workspace API token immediately after deployment. The Modal API-token page was reloaded and showed zero active tokens.
- Updated the production Sites environment variable `MODAL_WORKLOAD_IMAGE_FINGERPRINT` to candidate fingerprint `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`. No secret was read or changed. `CPU_WORKLOAD_ADMISSION_ENABLED` remains `false`; the registered image digest and source SHA were left unchanged.
- Published existing Sites Version 33 with environment revision 36. Deployment `appgdep_6af842f14bd081919b9b13ac4bde12ad` succeeded at `https://gpu-control-sites.unjuno.chatgpt.site`.
- Exact-head GitHub CI for candidate `d23f1bed91be32c833d20182d2ff5d69b846996f` passed all six checks: Python 3.11, 3.12, 3.13, Trusted reference container, Project bridge tests, and Sites Worker and D1 contract.

## Spend checkpoint

- Modal Usage page currently reports total Workspace usage of `$0.10` for the November billing cycle. Earlier account UI showed the Workspace usage limit at `$1`; no payment method was added. The overall authorized project test budget remains `$1` aggregate through completion, not `$1 per run`. Keep the Workspace cap at `$1` and recheck usage before further provider calls.
- The Modal app overview after redeploy showed `$0.10` total usage this cycle, 0 live containers, 0 live Sandboxes, and 0 Sandboxes created in the last 24 hours. The `control_api` function details show 1 CPU core requested, 512 MiB memory requested, no explicit CPU or memory limit, 60-second timeout, maximum 1 container, no GPU, and preemptible execution. These are control-function settings, not evidence of the separate Sandbox's resource limits. The visible latest `GET /v1/health` call was on Nov 13 (HTTP 200), before the Nov 14 redeploy; no post-deploy health call is recorded.
- The registered inference plan estimates `$0.0013` Sandbox CPU/memory and has a `$0.01` Sandbox-only ceiling. Modal control-function charges are separate and must also fit within the aggregate project budget.

## Exact-plan health check pending

- ChatGPT `experiment_capabilities` confirms provider configured but admission disabled, with blocker `CPU_WORKLOAD_ADMISSION_DISABLED`. This is the intended closed state until acceptance gates pass.
- Prepared the first health-check plan through the installed ChatGPT tool for the registered `tiny-stories-inference-v1` workload: repository `Unjuno/gpu-control`, registered source SHA `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, prompt `Once`, one token, seed `61112`, 30 seconds, CPU-only, no network, and the `$0.01` Sandbox ceiling. Plan/run ID `53a421b131ba41de8b8021ddd4539f1c` was not authorized before its short confirmation window elapsed.
- Re-prepared the same bounded plan. Plan/run ID `df24bffd138f4eefad332f4db0c5a60d` and fingerprint `c8876c8305b2d31975e9a3ceb425bdfd840367385a0120290a36404264337d0d` expired at 2026-11-14 11:27 UTC without owner authentication or confirmation. The Site required ChatGPT sign-in before displaying the plan. No credentials were entered; no health call or Sandbox execution occurred. Wait for owner sign-in before preparing another short-lived plan.
- After owner confirmation, perform the single health call, verify readiness, then prepare/confirm exactly one bounded inference plan. Collect successful output, digest, cleanup evidence, and actual Modal Sandbox CPU/memory/network limits. Leave admission disabled until these checks and the outstanding P0 review are complete.

## RunPod account and deploy-screen checkpoint

- The signed-in RunPod console shows the Pod deployment screen, but no GPU is selected and no Pod has been created. The Deploy button is disabled.
- The selected PyTorch 2.8.0 template is marked Deprecated. The default 50 GB container disk contributes `$0.007/hour`; with no GPU selected, the UI shows `$0.01/hour` total. The GPU catalog currently displayed RTX A5000 at `$0.27/hour`, RTX A6000 at `$0.69/hour`, RTX 6000 Ada at `$1.09/hour`, and A100 PCIe at `$2.09/hour`. These are dashboard rates at observation time, not a current live allocation or an authorization to create one.
- RunPod account Settings showed profile and GitHub connection details but no credit balance. The previously mentioned `$15` balance is therefore not verified. No billing/top-up change, Pod creation, or RunPod charge occurred during this check.
- Do not use the selected Deprecated template for a live test. Before any registered RunPod GPU experiment, select and verify a current supported template, confirm remaining account credits and a hard spend limit, wire the Site-side account lease/authorization/result route, and prove cleanup.

## Remaining release gates

- Current Modal inference remains unaccepted: latest recorded Modal-origin attempt failed with `MODAL_WORKLOAD_EXIT_2`; no successful result artifact is established for this candidate.
- The repository-wide P0 Deep Scan continuation was attempted on 2026-11-14 and did not start/rejoin. Exact blocker: `Deep Scan cannot safely start a read-only worker: the parent must provide a managed filesystem permission profile.` The existing scan remains incomplete; no replacement scan or security clearance is claimed.
- Verify actual Modal Sandbox resource and network limits from the provider record, not only code/config.
- Complete repository-wide P0 security review; the historical scan is stale and incomplete.
- RunPod/GPU acceptance remains parked. Do not claim full ChatGPT experiment completion until the live ChatGPT-to-provider path, artifact ownership, cleanup, account isolation, and required security gates have evidence.

## Later correction — 2026-11-14

The token-inventory statement above records the immediate post-deployment
snapshot only. A later one-hour Workspace API token was created but not used
after a Modal source comparison showed no deployable Modal code change at that
point. The inventory still lists that token after its displayed expiry and
shows no recent activity; revocation has not been verified. Do not interpret
the earlier “zero active tokens” snapshot as the current state. No secret value
was recovered or used. Current budget and candidate state are recorded in
`2026-11-14-modal-capture-hardening.md`.

## Candidate redeploy and Site gate follow-up — 2026-11-14 13:55 UTC

- Current PR head `6a024f5b584e85efa93cf6df3cd0fa827f833bc2` passed all six
  exact-head checks. Modal `gpu-control-sites` was deployed to `unjuno/main`
  from that candidate using a one-hour Workspace token held only in ephemeral
  process environment variables; CLI exit code was 0. No Sandbox was started.
- The current Site source candidate was reconciled with its remote source
  history and published as Version 34 from commit
  `18339d5106ff148d0ec4b3acf8da64791b69d54f`. Deployment succeeded at
  `https://gpu-control-sites.unjuno.chatgpt.site` with environment revision 37.
  The live `experiment_capabilities` call reported `available=true`, a matching
  image fingerprint, one-use exact-plan approval, and 1-core / 512-MiB limits.
- Modal Usage showed `$0.10 / $1` usage (credits), `$0` in charges, and a `$1`
  Workspace limit. One bounded plan was prepared (TinyStories 15M, prompt
  `Once`, 1 token, seed 61112, 30 seconds, CPU only, estimate `$0.0013`, ceiling
  `$0.01`). Its Site authorization redirected to OpenAI sign-in. No owner login
  or approval occurred before expiry, and the plan was not submitted. The
  owner-scoped run list did not show it; a direct status request returned
  `INVALID_ARGUMENT` after expiry.
- To avoid leaving production admission open without owner approval, the Site
  gate was set back to false and Version 34 redeployed successfully at
  environment revision 38. No health request or Sandbox inference occurred.
  Reopen only after the owner completes sign-in and a fresh exact plan is ready.
- The API-token page still lists the newly created one-hour token and an older
  same-name token; revocation of the new token is awaiting action-time
  confirmation. No token value is included here. Repository-wide security
  review remains incomplete; this deployment does not constitute P0 clearance.
