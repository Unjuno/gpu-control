# P5 RunPod candidate account-lease contract gate — 2026-10-31

## Change

Added the `RunPodAccountLeaseBackend` contract and
`ProviderAccountLeaseRequest` value type. The contract separates a
non-networking prepare step, a create call that receives the persisted
challenge, reconciliation that receives that same challenge and must not
create, and an exact provider-job-ID projection from the returned handle.
Provider credentials remain in worker settings and are excluded from the
request type.

`supports_candidate_execution` now refuses RunPod candidate plans unless the
backend implements every account-lease method. Worker already applies this
check before writing submission intent, so a legacy RunPod backend cannot
dispatch a candidate through an unleased path. Existing generic RunPod CI
bridging remains outside candidate execution.

## Verification

- TDD red: a RunPod candidate backend with lifecycle and authorization hooks,
  but no account-lease methods, was incorrectly accepted.
- TDD green: the same backend is rejected; adding the complete lease contract
  makes it structurally eligible, subject to the independent authorization
  and provider registration gates.
- Full Gateway suite passed **508 tests, 16 skipped** in 10.59 seconds.
  Skips were optional Torch/Modal dependencies and unavailable local Docker
  CPU/PostgreSQL integration services. One existing Starlette deprecation
  warning was reported.

## Limits

This is a contract and dispatch gate only. No adapter yet implements the
contract, and Worker submission does not yet derive HMAC scope, atomically
reserve a lease, persist/reuse the provider challenge, or recover through the
new reconciliation method. Signed paid authorization persistence and real
RunPod lifecycle acceptance remain open. Keep candidate execution disabled,
mode `parked`, and spending gates closed.
