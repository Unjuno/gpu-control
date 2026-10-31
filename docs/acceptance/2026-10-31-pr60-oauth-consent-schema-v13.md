# PR #60 OAuth consent remediation and schema v13

## Scope

PR #60 already rendered an explicit OAuth consent page and required a
same-origin, session-CSRF-protected POST before issuing an authorization code.
This integration makes the lower-level authorization method enforce the same
CSRF boundary and advances the aggregate Gateway schema from v12 to v13.

Schema v9 had classified every client referenced by any historical token row as
persistent. Those rows do not prove explicit owner consent. Schema v13 resets
legacy persistence flags and requires the owner to approve the client again.
Identical Dynamic Client Registration metadata remains deterministic, so
re-registration preserves the client ID.

## Security properties

- Authorization GET remains display-only.
- Code issuance and client persistence require the owner session CSRF token at
  both the HTTP route and the authorization method boundary. The affirmative
  `approve` decision is also carried to and enforced by the method boundary.
- Denial issues no code and does not persist the client.
- Historical, expired, or revoked token rows never establish consent.
- Databases that already passed through schema v9 are corrected by schema v13.
- The repository remains in `mode: parked`; no provider call or paid resource is
  enabled by this migration.

## Compatibility

Existing access and refresh token rows are not deleted. The migration only
removes the unproven permanent-client classification. A client may need to
re-register and obtain explicit approval before a later authorization request.
Revocation remains available for an existing credential even after the client
registration expires or loses its unproven persistence classification.

## Verification

- RED: focused consent/migration tests failed because direct authorization
  accepted no CSRF and schema v9/v12 clients remained persistent.
- GREEN: focused OAuth consent, migration, and post-migration revocation
  triggers passed; owning OAuth and migration modules: `20 passed`.
- Full Gateway suite with a dedicated PostgreSQL 16 database: `540 passed,
  6 skipped`.
- Full core suite: `559 passed, 1 skipped`.
- `git diff --check` passed. The temporary PostgreSQL database was removed; the
  existing local test container was left unchanged.
