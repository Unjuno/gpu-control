# P1 DCR persistence stack rebase — 2026-10-31

## Scope

- Validated source head before this evidence-only update:
  `e7918adcfee86036ce4e68ceceeecf9e32670be0`.
- Updated base: PR #51 head `3ad3797a2ace96ab0330317a303376e8af75fb21`.
- DCR feature commit replayed as `64facc8`; the stack retains the PR #57
  atomic refresh/revocation fix and the rebased P1–P5 continuation.
- The PR-specific diff is eight files covering OAuth client persistence,
  schema migration, PostgreSQL tests, and acceptance records.

## Validation

Gateway suite used a dedicated local PostgreSQL 16 database, the CPU smoke
container, and disabled Modal/RunPod integrations:

```text
GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://.../gateway_p58_rebased_full_test
GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST=sha256:07da90a98f66cca25c1afe3208cde7928012f6bdf1fdee9d5e9939c50cf7d32f
GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY=Unjuno/gpu-control
GPU_CONTROL_CPU_SMOKE_SOURCE_SHA=d5a30985d8f2df0e7221476f47f1dfecff2faedb
python -m pytest -o addopts='' gateway/tests -q
```

Result: **433 passed, 3 skipped**, one existing Starlette deprecation warning,
19.48 seconds. This includes DCR persistence, PostgreSQL refresh/revoke races,
refresh rollback behavior, and the real CPU smoke container path.

Core suite result: **550 passed, 1 skipped** in 1.38 seconds.
`git diff --check` passed.

## Limits

These are local test-host results. The exact rebased PR head still requires
fresh GitHub CI and GitHub review. No live ChatGPT OAuth exchange, public
runtime acceptance, provider call, GPU allocation, paid execution, or target
host restore/operations exercise was performed. Repository mode remains
`parked`.
