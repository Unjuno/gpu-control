# P5 Worker provider-account cleanup commit — 2026-10-31

## Change

Worker cleanup now handles a persisted RunPod account lease on both the normal
terminal path and the pending-cleanup recovery path. Before cleanup it reloads
the lease using the current Worker claim, asks the configured adapter for the
provider job ID corresponding to the persisted handle, requires that ID to
match the lease, and moves the lease to `cleanup_pending`. After adapter cleanup
returns literal `True` from `is_clean(handle)`, one database transaction:

- marks the exact provider lease `released`;
- marks the run and result cleanup `complete` and sets its terminal state;
- returns the admission slot and clears the Worker claim.

The Store transaction is fenced by both lease and current Worker tokens. A
missing or mismatched resource ID, unconfirmed cleanup, expired claim, or
inconsistent persisted intent prevents the commit. The account lease remains
held for a later recovery attempt.

## Verification

- TDD red: the Store-level atomic release test failed because
  `finish_run_after_provider_cleanup` did not exist.
- TDD green: the Store test verifies wrong provider ID and unconfirmed cleanup
  do not release the lease; the valid path commits lease release, terminal
  run/result state, and active-slot decrement together.
- Worker fake-provider integration covers both normal cleanup and a first
  unconfirmed cleanup followed by recovery under a successor Worker claim.
  Both end with one released lease, a terminal run, and zero reserved slots.
- Current full Gateway run after the final change: **507 passed, 16 skipped**
  in 11.68 seconds. The focused provider-lease suite passed **13 tests**.
- Skip reasons in that Gateway run were optional Torch/Modal dependencies and
  unset Docker CPU image/PostgreSQL test services. One existing Starlette
  deprecation warning was reported.

## Limits

Worker submission still does not derive the provider account scope, obtain a
provider create challenge, reserve the lease, or persist the signed paid
authorization. The new cleanup path activates only when such a lease intent
exists. Fake-provider evidence is not PostgreSQL cross-process or live RunPod
evidence. Keep candidate execution disabled, repository mode `parked`, and all
spending gates closed.
