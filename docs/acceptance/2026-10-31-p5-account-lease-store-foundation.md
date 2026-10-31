# P5 account lease store foundation

Date: 2026-10-31 (Asia/Tokyo)

## Scope

This is a partial implementation of roadmap item P5.3a. It adds schema v10,
Store operations for reserving one provider account scope, applying fenced
state transitions, and releasing only after the caller supplies confirmed
cleanup and the exact stored provider job ID. It also adds an HMAC-SHA256
helper that derives an opaque scope from a provider credential and a separate
operator-held key. Tests cover stable derivation, account/provider separation,
SQLite, and two independent Store instances sharing one database. This does
not establish cross-host production behavior.

The HMAC helper is not wired to operator configuration or the lease store. The
lease store is not connected to run submission intent, paid authorization,
RunPod create/reconcile, or the worker's cleanup transaction. It does not yet
persist the provider request challenge, core-plan fingerprint, or
authorization ID required by the P5.3a contract.
Therefore the candidate/paid RunPod path remains ineligible for enablement, and
this artifact is not provider or GPU acceptance.

## Evidence

- Repository HEAD at inspection: `a794438f42bd7246f463eaaa40d963af0aae9d13`;
  changes below are uncommitted working-tree changes.
- `gateway/gpu_gateway/migrations.py` SHA-256:
  `f8ff71074c20d19ad3e3929c6b18b9b82b1b52bf2ccf4ffbcf2258434c6ceab5`
- `gateway/gpu_gateway/store.py` SHA-256:
  `e0711d3088d3c44530322ab9ef48d3f43629b332b4a473bf47e981162c072b76`
- `gateway/gpu_gateway/provider_account_scope.py` SHA-256:
  `fad8c4249693080ebfc9000e2bc53e43503c55b45e22a1c5a188a3a824e463a4`
- `gateway/tests/test_provider_account_leases.py` SHA-256:
  `c815955eeab2574fd94606034dd4164487e221d2257ac68d1c11eb46f5f13d4a`
- `gateway/tests/test_provider_account_scope.py` SHA-256:
  `7204eff7c710d6573ca28f1091efdc03ff7be5228e8e295d7d3fb79cfc0e5ffd`
- Focused verification:
  `cd gateway && ./.venv/bin/python -m pytest -q -o addopts= tests/test_provider_account_scope.py tests/test_provider_account_leases.py tests/test_migrations.py`
  -> 19 passed. A SQLite trigger deterministically exercises the insert-conflict
  branch and confirms a row with a different provider/run/owner/plan identity
  is rejected. Reservation now starts in `reserved`; repeated exact-run
  reservations share its token, but compare-and-set allows only one caller to
  move it to `submitting`.
- Gateway suite:
  `cd gateway && ./.venv/bin/python -m pytest -q -o addopts=`
  -> 494 passed, 15 skipped.
- `git diff --check` passed.

## Security review follow-up

Security diff scan `5dc464d8-cad1-46ba-a355-7cfc319eec49` reviewed snapshot
`codex-security-snapshot/v1:sha256:4a881c989aabeffb58fd970fc21925cd6d0201a2d5e9dac72b3d3105fd5aa65c`.
It reported no current vulnerability and retained one internal identity-check
candidate as deferred because there was no worker/service caller. After that
snapshot was sealed, a regression test reproduced the wrong-row return and the
conflict path was fixed to compare provider, run ID, owner, and plan
fingerprint. A fresh-context independent reviewer confirmed the four explicit
comparisons and that the trigger test reaches the conflict branch; the focused
test and full Gateway suite then passed on the fixed source. The sealed scan's
digest predates this follow-up, so it remains evidence for the earlier source
snapshot only.

## Remaining acceptance

The complete P5.3a process-kill, ambiguous-create, delayed-inventory,
reconciliation, terminal cleanup, stale-worker, and next-allocation cases are
still required with at least two independent processes/connections. PostgreSQL
cross-process behavior and the exact transaction boundary with run intent must
also be tested. The HMAC key needs stable, secret operator configuration and
must be shared across all gateway processes before scopes can be used live. No
RunPod API was contacted, no resource was created, and no paid setting or
parked policy was changed.

## Schema v11 challenge binding follow-up — 2026-10-31

Extended the lease record with the core-plan fingerprint, authorization ID,
bounded provider request challenge, and its SHA-256 digest. A challenge can be
bound only once to the exact `reserved` lease; `reserved -> submitting` now
requires the persisted digest. Challenge JSON is limited to 16 KiB and rejects
credential-like keys recursively. Migration v10 -> v11 adds nullable columns,
preserving any existing held lease conservatively.

Focused verification:

```text
cd gateway && ./.venv/bin/python -m pytest -q -o addopts= tests/test_provider_account_leases.py tests/test_migrations.py
16 passed, 1 warning
```

The tests include a v10 held-lease migration preservation case, secret-key
rejection, single-bind behavior, and refusal to transition before challenge
binding. This still does not couple reservation to the Gateway run intent,
validate the challenge against a provider adapter, or integrate create,
reconcile, and cleanup with the worker. Keep P5.3a unchecked and all RunPod
execution switches disabled.

## Atomic lease and run-intent reservation — 2026-10-31

Added `Store.reserve_provider_account_lease_with_submission_intent`. It
validates the run's current worker lease token, owner, plan fingerprint and
attempt, then writes the reserved account lease (including the create challenge
and digest) and the linked run submission intent in one database transaction.
The intent includes account scope, core-plan fingerprint, authorization ID and
challenge digest. A conflict, stale worker token, or mismatched run state rolls
back both records. No provider I/O is performed by this Store operation.

Verification:

```text
cd gateway && ./.venv/bin/python -m pytest -q -o addopts= tests/test_provider_account_leases.py tests/test_migrations.py
20 passed, 1 warning
```

Coverage includes successful atomic persistence, rollback on occupied account,
rollback for a stale worker token, and two independent Store instances racing
on one SQLite database with exactly one lease and one intent commit. This is
SQLite multi-connection evidence only. The worker does not call this method
yet; stable account-scope configuration, a concrete RunPod adapter/challenge
validator, PostgreSQL process-level competition, recovery and cleanup remain
open. RunPod remains disabled and parked.
