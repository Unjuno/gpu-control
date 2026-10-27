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

## Validation

- Artifact-store, API and protocol-adjacent tests: **29 passed**, one existing
  Starlette deprecation warning.
- `docker compose config -q` accepted the updated shared-volume configuration;
  the compose services themselves were not deployed or run for artifact IO.
- Final full Gateway suite with digest-pinned CPU image and disposable
  PostgreSQL 16: **208 passed, 2 skipped** (optional Torch and Modal SDK), one
  existing Starlette deprecation warning. This includes the final artifact
  metadata constraints and cleanup-state eligibility.
- Tests include a 102,400-byte artifact fetched in verified chunks, private file
  mode, owner mismatch, unlisted ID, expiry, and protocol tool count/scope.

## Limits

- No current registered production workload emits artifact payloads. Storage and
  retrieval were exercised with synthetic payloads, not a real experiment
  artifact.
- Expiry is enforced at retrieval, but automated blob deletion/quota accounting
  is not implemented. Operators must plan volume cleanup; artifact-producing
  workloads should not be enabled for long-term operation until retention is
  automated and tested.
- A real ChatGPT conversation, cross-conversation artifact retrieval, and shared
  persistent API/worker volume have not been exercised.
