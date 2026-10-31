# P1 readiness diagnostics privacy — 2026-10-31

## Scope

Follow-up on PR #62 head
`fd5932c596426cd2add7a5d6af0d2a757f35ef38` after an independent static
Security Review found that public `/readyz` exposed workload identifiers,
admission blockers, heartbeat ages, schema details, and artifact free-space
information.

Public `/readyz` now returns only `{"ready": true|false}` with status 200 or
503. Detailed diagnostics move to `/api/readiness`, which requires an
authenticated principal with `experiments:read`; the existing `/api` middleware
sets `Cache-Control: no-store`. It uses the same readiness calculation, so the
aggregate and detailed views cannot disagree due to duplicated health logic.

## Verification

- Regression-first check failed against the original PR #62 code because public
  `/readyz` returned 15 additional diagnostic fields and `/api/readiness` did
  not exist.
- After the change, `gateway/tests/test_http_auth.py`: **33 passed**, with one
  existing Starlette deprecation warning.
- Tests verify the public response contains only the aggregate boolean, the
  private route returns diagnostic fields, unauthenticated access is denied,
  and a bearer token without `experiments:read` is denied.
- `git diff --check` passed.

## Review limits

The original finding is from a static independent review of PR #62. This
remediation has not yet received an independent follow-up review, full Gateway
CI, deployment, or authenticated ChatGPT acceptance. No production setting,
share token, provider, or paid execution was used. Repository mode remains
`parked`.
