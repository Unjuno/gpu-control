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

## Limits

This is a local SQLite regression on a PR #61-based candidate. It does not
exercise PostgreSQL, a live provider, credential values, GitHub CI/review, or
production configuration. Repository mode remains `parked`; provider calls and
paid execution remain disabled.
