# Capacity bridge read-only health command

Date: 2026-10-28 (Asia/Tokyo)

## Change

Added `capacity_event_bridge.py --show-health` to inspect the local durable
outbox without constructing or querying a journald source. The output contains
only the existing fixed health projection: initialization/current status,
pending/acknowledged/exhausted counts, and fixed attempt-result counts. It
excludes source cursors, event bodies/reasons, exceptions, and sink responses.
It does not prove journal-reader health or human notification receipt.

## Regression evidence

The new CLI test failed before implementation because `--show-health` was not
a supported action. After adding it, the test proved the journal source factory
is not called and sensitive event-specific values are not printed. The
capacity-state, backup-generation, and systemd-unit suites passed:

```sh
gateway/.venv/bin/python -m pytest -o addopts='' -q \
  gateway/tests/test_capacity_event_state.py \
  gateway/tests/test_backup_generation.py \
  gateway/tests/test_deploy_units.py
```

Result: **72 passed**, one existing Starlette `BlockingPortal` deprecation
warning. `git diff --check` passed.

An independent review found that health-state reads occurred outside the CLI's
fixed-error boundary. Moved `delivery_health()` inside the guarded operation
and added a corrupt-state regression. Re-running the same command produced
**73 passed**, one existing Starlette deprecation warning; `git diff --check`
passed. The new case verifies that corrupt JSON returns only the fixed error
code and does not reveal the path or parse detail.

## Evidence boundary

This is local CLI/fake-state evidence. No Linux host, live journal, systemd
service, notification sink, or recipient was contacted. It does not close P3
host monitoring or delivery acceptance.
