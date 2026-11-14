# Modal deploy and exact-plan authorization checkpoint — 2026-11-14

## Scope and outcome

- Deployed the current `codex/sites-modal-runner` candidate to Modal `unjuno/main` in app `gpu-control-sites` after explicit user approval for a one-hour Workspace API token. The initial CLI attempt stopped before contacting Modal because its ephemeral CLI environment lacked `fastapi`; retrying with the locked `sites/gpu-control-sites/modal/requirements.txt` succeeded. No Sandbox was started by the deployment.
- Revoked the temporary Workspace API token immediately after deployment. The Modal API-token page was reloaded and showed zero active tokens.
- Updated the production Sites environment variable `MODAL_WORKLOAD_IMAGE_FINGERPRINT` to candidate fingerprint `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`. No secret was read or changed. `CPU_WORKLOAD_ADMISSION_ENABLED` remains `false`; the registered image digest and source SHA were left unchanged.
- Published existing Sites Version 33 with environment revision 36. Deployment `appgdep_6af842f14bd081919b9b13ac4bde12ad` succeeded at `https://gpu-control-sites.unjuno.chatgpt.site`.
- Exact-head GitHub CI for candidate `d23f1bed91be32c833d20182d2ff5d69b846996f` passed all six checks: Python 3.11, 3.12, 3.13, Trusted reference container, Project bridge tests, and Sites Worker and D1 contract.

## Spend checkpoint

- Modal Usage page currently reports total Workspace usage of `$0.10` for the November billing cycle. Earlier account UI showed the Workspace usage limit at `$1`; no payment method was added. The overall authorized project test budget remains `$1` aggregate through completion, not `$1 per run. Keep the Workspace cap at `$1` and recheck usage before further provider calls.
- The registered inference plan estimates `$0.0013` Sandbox CPU/memory and has a `$0.01` Sandbox-only ceiling. Modal control-function charges are separate and must also fit within the aggregate project budget.

## Exact-plan health check pending

- ChatGPT `experiment_capabilities` confirms provider configured but admission disabled, with blocker `CPU_WORKLOAD_ADMISSION_DISABLED`. This is the intended closed state until acceptance gates pass.
- Prepared the first health-check plan through the installed ChatGPT tool for the registered `tiny-stories-inference-v1` workload: repository `Unjuno/gpu-control`, registered source SHA `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, prompt `Once`, one token, seed `61112`, 30 seconds, CPU-only, no network, and the `$0.01` Sandbox ceiling. Plan/run ID `53a421b131ba41de8b8021ddd4539f1c` was not authorized before its short confirmation window elapsed.
- Re-prepared the same bounded plan. Plan/run ID `df24bffd138f4eefad332f4db0c5a60d` and fingerprint `c8876c8305b2d31975e9a3ceb425bdfd840367385a0120290a36404264337d0d` expired at 2026-11-14 11:27 UTC without owner authentication or confirmation. The Site required ChatGPT sign-in before displaying the plan. No credentials were entered; no health call or Sandbox execution occurred. Wait for owner sign-in before preparing another short-lived plan.
- After owner confirmation, perform the single health call, verify readiness, then prepare/confirm exactly one bounded inference plan. Collect successful output, digest, cleanup evidence, and actual Modal Sandbox CPU/memory/network limits. Leave admission disabled until these checks and the outstanding P0 review are complete.

## Remaining release gates

- Current Modal inference remains unaccepted: latest recorded Modal-origin attempt failed with `MODAL_WORKLOAD_EXIT_2`; no successful result artifact is established for this candidate.
- The repository-wide P0 Deep Scan continuation was attempted on 2026-11-14 and did not start/rejoin. Exact blocker: `Deep Scan cannot safely start a read-only worker: the parent must provide a managed filesystem permission profile.` The existing scan remains incomplete; no replacement scan or security clearance is claimed.
- Verify actual Modal Sandbox resource and network limits from the provider record, not only code/config.
- Complete repository-wide P0 security review; the historical scan is stale and incomplete.
- RunPod/GPU acceptance remains parked. Do not claim full ChatGPT experiment completion until the live ChatGPT-to-provider path, artifact ownership, cleanup, account isolation, and required security gates have evidence.
