# PR #58 runtime database security validation

Date: 2026-11-02 UTC

## Candidate and scope

- Candidate branch: `codex/pr58-cpu-vertical-reconcile-20261102`.
- Candidate base: PR #58 head `90bd6d8c84e319365d66951ca96c7ccceff40998`.
- This records the local runtime-role separation added while replaying PR #59
  operations work. It is not a production provisioning or deployment record.

## Implemented controls

- API, worker, and manual migration use distinct PostgreSQL identities and
  environment files. Fixed role names require separate PostgreSQL clusters for
  Preview and Production because roles are cluster-wide.
- Runtime roles are non-superuser and `NOINHERIT`; checks reject membership
  edges both into and out of protected roles. Existing table ownership can be
  transferred separately before the read-only database preflight.
- API has OAuth persistence access and narrow Gateway row privileges, but no
  schema DDL. Worker has no OAuth access, table-wide run/control UPDATE,
  INSERT/DELETE, or direct slot-counter updates. Its lifecycle writes are
  column-scoped.
- Slot release is a fixed SECURITY DEFINER function using a fixed search path,
  qualified table names, control-then-run row locking, terminal/reservation/
  lease-token checks, and an atomic one-slot decrement. PUBLIC execution is
  revoked and execution is limited to worker/migration.
- The worker remains a trusted service: its credential can read run rows across
  owners and update its explicitly allowed lifecycle/result fields. The
  dedicated worker host's Docker authority is also inside the trusted boundary.

## Local verification

- Disposable PostgreSQL 16 role/ACL regression, including forbidden writes,
  OAuth isolation, correct/stale/repeated lease-token release, rollback, and
  both directions of role membership: included in Gateway suite.
- Gateway suite: **351 passed, 14 skipped** on Python 3.12.13. Skips are
  optional integrations; this suite result is not evidence of hosted grants.
- Core suite: **515 passed, 1 skipped** on Python 3.12.
- systemd unit verifier passed in a network-isolated Linux container.
- Independent read-only Security Review of the staged candidate found no
  actionable findings. It confirmed the worker trust boundary above.
- `git diff --cached --check` and `git diff --check` passed.
- The disposable PostgreSQL test container was removed after verification.

## Acceptance not established

No hosted database, production secrets, Preview/Production roles, deployment,
or real ChatGPT account were changed or exercised. Before deployment, provision
and verify the three identities in the target environment with credentials
kept out of logs; inspect effective ACLs and role memberships there. Complete
ChatGPT OAuth connection/reconnect and user-facing CPU run/result retrieval
acceptance separately. Keep real GPU and paid-provider execution parked until
their own hardware, cost, cancellation, cleanup, and security evidence passes.
