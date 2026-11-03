# P1/P5 PostgreSQL role reconciliation acceptance

This candidate reconciles P5 provider-account leases, signed provider observations,
paid-authorization reads, and terminal slot release with the P1 API/worker database
role boundary. It does not enable provider calls or change parked execution policy.

## Changes

- Both provider-cleanup completion and proven pre-submission abort keep the
  worker run lease token until `gpu_control_release_finished_slot` succeeds in
  the same transaction. The helper clears `slot_reserved` and decrements the
  admission counter; only after that succeeds does the caller clear the run
  token/expiry. Any mismatch raises the internal abort and rolls the transaction
  back.
- PostgreSQL provider-observation admission reads use the
  `gpu_control_lock_provider_observation(text)` SECURITY DEFINER function on the
  current connection. This preserves the row lock without direct API UPDATE
  privilege. Signature, digest and expiry validation remain in Python.
- The API and worker have explicit least-privilege grants for P5 tables. Runtime
  roles cannot change provider/account-scope keys or delete leases. Paid
  authorizations remain writable only by the migration/operator boundary; the
  worker reads them. Paid-authorization readers lock the associated run row,
  and the supported writer takes that same run lock before modifying the record,
  so a row lock on the authorization itself is unnecessary.
- Ownership transfer includes the three P5 tables and the new function; role
  reapplication revokes old grants before installing the allowlist and keeps
  PUBLIC function execution revoked.

The worker lease-table grants support the current trusted worker implementation.
They do not claim isolation against a compromised worker database credential;
that stronger property requires moving all lease lifecycle writes and run claim
mutations behind constrained database functions.

## Verification

- `gateway/.venv` has application dependencies but not pytest. Tests were run
  with the locked project environment plus ephemeral `pytest==8.4.2` via `uv`;
  no dependency files were changed.
- `uv run --locked --with pytest==8.4.2 python -m pytest -q
  tests/test_provider_account_leases.py tests/test_migrations.py`: **29 passed**,
  including completion/abort terminal-accounting regression coverage.
- `tests/test_database_runtime_roles.py`: collected successfully but **3 skipped**
  because `GATEWAY_TEST_DATABASE_URL` is unavailable. OrbStack's Docker socket
  was not running, and no local `postgres` server/client was available, so the
  effective-role PostgreSQL integration checks remain unverified.
- `python3 -m compileall -q gateway/gpu_gateway` and `git diff --check` passed
  after the code/test edits.

This is a local integration candidate only. Do not merge, deploy, or represent
the PostgreSQL privilege boundary as accepted until the role tests run against
a disposable PostgreSQL instance, including API/worker Store calls, rollback,
concurrent observation locking, and ownership/default-privilege checks.
