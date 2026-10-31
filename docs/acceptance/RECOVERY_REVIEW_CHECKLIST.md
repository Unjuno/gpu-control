# Provider-independent recovery review checklist

Status: **REVIEWED — FINDINGS**. Independent source and failure-boundary review
of the local worktree only; this is not production recovery acceptance.

## Reviewer record

- Reviewer (not the implementation author): independent subagent (`/root/recovery_review`)
- Reviewed commit SHA: `eff04c508f02c7f8206e23884f281e1edff4ddab`
- Reviewed worktree state, including uncommitted and untracked files: branch `codex/chatgpt-cpu-vertical`; second-pass starting tracked diff SHA-256 `292e161f082f50e266eacd60b91eae49a6a3270bcba9da280adba4cba04c1923`. Rechecked every untracked hash listed in the handoff; all matched. Full `git status --short` inventory refreshed. Post-review diff hash intentionally omitted here to avoid self-reference; HEAD unchanged; no implementation changes made.
- Review date (UTC): 2026-10-28
- Scope: local CPU lifecycle and control-plane recovery only
- Decision: FINDINGS
- Findings and severity: P2 — local capacity monitor behavior is only unit-tested; service has `RequiresMountsFor=/var/lib/gpu-control/artifacts`, but no target-host mount or service availability drill. A failed oneshot/timer is separate from API/worker/supervisor units; API capability and prepare plus worker pre-start recheck fail local admission closed, leaving recovery/cancel paths operational in source. P2 — evidence is limited to local CPU/control-plane scope. Existing docs explicitly leave deployed host, persistent production storage, remote providers, production DB, RPO/RTO, and seven-day operation unverified. No concrete lifecycle defect found in reviewed local code; no production claim follows.
- Required changes and follow-up commit: no source change identified by this review. Before deployment, verify mount/service behavior on the target host and complete production backup/restore and remote-provider acceptance; refresh review after any code change.

## Source review

- [x] Trace `gateway/gpu_gateway/worker.py` claim, lease renewal, intent
  persistence, provider start, handle persistence, inspect, result persistence,
  cancellation, cleanup, and slot release.
- [x] Trace `gateway/gpu_gateway/store.py` transaction boundaries, control-row
  invariants, migrations, and lease-token fencing.
- [x] Trace `gateway/gpu_gateway/local_backend.py` start/inspect/cancel behavior
  and `gateway/gpu_gateway/container_runtime.py` identity and cleanup checks.
- [x] Trace `gateway/gpu_gateway/artifacts.py` atomic writes, manifest binding,
  owner scoping at the API boundary, pruning, and failure behavior.
- [x] Trace `gateway/gpu_gateway/experiment_api.py` owner checks and ensure
  status/readiness never report missing or stale control state as executable.
- [x] Trace `gateway/gpu_gateway/owner_migration.py` preflight, filesystem copy
  ordering, complete source-row snapshot revalidation before destination-scope
  installation, DB transaction, rerun behavior, and OAuth credential revocation.
- [x] Search all other callers of the reviewed functions. Confirm that the
  conclusion covers the canonical MCP path and does not silently generalize to
  the GitHub comment bridge or remote providers.

Source/caller notes: `protocol.py` dispatches canonical MCP tools to
`experiment_api.invoke`; `app.py` exposes readiness and MCP route. Worker
construction callers are `gateway/modal_worker.py` and worker CLI in
`worker.py`; reviewed local recovery calls backend `start/reconcile/capture/
cancel/cleanup/is_clean`. `ci_bridge.py` and `gateway/scripts/comment_bridge.py`
are separate GitHub-comment path and are not covered. `registry.py` and
`backends.py` retain remote adapters behind provider registration; their
behavior is explicitly outside this local CPU review.

## Required failure-boundary analysis

For each row, cite the relevant code and existing acceptance/test evidence. If
the evidence is simulated or uses a fake backend, say so explicitly.

