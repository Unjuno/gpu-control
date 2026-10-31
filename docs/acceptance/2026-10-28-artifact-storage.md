# Artifact storage and retrieval evidence — 2026-10-28

## Implemented

- Backend observations may carry artifact payloads into the worker. The worker
  enforces at most 10 objects and 1 MiB per object (10 MiB total maximum),
  rejects duplicate IDs, and generates metadata instead of trusting backend
  paths or URLs.
- Blobs are written atomically with mode 0600 under mode 0700 directories. Disk
  names derive from a hash of owner/run identity and artifact ID; client input
  is never interpreted as a path. Result metadata records SHA-256, size, media
  type and a 30-day expiry.
- The canonical MCP surface now has eight tools. `experiment_artifact` requires
  an owned run, an artifact ID already listed in its result, terminal run state,
  confirmed cleanup, and a bounded byte range. It verifies the complete stored
  blob against the result digest and returns a base64 chunk of at most 24 KiB.
- A caller with another owner receives the same not-found response as for an
  unknown run. Unlisted IDs are not readable. Expired artifacts return an
  explicit expiry error. No URL, filesystem path, or arbitrary storage key is
  accepted from the caller.
- API and worker deployments that produce artifacts must share a persistent
  `GATEWAY_ARTIFACT_DIR`. Artifact-free workloads do not require this setting.
- Worker and supervisor processes scan artifact manifests hourly. Expired
  manifest blobs are removed; unmanifested files are removed only after a
  24-hour grace period and never while their run is active. The cleanup is
  idempotent across worker/supervisor processes.
- The registered `cpu-smoke-v1` workload emits its canonical, identity-bound
  JSON report on stdout. After validating the complete report, the local CPU
  backend exposes those exact bytes as `cpu-smoke-result.json`; the worker
  stores the payload and publishes its digest and size in the terminal result.
  This uses the bounded log capture already retained for the run, so it does
  not depend on reading an ephemeral container filesystem after exit.

## Validation

- Artifact-store, API and protocol-adjacent tests: **29 passed**, one existing
  Starlette deprecation warning.
- `docker compose config -q` passed. Both API and worker images built; the
  disposable `artifact-init` service set the shared volume to UID/GID 10001,
  then the API container wrote a mode-0600 probe and the worker container read
  it and wrote a second probe successfully. The unique Compose project and its
  volumes were removed after this check.
- Final full Gateway suite with digest-pinned CPU image and disposable
  PostgreSQL 16: **214 passed, 2 skipped** (optional Torch and Modal SDK), one
  existing Starlette deprecation warning. This includes the final artifact
  metadata constraints and cleanup-state eligibility.
- A fresh digest-pinned Linux/arm64 CPU image completed through the real Docker
  backend. The process-crash recovery test adopted the already-started
  container, completed the same run, read the exact report bytes back from the
  owner-scoped artifact store, and confirmed container cleanup. Tested image:
  `sha256:92eefb29cdbe77b66f5381afba946c12e31f5bc4fd4d32e907fa5b0aa9548092`.
- With a disposable PostgreSQL 16 container stopped after terminal capture,
  the worker retained the run/resource until database recovery, then read the
  persisted artifact back byte-for-byte and completed cleanup.
- Retention tests verify expired manifest deletion, 24-hour orphan grace,
  preservation of active-run blobs, and preservation of recent orphan files.
- Tests include a 102,400-byte artifact fetched in verified chunks, private file
  mode, owner mismatch, unlisted ID, expiry, and protocol tool count/scope.

## Limits

- The real CPU smoke artifact is a bounded execution report, not a model
  checkpoint or scientific experiment output. GPU workloads and larger file
  artifacts have not been exercised end to end.
- Quota accounting and volume usage alerts are not implemented. Operators must
  set and monitor volume capacity before enabling artifact-producing workloads.
- A real ChatGPT conversation and cross-conversation artifact retrieval have
  not been exercised. The shared-volume check used a disposable local Compose
  volume, not a deployed persistent host volume. Result retrieval remains
  UNCERTAIN until deployed API access and a second-conversation ChatGPT check
  prove the owner, source, plan, digest, and returned bytes together.
