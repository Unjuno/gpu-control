# P5 account lease process race on PostgreSQL — 2026-10-31

## Scope

Verified the atomic Store primitive that writes a provider account lease and
matching `gateway_runs_v1.submission_intent` in a single transaction. Two
independently spawned Python processes, each constructing a separate Store and
PostgreSQL connection, raced on the same initially unreserved account scope.
Exactly one process returned a lease; exactly one run row had an incremented
attempt and matching intent; the single persisted lease referenced that run.

This exercises the database reservation primitive only. The Worker does not
call it yet, and the test does not contact a provider or establish provider
create, ambiguous-create reconciliation, or cleanup behavior.

## Reproducible inputs

- Checkout HEAD: `a794438f42bd7246f463eaaa40d963af0aae9d13`; test used the dirty
  current worktree, not the HEAD-only source.
- PostgreSQL: 16.15 (`postgres:16` local image ID
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`).
- Store source SHA-256: `4db23d94b38127efbc29e0afc85e22c14d5d9e578de4bd9f6db0a0556d25fcfd`
- Migration source SHA-256: `8251f6aa4c05c4d9d7d551a04bee8d6acc7526f7c31a60914e5d17b069130bf5`
- PostgreSQL acceptance test SHA-256: `7497daa810ca4a655bb4dcdc9779807a4209f0a4bf464ed7e02b40955ffc975b`
- The PostgreSQL server ran in a task-created local container with a dedicated
  disposable database. The container was removed after the tests.

## Results

- `tests/test_postgresql.py`: **6 passed** (includes the new spawned-process
  race); one Starlette deprecation warning.
- Full Gateway suite with `GATEWAY_TEST_DATABASE_URL` set to a fresh dedicated
  PostgreSQL database: **508 passed, 7 skipped**, one Starlette deprecation
  warning. The skips were missing Torch, Modal SDK, and digest-pinned CPU image,
  plus two PostgreSQL outage/recovery cases requiring a separately configured
  stoppable database container.
- `git diff --check`: passed.

The test URL and database password are intentionally omitted from this record.
No provider, paid resource, production deployment, GitHub write, or ChatGPT
workspace was used. Repository policy remains `mode: parked`.
