# P1/P5 PostgreSQL role reconciliation acceptance

This local candidate reconciles P1 OAuth login admission and P5 provider-account
leases, signed provider observations, paid-authorization reads, and terminal slot
release with the API/worker database role boundary. It does not enable provider
calls or change parked execution policy.

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
- Local OAuth login now applies a bounded per-source attempt window, a durable
  global token budget, and a bounded per-process KDF semaphore. IP source
  resolution is explicit for direct, trusted-proxy, and Vercel deployments;
  only a keyed/hash-derived source bucket is persisted. KDF work runs outside
  the database transaction.

The worker lease-table grants support the current trusted worker implementation.
They do not claim isolation against a compromised worker database credential;
that stronger property requires moving all lease lifecycle writes and run claim
mutations behind constrained database functions.

## Verification

- Disposable PostgreSQL 16.14 cluster, database `gpu_control_runtime_test`:
  effective-role integration checks passed, including Store paths, actual
  `Worker.finish`, provider cleanup, pre-submission abort, observation locking,
  paid-authorization reader, and role privileges.
- Full Gateway suite: **564 collected; all runnable tests passed, 7 skipped**.
  Skips are environment-dependent tests; the database role tests were run
  separately against the disposable PostgreSQL cluster.
- `python3 -m compileall -q gateway/gpu_gateway` and `git diff --check` passed.
- PR #66 Preview `/healthz` returned 200 with `configured=false` and
  `auth_configured=false`; `/readyz` returned 503. This is Preview configuration
  evidence only; no secrets, Production settings, or environment variables were
  read or changed.

This is a locally verified integration candidate, not a hosted or production
acceptance. The working-tree changes are uncommitted and unpushed. Preview remains
unconfigured and not ready. Live ChatGPT OAuth/tool execution, hosted database
role application, durable worker operation, and paid GPU execution remain
unverified; RunPod policy is parked and no pod was created.
