# PR #51 continuation rebased after OAuth revocation fix — 2026-10-31

## Scope

- Candidate PR #51 head: `cbe1c045f10dba271b239628c41f88bba4839c95`.
- Updated base: PR #57 head `dc886033550783799520dce3e201e96ba1e8ac9c`.
- Replayed the 26 continuation commits onto the fixed OAuth lifecycle base;
  preserved P1–P5 changes and added SQLite/PostgreSQL refresh-versus-revoke
  regressions. The callback fixtures use the currently accepted ChatGPT URI.
- Repository policy remains `mode: parked`, with live paid compute, RunPod
  calls/adapter, and generic external container execution disabled.

## Validation

Gateway suite used a dedicated local PostgreSQL 16 database, the real CPU
smoke container, and disabled Modal/RunPod integrations:

```text
GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://.../gateway_p51_rebased_full_test
GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST=sha256:07da90a98f66cca25c1afe3208cde7928012f6bdf1fdee9d5e9939c50cf7d32f
GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY=Unjuno/gpu-control
GPU_CONTROL_CPU_SMOKE_SOURCE_SHA=d5a30985d8f2df0e7221476f47f1dfecff2faedb
python -m pytest -o addopts='' gateway/tests -q
```

Result: **427 passed, 3 skipped**, one existing Starlette deprecation warning,
19.14 seconds. This includes PostgreSQL refresh/revoke race, concurrent refresh,
and rollback-on-insert-failure coverage, plus the local CPU container path.

Core suite result: **550 passed, 1 skipped** in 1.30 seconds.
`git diff --check` passed. A read-only static Security Review of the rebased
continuation and OAuth test edits found no actionable issues; GitHub review is
still outstanding.

## Limits

These are local test-host results. The exact rebased #51 head requires fresh
GitHub CI and GitHub review. No live ChatGPT OAuth/tool invocation, public
runtime acceptance, provider call, GPU allocation, paid execution, or target
host restore/operations exercise was performed.
