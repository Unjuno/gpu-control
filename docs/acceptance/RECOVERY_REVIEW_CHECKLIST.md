# Provider-independent recovery review checklist

Status: **NOT REVIEWED**. This checklist prepares an independent review; it is
not evidence that the review occurred or that recovery is production-ready.

## Reviewer record

- Reviewer (not the implementation author):
- Reviewed commit SHA:
- Review date (UTC):
- Scope: local CPU lifecycle and control-plane recovery only
- Decision: PASS / FINDINGS / BLOCKED
- Findings and severity:
- Required changes and follow-up commit:

## Source review

- [ ] Trace `gateway/gpu_gateway/worker.py` claim, lease renewal, intent
  persistence, provider start, handle persistence, inspect, result persistence,
  cancellation, cleanup, and slot release.
- [ ] Trace `gateway/gpu_gateway/store.py` transaction boundaries, control-row
  invariants, migrations, and lease-token fencing.
- [ ] Trace `gateway/gpu_gateway/local_backend.py` start/inspect/cancel behavior
  and `gateway/gpu_gateway/container_runtime.py` identity and cleanup checks.
- [ ] Trace `gateway/gpu_gateway/artifacts.py` atomic writes, manifest binding,
  owner scoping at the API boundary, pruning, and failure behavior.
- [ ] Trace `gateway/gpu_gateway/experiment_api.py` owner checks and ensure
  status/readiness never report missing or stale control state as executable.
- [ ] Search all other callers of the reviewed functions. Confirm that the
  conclusion covers the canonical MCP path and does not silently generalize to
  the GitHub comment bridge or remote providers.

## Required failure-boundary analysis

For each row, cite the relevant code and existing acceptance/test evidence. If
the evidence is simulated or uses a fake backend, say so explicitly.

| Failure boundary | Required conclusion | Evidence / finding |
| --- | --- | --- |
| Worker exits after container start, before handle persistence | Same run is reconciled; no duplicate start | |
| Worker lease expires while provider start is still in flight | Late handle is persisted safely; stale worker cannot overwrite newer state | |
| Result captured but database write fails | Resource and slot remain tracked until durable result and cleanup | |
| Result persisted but cleanup fails or supervisor exits | Replacement recovery uses saved result/handle; no false success or premature slot release | |
| Cancellation or deadline races with successful exit | Terminal state follows persisted intent and cleanup proof | |
| Provider outcome cannot be observed | State remains unknown; no blind resubmission | |
| Artifact write/manifest persistence is interrupted | No unsupported artifact is advertised; safe retry or cleanup is defined | |
| Database is unavailable or control singleton is missing | Readiness and capabilities fail closed with an actionable blocker | |
| Worker heartbeat age is exactly 15 seconds | Readiness and supervisor recovery both classify it as stale | |
| Another owner requests a run/result/artifact | No run or blob data crosses the owner boundary | |

## Acceptance boundary

- [ ] Confirm local Docker evidence is identified as local CPU evidence only.
- [ ] Confirm fake-backend crash tests are not presented as real-provider proof.
- [ ] Confirm no claim is made about target-host restart, persistent production
  storage, remote provider recovery, timed RPO/RTO, or seven-day operation.
- [ ] Confirm `policies/repository-state.yaml` remains `parked`; this review does
  not activate paid/GPU paths or authorize provider calls.
- [ ] Record any required code changes separately and review the resulting new
  commit; do not treat an earlier commit's review as covering later changes.

## Existing evidence to inspect

- `docs/acceptance/2026-10-28-recovery-supervisor.md`
- `docs/acceptance/2026-10-28-artifact-storage.md`
- `gateway/tests/test_worker_recovery.py`
- `gateway/tests/test_local_lifecycle_integration.py`
- `gateway/tests/test_postgres_lifecycle_integration.py`

The current review target must be refreshed from `git rev-parse HEAD` when a
reviewer starts. The acceptance files describe earlier evidence and do not
automatically validate later code changes.
