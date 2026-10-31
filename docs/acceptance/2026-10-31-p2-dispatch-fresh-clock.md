# P2 dispatch freshness boundary — 2026-10-31

## Scope

- Candidate base: PR #53 head `6b755fc45c3c95fcc54dae184914552763743392`.
- The candidate changes only `gateway/gpu_gateway/store.py`,
  `gateway/gpu_gateway/worker.py`, `gateway/tests/test_experiment_api.py`, and
  this acceptance record.
- The primary checkout's other uncommitted work was not copied or changed.

## Change

The dispatch claim now samples the injected worker clock after locking the run
row. It checks the persisted worker lease and persisted approval expiry at that
time, then atomically records `provider_call_started`. The worker passes its
clock into the store claim. Regression tests advance time after the worker's
earlier validation and confirm that an expired lease prevents the provider call
and that an expired approval produces an `expired` run without provider I/O.

## Validation

Executed from this candidate worktree:

```text
/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **200 passed, 8 skipped**, one existing Starlette deprecation warning,
7.48 seconds. The command ran from the candidate's `gateway/` directory using
the existing Gateway virtualenv; imports were confirmed to resolve to this
candidate worktree.

## Limits

This is local candidate evidence. The exact candidate still needs GitHub CI and
independent review. The repository remains `mode: parked`; this change does not
authorize provider calls, GPU allocation, or paid execution.
