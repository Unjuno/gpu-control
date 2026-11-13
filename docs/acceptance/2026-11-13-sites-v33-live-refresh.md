# ChatGPT Sites Version 33 live refresh — 2026-11-13

## Published Site and ChatGPT connector

- The Sites control plane is `gpu-control-sites`, project
  `appgprj_6af482670c2081919ffe27a6faa0f746`, at
  <https://gpu-control-sites.unjuno.chatgpt.site>.
- Version 33 is deployed successfully from source commit
  `c85fdf7da994ab59b8a19bbb42b2998bc9814e69`, deployment
  `appgdep_6af709c728a08191925d228213edbd03`, environment revision 34, MCP
  enabled. The Site access mode is public; its owner account ID allowlist has
  one entry. An independent account denial test is still missing.
- Calls from this ChatGPT owner account to `experiment_capabilities` and
  `experiment_list` succeeded. The live capability response reports
  `provider_configured=true`, `human_authorization_store_ready=true`,
  `admission_enabled=true`, `available=true`, and `provider_ready=null`
  (provider health is deferred until an authorized submit).
- The registered workload remains `tiny-stories-inference-v1`, CPU only,
  maximum 30 seconds, one in-flight run, Sandbox estimate `$0.0013`, and
  Sandbox CPU/memory ceiling `$0.01`. This ceiling excludes separately billed
  Modal control-function calls. Each exact plan requires a one-use owner
  confirmation.

## Latest Modal-origin runs

A current owner-scoped history read returned five newest Modal-origin runs.
Each was re-read individually. All five are terminal `failed`, use workload
source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288` and registered digest
`sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`,
report `cleanup_state=confirmed`, and have no result or artifact:

| Run | Provider failure code | Created (UTC) |
| --- | --- | --- |
| `e9330c5bb5454f42bb3dabe058091dc0` | `MODAL_WORKLOAD_EXIT_2` | 2026-11-12 13:43:31 |
| `b3380814d0854d93a5d978799d670013` | `MODAL_WORKLOAD_EXIT_2` | 2026-11-12 12:16:12 |
| `0f2a3ddaa7da40648600bae21ccd9ed1` | `MODAL_WORKLOAD_EXIT_2` | 2026-11-12 11:25:21 |
| `599473dcc1ed4034a42d849bcb42e261` | `MODAL_WORKLOAD_FAILED` | 2026-11-12 08:52:36 |
| `96d7efef9542463d9fc51f47ffbfd5d7` | `MODAL_WORKLOAD_FAILED` | 2026-11-12 08:21:05 |

These runs predate the Modal API deployment recorded for 2026-11-13. That
source deployment includes the Sandbox `CMD` correction intended to ensure the
fixed privilege-dropping bootstrap runs. Its real Modal Sandbox effect has not
been tested. The earlier succeeded history rows identify the retired local
Runner and do not establish Modal inference acceptance.

## Image, cost and security boundaries

- Modal API deployment is recorded at `unjuno/main`, PR #68 head
  `496e28cdb1b257c2a508e56a11fcdb07f6aa8028`. The corresponding API source
  fingerprint advertised by Sites is
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`.
- A local corrected Docker image ID was recorded as
  `sha256:60ea9d29f70def1ad4577021ac51e2b186b8f8d2c6dee7a2d2d848b441fcbda1`.
  The Site plan and Modal code still use
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  The local image ID is not a verified Modal-deployed OCI digest; the actual
  Modal image identity and authenticated `/v1/health` response remain open.
- This refresh did not invoke provider health or submit a run. No new Sandbox
  was created. A fresh post-deployment owner-confirmed inference is still
  needed after image identity and spend controls are reconciled.
- The last recorded Modal dashboard snapshot showed a `$1` Workspace usage
  limit and `$0` charges. The current net spend limit was not read in this
  refresh. Modal documents that Workspace usage budgets and net spend limits
  are separate: <https://modal.com/docs/guide/budgets> and
  <https://modal.com/docs/guide/billing>.
- The Site is public at the hosting layer but applies an owner ID allowlist in
  MCP operations. This observation does not complete the P0 audit: independent
  cross-account denial, trusted identity-header provenance, and the required
  managed-profile repository-wide security scan remain unverified.
- RunPod has no Sites Worker execution route. GPU and general paid execution
  remain parked. The retired macOS Keychain Runner remains out of scope.
