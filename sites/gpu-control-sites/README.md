# GPU Control Sites

Public ChatGPT MCP Site source for `Unjuno/gpu-control`.

## Source and release status — 2026-11-28

This file's older hosted-state notes below are historical snapshots and must
not be used as the current Site or provider status. The current source candidate
is PR #70 branch `codex/owner-training-workloads`; it is open and
blocked on required review. That candidate has an owner-selected GitHub source
to Modal GPU implementation, while `policies/repository-state.yaml` keeps
admission disabled and the repository parked. It has not been established here
that the candidate is merged, deployed, migrated in hosted D1, or accepted by a
fresh ChatGPT run.

Read [the repository architecture map](../../docs/architecture/repository-map.md)
for source ownership and state authority, and
[the refactoring backlog](../../docs/architecture/refactoring-backlog.md) for
the product and architecture acceptance sequence.

## Current hosted state

- Live URL: <https://gpu-control-sites.unjuno.chatgpt.site>.
- Site Version 34 is live from source commit
  `18339d5106ff148d0ec4b3acf8da64791b69d54f`; its published environment
  revision is 39 and deployment `appgdep_6af8a25b69b08191a7d67795a7b571ac`
  succeeded. Platform access is public, with an owner account ID allowlist
  enforced for MCP operations. Cross-account denial and trusted provenance of
  the platform-injected identity are not independently verified.
- State and artifacts use Sites D1/R2 bindings `DB` and `BUCKET`. ChatGPT
  capability and experiment-list calls succeeded from the connected owner
  account. Modal is configured and authorization storage is ready.
  `CPU_WORKLOAD_ADMISSION_ENABLED=true` in environment revision 39. The
  corrected Modal endpoint is deployed, but provider health and post-correction
  inference have not yet been verified.
