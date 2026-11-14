# ChatGPT Sites setup

## Supported architecture

The supported ChatGPT control plane is the public Sites MCP Worker at
`https://gpu-control-sites.unjuno.chatgpt.site`. Sites supplies the hosted
Worker, ChatGPT sign-in boundary, MCP publication, and D1 binding. D1 stores
plans, run state, and leases. Large immutable result files
are stored in R2; the Worker returns bounded chunks after owner/run and digest
verification. Eight complete result artifacts have been retrieved through
ChatGPT.

The Worker does not run Docker or model inference. The personal-host Runner
has been retired. The fixed Modal CPU adapter and the Sites Worker with
exact-plan human authorization are deployed. The current ChatGPT capability
response reports `provider_configured=true`, `provider_ready=null`,
`admission_enabled=false`, and `CPU_WORKLOAD_ADMISSION_DISABLED`; live provider
health is deferred until an authorized submit. No successful inference against
the current Modal deployment has been accepted through ChatGPT. RunPod GPU
execution remains a separately gated future path; paid execution is parked.

The legacy FastAPI/PostgreSQL Gateway and its Vercel deployment are archived
references, not supported deployment choices. Do not configure new Vercel or
Neon resources for this product. Historical setup evidence is preserved in
[`archive/CHATGPT_SETUP-legacy-vercel-gateway.md`](archive/CHATGPT_SETUP-legacy-vercel-gateway.md)
and [`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).

## Connect and use the Site MCP

1. Open the public Site from the ChatGPT account where its generated plugin is
   connected.
2. Install or connect the Site's generated `gpu-control` plugin when ChatGPT
   offers the plugin card.
3. In a ChatGPT conversation, select or mention `gpu-control` and call
   `experiment_capabilities` before preparing a run. The owner-only
   `experiment_provider_health` diagnostic checks the authenticated Modal
   endpoint and image identity without starting inference or a Sandbox; Modal
   control-function charges may apply separately from the Sandbox ceiling.
4. Prepare only the advertised fixed workload and review its exact source,
   usage estimate, and `$0.01` Sandbox-only ceiling. Modal control-function
   calls are billed separately. Credits are not a zero-cost guarantee. Site
   Version 30 added an owner-authenticated Modal health diagnostic and the
   exact-plan authorization implementation; Version 31 republishes the same
   Worker archive. The live D1 overview includes
   `authorization_challenges`, `human_authorizations`, and
   `modal_health_check_limits`. However, this ChatGPT connector still exposes
   the older tool schema without `experiment_provider_health`, and the current
   production confirmation flow has not been exercised end to end. Admission
   remains disabled. Do not submit until the connector schema is refreshed, the
   exact-plan confirmation flow is verified through ChatGPT, and the registered
   Modal image identity and readiness are reconciled. See the [Version 30
   acceptance record](acceptance/2026-11-13-sites-v30-modal-health-diagnostic.md)
   and [current release matrix](RELEASE_MATRIX.md). Once those gates pass, poll
   `experiment_status` and retrieve the terminal value with `experiment_result`.

The Site and plugin are separate access controls. The Site is public, while
stateful tools must use ChatGPT's authenticated Sites identity and server-side
owner checks on every data or execution operation. A successful call in the
owner's current ChatGPT connection does not prove another ChatGPT account or
process can install or use the plugin. Cross-account acceptance remains open.

## Current acceptance boundary

Historical TinyStories 15M CPU inferences through ChatGPT, Sites, D1, and the
now-retired local Runner produced provenance-checked results and retrievable
R2 artifacts. They establish that earlier CPU route only. They do not establish
current Modal inference, general model quality, or GPU execution. The latest
live capability read reports `provider_configured=true`,
`human_authorization_store_ready=true`, `available=true`, and
`admission_enabled=true`; readiness is checked during the normal submit path
after the exact plan is confirmed. Site Version 32 is active at environment
revision 34, and D1 includes the authorization and health-check tables. The
separate `experiment_provider_health` connector schema is still empty, but a
fresh submit calls the same authenticated Modal health endpoint internally.
The Modal digest remains unreconciled with the rebuilt local image, and no
post-deploy inference has been accepted. Use the ordinary prepare → exact
owner confirmation → submit flow; each authorization expires and is usable
once. The 30-second Sandbox ceiling is $0.01 and excludes separately billed
Modal control-function calls. The latest recorded exit-code-2 runs predate the
current Modal deployment; no result or artifact from a post-deploy test exists.

The former local Runner path is removed. Keep paid RunPod/GPU experiments
parked until their Sites route and security, result, recovery and cleanup gates
are accepted. The exact runtime keys and controlled publication steps are
in [`sites/gpu-control-sites/README.md`](../sites/gpu-control-sites/README.md);
current gates are in [`RELEASE_MATRIX.md`](RELEASE_MATRIX.md) and
[`STATUS.md`](STATUS.md).
The latest live-state evidence is recorded in
[`acceptance/2026-11-13-sites-modal-live-state-refresh.md`](acceptance/2026-11-13-sites-modal-live-state-refresh.md).

## Data and resource retirement

D1 is the selected control-plane database; PostgreSQL is not required for this
Sites product path. The Vercel `gpu-control` project has been deleted. The
legacy Neon project is soft-deleted and remains recoverable until
`2026-11-19T05:19:58Z`; verify that the recovery window expires and the project
is absent afterward. Neither service is a serving or rollback dependency.
Current retirement evidence is in
[`acceptance/2026-11-12-resource-retirement-inventory.md`](acceptance/2026-11-12-resource-retirement-inventory.md).
Keep historical evidence in the repository without recreating either runtime.