| Failure boundary | Required conclusion | Existing evidence to inspect (evidence pointer, not a conclusion) | Reviewer finding |
| --- | --- | --- |
| Worker exits after container start, before handle persistence | Same run is reconciled; no duplicate start | Real local Docker: `test_os_worker_crash_after_container_start_reconciles_same_run`; fake-backend cases in `gateway/tests/test_worker_recovery.py` | Supported for local Docker by named acceptance in `docs/acceptance/2026-10-28-recovery-supervisor.md` and artifact acceptance; `worker.py` records intent before start and non-queued recovery calls reconcile, not start. Fake cases are not provider proof. |
| Worker lease expires while provider start is still in flight | Late handle is persisted safely; stale worker cannot overwrite newer state | Fake-backend concurrency in `gateway/tests/test_service.py`; stale fencing in `gateway/tests/test_worker_recovery.py` | `worker.py` persists a returned handle only if DB handle remains NULL; subsequent state/result writes require lease token. Tests are fake backend; no remote-provider guarantee. |
| Result captured but database write fails | Resource and slot remain tracked until durable result and cleanup | Fake backend `test_result_database_write_failure_keeps_container_and_slot_for_retry`; local PostgreSQL `test_postgres_outage_after_capture_retains_resource_and_recovers` | Supported by named PostgreSQL lifecycle acceptance and fake regression: captured result is retried while resource/slot remain tracked. Disposable local PostgreSQL only. |
| Result persisted but cleanup fails or supervisor exits | Replacement recovery uses saved result/handle; no false success or premature slot release | Fake cleanup crash test in `gateway/tests/test_recovery_supervisor.py`; local Docker reconcile test above | `worker.py` uses saved result when cleanup_state=pending; `finish()` releases slot only after cleanup. Supervisor crash fixture is fake; Docker test covers start-crash path, not every cleanup crash. |
| Cancellation or deadline races with successful exit | Terminal state follows persisted intent and cleanup proof | `test_timeout_terminal_intent_survives_cleanup_failure`; local Docker cancellation in recovery supervisor acceptance | `worker.py` sets cancellation intent before observation and persists cleanup pending; acceptance documents timeout regression. Local Docker integration evidence only. |
| Provider outcome cannot be observed | State remains unknown; no blind resubmission | `test_submission_timeout_never_blindly_retries`, `test_reconciliation_recovers_handle_without_resubmission` in `gateway/tests/test_service.py` | Unknown remains `submit_unknown`; recovery reconciles. Test backend is fake; does not establish remote-provider behavior. |
| Artifact write/manifest persistence is interrupted | No unsupported artifact is advertised; safe retry or cleanup is defined | Injected `OSError` fake-backend `test_artifact_storage_failure_fails_run_but_cleans_terminal_container`; real Docker artifact retrieval in `test_os_worker_crash_after_container_start_reconciles_same_run` | `artifacts.py` writes temp+fsync+link and worker publishes manifest only after writes; failure acceptance says no metadata, cleanup pending retains slot. No real full-volume test. |
| Artifact backup archive contains traversal paths, links, duplicate names, or unsupported members | Verification rejects it before restore; extraction cannot escape the target artifact directory | `test_artifact_archive_rejects_unsafe_member_paths`, `test_artifact_archive_rejects_non_regular_members` in `gateway/tests/test_backup_generation.py` | Backup generator validates opaque layout before restore and never extracts during verification; local archive fixtures only. `docs/acceptance/2026-10-28-atomic-backup-generation.md` still labels production acceptance NOT RUN. |
| Database is unavailable or control singleton is missing | Readiness and capabilities fail closed with an actionable blocker | `test_capabilities_fail_closed_when_control_store_is_unavailable`; PostgreSQL outage test | `experiment_api.py` makes control_store false for query error/missing row, blocks local CPU; `store.py` lock_control raises if absent. PostgreSQL outage evidence is disposable local DB. |
| Worker heartbeat age is exactly 15 seconds | Readiness and supervisor recovery both classify it as stale | `test_heartbeat_threshold_is_shared_and_inclusive_for_recovery`; supervisor readiness tests | `health.py` uses age <15 fresh and >=15 stale, shared by readiness/claim. Existing tests named in `gateway/tests/test_health.py` and `test_recovery_supervisor.py`. |
| Another owner requests a run/result/artifact | No run or blob data crosses the owner boundary | API ownership tests and artifact owner/unlisted-ID tests | API routes resolve owned run before result/artifact; artifact ID must be in stored manifest and terminal+clean. `artifacts.py` scopes by owner/run digest. Evidence is local API fixture, not real ChatGPT multi-conversation. |
| External OIDC token/JWKS endpoint returns oversized or ambiguous JSON | Authentication fails closed within the bounded response size | Injected stream tests in `gateway/tests/test_external_auth.py` | Tests bound reads and reject ambiguous payloads; no live identity provider exercised. Not production IdP proof. |
| Issuer migration stops during artifact copy or before/after the DB commit, or source result changes during copy | Changed source snapshot refuses before destination installation; old owner remains usable before commit; retry is safe; after commit the new owner is usable and old credentials are revoked | SQLite regression plus disposable PostgreSQL SIGKILL evidence in `docs/acceptance/2026-10-28-owner-issuer-migration.md` | `owner_migration.py` fsyncs/copies rollback+staging first, locks/recompares full source rows before destination rename/owner transaction, revokes OAuth tokens/sessions/codes/clients. Evidence explicitly local fixtures; production and independent acceptance previously NOT RUN. |

## Acceptance boundary

- [x] Confirm local Docker evidence is identified as local CPU evidence only.
- [x] Confirm fake-backend crash tests are not presented as real-provider proof.
- [x] Confirm no claim is made about target-host restart, persistent production
  storage, remote provider recovery, timed RPO/RTO, or seven-day operation.
- [x] Confirm the capacity monitor targets the configured artifact mount while
  API/worker/supervisor remain available if it is missing; local CPU admission
  must fail closed without blocking recovery/cancellation.
- [x] Confirm `policies/repository-state.yaml` remains `parked`; this review does
  not activate paid/GPU paths or authorize provider calls.
- [x] Record any required code changes separately and review the resulting new
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

`2026-10-28-recovery-review-handoff.md` records a point-in-time HEAD and
worktree-diff hash to help the reviewer identify the prepared snapshot. It is
implementation-author material, excludes itself from the untracked-file hash
list, and is not independent review evidence. Refresh the manifest and inspect
the live worktree when review begins.
