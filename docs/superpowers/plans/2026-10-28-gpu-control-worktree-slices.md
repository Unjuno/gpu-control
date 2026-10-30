# Current worktree review slices

Snapshot: branch `codex/chatgpt-cpu-vertical`, base `f054aebe96460fe033dde8d91d7e3bbab0255655`, 2026-10-28; refreshed after the schema-v8 isolated systemd backup/restore drill.
This is a file-ownership map for independent review, not a claim that these changes are approved or ready to merge.
It supersedes the earlier 63-path inventory in the Luna handoff. No files are staged, committed, pushed, or deployed.

Inventory revalidation (2026-10-28): `git diff --name-only` reported 75 tracked
paths and `git ls-files --others --exclude-standard` reported 42 untracked
paths. A path-set audit against the lists below found exactly 117 actual paths,
117 unique ownership entries, no missing/stale paths, and no duplicates.
`git diff --check` passed. GitHub currently reports PR #51 OPEN/DRAFT at this
base/head, `REVIEW_REQUIRED`, with 121 files in its full base-to-head diff;
that remote PR inventory is separate from these 116 uncommitted worktree paths.
No repository or GitHub mutation was performed during this audit.

Latest snapshot revalidation (2026-10-28 11:38 UTC): the worktree has 75
tracked modified/deleted paths and 42 untracked paths (117 total), with zero
staged paths. A fresh path-set comparison found 117 assigned paths, no missing
or stale entries, and `git diff --check` passed. Root suite: 550 passed / 1
skipped. Full Gateway suite with a locally built CPU image and disposable
PostgreSQL 16 on fixed loopback port 55499: 423 passed / 2 optional Torch/Modal
skips. A separate synthetic schema-v8 backup/restore drill used an actual
systemd manager in disposable Ubuntu 24.04 and separate PostgreSQL 16 source
and target instances; generation verification and restore state checks passed.
PR #51 remains OPEN/DRAFT at remote head `f054aebe`; review and inline-thread
queries are empty. The latest combined-status response exposed only Vercel
success; it does not establish the other workflow states. A read-only GitHub branch metadata query confirms
`main` protected with the seven required CI contexts; the dedicated protection
endpoint returns 403 to this connector, so detailed review rules rely on the
earlier 09:44 settings readback recorded in `docs/BASELINE_AUDIT.md`. No
worktree changes are covered by those GitHub checks.

| Review order | Slice | Paths | Review boundary / acceptance evidence |
|---:|---|---:|---|
| 1 | P1 OAuth refresh rotation, scope validation, and PostgreSQL concurrent use | 4 | Check atomic rollback, one-time refresh, and owner/scope boundaries. Offline evidence only; real ChatGPT OAuth remains NOT RUN. |
| 2 | P3 artifact readiness, backup/recovery, systemd identities, and capacity bridge | 48 | Review together with the current operational docs. Validate local tests and guarded Linux unit checks; no target host, sink, quota, or alert acceptance. |
| 3 | P4 RunPod v2 API contract, provider observations, candidate selection, result receipts, worker revalidation, and shared P1 T2 Gateway tool contract | 50 | Review exact-resource/fingerprint/expiry checks and every unknown-evidence refusal. Also review the newly added outputSchema/status-log projection together with the pre-existing P4 changes in shared `experiment_api.py` and its tests. No candidate backend is accepted, no live provider call or GPU run occurred. |
| 4 | P5 paid authority design and policy gate | 3 | Review the trust chain and ensure the repository remains parked. Design only; no issuer, permit, spending, or live provider authorization is implemented. |
| 5 | Cross-cutting acceptance and Luna handoff | 12 | Reconcile status wording only after code slices are reviewed; preserve evidence scope and current blockers. |

The counts sum to the exact current 117-path changed inventory, including this map file and the updated SDD progress ledger. Each path appears in exactly one slice below. `docs/acceptance/2026-10-28-neon-first-schema-migration.md` was added to the cross-cutting evidence slice for the read-only production-state refresh. The v8 restore refresh is assigned to the P3 operational slice. The two earlier paths in that review refresh were `gateway/gpu_gateway/protocol.py` and `docs/specs/chatgpt-native-experiment-control-plane.md`; the P1 status-log overlay also touches P4-owned `experiment_api.py` and its existing test file, so their full combined diff remains within the P4 single-owner slice.
Review sequentially because several contracts span Gateway, core, migrations, and tests. Keep shared files wholly within their assigned slice.

## P1 — OAuth refresh and PostgreSQL concurrency (4 paths)

Current implementation self-check (2026-10-28): scope-narrowing validation
occurs before refresh-token revocation; revocation and replacement access /
refresh insertion share one SQLAlchemy transaction. The injected insertion
failure regression verifies rollback/retry on SQLite, and the PostgreSQL race
regression verifies exactly one concurrent refresh succeeds while the loser
receives `invalid_grant`. Current full Gateway/PostgreSQL 16 suite passed 418
tests with two optional SDK skips. No source defect was identified in this
self-check. This is not the independent reviewer gate; live ChatGPT OAuth and
production database behavior remain unverified.

