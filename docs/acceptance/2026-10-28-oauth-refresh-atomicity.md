# OAuth refresh-token rotation atomicity

Date: 2026-10-28 (Asia/Tokyo)

## Defect and change

A client requesting a scope expansion during refresh received `invalid_scope`,
but the server had already revoked its refresh token. Also, the prior rotation
committed old-token revocation before inserting the replacement access/refresh
pair, so a persistence failure could consume the only usable refresh token.

The refresh flow now validates any requested narrower scope before mutation,
then revokes the presented refresh token and inserts the replacement pair in
the same database transaction. `_new_token_pair` inserts both token rows in one
transaction when it owns the transaction, or uses the existing transaction
when rotating a refresh token. Thus a failed insert rolls back both the old
revocation and partial new token rows.

## Regression evidence

The new scope-expansion regression failed before the fix: the subsequent valid
refresh returned HTTP 400 because the token had been revoked too early. After
the fix, the OAuth refresh/revocation integration test passed. A second test
injects failure during replacement refresh-token insertion and verifies that
both original tokens remain valid, no partial replacement survives, and retry
with the original refresh token succeeds.

OAuth modules:

```sh
gateway/.venv/bin/python -m pytest -o addopts='' -q \
  gateway/tests/test_local_oauth.py \
  gateway/tests/test_http_auth.py \
  gateway/tests/test_external_auth.py
```

Result: **37 passed**, one existing Starlette deprecation warning.

Complete offline Gateway suite (PostgreSQL, Docker, and CPU-container integration
inputs explicitly unset): **395 passed / 9 skipped**, one existing Starlette
deprecation warning. `git diff --check` passed. Skips are unconfigured or
optional integrations; this is not deployed ChatGPT/OIDC acceptance.

PostgreSQL concurrency follow-up: added
`test_postgres_refresh_token_can_only_be_consumed_once_concurrently`, which
starts two refresh requests together using separate worker threads against the
same token. With PostgreSQL 16 image
`postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
on loopback port `55546`, the test passed **1/1**. Exactly one request rotated
the token; the other returned `invalid_grant`; persisted state contained one
revoked original refresh token and one active replacement pair. The dedicated
container was removed after the test. This is local PostgreSQL concurrency
evidence, not a production database or live ChatGPT acceptance.

## Evidence boundary

The atomic-failure test uses SQLite and fault injection; it verifies application
transaction handling. The separate PostgreSQL test verifies row-lock behavior
for two concurrent uses of one refresh token, but does not simulate database
failure during token insertion. No ChatGPT workspace, live OAuth client,
deployed database, or provider was contacted. Live PKCE/refresh/revocation and
cross-conversation acceptance remain open.

## Current-worktree continuation — 2026-10-28

Re-ran the focused OAuth modules against the current worktree:
`gateway/.venv/bin/python -m pytest -o addopts='' -q
gateway/tests/test_local_oauth.py gateway/tests/test_http_auth.py
gateway/tests/test_external_auth.py` — **37 passed**, one existing Starlette
deprecation warning.

Re-ran the PostgreSQL one-time-consumption race against the digest-pinned
PostgreSQL 16 image above, bound only to loopback port 55547. The first attempt
used the default `postgresql://` dialect and stopped at missing `psycopg2`;
the repository declares psycopg 3 and CI uses `postgresql+psycopg://`. Re-run
with that configured driver passed **1/1**. The disposable container was removed
by the command's exit cleanup. This validates the PostgreSQL concurrency
behavior only; database-insert rollback was added as a separate follow-up
below. Neither test establishes production/ChatGPT acceptance.

PostgreSQL rollback follow-up: added
`test_postgres_refresh_rotation_rolls_back_if_replacement_insert_fails` to
inject a failure after the replacement access-token insert and during the
replacement refresh-token insert. On the digest-pinned PostgreSQL 16 image
above, bound to loopback port `55548`, the new test passed **1/1**: the old
refresh token remained active, the partial access row was rolled back, and a
retry using the old refresh token rotated successfully. The disposable
container was removed after the test. The focused OAuth HTTP/OAuth modules
also passed **37 tests**, one existing Starlette deprecation warning. This is
local PostgreSQL and unit evidence only; production and ChatGPT OAuth
acceptance remain open.
