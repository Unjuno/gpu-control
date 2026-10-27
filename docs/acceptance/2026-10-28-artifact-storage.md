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

## Validation

- Artifact-store, API and protocol-adjacent tests: **29 passed**, one existing
  Starlette deprecation warning.
- `docker compose config -q` passed. Both API and worker images built; the
  disposable `artifact-init` service set the shared volume to UID/GID 10001,
  then the API container wrote a mode-0600 probe and the worker container read
  it and wrote a second probe successfully. The unique Compose project and its
  volumes were removed after this check.
- Final full Gateway suite with digest-pinned CPU image and disposable
  PostgreSQL 16: **209 passed, 2 skipped** (optional Torch and Modal SDK), one
  existing Starlette deprecation warning. This includes the final artifact
  metadata constraints and cleanup-state eligibility.
- Retention tests verify expired manifest deletion, 24-hour orphan grace,
  preservation of active-run blobs, and preservation of recent orphan files.
- Tests include a 102,400-byte artifact fetched in verified chunks, private file
  mode, owner mismatch, unlisted ID, expiry, and protocol tool count/scope.

## Limits

- No current registered production workload emits artifact payloads. Storage and
  retrieval were exercised with synthetic payloads, not a real experiment
  artifact.
- Quota accounting and volume usage alerts are not implemented. Operators must
  set and monitor volume capacity before enabling artifact-producing workloads.
- A real ChatGPT conversation and cross-conversation artifact retrieval have
  not been exercised. The shared-volume check used a disposable local Compose
  volume, not a deployed persistent host volume or a real artifact-producing
  workload.