Current-worktree follow-up (2026-10-28): added and ran the PostgreSQL
replacement-insert failure regression on the digest-pinned PostgreSQL 16
image. Failure during refresh-token insertion rolled back the replacement
access row and original-token revocation; retry succeeded. Focused OAuth HTTP
and token modules passed 37 tests. Evidence:
`docs/acceptance/2026-10-28-oauth-refresh-atomicity.md`.

- `docs/acceptance/2026-10-28-oauth-refresh-atomicity.md`
- `gateway/gpu_gateway/local_oauth.py`
- `gateway/tests/test_local_oauth.py`
- `gateway/tests/test_postgresql.py`

## P3 — CPU operations, artifact storage, and recovery (47 paths)

Current artifact-boundary self-check (2026-10-28): the store derives an opaque
scope from owner + run ID and hashes artifact IDs into filenames; the tool
resolves the run under the authenticated owner before storage access. Reads
check regular-file type, exact manifest size and SHA-256, then return bounded
chunks. Existing regressions cover cross-owner denial, unlisted/expired IDs,
symlink and write-probe failures, content mismatch, and bounded retrieval. The
current full Gateway/PostgreSQL 16 integration run passed 418 tests; the
focused P3 artifact/capacity/deploy regression set passed 92 tests, and the
guarded Linux helper verified all eight systemd service/timer templates in
Debian 12/systemd 252.39. No source defect was identified in this self-check.
It is not an independent review and does not prove target-host filesystem
permissions, mount filtering, race behavior, quota, or production acceptance.

Current-worktree follow-up (2026-10-28): backup-generation tests now inject
failure in both `pg_dump` and `pg_restore --list` and verify that no partial
generation or staging directory is published. Focused backup-generation suite:
22 passed, one existing Starlette deprecation warning. Evidence:
`docs/acceptance/2026-10-28-atomic-backup-generation.md`.

Artifact permission migration follow-up: injected a mid-apply `chown` failure,
verified payload preservation, and reran the migration to the exact final mode
contract. Focused migration suite: 9 passed, one existing Starlette
deprecation warning. Evidence: `docs/acceptance/2026-10-28-artifact-storage.md`.

Capacity delivery ordering follow-up: fixed a retry window that could allow a
later clear to overtake a failed alert within or between pump batches. The
focused capacity state suite passed 40 tests; evidence is recorded in
`docs/acceptance/2026-10-28-capacity-bridge-regression.md`.

- `.github/workflows/gateway-ci.yml`
- `docs/OPERATIONS.md`
- `docs/acceptance/2026-10-28-artifact-storage.md`
- `docs/acceptance/2026-10-28-atomic-backup-generation.md`
- `docs/acceptance/2026-10-28-capacity-bridge-health-cli.md`
- `docs/acceptance/2026-10-28-capacity-bridge-regression.md`
- `docs/acceptance/2026-10-28-capacity-retention-reconciliation.md`
- `docs/acceptance/2026-10-28-linux-capacity-poll-lock.md`
- `docs/acceptance/2026-10-28-local-integration-revalidation.md`
- `docs/acceptance/2026-10-28-paired-artifact-restore.md`
- `docs/acceptance/2026-10-28-recovery-drill-record-template.md`
- `docs/acceptance/2026-10-28-recovery-regression-refresh.md`
- `docs/acceptance/2026-10-28-systemd-uid-boundary.md`
- `docs/decisions/2026-10-28-p3-deployment-topology.md`
- `docs/specs/capacity-alert-bridge-contract.md`
- `docs/superpowers/plans/2026-10-28-systemd-ci-verification.md`
- `gateway/README.md`
- `gateway/deploy/api.env.example`
- `gateway/deploy/backup_generation.py`
- `gateway/deploy/capacity-event.schema.json`
- `gateway/deploy/capacity.env.example`
- `gateway/deploy/capacity_event_bridge.py`
- `gateway/deploy/capacity_event_delivery.py`
- `gateway/deploy/capacity_event_state.py`
- `gateway/deploy/check_artifact_capacity.py`
- `gateway/deploy/gateway.env.example`
- `gateway/deploy/gpu-control-api.service`
- `gateway/deploy/gpu-control-artifact-capacity.service`
- `gateway/deploy/gpu-control-capacity-bridge.service`
- `gateway/deploy/gpu-control-db-check.service`
- `gateway/deploy/gpu-control-db-migrate.service`
- `gateway/deploy/gpu-control-supervisor.service`
- `gateway/deploy/gpu-control-worker.service`
- `gateway/deploy/migrate_artifact_permissions.py`
- `gateway/deploy/verify_systemd_units_ci.sh`
- `gateway/deploy/worker-secrets.env.example`
- `gateway/deploy/worker.env.example`
- `gateway/gpu_gateway/app.py`
- `gateway/gpu_gateway/artifacts.py`
- `gateway/tests/test_artifact_permission_migration.py`
- `gateway/tests/test_artifact_storage.py`
- `gateway/tests/test_backup_generation.py`
- `gateway/tests/test_capacity_event_state.py`
- `gateway/tests/test_deploy_units.py`
- `gateway/tests/test_http_auth.py`
- `gateway/tests/test_local_lifecycle_integration.py`
- `gateway/tests/test_local_mcp_integration.py`
- `gateway/tests/test_postgres_lifecycle_integration.py`

