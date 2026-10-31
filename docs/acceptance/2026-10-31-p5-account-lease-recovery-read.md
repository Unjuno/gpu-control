# P5 provider-account lease recovery read — 2026-10-31

## Scope

Added a Store read boundary for resuming a previously reserved provider-account
lease after a worker claim changes. It reloads the scope from the durable run
submission intent, locks the lease row before relocking the run row to preserve
the reservation lock order, and returns a lease only when the current unexpired
Gateway worker token, owner, run, plan, attempt, authorization ID, challenge
digest, and stored lease identity all match. It rejects released leases and
active/cleanup-pending rows without a provider job ID.

This is a recovery primitive only. Worker dispatch/reconciliation and the
RunPod adapter do not call it yet; no account credential identity, HMAC key,
paid authorization envelope, provider create, or cleanup confirmation is wired
to this method.

## Verification

- TDD red: the new SQLite recovery test failed because
  `Store.read_provider_account_lease_for_run` did not exist.
- TDD green: the focused lease module passed **11 tests**. The new recovery
  test uses a second independent Store engine and verifies reload, expired
  claim, changed worker token, owner/plan mismatch, and a tampered challenge
  binding.
- PostgreSQL process test passed **1 test**. The winning process reloaded the
  lease through its own Store connection; the losing contender returned no
  lease. This used a task-created PostgreSQL 16 container, image digest
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  published only on `127.0.0.1:55495`.
- Full current Gateway suite with the same PostgreSQL service and commit-bound
  CPU image passed **514 tests, 2 optional skips** in 25.44 seconds. Only Torch
  and Modal SDK tests skipped. The run includes PostgreSQL outage recovery and
  the real local CPU/MCP result and artifact retrieval flow.
- The exact test-created PostgreSQL container and anonymous volume were
  removed; no listener remained on port 55495. `git diff --check` passed.
- Source hashes after the type annotation-only follow-up:
  `gateway/gpu_gateway/store.py`
  `15f200a0cc8d687c2798ba389b25b5b0a8a8c2cf712d498673174433c5fd4c2b`,
  `gateway/tests/test_provider_account_leases.py`
  `1783787a5379b13d2236afc2380641ebac91627b29820f402b8593ca6c9bf863`,
  and `gateway/tests/test_postgresql.py`
  `0bf3d619261580836a3859b51c9ff9ac789c4c23cc093817e169301c17f29101`.

Repository policy remains `mode: parked`. This does not establish a live
provider call, ChatGPT execution, deployed recovery, or paid execution.
