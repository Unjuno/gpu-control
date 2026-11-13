# Sites Version 33 ChatGPT sign-in fix — 2026-11-13

## Deployment

- Site: `gpu-control-sites`
- Production URL: <https://gpu-control-sites.unjuno.chatgpt.site>
- Version: 33
- Site source commit: `c85fdf7da994ab59b8a19bbb42b2998bc9814e69`
- Deployment: `appgdep_6af709c728a08191925d228213edbd03`
- Runtime environment revision: 34
- MCP: enabled
- Deployment status: succeeded

## Change and checks

The `/authorize` route previously returned a 401 page telling an anonymous
visitor to reopen the Site, without a sign-in link. Version 33 uses the Sites
platform's documented `/signin-with-chatgpt` route and a same-origin relative
return path containing only a syntactically valid run ID and plan fingerprint.
After authentication, the page rechecks the exact plan and owner. A present but
non-allowlisted account receives 403 instead of being redirected into a login
loop. The approval POST still requires the owner, exact plan, same-origin
request, CSRF challenge, explicit checkbox, and one-use authorization.

Validation on the exact Site source before packaging:

- `npm test`: 36 passed, 0 failed.
- `npm run build`: passed.
- `npm run validate`: passed (`Site Worker artifact is complete`).
- Native Sites save and production deployment: succeeded; MCP remained enabled.

## ChatGPT and plan evidence

The ChatGPT `gpu_control_chatgpt_experiment_capabilities` connector call
returned `status=ok`, `available=true`, `provider_configured=true`,
`human_authorization_store_ready=true`, and `admission_enabled=true`. It also
reported a fixed CPU-only TinyStories workload, 30-second maximum runtime, one
in-flight run, `$0.0013` estimated Sandbox cost, and `$0.01` Sandbox ceiling.
Provider health remains deferred until an approved submit.

A fresh plan was prepared with:

- Run ID: `851a10287ace484d8f4fb404cd2d5795`
- Fingerprint: `4a4194ffee2159c783994831464d216396bcb99a99001e906242e18c28db727f`
- Workload: registered TinyStories 15M CPU inference
- Prompt: `Once`; output limit: 1 token; seed: 61112
- Runtime limit: 30 seconds; no GPU; network egress blocked
- Sandbox estimate: `$0.0013`; Sandbox ceiling: `$0.01`
- Expiration: `2026-11-13T13:05:50Z`

The approval URL rendered the new sign-in link and preserved the exact plan in
its return path. The in-app browser then reached `https://auth.openai.com/log-in`,
which means a browser sign-in was required. The user did not complete that sign-in
during this check. No approval was recorded, no provider health call was made,
and no Modal Sandbox was started. A status lookup returned `RUN_NOT_FOUND`;
this is consistent with the prepared plan not having been submitted. The Worker
source and regression test are mirrored in the GitHub PR branch; production
publication still reads the separate Sites source repository.

## Remaining acceptance

- Complete ChatGPT browser sign-in and confirm that the exact plan page returns
  for the allowlisted account.
- Prepare a fresh plan if the above plan has expired; explicitly approve that
  exact plan, then verify authenticated Modal readiness, inference result,
  artifact digest, execution provenance, and Sandbox cleanup.
- Verify denial from a genuinely separate ChatGPT account and confirm the
  provenance of the platform-injected identity header.
- Reconcile the advertised workload image digest against the Modal deployment.
- Keep RunPod GPU and paid training parked until their separate Sites route,
  security, result-authentication, recovery, and cleanup gates pass.

The Sandbox ceiling covers eligible CPU and memory usage only. Separately
billed Modal control-function calls are not included. Credits may offset eligible
usage but do not guarantee that no charge will occur. Recheck the current Modal
Workspace and net-spend limits before any new execution.
