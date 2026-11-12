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
has been retired. The fixed Modal CPU adapter is deployed; the latest recorded
ChatGPT capability read passed all provider checks, while admission remained
disabled. No successful inference against the current Modal deployment has
been accepted through ChatGPT. RunPod GPU execution remains a separately gated
future path; paid execution is parked.

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
   `experiment_capabilities` before preparing a run.
4. Prepare only the advertised fixed workload and review its exact source,
   usage estimate, and `$0.01` Sandbox-only ceiling. Modal control-function
   calls are billed separately. Credits are not a zero-cost guarantee. Submit
   only with explicit authorization for the exact prepared plan. Poll
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
live capability read reports `provider_ready=true`, `admission_enabled=false`,
and `available=false` with blocker `CPU_WORKLOAD_ADMISSION_DISABLED`. The
currently exposed ChatGPT `experiment_prepare` schema constrains
`max_cost_usd` to `0.00`, while the Worker requires `0.01`; resolve and verify
that published tool-schema mismatch before preparing a new run. A fresh
ChatGPT inference and artifact verification against the current Modal deployment
are still required.

The former local Runner path is removed and provider admission remains closed.
Keep paid providers parked. The exact runtime keys and controlled publication steps are
in [`sites/gpu-control-sites/README.md`](../sites/gpu-control-sites/README.md);
current gates are in [`RELEASE_MATRIX.md`](RELEASE_MATRIX.md) and
[`STATUS.md`](STATUS.md).

## Data and resource retirement

D1 is the selected control-plane database; PostgreSQL is not required for this
Sites product path. The Vercel `gpu-control` project has been deleted. The
legacy Neon project is soft-deleted and remains recoverable until
`2026-11-19T05:19:58Z`; verify that the recovery window expires and the project
is absent afterward. Neither service is a serving or rollback dependency.
Current retirement evidence is in
[`acceptance/2026-11-12-resource-retirement-inventory.md`](acceptance/2026-11-12-resource-retirement-inventory.md).
Keep historical evidence in the repository without recreating either runtime.
