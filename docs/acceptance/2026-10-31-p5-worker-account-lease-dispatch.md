# P5 RunPod worker account-lease dispatch wiring — 2026-10-31

Status: **PASS for local Worker dispatch, PostgreSQL persistence/recovery, and
the current Gateway/Core test suites. Live RunPod and paid execution remain
unverified and disabled.**

## Change

The candidate-bound RunPod Worker path now derives an opaque account scope from
the configured provider credential and HMAC key, persists the exact provider
create challenge with the run submission intent and account lease, and passes
that persisted challenge to the adapter. Ambiguous create recovery calls only
the no-create reconciliation method. Provider handle identity is bound to the
lease before observation or cleanup. The Worker refuses RunPod paid and
credit-backed candidate plans with
`runpod_authorization_persistence_unavailable` before creating a lease or
calling the provider because durable signed-authorization persistence and
worker recovery are not integrated.

PostgreSQL validation exposed a cross-dialect defect in the new handle
recovery predicate: PostgreSQL's `json` type does not implement equality. The
Worker now detects both SQL `NULL` and JSON `null` by casting the JSON value to
text before comparison. This predicate is used in the normal submit and
recovery handle-persistence paths.

## Verification

- Focused Gateway API, account-lease, and registry tests: **62 passed** before
  the PostgreSQL predicate correction.
- PostgreSQL 16 local outage-recovery and real Docker worker-crash integration
  tests after the correction: **2 passed**. The outage test stopped and
  restarted the dedicated database, then recovered the same CPU run and
  artifact. The crash test recovered the same run after a worker process exited
  immediately after starting its Docker container.
- Full Gateway suite against the current dirty working tree, PostgreSQL 16 and
  commit-bound CPU smoke image `sha256:e82806277a195971ba3a0fc443650f47e4e15ddd913df6fb26a9ef7f07348922`:
  **524 passed, 2 skipped, 1 existing Starlette deprecation warning** in
  26.08 seconds. Only optional Torch and Modal SDK tests were skipped.
- Core suite: **559 passed, 1 skipped** in 0.94 seconds. The skip is the
  Python 3.11-only malformed RunPod log reproducer; this runtime is Python
  3.12.
- `git diff --check` passed after the change.

Full-suite command, from `gateway/`:

```sh
GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55499/postgres \
GPU_CONTROL_POSTGRES_CONTAINER=gpu-control-recheck-p5-pg-20261031 \
GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST=sha256:e82806277a195971ba3a0fc443650f47e4e15ddd913df6fb26a9ef7f07348922 \
GPU_CONTROL_CPU_SMOKE_SOURCE_SHA=a794438f42bd7246f463eaaa40d963af0aae9d13 \
GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY=Unjuno/gpu-control \
./.venv/bin/python -m pytest -o addopts= -q -rs tests
```

Core command, from the repository root:

```sh
./.venv/bin/python -m pytest -o addopts= -q -rs
```

Source hashes at verification:

- `gateway/gpu_gateway/worker.py`:
  `2871edd73a64136eb5c7cf35ac48d5b74703da52f3e90cda353ae661c9e20a9a`
- `gateway/tests/test_experiment_api.py`:
  `7bfddf96391852045e7922194509fc4ba91712979b842e04fca4d3f7a880d6c7`
- `gateway/tests/test_provider_account_leases.py`:
  `f8787ae8934d84157e3c259bd08480c335751af92575b9509e252e2450c0d849`
- `gateway/tests/test_postgres_lifecycle_integration.py`:
  `94ae8b1838cdd99c80f87a68d6e25a5c1ea8c18d8231a49699e1392dcf6a8bf0`

## Limits

RunPod dispatch and recovery were exercised only with fake adapters. The
PostgreSQL/Docker integrations exercised the local CPU backend. No RunPod API,
provider account, GPU allocation, billing, target host, production database,
ChatGPT Workspace, or deployed MCP connection was used. The RunPod adapter
contract still has no accepted production implementation; signed paid/credit
authorization remains deliberately blocked. Keep P5.3a unchecked,
`policies/repository-state.yaml` at `mode: parked`, and all spending gates
closed.
