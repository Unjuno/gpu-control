# P1 DCR client persistence and schema v9

## Change

OAuth Dynamic Client Registration (DCR) clients remain provisional and
short-lived until the resource owner grants consent. On consent, the client is
marked persistent so a long-idle ChatGPT connection can reauthorize with the
same `client_id` after its access and refresh tokens expire. Cleanup continues
to prune expired provisional registrations.

Schema v9 adds `persistent` to `gateway_oauth_clients_v1`. Migration from v8
preserves clients referenced by historical OAuth token rows, including revoked
or expired rows, because those clients may be needed for a later authorization.
Fresh databases receive the column from model metadata.

## Verification

- `gateway/tests/test_local_oauth.py` and `gateway/tests/test_migrations.py`:
  **17 passed**. This includes reauthorization after 31 days using the same
  client ID and cleanup of expired provisional registrations.
- PostgreSQL 16 v8-to-v9 migration regression: **1 passed**, using pinned image
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
- Full Gateway suite against PostgreSQL 16: **426 passed, 7 skipped, 1
  warning**. CPU/Docker smoke integration was not enabled in this run.
- Temporary PostgreSQL container was stopped and removed. No image was removed.
- No production or hosted database was migrated.

## Acceptance boundary

This is local code and migration evidence. It does not establish current GitHub
CI/review, ChatGPT OAuth or tool acceptance, hosted migration, or production
readiness. Paid execution remains parked.

## Current dirty-source PostgreSQL OAuth/migration rerun — 2026-10-31 03:38 JST

Re-ran the PostgreSQL migration and refresh-token concurrency tests against the
current worktree at HEAD `a794438f42bd7246f463eaaa40d963af0aae9d13`. The focused
command was
`gateway/.venv/bin/python -m pytest -o addopts= -q tests/test_postgresql.py tests/test_postgresql_oauth.py`.
With a disposable loopback-only PostgreSQL 16 instance pinned to
`sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
the result was **7 passed** with one existing Starlette deprecation warning.
This covers current-schema initialization, v1/v4/v8 migration paths to schema
v9, preservation of historical token-referenced clients, single-consumer
refresh rotation under concurrency, and transaction rollback on replacement
token insertion failure.

The database container was removed; test ports 55471 and 55472 had no listener
after cleanup. Current source file hashes are:

- `gateway/gpu_gateway/local_oauth.py`:
  `12bf92a69ddf535ba8e3dedd8dea23673d13f0b9986ac01be0ff5109ee0749ca`
- `gateway/gpu_gateway/migrations.py`:
  `3719b4b5572bfeaae2b00d0a5d53bb139944717cb2b3c170e70d30d107504a01`
- `gateway/tests/test_postgresql.py`:
  `d83d222c97995a57e125f12f6baa44b5eeeb19671b70262a145133558ae08326`
- `gateway/tests/test_postgresql_oauth.py`:
  `7f48ac06139142399d7865c5237d11a78f824a2d89264764db6ae46d19d129c3`

This is local PostgreSQL evidence, not ChatGPT OAuth, GitHub review/CI for the
dirty worktree, or hosted schema migration/restore acceptance.

## PR #51-base review candidate replay — 2026-10-31

Built the P1 DCR/schema-v9 code-and-test overlay on a detached worktree based
on PR #51's current pushed head
`aa681f4062dac6b73bcf380a38a4258b96a47e1`. The patch includes
`local_oauth.py`, `migrations.py`, their unit/migration/PostgreSQL tests, and
the new isolated `test_postgresql_oauth.py`; it applies cleanly to that base.
The code/test-only patch is available at
`/tmp/gpu-control-p1-dcr-v9-review.patch` with SHA-256
`1a0e4bafe567caf240b8aa8623280c8ae6a32ff6251d985d8bd73669a1c7fb27`.
All six candidate code/test files were byte-identical to the source used in
the current worktree.

- OAuth and migration unit tests: **17 passed** (one existing Starlette
  deprecation warning).
- PostgreSQL migration and refresh-rotation tests: **7 passed** with a
  disposable PostgreSQL 16 container pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  bound only to `127.0.0.1:55474`.
- Container removed after the run; confirmed no matching container and no
  listener on port 55474.
- This candidate overlay is based on the pushed PR #51 head, not a proposed
  reviewed/merged P1 series from `main`. Its tests are local, not GitHub CI or
  independent GitHub review. ChatGPT OAuth/tool acceptance and hosted schema
  migration remain NOT RUN.
