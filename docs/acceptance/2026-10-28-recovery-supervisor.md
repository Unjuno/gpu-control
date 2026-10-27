# Recovery supervisor evidence — 2026-10-28

## Implemented behavior

The worker CLI now has a `--supervise` recovery-only mode. It shares the same
database and lease-token fencing as the execution worker, but does not claim
newly queued jobs. It can reclaim expired active leases and can reclaim a
`submitting` intent early when the execution-worker heartbeat has been stale for
15 seconds. Recovered submissions are reconciled from their persisted intent;
this mode never calls `Backend.start()` for a non-queued run. Its heartbeat is
stored separately as schema v5 `supervisor_seen_at`. `/readyz` is ready only
while both worker heartbeats are fresh. Schema v6 adds nullable
`last_observed_at` to each run; successful inspect/reconcile observations update
it, and owner-scoped status, result and list responses expose it. A failed
provider call does not overwrite the last successful observation time.

The local CPU smoke image already has its own in-container hard deadline
supervisor. This database-backed process addresses control-plane recovery while
the execution worker is stopped. It is not a substitute for provider-native
timeouts when a provider requires them.

## Evidence

- Full Gateway suite at this revision: **214 passed, 2 skipped**, one Starlette
  deprecation warning. The skipped optional tests require the Torch and Modal
  SDK packages, respectively.
- The suite used the digest-pinned local CPU image
  `sha256:92eefb29cdbe77b66f5381afba946c12e31f5bc4fd4d32e907fa5b0aa9548092` and
  a dedicated PostgreSQL 16 test container
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
- Real Docker lifecycle integration killed the execution-worker subprocess after
  container start but before handle persistence. The recovery-only supervisor
  reconciled the existing container, returned the same run result and removed
  that container without starting a second one.
- The same integration started another CPU container, recorded cancellation,
  stopped execution-worker ticks and expired its lease. The recovery supervisor
  cancelled and cleaned up the existing container; repeated cancellation stayed
  idempotent.
- A process-level fault-injection test forced the recovery supervisor to exit
  with `os._exit(73)` during cleanup, after it had persisted the cancellation
  result and `cleanup_pending` state. A replacement supervisor reused the saved
  result and handle, completed cleanup, marked the run cancelled, and released
  the slot. This specific crash boundary uses a fake local backend; real Docker
  cancellation/recovery is covered by the integration above.
- A timeout-triggered cancellation with `cancel_requested=false`, a successful
  exit code, and a cleanup failure retains `cleanup_pending:cancelled`. A
  replacement worker finishes cleanup and keeps the run `cancelled`; this guards
  against recovering it as `succeeded` from the exit code alone.
- PostgreSQL-backed tests migrated an existing v4 database to v6 while
  preserving the execution-worker heartbeat and adding both recovery fields,
  exercised concurrent admission and lease fencing, and stopped PostgreSQL
  after result capture before recovering the same result after restart. Legacy
  v1-to-v6 migration is covered by the
  migration test fixture.
- A v5-to-v6 migration test verifies the observation timestamp is nullable and
  migration is idempotent. The ambiguous-start test verifies `submit_unknown`
  exposes its last successful reconciliation timestamp through owner-scoped
  status and list results.
- Focused tests verify the supervisor leaves queued jobs untouched, uses a
  distinct heartbeat, claims a stale `submitting` intent without a handle, and
  never resubmits it. Readiness stays false when either heartbeat is absent or
  stale.
- A provider start that outlives its lease was overlapped with a competing
  worker claim. The original worker persisted its returned handle despite
  losing the lease; recovery used that handle, did not call `start()` again,
  and completed the run.
- Terminal success without a result is converted to an explicit failure. For a
  lifecycle backend, the failure is persisted before cleanup, unmanifested
  artifact bytes are discarded, and the admission slot remains reserved until
  cleanup is confirmed. The same missing-result success cannot pass through a
  backend without lifecycle cleanup.

## Boundaries

The systemd worker and supervisor units are templates; they have not been
installed or validated on a target Linux host. Recovery has not been tested
against a real remote provider or a production database. A worker that is alive
but unable to access its provider may still require operator intervention when
the outcome cannot be proved. HTTPS, real OAuth, ChatGPT tool use, result retrieval
from a second conversation, seven-day observation, GPU execution and paid
execution remain unverified or parked.
