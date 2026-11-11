# GPU Control Sites

Private ChatGPT MCP Site target for `Unjuno/gpu-control`.

The owner-private Site now publishes the fixed TinyStories CPU inference
workload. ChatGPT has completed four provenance-valid end-to-end inferences,
retrieved their persisted results, and confirmed container cleanup. Two R2
result artifacts (988 and 991 bytes) were also retrieved and verified through
ChatGPT. Two earlier outputs with a non-resolving source SHA are excluded from
acceptance. This is a
narrow acceptance slice; recovery, cross-owner isolation, artifact retention and
orphan cleanup, GPU execution, and paid execution remain open or parked.

## Current slice

- Cloudflare Worker exposes MCP `server/discover`, `tools/list`, and `tools/call` at `/mcp`.
- D1 (`DB`) stores owner-scoped plans, idempotency keys, run states, leases, and runner heartbeat.
- The Worker defines only the fixed `tiny-stories-inference-v1` workload. It runs the MIT-licensed, pretrained `karpathy/tinyllamas` 15M checkpoint pinned by Hugging Face revision and SHA-256. Paid providers remain parked and are not advertised as executable.
- The executor interface is a separate, authenticated polling API. The Site Worker never receives a Docker socket or executes user-provided code.
- `runner/run.py` is a separate Docker-capable polling process. It accepts only the registered image digest, verifies OCI source/revision labels and host architecture, applies the fixed no-network/read-only/non-root resource profile, validates model/prompt/output identity and the result checksum, and confirms container removal before reporting success.
- The runner checks expired leases. It removes only containers whose run, plan, source, and image labels match, verifies absence, then asks the Worker to terminalize the interrupted run as failed. Recovery does not auto-retry work.
- Results are bounded and validated against run, plan, source, workload, parameter, and checksum identity before becoming terminal.

## Required runtime configuration

`CPU_WORKLOAD_ADMISSION_ENABLED` defaults to disabled and gates capability readiness and submission. `experiment_prepare` does not execute compute but can write a bounded plan to D1 when the database is configured. Set execution admission only after reviewing the exact immutable image and source registration:

- `CPU_WORKLOAD_ADMISSION_ENABLED=true`
- `CPU_WORKLOAD_REPOSITORY=owner/repo`
- `CPU_WORKLOAD_SOURCE_SHA=<40 lowercase hex characters>`
- `CPU_WORKLOAD_IMAGE_DIGEST=sha256:<64 lowercase hex characters>`
- `RUNNER_BEARER_TOKEN=<random high-entropy secret>`
- The runner must also use the Site's existing service-access credential in `OAI-Sites-Authorization`; it supplies no visitor identity, so `RUNNER_BEARER_TOKEN` remains independently required. Keep both credentials outside source and never log them.

`RUNNER_BEARER_TOKEN` must be held by the runner and Sites runtime secret storage only. Never add it to Git, the Site manifest, tool arguments, logs, or artifacts. The authenticated Site user ID is the sole owner key; callers cannot provide an owner ID.
The Worker lease is a fixed 180 seconds, exceeding the runner's bounded Docker setup, execution, cleanup and result-submission timeouts.

## Current verification boundary

On 2026-11-12, ChatGPT run `d17dcc650783466088bacb734826bcdb` used source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`, prompt `Once upon a time`, seed `61112`, and a maximum of 24 tokens. It generated the TinyStories result in 430 ms, passed registered identity/checksum checks, reported `gpu_used=false`, persisted the result in D1, and confirmed cleanup. Paid execution stays parked.

A second run, `6175c7a710e4424bb30f595d019d3eb7`, used the same registered source and image with seed `61113` and a 16-token limit. It completed in 313 ms, passed the same identity/checksum checks, returned checksum `3d67d5c215c128d7bf8a556e532cdfd867542e2056c9977d66b3275989fdcdd5`, reported `gpu_used=false`, was retrieved through the ChatGPT result tool, and confirmed cleanup. Its cost ceiling was `$0.00`. A request using the Sites source repository's own commit instead of the separately registered workload source was safely rejected before execution.

After adding the Sites R2 `BUCKET` binding and D1 artifact-reference migration,
run `f6503635680e4e4f9bbd6f371bb6d92a` completed with seed `61114` and a
12-token limit in 249 ms. ChatGPT retrieved the 988-byte `result.json` artifact
as a complete chunk. The Worker verified its owner/run binding and SHA-256
(`f742e6def8597958fbb3b62b37202ab2890b30c028422313a02933a35cdbb898`) before
returning the bytes. The result passed source, model, parameter and checksum
checks, reported `gpu_used=false`, and confirmed cleanup at a `$0.00` ceiling.
Artifact retention and cleanup remain open.

The runner requires `GPU_CONTROL_SITE_URL`, `GPU_CONTROL_RUNNER_BEARER_TOKEN`, `GPU_CONTROL_SITES_SERVICE_TOKEN`, and the exact three `CPU_WORKLOAD_*` registration values. Store the Site service token and runner bearer token only in the runner host's secret store and the Sites runtime secret store where applicable. The runner sends both the Sites service authorization header and independent bearer token. It never logs response bodies or credentials. It does not accept code, image names, Docker options, or provider selection from tool callers.

The migration directory is append-only after publication. The initial schema creates only control-plane tables; it does not seed owners, credentials, or workload approvals.
