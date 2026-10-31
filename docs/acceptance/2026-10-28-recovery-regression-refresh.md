# P2 recovery regression refresh — 2026-10-28

## Scope and identity

Revalidated the current Gateway recovery code on branch
`codex/chatgpt-cpu-vertical`, base commit
`f054aebe96460fe033dde8d91d7e3bbab0255655`. At invocation time, the SHA-256
of tracked Gateway changes (`git diff --binary -- gateway | shasum -a 256`)
was `f98f3eeb9e6dedb4bce9c9e69fa6e6de68575dfcf286938c6f69d82ff3baea95`.

## Verification

Command:

```sh
gateway/.venv/bin/python -m pytest \
  gateway/tests/test_worker_recovery.py \
  gateway/tests/test_recovery_supervisor.py -q
```

Result: **11 passed**, with one existing Starlette `BlockingPortal` deprecation
warning. These tests exercise missing/invalid terminal results, cleanup retry
and slot retention, stale lease fencing, result-write DB failure, timeout
intent, artifact persistence failure, stale-worker submission reconciliation,
and supervisor restart during cancellation cleanup.

A full Gateway regression run on the same worktree also passed **393 tests**
with **3 skipped** and one existing Starlette deprecation warning. The skips
were optional Torch and Modal coverage plus the dedicated PostgreSQL outage
test (not configured in that invocation).

The dedicated PostgreSQL outage test was then run against a disposable,
non-auto-removing PostgreSQL container and the pinned CPU smoke image:
`test_postgres_outage_after_capture_retains_resource_and_recovers` passed.
It stopped PostgreSQL after real CPU result capture, verified the failed
persistence retained the run and slot, restarted PostgreSQL, recovered the
lease, verified the persisted artifact, and confirmed cleanup and slot release.
The first harness attempt failed because its `--rm` container disappeared on
stop and its database name did not match the test's readiness probe; this was
corrected before the passing run. The isolated container and volume were
removed after verification.

`git diff --check -- gateway` passed for the recorded Gateway source snapshot.
The extra integration changed no tracked source files.

## Limits

The focused unit run is the fake-backend/SQLite scope. The full Gateway suite
and one isolated PostgreSQL failure/recovery path passed, but this does not
establish target-host recovery, Neon behavior, measured RPO/RTO, or ChatGPT
recovery. Repository policy remains `parked`.
