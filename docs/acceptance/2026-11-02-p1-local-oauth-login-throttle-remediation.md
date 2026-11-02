# P1 local OAuth login-throttle remediation

## Scope

The Codex Security Standard scan of commit
`0c212ae6e12f4e7e5539d74224601f91823f00aa` reported medium CWE-645 on
`POST /auth/login`: five unauthenticated failures could lock the singleton
account-wide guard for 300 seconds and block the owner from signing in. This
candidate replaces that admission path; it does not establish that the hosted
service has been upgraded.

## Candidate change

- Schema v10 adds persistent, expiring per-source buckets and a global token
  budget for password-hash work. The legacy singleton guard remains for upgrade
  compatibility but is no longer used by the login path.
- The API limits active password-hash jobs per process, reserves global work
  budget in a short database transaction, and runs scrypt outside the database
  transaction and event loop. Rate-limited responses include `Retry-After`.
- Client addresses come only from the socket peer, an explicitly configured
  trusted proxy chain, or Vercel's platform client-IP header. Uvicorn proxy
  header rewriting is disabled. Invalid trusted-proxy input fails closed.
- Runtime-role SQL gives the new state tables to the API only. The worker gets
  no privileges; the API no longer gets update access to the legacy guard.
- The operations guide documents stopping services, applying schema v10 and
  role grants, and configuring the source-IP trust boundary.

## Verification

- Gateway suite against a disposable PostgreSQL 17.11 instance:
  **372 passed, 5 skipped**. The PostgreSQL role, migration, lifecycle, and
  backup-integrity tests ran and passed.
- The five skips were for unavailable optional Torch and prebuilt CPU/Docker
  integration fixtures; they are outside this login-throttle slice.
- `git diff --check` and Python `compileall` passed.
- Independent read-only Astra security review found no remaining actionable
  issues. It initially found that cancelling requests queued on AnyIO's thread
  limiter could leak two pre-acquired login slots. The route now acquires the
  semaphore only inside `LocalOAuth.login`, after the worker callback starts.
  Repeating the cancellation probe against `/auth/login` left both slots
  available and executed zero password callbacks.

## Acceptance boundary

This is local candidate evidence only. The patch is uncommitted and has not
been deployed. No schema migration or role-grant change was applied to a live
database. Hosted `/readyz`, the intended ChatGPT account's OAuth flow, tool
discovery, a real CPU run, and result/artifact retrieval remain separate
acceptance gates. Paid execution and GPU paths remain parked.
