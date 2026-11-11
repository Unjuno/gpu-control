# GPU Control Sites

Private ChatGPT MCP Site target for `Unjuno/gpu-control`.

## Current slice

- Cloudflare Worker exposes MCP `server/discover`, `tools/list`, and `tools/call` at `/mcp`.
- D1 (`DB`) stores owner-scoped plans, idempotency keys, run states, leases, and runner heartbeat.
- Only the fixed `cpu-smoke-v1` workload is represented. Paid providers remain parked and are not advertised as executable.
- The executor interface is a separate, authenticated polling API. The Site Worker never receives a Docker socket or executes user-provided code.
- `runner/run.py` is a separate Docker-capable polling process. It accepts only the registered image digest, verifies OCI source/revision labels and host architecture, applies the fixed no-network/read-only/non-root resource profile, validates the bounded smoke checksum, and confirms container removal before reporting success.
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

The private Site is published and MCP-ready, its D1 migration and runtime configuration are active, and the separate Linux/ARM64 Runner has written a live D1 heartbeat. A local Docker run of the fixed CPU image passed with the runner's isolation flags, checksum validation, and cleanup confirmation. These are not proof of a ChatGPT-originated run: the Site plugin call, persisted run/result retrieval, and owner-isolation acceptance remain unverified. Admission is still disabled, and paid execution stays parked.

The runner requires `GPU_CONTROL_SITE_URL`, `GPU_CONTROL_RUNNER_BEARER_TOKEN`, `GPU_CONTROL_SITES_SERVICE_TOKEN`, and the exact three `CPU_WORKLOAD_*` registration values. Store the Site service token and runner bearer token only in the runner host's secret store and the Sites runtime secret store where applicable. The runner sends both the Sites service authorization header and independent bearer token. It never logs response bodies or credentials. It does not accept code, image names, Docker options, or provider selection from tool callers.

The migration directory is append-only after publication. The initial schema creates only control-plane tables; it does not seed owners, credentials, or workload approvals.
