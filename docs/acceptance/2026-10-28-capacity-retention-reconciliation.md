# Capacity journal retention-gap reconciliation

Date: 2026-10-28 (Asia/Tokyo)

## Scope

Implemented an explicit operator recovery path for the capacity bridge when
journald has vacuumed the saved cursor. It does not make the bridge continuous
or enable notification delivery. Repository mode remains `parked`.

`JournalPoller.reconcile_latest()` now requires initialized state, confirms the
saved cursor is missing before and after reading exactly one latest trusted
capacity event, and fails without advancing if the outbox cannot accept another
record. It preserves pending entries and queues the latest status even if that
status matches the old state, so the operator sees the current condition after
a gap. It cannot reconstruct intermediate events removed by journal retention.
The CLI exposes this only through `--reconcile-latest`; regular polling remains
fail-closed after a retention gap. Operations and contract documentation now
explain the command, its output, and evidence limitations.

## Regression evidence

Added tests for successful reconciliation with pending-outbox preservation,
reannouncement when latest status matches the known status, refusal when the
checkpoint remains available, and safe CLI reporting. Before implementation,
the two poller tests failed because `reconcile_latest` did not exist. After the
implementation, the focused suite passed:

```sh
gateway/.venv/bin/python -m pytest -o addopts='' -q \
  gateway/tests/test_capacity_event_state.py \
  gateway/tests/test_backup_generation.py \
  gateway/tests/test_deploy_units.py
```

Result: **71 passed**, one existing Starlette `BlockingPortal` deprecation
warning. `git diff --check` passed.

## Evidence boundary

These tests use fake journal records and local state files. No live journald,
Linux host, systemd service, notification sink, or recipient was contacted.
This does not prove target-host retention recovery or notification delivery.
Record the operator's reconciliation decision and command output during any
future host acceptance run.
