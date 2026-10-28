# Release acceptance matrix

This matrix reports evidence on the current working branch. It does not infer
readiness from mocks, source inspection, or a green test suite alone.

| Axis | Status | Current evidence | Remaining acceptance |
| --- | --- | --- | --- |
| `MCP_CONNECTIVITY` | UNCERTAIN | Public Vercel production remains on pre-vertical main SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. PR #51 preview head `e67eb72` passes `/healthz` HTTP 200, but `/readyz` returns 503 with all dependencies false; OAuth discovery and `/mcp` return `configuration_required`. No ChatGPT OAuth or tool scan has completed. | Configure and verify a reviewed persistent deployment with DB, OIDC, registry, worker and supervisor; complete production backup/restore gates; obtain independent PR review and authorized deployment; then complete real OAuth and tool discovery/calls in the intended ChatGPT account. |
| `CHATGPT_TOOL_USABILITY` | UNCERTAIN | Canonical experiment tools implement prepare/submit/status/result/artifact/cancel/list contracts and have service-level tests. | Complete a real CPU run through ChatGPT without CLI/Issue interaction, including a second conversation; record it in [`docs/CHATGPT_ACCEPTANCE.md`](CHATGPT_ACCEPTANCE.md). |
| `CPU_EXECUTION` | PASS (local lane only) | Revalidated 2026-10-28 at implementation commit `f15ab32`: digest-pinned CPU container ran on OrbStack with bounded runtime, source/image/result binding, authenticated MCP path and cleanup; Gateway suite with real Docker/PostgreSQL integrations: 274 passed, 2 optional Torch/Modal skips. The same code diff is in PR #51 head `89ea42e`; all four GitHub Actions checks passed and Vercel built its preview to READY. Exact local environment and scope: [`2026-10-28-local-integration-revalidation.md`](acceptance/2026-10-28-local-integration-revalidation.md). | Repeat on the selected persistent deployment host and workload; current evidence is local and not seven-day operational acceptance. |
| `FREE_GPU_EXECUTION` | BLOCKED | No GPU backend has been live-verified with device, quota, additional-cost, cancellation, and cleanup evidence. | Verify an eligible provider/account and run a bounded real GPU smoke with cost and cleanup proof; preserve `FREE_FIRST` gates. |
| `PAID_GPU_EXECUTION` | BLOCKED | Paid mode remains parked; no current exact human authorization or live provider execution. | Complete P5 controls and obtain separate explicit authorization for a bounded canary before any spend. |
| `RECOVERY` | PASS (local CPU lane only) | In addition to the crash-reconcile and local paired restore evidence, 2026-10-28 full revalidation passed the real PostgreSQL outage-after-capture test: the same Docker run remained reserved through DB outage, was recovered after PostgreSQL restart, and its result/artifact were read back. The same code diff passed GitHub Gateway offline CI at PR #51 head `89ea42e`. Fixed loopback port was required for reliable OrbStack stop/start. See [`2026-10-28-local-integration-revalidation.md`](acceptance/2026-10-28-local-integration-revalidation.md). | Exercise the selected deployed host and provider; verify the full crash matrix and no duplicate resources there. Production backup retention, target-host recovery and measured RPO/RTO remain open. |
| `CANCELLATION` | PASS (local CPU lane only) | Existing CPU container was cancelled and removed by the recovery supervisor while execution-worker ticks were stopped. | Repeat against the deployment host and, for GPU, its real provider resource. |
| `RESULT_RETRIEVAL` | UNCERTAIN | A real digest-pinned local CPU smoke run emits a validated JSON report; worker recovery persists it to owner-scoped storage and retrieves its exact bytes. PostgreSQL outage recovery preserves the run; artifact chunk API/storage tests and local shared-volume checks pass. A separate synthetic paired PostgreSQL 16 dump/artifact archive restore retrieved the restored bytes through the owner-scoped application path and rejected an unrelated owner. No deployed API or real ChatGPT conversation was used. | Verify an actual run and exact plan/source binding from a second ChatGPT conversation, including returned artifact digest and bytes; test a deployed persistent volume and set a quota/alert policy. See `docs/acceptance/2026-10-28-artifact-storage.md` and `docs/acceptance/2026-10-28-paired-artifact-restore.md`. |
| `SECURITY` | UNCERTAIN | A focused read-only security review found built-in OAuth authorization-code issuance on GET without owner consent. Commit `bf01d12` adds client/scope/redirect consent and requires same-origin CSRF-protected POST; local Gateway suite passes 268 tests with 8 optional integration skips and all four GitHub Actions pass at this head. The fix has not received independent post-fix review or live ChatGPT acceptance. Owner scoping, local CPU admission, Docker hardening, and bounded outbound HTTP checks have local evidence. | Independently re-review the exact OAuth consent fix, complete deployed OAuth/owner-boundary acceptance, target-host permissions review, live provider compatibility checks, and operational security checks. This is scoped evidence, not a claim of complete safety. |

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
