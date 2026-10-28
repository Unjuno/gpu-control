# Release acceptance matrix

This matrix reports evidence on the current working branch. It does not infer
readiness from mocks, source inspection, or a green test suite alone.

| Axis | Status | Current evidence | Remaining acceptance |
| --- | --- | --- | --- |
| `MCP_CONNECTIVITY` | UNCERTAIN | Rechecked 2026-10-28: public Vercel `/healthz` and OAuth discovery return 200, `/readyz` returns 404, and unauthenticated `/mcp` returns 401. Live authorization metadata advertises PKCE S256, refresh tokens and `offline_access`; Vercel reports the latest READY production deployment is still pre-vertical `main` SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, with SSO enabled except on custom domains. A local PostgreSQL 16 v1-to-v6 rehearsal preserved synthetic run and OAuth state; local code now adds unverified v6-to-v7 OAuth grant migration/revocation. No ChatGPT OAuth or tool scan has completed. | Independently review the migration, validate paired production backup/restore, then deploy the reviewed CPU vertical with persistent worker/database/artifact storage and complete real OAuth and tool discovery/calls in the intended ChatGPT account. |
| `CHATGPT_TOOL_USABILITY` | UNCERTAIN | Canonical experiment tools implement prepare/submit/status/result/artifact/cancel/list contracts and have service-level tests. | Complete a real CPU run through ChatGPT without CLI/Issue interaction, including a second conversation; record it in [`docs/CHATGPT_ACCEPTANCE.md`](CHATGPT_ACCEPTANCE.md). |
| `CPU_EXECUTION` | PASS (local lane only) | Digest-pinned CPU container ran on OrbStack Linux/arm64 with bounded runtime, isolation settings, result binding, and cleanup. See `docs/acceptance/2026-10-28-recovery-supervisor.md` and `docs/IMPLEMENTATION_PROGRESS.md`. | Repeat on the selected persistent deployment host and workload; current evidence is local and not seven-day operational acceptance. |
| `FREE_GPU_EXECUTION` | BLOCKED | No GPU backend has been live-verified with device, quota, additional-cost, cancellation, and cleanup evidence. | Verify an eligible provider/account and run a bounded real GPU smoke with cost and cleanup proof; preserve `FREE_FIRST` gates. |
| `PAID_GPU_EXECUTION` | BLOCKED | Paid mode remains parked; no current exact human authorization or live provider execution. | Complete P5 controls and obtain separate explicit authorization for a bounded canary before any spend. |
| `RECOVERY` | PASS (local CPU lane only) | Real Docker recovery reconciled the same run after execution-worker exit before handle persistence. PostgreSQL restart and supervisor restart during `cleanup_pending` are covered. The latter process-exit boundary uses a fake backend. Timeout-cancellation intent is retained through a cleanup failure. A local PostgreSQL 16 paired backup tool now stages DB and artifact archives together, checksums and validates them, publishes atomically, and was exercised through separate-target restoration and owner-scoped artifact byte readback; injected archive failure published no partial generation. See `docs/acceptance/2026-10-28-atomic-backup-generation.md`. | Exercise the selected deployed host and provider; verify the full crash matrix and no duplicate resources there. Production backup retention, target-host recovery and measured RPO/RTO remain open. |
| `CANCELLATION` | PASS (local CPU lane only) | Existing CPU container was cancelled and removed by the recovery supervisor while execution-worker ticks were stopped. | Repeat against the deployment host and, for GPU, its real provider resource. |
| `RESULT_RETRIEVAL` | UNCERTAIN | A real digest-pinned local CPU smoke run emits a validated JSON report; worker recovery persists it to owner-scoped storage and retrieves its exact bytes. PostgreSQL outage recovery preserves the run; artifact chunk API/storage tests and local shared-volume checks pass. A separate synthetic paired PostgreSQL 16 dump/artifact archive restore retrieved the restored bytes through the owner-scoped application path and rejected an unrelated owner. No deployed API or real ChatGPT conversation was used. | Verify an actual run and exact plan/source binding from a second ChatGPT conversation, including returned artifact digest and bytes; test a deployed persistent volume and set a quota/alert policy. See `docs/acceptance/2026-10-28-artifact-storage.md` and `docs/acceptance/2026-10-28-paired-artifact-restore.md`. |
| `SECURITY` | UNCERTAIN | Input contracts, owner scoping, local CPU admission, Docker hardening, bounded OIDC/GitHub/RunPod HTTP responses, redirect rejection, and targeted adversarial/recovery tests exist. RunPod adapters recheck permit, price freshness, and occupancy immediately before create; injected-clock tests prove stale evidence prevents create. No live identity-provider or RunPod API was exercised. | Complete independent provider-independent review, deployed OAuth/owner-boundary acceptance, target-host permissions review, live provider compatibility checks, and operational security checks. This is scoped evidence, not a claim of complete safety. |

## Operational gates

- P2 recovery work remains in progress: durable owner-scoped artifact storage
  and local CPU report retrieval are implemented and locally exercised;
  provider-independent recovery review, deployed storage/quota controls, and
  ChatGPT retrieval acceptance remain incomplete. Unsupported artifacts must
  not be represented as retrievable.
- P3 remains pending: systemd units are templates only; there is no selected
  deployed Gateway/worker host, real ChatGPT connection, seven-day observation,
  or timed production restore drill. The local synthetic paired restore in
  `docs/acceptance/2026-10-28-paired-artifact-restore.md` does not establish
  production backup controls, owner/OAuth parity, or worker reconciliation.
  The atomic backup generation drill in
  `docs/acceptance/2026-10-28-atomic-backup-generation.md` is also local-only;
  encrypted off-host retention, second-operator restore, and timed production
  recovery are still required.
  The existing Neon production branch has no schema-version table and has not
  been migrated; only zero aggregate run/active-slot counts were queried. Review
  the migration and production backup/restore plan before any database change.
- Paid and GPU paths stay parked until their separate evidence and authorization
  gates are satisfied. Local CPU evidence does not satisfy either gate.

Update this table only when new evidence is produced. Link acceptance artifacts
and state the scope of each PASS.
