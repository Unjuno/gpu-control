# P1 OAuth refresh and grant revocation atomicity — 2026-10-31

## Scope

- PR #57 follow-up on candidate base `3fd9d54ca0cf8d202544542a39c59cf52cf62269`.
- Fixes the reviewed race where refresh rotation could commit the presented
  token's revocation, allow grant revocation to observe no active token, and
  then insert replacement credentials after the revoke returned.
- Refresh-token consumption and replacement access/refresh token insertion now
  share one database transaction. Token-pair issuance is atomic for initial
  authorization-code grants as well. Revoking a known refresh token continues
  to revoke its grant family after rotation has marked that token revoked.

## Validation

The Gateway suite ran from this candidate with a dedicated PostgreSQL 16
database, provider integrations disabled, and Docker CPU-smoke inputs omitted:

```text
GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://.../gateway_pr57_oauth_race_test
PYTHONPATH=/tmp/gpu-control-pr57-oauth-revoke-fix/gateway
python -m pytest -o addopts='' gateway/tests -q
```

Result: **252 passed, 6 skipped**, one existing Starlette deprecation warning,
9.54 seconds. This includes a PostgreSQL concurrency regression that pauses
rotation after consuming the old refresh token, races grant revocation, then
checks that the old refresh and both replacement credentials are revoked.
The local OAuth suite also passed **5 tests**. `git diff --check` passed.

## Limits and next gate

This is local SQLite/PostgreSQL test evidence. No live ChatGPT OAuth exchange,
deployment, provider call, GPU allocation, or paid execution was performed.
The change requires fresh independent review and PR-head GitHub CI before it
can be treated as integrated. Repository mode remains `parked`.
