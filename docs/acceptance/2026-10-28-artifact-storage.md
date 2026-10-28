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
- Re-ran both real Docker integration tests on the current working tree with
  `GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST` set to the digest above:
  `tests/test_local_backend_integration.py` and
  `tests/test_local_lifecycle_integration.py`: **2 passed**. The tests covered
  container restrictions, bounded CPU smoke and timeout behavior, process
  crash after container start, same-run reconciliation, byte-exact artifact
  retrieval, and cleanup. A follow-up `docker ps` found no remaining
  containers. This is local OrbStack evidence, not deployed-host acceptance.
- With a disposable PostgreSQL 16 container stopped after terminal capture,
  the worker retained the run/resource until database recovery, then read the
  persisted artifact back byte-for-byte and completed cleanup.
- Re-ran the full Gateway suite on the current working tree against a new
  loopback-only disposable PostgreSQL 16 container, with the digest-pinned CPU
  smoke image configured: **236 passed, 2 skipped** (optional Torch and Modal
  SDK), one Starlette deprecation warning. This included PostgreSQL parallel
  admission, cross-process state, worker lease fencing, v4-to-v6 migrations,
  the real local CPU container tests, and the PostgreSQL outage-after-capture
  recovery test. The dedicated PostgreSQL container was removed after the run.
- After adding a configurable artifact headroom floor enforced by both
  capabilities and prepare, re-ran the same PostgreSQL 16 + CPU image acceptance
  on the updated tree: **246 passed, 2 skipped** (optional Torch and Modal SDK),
  one Starlette deprecation warning. This includes the dedicated-filesystem
  check and below-threshold no-run regression. The disposable database was
  removed and `docker ps` was empty afterward.
- Repeated that full Gateway acceptance on the current checkout with a newly
  created PostgreSQL 16 container bound only to `127.0.0.1:55432`, the same
  immutable CPU smoke image ID, and the dedicated stop/restart integration
  setting: **246 passed, 2 skipped** (optional Torch and Modal SDK), one
  Starlette deprecation warning, in 18.24 seconds. The trap removed the
  disposable database container; a follow-up `docker ps -a` found no container
  with that test name. `yq` parsed the changed Gateway CI workflow and
  `git diff --check` passed. This verifies the local test path and workflow
  syntax, not a GitHub Actions run.
- Added a worker-side headroom recheck immediately before local CPU backend
  start. The regression proves low space prevents container creation, records
  `ARTIFACT_STORAGE_UNAVAILABLE`, and releases the queued admission slot. With
  the worker check present, the full Gateway suite passed **247 tests**, with 2
  optional skips (Torch and Modal) and one Starlette deprecation warning, in
  19.35 seconds on the exact current checkout. The real Docker crash-recovery and PostgreSQL outage/recovery
  tests were rerun and passed after provisioning their temporary artifact
  directories. These checks ran locally against the current worktree; GitHub
  Actions has not run this workflow revision.
- Exercised the CI image-build step itself with
  `docker build --file workloads/cpu-smoke/Dockerfile --tag
  gpu-control-cpu-smoke-ci workloads/cpu-smoke`; the generated image ID was
  `sha256:9b3a5ff76d08719992dab75f25c0df3bdd03f28fe4d045de97dc389b4b040111`
  (`linux/arm64` on OrbStack). Passing that freshly built ID and a disposable
  PostgreSQL 16 container into the full Gateway suite yielded **247 passed, 2
  skipped**, one Starlette deprecation warning, in 18.66 seconds. The container
  and temporary image tag were removed. This validates the workflow's build and
  integration-test steps locally; it does not validate GitHub's Ubuntu runner.
- Retention tests verify expired manifest deletion, 24-hour orphan grace,
  preservation of active-run blobs, and preservation of recent orphan files.
- An injected artifact-volume write failure after terminal capture now persists a
  failed result with `failure_code: artifact_persistence_failed`, publishes no
  artifact metadata, retains the slot while cleanup is interrupted, and lets a
  replacement worker finish cleanup. This was tested with an injected `OSError`
  and fake backend; it is not a real full-filesystem test.
- Tests include a 102,400-byte artifact fetched in verified chunks, private file
  mode, owner mismatch, unlisted ID, expiry, and protocol tool count/scope.

## Limits

- The real CPU smoke artifact is a bounded execution report, not a model
  checkpoint or scientific experiment output. GPU workloads and larger file
  artifacts have not been exercised end to end.
- No production volume quota or alert route is configured. The Linux systemd
  deployment templates now include a five-minute capacity check that requires
  the artifact path to be a distinct filesystem and logs low-space/probe errors
  to journald. `GATEWAY_ARTIFACT_MIN_FREE_BYTES` now feeds both capabilities and
  prepare, which also require a distinct filesystem and block admission below
  the reserve even if an alert consumer is unavailable. The filesystem's fixed
  size provides the hard ceiling; the
  monitor does not enforce it or deliver human notifications. Operators must
  configure the dedicated filesystem and host alert routing, then exercise a
  real quota-boundary write failure before enabling artifact-producing
  workloads.
- A real ChatGPT conversation and cross-conversation artifact retrieval have
  not been exercised. The shared-volume check used a disposable local Compose
  volume, not a deployed persistent host volume. Result retrieval remains
  UNCERTAIN until deployed API access and a second-conversation ChatGPT check
  prove the owner, source, plan, digest, and returned bytes together.
