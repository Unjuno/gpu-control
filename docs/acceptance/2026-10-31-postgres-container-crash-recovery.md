# PostgreSQL worker crash after container start — 2026-10-31

Status: **PASS for local synthetic PostgreSQL + Docker recovery; target-host acceptance NOT RUN**.

## Scope

This integration closes one recovery window: a real execution worker exits after
Docker has started the CPU container but before the worker can persist the
returned container handle. A new recovery supervisor must find and adopt that
same run's container from the durable PostgreSQL submission intent, finish the
run, retrieve its result, clean up the resource, and release the admission slot.

## Environment and checks

- Disposable PostgreSQL 16 container using the Gateway CI image digest
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
- Local Docker/OrbStack daemon and CPU smoke image digest
  `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`.
- The crash test and existing PostgreSQL outage-after-capture integration
  passed together: **2 passed**.
- The latest full Gateway suite on the current local source, after the child
  process stopped receiving the database URL in argv, passed **427 tests with
  2 skips** against the pinned PostgreSQL 16 and CPU smoke images. The skips
  were optional PyTorch bridge and Modal backend. One existing Starlette
  deprecation warning was reported.
- Recovery assertions require the same run ID and source SHA, exactly one
  matching run-labelled container, `simulation=false`, `gpu_used=false`, exact
  artifact bytes, completed cleanup, no remaining container, and
  `active_count=0`.
- The disposable PostgreSQL container was removed after validation. No
  provider, production database, paid resource, or selected deployment host was
  used.

## Limits

This is local synthetic evidence on macOS/OrbStack with a real local Docker
container and PostgreSQL. It does not establish selected Linux host behavior,
second-operator reproducibility, production backup retention, worker-host loss
reconciliation, measured RPO/RTO, seven-day stability, or ChatGPT-originated
recovery and retrieval. P2/P3 operational acceptance remains open.

## Current-worktree exact-image rerun — 2026-10-31 03:41 JST

Re-ran the crash-after-Docker-start recovery test against the current source
at HEAD `a794438f42bd7246f463eaaa40d963af0aae9d13` using the current local CPU
image `sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b`
(`linux/arm64`) and a disposable PostgreSQL 16 container pinned to
`sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
Command from `gateway/`:

```sh
.venv/bin/python -m pytest -o addopts= -q tests/test_postgres_lifecycle_integration.py::test_postgres_worker_crash_after_docker_start_recovers_same_run
```

Result: **1 passed**, one existing Starlette deprecation warning. The test
observed the worker exit after real container start but before handle
persistence, then verified the supervisor recovered that same run, returned
the exact result artifact, recorded cleanup complete, removed the run-labelled
container, and released the slot (`active_count=0`). The DB was published only
on `127.0.0.1:55473`; the uniquely named DB container was removed and that port
had no listener afterward.

Current tested file SHA-256 values:

- `gateway/tests/test_postgres_lifecycle_integration.py`:
  `94ae8b1838cdd99c80f87a68d6e25a5c1ea8c18d8231a49699e1392dcf6a8bf0`
- `gateway/gpu_gateway/worker.py`:
  `139b040905f63a7a2767c34658b4679d1f23ee90113559b861261273f955f847`
- `gateway/gpu_gateway/local_backend.py`:
  `3617efda53ff0437f9f6df8e1484b7fa5b2a276b2cec6fd49e51f5a8ca962b8c`
- `gateway/gpu_gateway/store.py`:
  `74de25e8e4fb350bbd9918d1e502fe0d8b56acaab7d7a3cdbf50697cc09b0b66`

This is current-source local macOS/OrbStack acceptance only. It does not
verify recovery on a selected Linux host, after host loss, across ChatGPT
conversations, or against a real external provider.

## PR #51-base review candidate replay — 2026-10-31

Applied the current crash-recovery test/documentation overlay to a detached
worktree at PR #51 pushed head `aa681f4062dac6b73bcf380a38a4258b96a47e1`.
The two candidate files match the current worktree byte-for-byte. Patch:
`/tmp/gpu-control-p2-worker-crash-review.patch`, SHA-256
`0a6f5f4c84e7ca92ea4e416dfcf5a801f015378cf3b81fd0de1001598f299b60`.

With a disposable, digest-pinned PostgreSQL 16 container bound to
`127.0.0.1:55476` and the current local CPU image
`sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b`,
the candidate-source crash-after-Docker-start test passed **1/1**. It verified
same-run adoption, exact result artifact, cleanup, and released admission
slot. The DB container was removed and the port closed. This is local
candidate evidence only, not GitHub CI, target-host recovery, or ChatGPT
acceptance.

## P1+P2 cumulative candidate on exact PR #58 base — 2026-10-31 11:47 JST

- Rebuilt a detached candidate at `/tmp/gpu-control-p1p2candidate-on-561a6c7`
  on exact base `561a6c7ac697dfdf22f304b60e313fccb2c806a4`, applying the P1
  readiness patch (`853b4a7177318bcee87b1608b592ad54229bac6974accebeac8355cad5cc27c4`)
  followed by the P2 recovery patch
  (`67fb68d464202d3a1be905873712b4f73d6fa8155aa330589c99eea5d3c17850`). Both
  passed `git apply --check` and the combined tree passed `git diff --check`.
- Built the CPU smoke image from this candidate's workload Dockerfile using
  its pinned Python base. Image ID:
  `sha256:089c7ce625464b183cf5dcbe2431708a6c5e94e009042b58f365928e0ad1e2fc`;
  its OCI source label was `Unjuno/gpu-control` with synthetic fixture source
  SHA `cccccccccccccccccccccccccccccccccccccccc`. This is local test identity,
  not a claim of a published source revision.
- Ran the candidate's complete Gateway suite using PostgreSQL 16 image
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  bound only to `127.0.0.1:55499`, and the candidate-local source imports.
  Result: **430 passed, 2 skipped**, one existing Starlette deprecation
  warning, in 24.80 seconds. Skips were optional Torch and Modal dependencies.
  The P2 crash-after-container-start recovery test also passed individually
  (**1 passed**) on the same candidate.
- Removed the disposable database container and CPU smoke image; port 55499
  was confirmed closed. No provider, GPU, or paid resource was used. This is
  local P1+P2 evidence only; GitHub CI/review, target-host recovery, production
  readiness, and ChatGPT run/result acceptance remain open. Keep `parked`.