- Only `tiny-stories-inference-v1` is exposed: maximum 30 seconds, one
  in-flight run, estimated Sandbox cost `$0.0013`, and a declared `$0.01`
  per-run Sandbox CPU/memory ceiling. The currently deployed Sandbox had CPU
  and memory limits displayed as `None`; its `cpu=1` and `memory=512` values
  were requests, so bursting could exceed that declared dollar ceiling. Current
  candidate source now sets request=limit to 1 physical CPU core and 512 MiB,
  fingerprints both limits, and documents CPU throttling and memory OOM failure.
  Current Site environment revision 39 registers fingerprint
  `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5` and image
  digest `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  Modal control-function charges remain outside the per-run Sandbox ceiling. A
  one-use confirmation is required for each exact plan.
- The five most recent Modal-origin runs failed with `MODAL_WORKLOAD_EXIT_2`
  or `MODAL_WORKLOAD_FAILED`; each reports cleanup confirmed and has no result
  artifact. The newest inspected sandbox failed after 247 ms on November 12,
  before the November 14 Modal API deployment, and had no logs. A local
  OrbStack reference-container smoke passed with the fixed bootstrap, but a
  successful inference on the current Modal deployment is not yet accepted.
  Earlier successful records used the retired local Runner and are not Modal
  acceptance.
- The Modal `main` app was redeployed from PR #68 candidate
  `3eb2ab5d218b06c2559fd22088e1a4763fc78521`; the deployment completed
  successfully without starting a Sandbox. The control function currently has
  zero live containers and zero running calls. Its displayed limits are 1 CPU
  request with default CPU limit, 512 MiB memory request with no memory limit,
  and a 60-second timeout. These control-function settings and charges are
  separate from the hard-limited Sandbox workload.
- Account-specific usage and balance details are intentionally omitted from
  this public repository. Check current provider limits before execution. The
  Workspace API-token list shows zero active tokens after the temporary deploy
  token was revoked. The user's `$1`
  testing authorization is aggregate, not per run. Control-function charges
  count toward the Workspace limit but are not included in the Sandbox
  estimate. Keep the Workspace hard limit in place.
- The current owner prepared a fresh exact CPU plan, but its confirmation page
  required a ChatGPT sign-in in the browser. No health call or Sandbox request
  was issued from that plan; the five-minute plan expired before owner
  confirmation. CPU admission is enabled under the Workspace `$1` cap and
  exact-plan, one-use confirmation. Sign into the Site, then prepare and confirm
  a fresh plan before any provider call.
- The former macOS Runner, its Worker routes, and its bearer secret are retired.
  RunPod is not connected to the Site Worker; GPU and paid execution remain
  parked. Vercel and Neon/PostgreSQL are not target runtime dependencies.
- See [current Site acceptance](../../docs/acceptance/2026-11-13-sites-v33-live-refresh.md),
  [Modal deployment acceptance](../../docs/acceptance/2026-11-13-modal-main-deploy.md),
  and [latest Modal local smoke and live gate](../../docs/acceptance/2026-11-14-modal-local-smoke-and-live-gate.md).

## ChatGPT-native approval candidate

PR #68 now includes a candidate flow that returns the exact plan fields to the
ChatGPT conversation and requires approval of the destructive `experiment_submit`
MCP action. Its confirmation request carries the reviewed fields. The Worker
binds them to the authenticated Site owner, stored plan fingerprint, image digest, expiry, and one-use D1
authorization. This removes the separate browser sign-in from the intended
ChatGPT workflow while keeping the Site public and MCP execution owner-scoped.
This candidate is not live: Site Version 34 still uses the browser confirmation
page. Verify how ChatGPT renders the exact tool arguments before approval, the
platform identity source, cross-account denial, migration, and end-to-end
cleanup before publishing.

## Target execution architecture

The Site remains the only ChatGPT-facing product and control plane. The compute
providers are exactly Modal, RunPod, Kaggle, and Hugging Face. Each stays behind
separate authorization, pricing or free-quota, availability, result-integrity,
and cleanup gates. D1/R2 lifecycle data is authoritative.

### Modal provider adapter (staged, disabled by default)

The source includes a fail-closed Sites-to-Modal-adapter transport for the
Kaggle/Hugging Face extension. It is not enabled merely by publishing this
Site. D1 must be migrated through `0016_provider_adapter_state.sql`. Configure
the Site only with `PROVIDER_ADAPTER_URL` (the authenticated Modal HTTPS
origin), `PROVIDER_ADAPTER_KEY_ID`, and secret
`PROVIDER_ADAPTER_HMAC_KEY_B64`, plus the adapter-specific Modal proxy token
pair. Legacy `GATEWAY_*` configuration is rejected.
Railway, Neon, Vercel, PostgreSQL, and a separately hosted Gateway are not part
of this execution path.

Every delegated request binds the authenticated Sites owner, canonical tool
name, exact arguments, a 60-second validity window, and a random nonce. The
adapter rejects replay before dispatch. Transport authentication alone is
deliberately insufficient for `experiment_submit`. Sites stores the exact
owner-bound provider plan and opaque provider handle in D1, creates one
short-lived ChatGPT write authorization, and binds it to the run before the
provider can queue work. Transport retries reuse that same authorization and
cannot bind it to another run. Do not advertise live Kaggle/Hugging Face before
deployment, quota checks, private artifact/Space checks, and end-to-end
recovery acceptance are complete.

```text
ChatGPT -> Sites MCP Worker -> owner-scoped D1/R2
                    -> exact-plan ChatGPT write approval -> one-use D1 authorization
                                    -> authenticated Modal CPU function
                                    -> fixed Modal T4 canary function
                                    -> RunPod REST v2 after paid gates pass
                                    -> signed/replay-safe Modal provider adapter
                                       -> Kaggle training -> private HF artifact
                                       -> private ZeroGPU evaluation
