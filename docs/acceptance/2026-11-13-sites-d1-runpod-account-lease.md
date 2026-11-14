# Sites D1 RunPod account lease foundation

This change adds the first persistent storage layer for serializing allocations
by RunPod account in the ChatGPT Sites Worker. It does not enable RunPod
dispatch or open admission.

## Implemented

- Migration `0006_runpod_account_leases.sql` stores an HMAC-derived account
  scope digest, exact run/owner/plan/authorization binding, a persisted
  create-challenge digest, lease generation/revision/token, lifecycle state,
  provider job identity, and release evidence. Rows do not expire by time.
- `provider_account_lease.js` derives account scope hashes and implements
  atomic reserve/replay plus compare-and-set lifecycle transitions. Release is
  restricted to proof that create was never sent, or a terminal run with
  confirmed cleanup and a durable cleanup receipt. Transition events reject
  updates and deletes.
- The build and artifact validator include the helper and migration.
- Node tests exercise idempotent reservation, competing intent rejection,
  stale-worker fencing, ambiguous-create retention, and release after cleanup
  using a SQLite-backed D1 contract shim.

## Verification and limits

The SQLite shim verifies SQL and transition behavior in one local database. It
does not prove Cloudflare D1 cross-host concurrency behavior. The helper is not
yet imported by `worker/index.js` or called by RunPod submission, reconciliation,
cancellation, or cleanup. The change does not atomically couple a lease with
submission intent, validate a live provider receipt, run multi-process races,
or verify that a matching Pod can be recovered after an ambiguous create.
Account-scope HMAC secret configuration and safe key rotation are also not
implemented. No live D1 migration, Sites environment change, deployment, or
provider operation was performed as part of this change.

Therefore this is a storage foundation only, not P5 acceptance. RunPod remains
parked and disabled pending adapter wiring and the offline and live lifecycle
acceptance in `docs/specs/p5-gateway-runpod-permit-bridge.md`.
