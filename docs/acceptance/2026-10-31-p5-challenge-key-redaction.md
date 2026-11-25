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
- Codex Security diff scan `c9b9af12-491e-481e-a7cf-af83b8c835d3` completed
  against base/head `97c0c798ada6145dd4f7a0fe74f1231c28e81d3e` and snapshot
  `codex-security-snapshot/v1:sha256:eb4fec65e9beacc974cf61dfb688e3dff211c8c0da9c751678dab47b3ca379ae`.
  It covered the changed challenge canonicalization source and its Worker,
  backend-contract, and regression-test context; one source file was in the
  scan inventory, zero candidates were reported, and coverage was complete.
- On PR #64 head `0e1b68545370a0f7e9b58e533fece74efbe6bd22`, all nine published
  GitHub/Vercel status checks passed. The PR remains Draft and has no GitHub
  review decision.

## Limits

The focused regression uses local SQLite. This evidence does not exercise
PostgreSQL, a live provider, credential values, or production configuration.
The Codex Security scan covers the exact local code patch, not the full PR #64
branch diff, and is not a GitHub approval. Repository mode remains `parked`;
provider calls and paid execution remain disabled.