## P4 — Provider evidence, selection, GPU contracts, and shared P1 T2 Gateway tool contract (50 paths)

- `docs/acceptance/2026-10-28-result-plan-binding.md`
- `docs/acceptance/2026-10-28-runpod-api-v2-revalidation.md`
- `docs/decisions/2026-10-28-p4-modal-readiness.md`
- `docs/specs/chatgpt-native-experiment-control-plane.md`
- `docs/specs/p4-candidate-execution-receipt-contract.md`
- `docs/specs/p4-capability-selection-contract.md`
- `gateway/deploy/provider-evidence.env.example`
- `gateway/gpu_gateway/admission.py`
- `gateway/gpu_gateway/backends.py`
- `gateway/gpu_gateway/candidate_receipts.py`
- `gateway/gpu_gateway/config.py`
- `gateway/gpu_gateway/contracts.py`
- `gateway/gpu_gateway/experiment_api.py`
- `gateway/gpu_gateway/migrations.py`
- `gateway/gpu_gateway/modal_evidence.py`
- `gateway/gpu_gateway/provider_evidence.py`
- `gateway/gpu_gateway/provider_selection.py`
- `gateway/gpu_gateway/protocol.py`
- `gateway/gpu_gateway/registry.py`
- `gateway/gpu_gateway/runpod_inventory.py`
- `gateway/gpu_gateway/service.py`
- `gateway/gpu_gateway/store.py`
- `gateway/gpu_gateway/worker.py`
- `gateway/tests/test_candidate_receipts.py`
- `gateway/tests/test_candidate_result_read.py`
- `gateway/tests/test_contracts_v2.py`
- `gateway/tests/test_experiment_api.py`
- `gateway/tests/test_local_admission.py`
- `gateway/tests/test_local_backend.py`
- `gateway/tests/test_migrations.py`
- `gateway/tests/test_modal_evidence.py`
- `gateway/tests/test_provider_evidence.py`
- `gateway/tests/test_registry.py`
- `gateway/tests/test_runpod_inventory.py`
- `policies/runpod-v2-policy.yaml`
- `src/gpu_control/capabilities.py`
- `src/gpu_control/providers/runpod_adapter.py`
- `src/gpu_control/providers/runpod_current_pricing.py`
- `src/gpu_control/providers/runpod_network_volume_payload.py`
- `src/gpu_control/providers/runpod_pricing.py`
- `src/gpu_control/providers/runpod_v2.py`
- `src/gpu_control/selection.py`
- `src/gpu_control/workloads.py`
- `tests/test_capabilities.py`
- `tests/test_prompt_context_security.py`
- `tests/test_runpod_adapter.py`
- `tests/test_runpod_network_volume_payload.py`
- `tests/test_runpod_v2.py`
- `tests/test_runpod_v2_policy.py`
- `tests/test_selection.py`

## P5 — Paid authority and parked-mode boundary (3 paths)

- `docs/specs/p5-gateway-runpod-permit-bridge.md`
- `policies/repository-state.yaml`
- `tests/test_repository_state.py`

## Cross-cutting evidence and Luna handoff (12 paths)

- `docs/BASELINE_AUDIT.md`
- `docs/CHATGPT_ACCEPTANCE.md`
- `docs/CHATGPT_SETUP.md`
- `docs/IMPLEMENTATION_PROGRESS.md`
- `docs/acceptance/2026-10-28-neon-first-schema-migration.md`
- `docs/RELEASE_MATRIX.md`
- `docs/STATUS.md`
- `docs/superpowers/plans/2026-10-28-gpu-control-first-vertical.md`
- `docs/superpowers/plans/2026-10-28-gpu-control-luna-handoff.md`
- `docs/superpowers/plans/2026-10-28-gpu-control-roadmap.md`
- `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`
- `.superpowers/sdd/2026-10-28-gpu-control-first-vertical/progress.md`

## Suggested verification order

1. OAuth targeted modules and PostgreSQL one-time refresh regression, then the full Gateway suite with a stoppable PostgreSQL 16 container and digest-pinned CPU image.
2. P3 artifact/backup/capacity tests, `git diff --check`, and the guarded `systemd-analyze verify` helper in an isolated Linux runner. Do not treat this as target-host acceptance.
3. Root/core suite for P4 selector and RunPod v2 contracts; inspect candidate receipt/result tests separately from provider attestation claims.
4. Confirm `policies/repository-state.yaml` is still `parked`; no provider credentials, public settings, spend, or deployment changes.
5. Refresh the full-worktree inventory and exact content digest after any review fix. Run GitHub CI/security review only on the final composed revision before integration.

Current product gates still requiring owner/environment input: intended ChatGPT workspace write-action entitlement and access; selected Linux host, region, public origin, and cost ceiling; notification sink/route/SLO; account-specific free-GPU/quota evidence. Those gates do not stop the offline review work but they prevent claiming live acceptance.
