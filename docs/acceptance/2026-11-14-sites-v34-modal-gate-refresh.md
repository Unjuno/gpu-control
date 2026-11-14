# Sites v34 and Modal gate refresh — 2026-11-14

## Sites production state

- The Sites project `appgprj_6af482670c2081919ffe27a6faa0f746` is active and
  owned by the connected account. Version 34 is deployed successfully from
  source commit `18339d5106ff148d0ec4b3acf8da64791b69d54f`; environment revision
  38 is active at `https://gpu-control-sites.unjuno.chatgpt.site`.
- The Site audience is public. Its MCP operation policy has one owner account
  allowlisted. This does not independently establish trusted provenance for
  the platform-injected identity or prove denial from a second account.
- Production configuration contains the CPU admission flag, registered source
  and image identities, Modal endpoint and Proxy Token settings, and the
  workload image fingerprint. Secret values were not read into this record.
- ChatGPT MCP capabilities report `CPU_WORKLOAD_ADMISSION_DISABLED`; no provider
  is advertised as ready. Existing D1/R2 bindings and run history remain in
  place.

## Modal state and aggregate spending

- The Modal `unjuno/main` app was deployed from candidate commit
  `6c2260d75232b30e440ca0b8eb635bfe58f12779`. The deployment succeeded and did
  not launch a Sandbox. The `control_api` page showed zero live containers and
  zero running calls.
- The `control_api` function page showed 1 CPU requested with the default CPU
  limit, 512 MiB requested with no memory limit, and a 60-second timeout. These
  are control-function settings; the workload Sandbox has its own hard limits
  of 1 CPU, 512 MiB, and 30 seconds. Control-function charges are separate from
  the Sandbox estimate.
- The Modal Workspace page showed a `$1` usage limit. The API token list showed
  zero active tokens after the temporary deployment token was revoked. The
  user's `$1` is an aggregate project testing cap. Account-specific usage and
  balance details are intentionally omitted from this public repository; they
  must be checked in the Workspace before any provider call.
- The latest five Modal-origin runs in the connected account's run list failed
  with `MODAL_WORKLOAD_EXIT_2`; their cleanup was confirmed and no result
  artifact was recorded. The latest of those runs predates the November 14
  deployment and the Modal logs page had no matching entries. They do not
  establish that the current deployment fails, and they do not prove it works.

## Exact-plan confirmation gate

- A bounded plan was prepared with run ID
  `263a8e82b6b94b4a95eb5d29c44eae0b`, fingerprint
  `c8876c8305b2d31975e9a3ceb425bdfd840367385a0120290a36404264337d0d`, model
  TinyStories 15M, prompt `Once`, one output token, seed `61112`, and a 30-second
  runtime. The declared Sandbox estimate is `$0.0013` with a `$0.01` ceiling;
  control-function charges are excluded.
- The Site redirected the confirmation page to OpenAI sign-in. The connected
  in-app browser was at the OpenAI login page, so the owner did not confirm this
  exact plan. No provider health request or Sandbox submission was made from
  it. The confirmation is one-use and expires after 600 seconds; prepare a
  fresh plan after the owner completes sign-in.
- Keep admission disabled until the owner confirms a fresh plan. Afterward,
  verify provider readiness, run only the authorized single inference, inspect
  result provenance, and confirm cleanup and actual Workspace usage before
  considering the CPU vertical complete.

## Remaining acceptance

This refresh verifies deployment and current configuration, not successful
Modal inference. Cross-account authorization, Site identity-header provenance,
fresh Modal readiness, successful ChatGPT-origin inference, artifact retrieval,
cleanup after success, and actual total charges remain open. RunPod and GPU
execution remain parked behind their separate account, security, spend,
availability, and cleanup gates.
