# P1 consented DCR persistence and schema-v9 remediation

## Scope

This focused slice removes the OAuth persistence change from the broad PR #51
aggregate. It applies directly to the current P1 CPU/OAuth branch and upgrades
the Gateway schema from v7 to v9.

Published review target: PR #58, based on
`codex/gpu-control-p1-04-cpu-oauth-recovery`.

Dynamic Client Registration entries remain provisional for one hour until the
owner explicitly approves that client on the consent page. The authorization
GET is display-only; a session-CSRF-protected POST issues the code and marks the
client persistent. Registration cleanup removes only expired provisional
clients. Schema-v7 clients remain provisional during migration because legacy
token rows do not prove explicit consent. Schema-v8 clients that the earlier
unsafe migration marked persistent are reset to provisional. An old client may
therefore need to register and obtain approval again; deterministic registration
preserves its client ID when its metadata is unchanged.

## Security properties

- Registration alone does not create a persistent client.
- Persistence requires an existing owner session and an explicit consent POST
  carrying that session's CSRF token. Denial issues no code and does not persist
  the client.
- Redirect URI restrictions, PKCE, resource binding, scope checks, refresh-token
  rotation, revocation, and login rate limits remain unchanged.
- The schema migration is additive and idempotent on SQLite and PostgreSQL;
  v9 deliberately resets the unsafe v8 persistence classification.
- The repository remains `mode: parked`; this change cannot allocate compute.

An exact-head Security Review found that the previous GET flow and legacy-token
migration were not consent-bound. This revision addresses that finding and
still needs an independent review of the remediation before merge.

## Verification

- Focused OAuth and SQLite migration modules: `14 passed`.
- Full Gateway suite with PostgreSQL configured: `264 passed, 5 skipped` using
  a dedicated temporary database in a local PostgreSQL 16 container.
- Full Core suite: `515 passed, 1 skipped`.
- `git diff --check` passed.

The temporary PostgreSQL database was removed after verification; the existing
local test container was left unchanged. These tests do not establish deployed
OAuth or a real ChatGPT workspace connection.
