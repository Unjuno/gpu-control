# P5 provider challenge key redaction — 2026-10-31

## Scope

Candidate based on PR #61 head
`1c715e527431b5407c6b8ac45a18e084b0dafb05`. Provider account lease
challenges are persisted in PostgreSQL. The recursive challenge filter now also
rejects key names matching `completion_key`, `signing_key`, and `private_key`,
including nested environment maps. These can carry operator-held completion
and adapter signing material and must not enter durable provider request state.

The provider account lease test adds regression inputs for
`GPU_CONTROL_COMPLETION_KEY_B64`, `adapter_signing_key`, and
`private_key_pem`. Values are placeholders only.

## Validation

- `git diff --check` passed.
- From `gateway/`,
  `python -m pytest -o addopts= -q tests/test_provider_account_leases.py`:
  **16 passed**, with one existing Starlette deprecation warning.
- The recursive key scan now fails closed beyond 64 container levels, so deeply
  nested untrusted adapter challenges cannot exhaust Python recursion while
  searching for secret key names. A 70-level regression fixture covers this.
- The scan also covers tuples, which Python's JSON encoder accepts and converts
  to arrays. A secret key inside a nested tuple is rejected before persistence.
- Revalidation after this tuple fix, from the PR #64 worktree's Gateway venv:
  `python -m pytest -o addopts= -q tests/test_provider_account_leases.py`
  passed **16 tests**, with one existing Starlette deprecation warning.
- Revalidation on the PR #64 candidate worktree with its own dependency
  environment: `gateway/tests/test_provider_account_leases.py` **16 passed**;
  one existing Starlette deprecation warning. The worktree was at source base
  `a2a0da35e48e61a483ed3d084941ac6a822095a6` plus the uncommitted 64-level
  guard and regression.

## Limits

This is a local SQLite regression on a PR #61-based candidate. It does not
exercise PostgreSQL, a live provider, credential values, GitHub CI/review, or
production configuration. Repository mode remains `parked`; provider calls and
paid execution remain disabled.