```

### Modal GPU candidate

The candidate source registers `modal-gpu-vector-add-v1` as a fifth execution
route across the four target services. It is not a generic GPU shell: the
separately deployed Modal app embeds one reviewed CUDA vector-add kernel, fixes
the GPU to one T4, blocks networking, attaches no secrets, uses single-use
containers, pins the amd64 Debian base manifest, binds a deterministic build
digest into the plan/result, and has a 30-second timeout. Sites prepares an
owner-bound exact plan, requires ChatGPT write confirmation, binds a maximum
one-hour Workspace usage/charge/limit/T4-price evidence record, reserves
`$0.01` in a separate Modal-GPU ledger with a `$1` monthly project ceiling, and
holds one workspace lease through provider-confirmed terminal cleanup. Admission
stays closed unless `MODAL_GPU_WORKLOAD_ADMISSION_ENABLED=true`. The Modal
Workspace hard limit remains the independent outer stop.

Offline Worker, adapter, GPU-backend, canary, packaging, migration, and artifact
tests pass for this candidate. This is not live acceptance: Modal currently
requires a payment method before the T4 app can be deployed, and no GPU call is
authorized merely by publishing the Site.

The browser confirmation page remains as a fallback. The new ChatGPT path must
not infer approval from a prompt or plan preparation alone; the submit tool is
marked destructive and the tool call contains the exact plan fields shown to
the user for confirmation.

No caller may choose arbitrary code, an image, a command, a provider URL, a
secret, or an owner ID. Provider call IDs and results must be bound to the
persisted run, plan fingerprint, and registered workload before they can change
run state or become retrievable artifacts.

## Retired local Runner

The former macOS LaunchAgent was unloaded, its local runtime was removed, and
its two Keychain credentials were deleted. Do not restore or use that path, ask
for a macOS password, or enable `RUNNER_BEARER_TOKEN` for a local poller. The
legacy `/runner/*` Worker routes and the obsolete Site secret are removed from
the current Site source/runtime. Historical run and artifact records remain
untouched.

## Source layout

- `worker/index.js`: ChatGPT MCP Worker and D1/R2 control-plane logic.
- `drizzle/`: append-only D1 schema migrations.
- `modal/`: authenticated, fixed-purpose Modal control API. Its Sandbox can
  start only the pinned CPU workload and has outbound networking blocked.
- `workloads/tiny_stories_inference/`: pinned workload and container recipe.
  Provider-specific packaging must verify the source and model digests before
  use.
- `workloads/third_party/llama2.c/`: the pinned upstream C inference source
  and its license.
- `../../workloads/runpod-gpu-canary/`: fixed RunPod Serverless GPU worker.
  It accepts only an owner-approved execution binding, returns HMAC-bound
  evidence, and relies on RunPod's per-job timeout and scale-to-zero lifecycle.
- `scripts/`: deterministic Worker build and artifact validation.

## Verification and acceptance

Past end-to-end CPU runs through the local Runner are historical evidence only.
Their exact inputs, outputs, checksums, and cleanup observations are retained
under `docs/acceptance/`. Current provider readiness must be established through
the ChatGPT Site itself. The staged plan and acceptance criteria are in
[`../../docs/SITES_MODAL_RUNPOD_DELIVERY.md`](../../docs/SITES_MODAL_RUNPOD_DELIVERY.md).

The migration directory is append-only after publication. Do not erase D1/R2
records or rewrite historical acceptance evidence during provider migration.

## MAP-44M training

The training tools are scoped to the authenticated Sites owner. Register the
reviewed `unjuno/model-as-a-paper` GitHub commit with `training_register`.
Omitting optional training settings selects `papers`, `map44m`, and a maximum
of 100,000 steps; `dataset`, `run_name`, and `steps` may be set on registration.
The execution entrypoint, L4 GPU, image, corpus/checkpoint Volumes, and Modal
credentials remain selected by the server. No shell command or image can be
provided through MCP. Use `training_prepare` by repository and commit (or
registration ID plus execution-spec ID), with runtime seconds and a budget in
millionths of a US dollar. Use a fresh idempotency key per intended execution.
The returned plan binds source, image, GPU, dataset, run name, step ceiling,
runtime, and cost ceiling before `training_submit` accepts its exact
`approved_plan`, run ID, and fingerprint. `training_submit` is the single
billable write action. Before it can dispatch, the authenticated owner confirms
that exact plan once at the `authorization_url` returned by `training_prepare`.
The Site records short-lived evidence bound to the owner, plan, control-plane
SHA, source, image, Modal function, runtime, and budget, then consumes it with
the one-use dispatch reservation. This confirmation is distinct from MCP
login: do not ask the user to reconnect ChatGPT Sites or sign in to Modal for
each run.

Use `training_status` to recover a submitted run, including after an
ambiguous submit. Avoid creating a new plan to retry an uncertain run.
`training_cancel` cancels a prepared plan or requests stopping the Modal
call. Poll status after requesting cancellation. A succeeded result contains
the checkpoint size and SHA-256. `training_checkpoint` reads bounded
base64 ranges for an authenticated client to reconstruct and verify; a typical
model checkpoint is too large to copy through a chat transcript.

## Owner-selected GitHub source (PR #70 source candidate)

For a custom repository, the owner connects the GitHub App once with
`github_connection_start`, selecting only repositories GPU Control may read.
The App's only repository permissions are Contents read and Metadata read.
`github_repositories` lists the selected repositories; `training_register`
accepts the repository name and pins its current default-branch commit. The
server creates the registration ID. `training_inspect` reads the manifest and
lockfile at that immutable commit with a short-lived token scoped to that one
repository. Tokens are never returned to MCP or passed to training code.

The source candidate continues through manifest inspection, preview, expiring
plan preparation, exact ChatGPT MCP write confirmation, owner/monthly and
per-run reservation, authenticated Modal adapter dispatch, trusted source
staging, isolated GPU execution, bounded result retrieval and cleanup evidence.
The source manifest contract is `.gpu-control/experiment.json`; the workload
does not provide a Dockerfile or arbitrary shell command. The owner-selected
custom-code route implemented by this candidate is Modal-only. Fixed RunPod,
Kaggle and Hugging Face workloads remain distinct and do not imply support for
arbitrary repositories on those providers.

This is candidate source, not a live capability. The code may report
`CUSTOM_TRAINING_RUNTIME_NOT_CONNECTED` when runtime image/quote settings are
absent; `OWNER_TRAINING_ADMISSION_ENABLED` is a separate gate. Keep admission
off while repository mode is parked. Release requires exact-head review and
CI, required D1 migrations, verified runtime/account limits and a fresh
owner-authorized ChatGPT GPU lifecycle with result and cleanup evidence.

For deployment, build the reviewed MAP source with
`workloads/map-training/build.sh` and provision the private corpus and
checkpoint Volumes referenced by `modal/map_training_app.py`. The selected
corpus must be available as a direct child of `/corpus` (the default is
`/corpus/papers`). The app and signed adapter need
the same `MAP_TRAINING_SOURCE_SHA`, `MAP_TRAINING_IMAGE_DIGEST`,
`MAP_TRAINING_RUNTIME_SECONDS`, `MAP_TRAINING_HOURLY_MICROUSD` and
`MAP_TRAINING_QUOTE_EXPIRES_AT` as Sites. Set
`MAP_TRAINING_CONTROL_PLANE_SHA` to the exact Sites source commit in both Sites
and the signed Modal adapter; it is required to bind the one-use authorization
to the running control-plane revision. Apply D1 migrations before updating
the Worker. Set the checked pricing configuration to expire within 30 days.
For a privately built Modal image, set `MAP_TRAINING_MODAL_IMAGE_ID` to the
immutable `im-…` ID in all three components instead of setting a GHCR digest.
The existing MCP field `image_digest` carries that ID in this mode.
Each prepared plan still expires within 10 minutes. Keep admission disabled until the image, dataset, workspace
billing limit, and exact execution authorization have been verified.
Sites requires `MAP_TRAINING_MONTHLY_MICROUSD`; its ledger reserves the full
per-run ceiling and is independent of Modal billing.
