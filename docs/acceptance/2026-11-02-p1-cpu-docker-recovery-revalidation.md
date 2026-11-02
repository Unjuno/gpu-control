# P1 local CPU and recovery revalidation

Date: 2026-11-02 UTC

## Candidate and runtime identities

- Control-plane branch: `codex/pr58-cpu-vertical-reconcile-20261102`, local
  candidate based on PR #58 head `90bd6d8c84e319365d66951ca96c7ccceff40998`.
- Gateway test runtime: Python 3.12.13, Docker/OrbStack daemon.
- CPU workload image ID/digest: `sha256:c9c40c8886e7c54d3b3ca87b291b651de976af87c0d2d03cb9f5c01b0ca9795c`.
- Image labels: source `Unjuno/gpu-control`, revision
  `6a80ac2c820e93ea64fbc5fe2406e6838ad641fc`.
- Database: disposable PostgreSQL 16 image
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.

The image labels bind the operator-built fixture to a source identity; they are
not signed supply-chain attestations. No provider credentials or paid GPU
provider were used.

## Real-container integration checks

From `gateway/`, the following four tests ran with the exact image digest and a
fresh PostgreSQL database:

- `tests/test_local_backend_integration.py`: deterministic CPU result, source
  and plan binding, isolation settings, timeout supervisor, cleanup.
- `tests/test_local_lifecycle_integration.py`: worker process crash after
  container start, same-run recovery, cancellation and cleanup.
- `tests/test_local_mcp_integration.py`: authenticated local MCP HTTP path,
  prepare/submit/idempotency, Docker worker execution, result and exact artifact
  retrieval through a second HTTP client.
- `tests/test_postgres_lifecycle_integration.py`: PostgreSQL outage after real
  container terminal capture, retained run slot/container, PostgreSQL restart,
  same-run recovery, result/artifact persistence and cleanup.

The Postgres outage integration now provisions runtime roles and applies the
runtime-role policy/function after schema migration, matching the documented
deployment sequence. This test setup change was required after the first run
failed with `gpu_control_release_finished_slot(...) does not exist`; that
failure exposed that the previous test setup omitted deployment ACL setup.

Command result: **4 passed**, one existing Starlette deprecation warning,
11.52 seconds. The disposable test container was removed after the run.

After this test-harness change, the full Gateway suite was run with the same
PostgreSQL 16 image and CPU image digest, with the dedicated stoppable database
container configured for the outage test:

```sh
GATEWAY_TEST_DATABASE_URL='postgresql+psycopg://postgres:local-ci-only@127.0.0.1:55445/gateway_test' \
GPU_CONTROL_POSTGRES_CONTAINER='gpu-control-pr58-final-gateway-pg16' \
GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST='sha256:c9c40c8886e7c54d3b3ca87b291b651de976af87c0d2d03cb9f5c01b0ca9795c' \
GPU_CONTROL_CPU_SMOKE_SOURCE_SHA='6a80ac2c820e93ea64fbc5fe2406e6838ad641fc' \
  uv run --project . --no-sync python -m pytest -o addopts= -q
```

Result: **364 passed, 1 skipped**, one existing Starlette deprecation warning,
22.57 seconds. The single skip is an optional integration; Docker, PostgreSQL
role tests, and the real CPU outage/recovery test were enabled. The dedicated
PostgreSQL test container was removed after the run.

## Acceptance boundary

This establishes a real local CPU container and local recovery/MCP transport
path. The MCP integration uses test clients, not a ChatGPT account. It does not
establish deployed HTTPS/OAuth, hosted PostgreSQL grants, account/workspace
permission, seven-day operational stability, real GPU execution, or paid
execution. The admission policy remains disabled in the shipped configuration;
no production policy was enabled.
