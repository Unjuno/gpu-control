# P2 cancellation and provider dispatch fence — 2026-10-31

## Finding

The working-tree Security Review found that cancellation could commit after the
worker persisted `submission_intent` but before `backend.start`, and the worker
would still create provider work.

## Change

`Store.confirm_submission_dispatch` atomically claims the provider-call boundary
for the current run lease, attempt, fingerprint, submitting state, and
uncancelled run. A cancellation committed before that claim prevents provider
I/O. A cancellation committed after it is ordered after dispatch and follows the
provider cancellation and reconciliation path. The intent records
`provider_call_started`, so recovery can reconcile a crash at this boundary
without blindly retrying creation.

## Validation

- The regression test commits cancellation immediately before the dispatch
  claim and verifies that the backend start method is never called.
- `test_experiment_api.py`, `test_worker_recovery.py`, and
  `test_postgresql.py`: **17 passed, 3 PostgreSQL-only skips**. The skipped
  cases need a dedicated PostgreSQL test service.
- No live provider request or paid execution was made. Repository mode remains
  `parked`; live paid compute and RunPod calls remain disabled.

## GitHub CI evidence

The pushed PR candidate at `188ed19ab72743ab22d396131016b74aed927cb1` passed
Gateway offline workflow run `41163335210`. Its job provisioned PostgreSQL 16
and set `GATEWAY_TEST_DATABASE_URL`; the pytest step reported **202 passed, 4
skipped**. CI also passed the repository's other eight required/status entries,
including Python 3.11/3.12/3.13, trusted reference container, bridge tests,
project tests, and Vercel.

These checks validate the pushed PR revision and its test suite. They do not
prove ChatGPT-originated execution, production deployment, or real provider
allocation. PR #53 remains Draft and has no submitted review decision.

## Scope limit

Local tests and GitHub CI do not constitute independent PR approval, hosted
recovery evidence, or ChatGPT acceptance.
