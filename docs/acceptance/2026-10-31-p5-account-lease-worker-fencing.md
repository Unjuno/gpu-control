# P5 provider-account lease worker fencing — 2026-10-31

## Change

Added `Store.transition_provider_account_lease_for_run`. A state change now
requires both the provider-account lease token and the current, unexpired
Gateway Worker claim token. The transaction locks the provider lease before
the run row and checks their exact shared run, owner, plan, attempt,
authorization, and provider-challenge bindings. It rejects malformed intent
state, expired/stale worker claims, and transitions to `active` or
`cleanup_pending` without a provider job ID.

## Verification

- TDD red: the new worker-fencing test failed because the Store method did not
  exist.
- TDD green: the new test passed, proving a stale worker token cannot mark
  the same lease active after a successor claims the run, while the successor
  can move the still-unresolved lease to `uncertain`, then reconcile it to
  `active` when a provider job ID is supplied. Reload confirms that ID is
  persisted.
- Focused suite: `cd gateway && ./.venv/bin/python -m pytest -q -o addopts= tests/test_provider_account_leases.py`
  -> **12 passed**, one existing Starlette deprecation warning.

## Limits

The Worker and provider adapter do not call this method yet. The provider
account lease is not released atomically with terminal run cleanup, and no
signed paid authorization envelope is persisted or reloaded here. PostgreSQL
and process-level behavior for this new transition method have not been
verified. Keep the candidate path disabled and repository policy `parked`.
