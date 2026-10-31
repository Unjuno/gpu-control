# P1 consented DCR persistence on current P1

## Scope

This focused slice removes the OAuth persistence change from the broad PR #51
aggregate. It applies directly to the current P1 CPU/OAuth branch and upgrades
the Gateway schema from v7 to v8.

Published review target: PR #58, based on
`codex/gpu-control-p1-04-cpu-oauth-recovery`.

Dynamic Client Registration entries remain provisional for one hour until the
owner successfully authorizes that client. Authorization marks the client
persistent. Registration cleanup removes only expired provisional clients.
Previously used clients are marked persistent during migration by matching
historical OAuth token rows, including revoked or expired rows, so an idle
ChatGPT connection can be reauthorized without changing its client ID.

## Security properties

- Registration alone does not create a persistent client.
- Persistence requires the existing owner session and authorization flow.
- Redirect URI restrictions, PKCE, resource binding, scope checks, refresh-token
  rotation, revocation, and login rate limits remain unchanged.
- Migration is additive and idempotent on SQLite and PostgreSQL.
- The repository remains `mode: parked`; this change cannot allocate compute.

The same logical OAuth persistence change on the previous schema-v9 stack was
independently Security Reviewed with no findings. The v8 adaptation still needs
review on its exact published head before merge.

## Verification

- Focused OAuth/migration/PostgreSQL modules: `17 passed` using a dedicated
  temporary PostgreSQL 16 container.
- Full Gateway suite with PostgreSQL configured: `280 passed, 5 skipped,
  38 subtests passed`.
- Full Core suite: `515 passed, 1 skipped`.
- `git diff --check` passed.

The temporary PostgreSQL container was removed after verification. These tests
do not establish deployed OAuth or a real ChatGPT workspace connection.
