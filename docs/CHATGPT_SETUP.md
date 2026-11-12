# ChatGPT Sites setup

## Supported architecture

The supported ChatGPT control plane is the owner-private Sites MCP Worker at
`https://gpu-control-sites.unjuno.chatgpt.site`. Sites supplies the hosted
Worker, ChatGPT sign-in boundary, MCP publication, and D1 binding. D1 stores
plans, run state, leases, and Runner heartbeats. Large immutable result files
are stored in R2; the Worker returns bounded chunks after owner/run and digest
verification. Eight complete result artifacts have been retrieved through
ChatGPT.

The Worker does not run Docker or model inference. A separate authenticated
Runner polls the Site and executes only the exact registered workload image.
It receives no caller-selected image, source, shell command, Docker option, or
provider credential. The current supported workload is free local CPU only;
GPU and paid execution remain parked.

The legacy FastAPI/PostgreSQL Gateway and its Vercel deployment are archived
references, not supported deployment choices. Do not configure new Vercel or
Neon resources for this product. Historical setup evidence is preserved in
[`archive/CHATGPT_SETUP-legacy-vercel-gateway.md`](archive/CHATGPT_SETUP-legacy-vercel-gateway.md)
and [`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).

## Connect and use the Site MCP

1. Open the private Site while signed in to the ChatGPT account that owns it.
2. Install or connect the Site's generated `gpu-control` plugin when ChatGPT
   offers the plugin card.
3. In a ChatGPT conversation, select or mention `gpu-control` and call
   `experiment_capabilities` before preparing a run.
4. Prepare only the advertised fixed workload, review its exact source and
   zero-cost limit, then submit. Poll `experiment_status` and retrieve the
   terminal value with `experiment_result`.

The Site and plugin are separate access controls. Keep the Site owner-private,
and retain server-side owner checks on every run, status, result, cancel, and
artifact operation. A Sites service-access credential authenticates the
Runner; it does not create a visitor identity or replace the Runner bearer
secret.

## Current acceptance boundary

The deployed version has completed a fixed-image checksum smoke and eight
provenance-valid TinyStories 15M CPU inferences through ChatGPT, Sites, D1, and
the Runner. The latest recheck, `1fdfe901fda14798a42e33e492edd538`, generated
four tokens in 155 ms, returned `gpu_used=false`, passed identity and sandbox
validation, and was retrieved through `experiment_result`; cleanup was
confirmed at `$0.00`. Three result artifacts have also been retrieved and
SHA-256 verified through ChatGPT. Two earlier outputs used a non-resolving
source SHA and are excluded from acceptance. These runs prove bounded inference
and artifact handling, not general model quality. Do not report GPU execution,
cross-account isolation, or live restart/cancellation recovery as accepted until
each has its own evidence.

Admission is limited to one in-flight CPU run and 30 seconds. Keep paid
providers parked. The exact runtime keys and controlled publication steps are
in [`sites/gpu-control-sites/README.md`](../sites/gpu-control-sites/README.md);
current gates are in [`RELEASE_MATRIX.md`](RELEASE_MATRIX.md) and
[`STATUS.md`](STATUS.md).

## Data and resource retirement

D1 is the selected control-plane database. PostgreSQL is not required for this
Sites product path. Vercel is not part of the current serving path and is not a
rollback dependency for Sites. The old Vercel deployment and Neon database are
legacy resources to inventory and retire; they must not receive new product
traffic or configuration. Before deleting Neon, classify its legacy auth and
run records and make a verified export or document that the data is disposable.
Retire the Vercel project after confirming no required DNS, GitHub, or user
workflow still points to it. Keep historical evidence in the repository, not
by treating a legacy service as an operational fallback.
