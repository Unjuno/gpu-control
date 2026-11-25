# Sites admission and CPU plan — 2026-11-15

## Published configuration

- Rechecked Sites project `gpu-control-sites`: active, public URL, current user
  is owner, MCP is ready, and its existing application owner allowlist remains
  configured. No allowlist or secret value was read or changed.
- Production environment revision 38 had
  `CPU_WORKLOAD_ADMISSION_ENABLED=false`. Set only that key to `true`, then
  redeployed existing saved Site Version 34. Production deployment
  `appgdep_6af8a25b69b08191a7d67795a7b571ac` succeeded at the existing Site
  URL with environment revision 39. No source version or audience changed.
- A fresh ChatGPT capabilities call reported `available=true`, Modal configured,
  health still deferred until a confirmed plan, one physical CPU core, 512 MiB,
  maximum 30 seconds, and a `$0.01` Sandbox ceiling. Modal usage immediately
  before this step was `$0.10` credits used, `$0` charges, `$1` Workspace limit.

## One-run plan

- Prepared run `aa687747b5474d0192b5cfc6fc6b89a7`, fingerprint
  `c8876c8305b2d31975e9a3ceb425bdfd840367385a0120290a36404264337d0d`:
  registered TinyStories 15M, source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`,
  prompt `Once`, one token, seed `61112`, 30 seconds, CPU only, no network.
  Sandbox estimate `$0.0013`, Sandbox-only ceiling `$0.01`; Modal control-call
  charges are excluded from that estimate.
- No health call, submit, or Sandbox was started. The owner authorization page
  redirected this browser to the ChatGPT login page. The five-minute plan
  expired without confirmation. A fresh plan and owner confirmation are
  required after the user signs in. Do not treat older authorization for a
  different fingerprint as approval for this one.
- Admission remains enabled under the Workspace `$1` cap and the application's
  owner allowlist and exact-plan, one-use confirmation flow. Recheck Modal
  usage before each run. Full P0 security review remains incomplete; RunPod/GPU
  and paid training remain parked.
