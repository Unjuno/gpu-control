# Cancellation Before Provider Dispatch — 2026-10-31

## Implemented

- Non-RunPod submission intent is written only if the current Worker lease is
  still held and `cancel_requested` is false.
- The Store validates exact intent identity, bounded run/owner/fingerprint,
  provider syntax, and integer types for attempt and timestamp before writing.
- RunPod account-lease reservation and intent persistence use the same
  cancellation condition. The reserved-to-submitting transition checks it
  again under the run-row lock. A canceled reserved lease is released before
  the run is finished as cancelled.
- The migration tests now assert the current schema constant (v12) instead of
  stale literal v11 expectations.

## Local verification

- `PYTHONPATH=gateway gateway/.venv/bin/python -m pytest -q gateway/tests/test_provider_account_leases.py gateway/tests/test_worker_recovery.py` — **23 passed**.
- `PYTHONPATH=gateway gateway/.venv/bin/python -m pytest -q gateway/tests` — completed successfully, with optional tests skipped by their configured conditions.
- `uv run pytest -q` — completed successfully; one configured skip was reported.
- `git diff --check` — passed.

Independent review confirmed the intent validation and both pre-dispatch
checks, with no issue introduced by the final validation hardening. It
identified the remaining transaction-to-provider-call race. A
concurrent cancel may arrive after the last database transition and while the
external create request is in flight. The provider API and database cannot be
made atomic. A returned handle is durably recorded and the Worker lifecycle
observes the cancel flag and performs cleanup on its next tick. The review found
no currently reachable paid path: RunPod paid/credit plans remain refused and
candidate execution is not opted in by the default registry.

## Current external acceptance boundary

Read-only checks at 2026-10-31 11:02 JST found `main` protection requiring one
approval, strict status checks, stale-review dismissal, conversation
resolution, and admin enforcement; force pushes and deletion are disabled.
Open PRs #51–#59 plus #43 remain OPEN/DRAFT; #52 and #43 report
`REVIEW_REQUIRED`, with no review decision on the others. Published CI applies
to remote heads, not this dirty worktree.

The production alias returned `/healthz` **200**, `/readyz` **404**,
unauthenticated `/mcp` **401**, and OAuth authorization-server metadata **200**.
The ChatGPT web session showed Log in / Sign up. Therefore deployed readiness,
authenticated ChatGPT tool discovery/call, and end-to-end CPU experiment/result
acceptance remain **NOT RUN**. No GitHub write, deployment, OAuth grant, or
provider call occurred. Preserve `mode: parked` and all spending gates.
