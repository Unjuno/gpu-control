# Capacity bridge and backup regression evidence

Date: 2026-10-28 (Asia/Tokyo)

## Scope

Revalidated the host-independent P3 capacity journal/outbox, sink-agnostic
delivery pump, backup generation verifier, and systemd unit contracts against
the current uncommitted worktree at branch
`codex/chatgpt-cpu-vertical`, base HEAD
`f054aebe96460fe033dde8d91d7e3bbab0255655`. The worktree was not staged,
committed, or pushed for this run.

## Commands and results

The root `.venv` did not contain the Gateway-only `PyJWT` dependency, so the
first `uv run pytest ...` invocation stopped while importing `gateway/tests/conftest.py`.
No test was collected in that attempt. Re-ran from the repository's existing
Gateway virtual environment:

```sh
gateway/.venv/bin/python -m pytest \
  gateway/tests/test_capacity_event_state.py \
  gateway/tests/test_backup_generation.py -q
```

Result: **53 passed**. This includes fake journal/source ordering, durable
outbox transitions, retry/backoff, fixed payload projection, sender exception
redaction, and backup generation/quiescence/checksum validation.

```sh
gateway/.venv/bin/python -m pytest gateway/tests/test_deploy_units.py -q
```

Result: **14 passed**. This validates the current service/timer template
contracts; it does not install or start them.

Both commands emitted the existing Starlette `BlockingPortal` deprecation
warning. No test contacted journald, a notification service, PostgreSQL, or a
provider.

## Evidence boundary and remaining acceptance

This establishes offline behavior with fake journal/sender inputs and local
backup command fixtures only. It does not verify a notification recipient,
delivery SLO, sink credential handling on a host, live systemd identities,
mounted artifact volume behavior, off-host backup retention, or a production
restore. The target host, region, cost ceiling, reachable origin/egress path,
recipient, credential store, and alert SLO remain unselected. No notification
sink or bridge service was enabled. Repository mode remains `parked`.

## Ordered retry follow-up

Reviewing the delivery contract exposed a transition-order gap: a batch was
selected before sends, so a retryable failure on an earlier alert could still
be followed by sending a later clear in that same batch. A later poll could
also skip the earlier pending event during backoff. The selector now stops at
the first pending event whose retry delay has not elapsed, and the pump stops
the current batch when an event remains pending after a retryable failure.
This preserves source-cursor order across both retry boundaries.

```sh
gateway/.venv/bin/python -m pytest gateway/tests/test_capacity_event_state.py -q
```

Result: **40 passed**, one existing Starlette deprecation warning. The new
fake-sender regression demonstrates that a clear waits behind a failed alert,
then sends after the alert succeeds. `git diff --check` passed. No sink,
journald, host service, or network delivery was exercised; this is local
ordering evidence only.
