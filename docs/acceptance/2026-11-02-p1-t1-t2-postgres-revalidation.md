# P1 T1/T2 migration and MCP contract revalidation

Date: 2026-11-02 UTC

## Candidate

- Branch: `codex/pr58-cpu-vertical-reconcile-20261102`.
- Base: PR #58 head `90bd6d8c84e319365d66951ca96c7ccceff40998`.
- Python: 3.12.13.
- PostgreSQL: 16, pinned image digest
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  disposable container `gpu-control-audit-pg16`, loopback port 55445.

## Command and result

From `gateway/`:

```sh
GATEWAY_TEST_DATABASE_URL='postgresql+psycopg://postgres:local-ci-only@127.0.0.1:55445/gateway_test' \
  uv run --project . --no-sync python -m pytest -o addopts= -q \
  tests/test_contracts_v2.py tests/test_migrations.py tests/test_postgresql.py \
  tests/test_experiment_api.py tests/test_protocol_validation.py tests/test_http_auth.py
```

Result: **91 passed**, one existing Starlette deprecation warning, 4.95 seconds.
The PostgreSQL-backed migration and lifecycle cases ran against the disposable
PostgreSQL 16 instance; SQLite contract/migration cases ran in the same suite.

The plan's standalone T2 command was then run from the same `gateway/`
environment with the same disposable PostgreSQL URL:

```sh
GATEWAY_TEST_DATABASE_URL='postgresql+psycopg://postgres:local-ci-only@127.0.0.1:55445/gateway_test' \
  uv run --project . --no-sync python -m pytest -o addopts= -q \
  tests/test_experiment_api.py tests/test_protocol_validation.py tests/test_ci_bridge.py
```

Result: **109 passed, 1 skipped**, one existing Starlette deprecation warning,
2.86 seconds.

This revalidates local compatibility and tool contracts, including legacy row
preservation, idempotent migrations, unknown-future-schema rejection, OAuth
consent migration, eight canonical tools, scope visibility, owner-bound access
and cursors, pending-result semantics, GPU-required no-fallback, and structured
MCP envelopes. It does not validate a live ChatGPT client, hosted database,
deployment, or provider execution.
