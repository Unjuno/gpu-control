# PR #52 P1 CPU security findings remediation candidate

## Scope and source

- Review source: PR #52 exact head `bc9b0305e6b2e86f9d8c214161b10511ce9f012c`.
- Candidate branch: `codex/p1-cpu-findings-fix`, based on that exact head.
- Published as commit `cdb1f8ad6f235df715a20c245737c71b2de730dd` to the PR #52
  head branch `codex/gpu-control-p1-05-recovery`. PR #52 remains a Draft and
  GitHub reports `REVIEW_REQUIRED`; no merge was made.
- An independent Security Review of the remediation diff reported no issues.
- `policies/repository-state.yaml` remains `mode: parked`; no provider or paid
  execution was enabled.

## Findings and changes

The exact-head Security Review found two Medium findings:

1. `service.submit()` revalidated local admission policy but did not compare
   the prepared plan with the current registered workload. It now rejects a
   missing or changed manifest before reserving a queue slot. The comparison
   binds provider, repository, source SHA, manifest digest, image digest, and
   runtime ceiling.
2. `Worker` repeated policy checks but did not have the current workload
   registry. It now receives the operator registry loaded by its process entry
   point and repeats the full manifest binding before starting a provider. A
   missing registry fails closed.
3. `LocalContainerBackend.cleanup()` and `cancel()` validated the stored handle
   shape but did not verify the remote Docker container labels. Both now inspect
   the full run, owner, plan, image, and source label binding before removal or
   stop. An already absent container remains idempotent; an ambiguous or
   mismatched identity is rejected before mutation.

Four regression tests cover stale manifests at submit and worker dispatch, plus
container label mismatches at cleanup and cancellation. Before implementation,
the three behavior guards for submit and Docker cleanup/cancellation failed as
expected. The worker guard test first exposed that `Worker` had no workload
registry input; after adding that input, its stale-manifest assertion also
failed as expected. All four tests pass after the changes.

## Verification

Full Gateway suite on Python 3.12, importing source from this candidate:

```text
197 passed, 7 skipped, 1 existing Starlette deprecation warning
```

Full Core suite on Python 3.12, importing source from this candidate:

```text
452 passed, 1 skipped
```

The GitHub checks on published PR #52 head `cdb1f8ad6f235df715a20c245737c71b2de730dd`
all passed: Python 3.11/3.12/3.13, Gateway offline tests, Gateway comment
bridge tests, Project bridge tests, trusted reference container, and Vercel.

`git diff --check` passed. The Gateway optional skips include Docker and
PostgreSQL integration paths, so these results do not exercise a live Docker
daemon, target host, provider, ChatGPT workspace, or paid resource. The existing
GitHub checks cover the published remediation head. They do not constitute
GitHub approval or deployed product acceptance.

## Remaining acceptance

- Obtain a fresh independent review and required GitHub approval on the exact
  remediation head; review of the earlier base cannot cover these changes.
- Run current required checks on the remediation head through the protected PR
  process and integrate the P1 stack in dependency order.
- Deploy to an approved environment with durable database, current schema,
  operator workload registry, worker, recovery supervisor, and OAuth settings;
  verify readiness and authenticated ChatGPT CPU execution/result retrieval.
- Keep P2/P3 operational recovery, real GPU, and separately authorized paid
  execution acceptance open.
