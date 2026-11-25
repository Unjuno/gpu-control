# Current worktree to PR stack reconciliation — 2026-10-31 02:24 UTC

## Scope and method

- Checkout at initial comparison: `codex/chatgpt-cpu-vertical` at `a794438f42bd7246f463eaaa40d963af0aae9d13`; that comparison contained 91 dirty paths. The 2026-10-31 02:40 UTC inventory delta below updates the current total to 92.
- Compared each dirty file content blob to every existing PR #51–#59 head, and compared each file path to that PR’s exact base-to-head changed-path set. This is a local content/path comparison against the live GitHub PR metadata refreshed for this report.
- Classes: `EXACT_HEAD_BLOB` means the dirty file bytes equal that PR head’s blob for a path changed by that PR; `SAME_PATH_DIVERGED` means an existing PR changes that path but no owning PR head has the current dirty bytes; `NOT_IN_PR_SLICE` means the path is absent from the changed-path sets of #51–#59. These labels do not imply review, approval, or mergeability.

## Summary

- Exact match to an existing slice head: **6**.
- Same path as an existing slice, but dirty content differs from its head: **39**.
- Not present in any current #51–#59 base-to-head slice: **47**.
- The local tree cannot be placed on an existing PR stack by blindly copying or pushing the current aggregate. Recompute review slices from this exact tree, preserving the stack dependencies and obtaining fresh CI/review for each proposed head.

## Current PR slices

| PR | Base | Head | Changed paths | Review |
|---:|---|---|---:|---|
| #51 | `codex/gpu-control-p1-04-cpu-oauth-recovery` `51b88f6110e2` | `codex/chatgpt-cpu-vertical` `e3ffcef580d4` | 127 | none submitted |
| #52 | `main` `24ecb9bba026` | `codex/gpu-control-p1-05-recovery` `bc9b0305e6b2` | 43 | REVIEW_REQUIRED |
| #53 | `codex/gpu-control-p1-05-recovery` `bc9b0305e6b2` | `codex/gpu-control-p2-01-recovery-readiness` `f8ee5d08be7c` | 19 | none submitted |
| #54 | `codex/gpu-control-p2-01-recovery-readiness` `f8ee5d08be7c` | `codex/gpu-control-p2-02-artifact-read` `113d7bf22665` | 21 | none submitted |
| #55 | `codex/gpu-control-p2-02-artifact-read` `113d7bf22665` | `codex/gpu-control-p2-03-readiness-heartbeat` `dc109cba978e` | 38 | none submitted |
| #56 | `codex/gpu-control-p2-03-readiness-heartbeat` `dc109cba978e` | `codex/gpu-control-p1-03-http-security` `34cc58c08f9a` | 25 | none submitted |
| #57 | `codex/gpu-control-p1-03-http-security` `34cc58c08f9a` | `codex/gpu-control-p1-04-cpu-oauth-recovery` `51b88f6110e2` | 54 | none submitted |
| #58 | `codex/chatgpt-cpu-vertical` `e3ffcef580d4` | `codex/gpu-control-p1-dcr-v9-review` `561a6c7ac697` | 7 | none submitted |
| #59 | `codex/gpu-control-p1-04-cpu-oauth-recovery` `51b88f6110e2` | `codex/gpu-control-p3-ops-candidate` `76c2a1a1b443` | 14 | none submitted |

All PRs #51–#59 currently report nine successful status-rollup entries:
seven Actions checks, Vercel deployment, and Vercel Preview Comments. The PR
descriptions are not all current: #51's body says #57 CI is incomplete, while
the live #57 rollup has all nine entries successful. #59's body names an older
candidate head (`9617d56`) and a 13-path diff; the current live head is
`76c2a1a1b4439cf093c4e6efdd39d5121eb08959` and its base-to-head diff/API list
has 14 paths. Refresh those descriptions before inviting human review, without
changing PR metadata as part of this local audit.

## Current local inventory delta — 2026-10-31 02:40 UTC

- Recounted the live worktree: **92 dirty paths** (49 modified tracked, 43
  untracked). The existing per-path table accounts for 91; the only unmapped
  path is this report itself.
- Added this report as `NOT_IN_PR_SLICE` below. Updated counts are 6 exact head
  blobs, 39 divergent paths overlapping existing PR slices, and 47 paths
  outside those slices. No source path is missing from the ownership map.
- `git diff --check` passes. These local changes remain outside published PR
  checks.

## P1 readiness review candidate replay — 2026-10-31 02:43 UTC

- Reconstructed the P1 readiness/OAuth evidence overlay in disposable detached
  worktree `/tmp/gpu-control-p1candidate-on-561a6c7`, based on exact PR #58
  head `561a6c7ac697dfdf22f304b60e313fccb2c806a4`.
- Patch `/tmp/gpu-control-slice-p1_oauth_readiness-on-561a6c7.patch`, SHA-256
  `853b4a7177318bcee87b1608b592ad54229bac6974accebeac8355cad5cc27c4`, passed
  `git apply --check`, applied cleanly, and passed `git diff --check`.
- The resulting review delta is seven paths: four tracked changes and three
  acceptance records, including the `/readyz` local CPU admission check and
  provenance/test-scope records. No tests were rerun here; this only verifies
  that the candidate patch reconstructs cleanly on the declared PR base. It
  still needs exact-head CI and independent review before it can be accepted.

## Exact full-tree review candidate and suite — 2026-10-31 12:10 JST

- Reconstructed `/tmp/gpu-control-exactfullcandidate-on-561a6c7` from exact
  PR #58 head `561a6c7ac697dfdf22f304b60e313fccb2c806a4` using a disposable
  index. The full-tree patch is
  `/tmp/gpu-control-exact-current-on-561a6c7-review.patch` (94 changed paths;
  its SHA-256 is reported with this update). The primary worktree and real Git index were
  not staged or modified by patch generation.
- Compared every tracked and untracked, non-ignored file in the primary
  worktree and candidate: **366 files matched byte-for-byte, zero different,
  zero missing, zero extra**. The full patch passed reverse `git apply
  --check` against that exact candidate, and the candidate passed
  `git diff --check`.
- Ran all candidate Gateway tests with imports directed into this candidate,
  a disposable PostgreSQL 16 container bound only to `127.0.0.1:55503`, and a
  local CPU smoke image built from its own Dockerfile. Gateway: **534 passed,
  2 optional skips** (Torch and Modal), one existing Starlette deprecation
  warning, in 28.23 seconds. Core: **559 passed, 1 Python-3.11-specific skip**
  in 1.35 seconds. The smoke image's OCI source revision was synthetic fixture
  `1212121212121212121212121212121212121212`; it is not a published source
  identity.
- The test database and image were removed, and port 55503 was confirmed
  closed. Repository policy remains `mode: parked`; no provider, GPU, paid
  execution, deployment, GitHub push, or PR update was performed. This exact
  tree is reproducible and locally tested, but GitHub CI/review and deployed
  ChatGPT acceptance remain outstanding.

## Full current-tree reconstruction artifact — 2026-10-31 02:33 UTC

- Generated `/tmp/gpu-control-main-current-20261031-reconciled.patch` from the
  exact current checkout using a disposable `GIT_INDEX_FILE`, based on
  `origin/main` at `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. The real index,
  branch, and primary worktree contents were not staged or changed by
  generation. It contains 219 changed paths; `git apply --check --reverse`
  against the source snapshot passed.
- This is a full reconstruction artifact, not a reviewable slice. It has no
  new independent test, GitHub CI, review, or deployment result. Use it to
  reproduce the exact current tree from main, then form sequential small
  review candidates from the path ownership and dependency evidence above.

## Exact PR #58-based review-slice replay — 2026-10-31 02:33 UTC

- Started from exact PR #58 head
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4` in a disposable detached
  worktree. Applied the six existing P1/P2/P3/P4/P5/cross-cutting slices,
  then five current additions (P1 readiness evidence, P3 deployment example,
  P4 credit lifecycle, P5 account-lease/authorization, and cross-cutting
  evidence), then four refresh overlays for P3 backup evidence, P4 contract,
  P5 worker/auth, and cross-cutting status documents.
- All patch `git apply --check` operations succeeded. The final replay tree
  exactly equaled the tree made from the primary checkout's current HEAD,
  tracked modifications, and untracked files: **94 changed paths, exact tree
  equality**. The disposable worktree was removed after comparison; the
  primary checkout and its index were not staged or changed.
- Exact patch paths are under `/tmp/gpu-control-slice-*-on-561a6c7.patch` and
  `/tmp/gpu-control-current-on-561-*.patch`. These patches provide a replayable
  review boundary map, not separate commits or GitHub PRs. This replay ran no
  tests; existing test records apply only to the scopes listed in their
  acceptance files. In particular, new account-lease and credit-authority
  wiring still needs fresh focused regression and independent review before
  it can be accepted. Paid and live-provider switches remain disabled.

## Per-path assignment

| Class | Path | Existing changed-path owner(s) | Dirty blob exactly matches head(s) |
|---|---|---|---|
| SAME_PATH_DIVERGED | `docs/BASELINE_AUDIT.md` | #51, #52, #57 | — |
| SAME_PATH_DIVERGED | `docs/CHATGPT_ACCEPTANCE.md` | #51, #56, #57 | — |
| SAME_PATH_DIVERGED | `docs/CHATGPT_SETUP.md` | #51, #53, #55, #57 | — |
| SAME_PATH_DIVERGED | `docs/IMPLEMENTATION_PROGRESS.md` | #51, #52, #53, #54, #55, #56 | — |
| SAME_PATH_DIVERGED | `docs/OPERATIONS.md` | #51, #53, #55, #57 | — |
| NOT_IN_PR_SLICE | `docs/PARKED_MODE.md` | — | — |
| SAME_PATH_DIVERGED | `docs/RELEASE_MATRIX.md` | #51, #54, #55, #56, #57 | — |
| NOT_IN_PR_SLICE | `docs/REPOSITORY_SECURITY.md` | — | — |
| SAME_PATH_DIVERGED | `docs/STATUS.md` | #51 | — |
| SAME_PATH_DIVERGED | `docs/acceptance/2026-10-28-atomic-backup-generation.md` | #51, #59 | — |
| SAME_PATH_DIVERGED | `docs/acceptance/2026-10-28-local-integration-revalidation.md` | #51 | — |
| SAME_PATH_DIVERGED | `docs/acceptance/2026-10-28-recovery-drill-record-template.md` | #51 | — |
| SAME_PATH_DIVERGED | `docs/acceptance/2026-10-28-systemd-uid-boundary.md` | #51 | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-30-current-worktree-source-matched-suite.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-30-dirty-source-paired-restore.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-cancel-dispatch-boundary.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-current-snapshot-full-suite.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-current-worktree-security-review.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p1-c817-source-provenance-suite.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p1-c824-candidate-suite.md` | — | — |
| SAME_PATH_DIVERGED | `docs/acceptance/2026-10-31-p1-dcr-persistence-schema-v9.md` | #58 | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p1-p3-integration-on-58.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p1-readiness-review-candidate-on-57.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p1-v9-source-matched-cpu-suite.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p3-cccf-package-candidate-suite.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p3-d794-candidate-suite.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p4-adapter-receipt-signer.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p4-credit-authorization-verifier.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p4-fake-candidate-lifecycle.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-account-lease-process-postgresql.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-account-lease-recovery-read.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-account-lease-security-review.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-account-lease-store-foundation.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-account-lease-worker-fencing.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-account-scope-key-config.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-account-scope-rotation-stability.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-paid-authorization-persistence-foundation.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-paid-authorization-verifier.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-runpod-lease-contract-gate.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-worker-account-lease-dispatch.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-worker-cleanup-lease-commit.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-p5-working-tree-security-diff.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-postgres-container-crash-recovery.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-pr51-full-current-candidate.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-working-tree-security-diff.md` | — | — |
| NOT_IN_PR_SLICE | `docs/acceptance/2026-10-31-pr-stack-reconciliation.md` | — | — |
| SAME_PATH_DIVERGED | `docs/decisions/2026-10-28-p3-deployment-topology.md` | #51, #59 | — |
| SAME_PATH_DIVERGED | `docs/decisions/2026-10-28-p4-modal-readiness.md` | #51 | — |
| SAME_PATH_DIVERGED | `docs/specs/p4-capability-selection-contract.md` | #51 | — |
| SAME_PATH_DIVERGED | `docs/specs/p5-gateway-runpod-permit-bridge.md` | #51 | — |
| SAME_PATH_DIVERGED | `docs/superpowers/plans/2026-10-28-gpu-control-luna-handoff.md` | #51, #52 | — |
| SAME_PATH_DIVERGED | `docs/superpowers/plans/2026-10-28-gpu-control-roadmap.md` | #51, #52, #55 | — |
| SAME_PATH_DIVERGED | `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md` | #51 | — |
| SAME_PATH_DIVERGED | `gateway/README.md` | #51, #53, #54, #55, #57 | — |
| EXACT_HEAD_BLOB | `gateway/deploy/backup_generation.py` | #51, #59 | #59 |
| SAME_PATH_DIVERGED | `gateway/deploy/worker-secrets.env.example` | #51 | — |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/admission.py` | #51, #52 | — |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/app.py` | #51, #53, #55, #57 | — |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/backends.py` | #51, #54 | — |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/config.py` | #51, #52, #54, #57 | — |
| NOT_IN_PR_SLICE | `gateway/gpu_gateway/credit_authorization_bridge.py` | — | — |
| EXACT_HEAD_BLOB | `gateway/gpu_gateway/local_oauth.py` | #51, #57, #58 | #58 |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/migrations.py` | #51, #52, #53, #55, #57, #58 | — |
| NOT_IN_PR_SLICE | `gateway/gpu_gateway/paid_authorization_bridge.py` | — | — |
| NOT_IN_PR_SLICE | `gateway/gpu_gateway/provider_account_scope.py` | — | — |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/registry.py` | #51, #52 | — |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/service.py` | #51, #52, #55 | — |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/store.py` | #51, #52, #53, #55 | — |
| SAME_PATH_DIVERGED | `gateway/gpu_gateway/worker.py` | #51, #52, #53, #54, #55, #56, #57 | — |
| EXACT_HEAD_BLOB | `gateway/tests/test_backup_generation.py` | #51, #59 | #59 |
| NOT_IN_PR_SLICE | `gateway/tests/test_credit_authorization_bridge.py` | — | — |
| SAME_PATH_DIVERGED | `gateway/tests/test_experiment_api.py` | #51, #52, #54, #55, #57 | — |
| SAME_PATH_DIVERGED | `gateway/tests/test_http_auth.py` | #51, #52, #53, #56 | — |
| EXACT_HEAD_BLOB | `gateway/tests/test_local_oauth.py` | #51, #52, #57, #58 | #58 |
| SAME_PATH_DIVERGED | `gateway/tests/test_migrations.py` | #51, #52, #53, #55, #57, #58 | — |
| NOT_IN_PR_SLICE | `gateway/tests/test_paid_authorization_bridge.py` | — | — |
| NOT_IN_PR_SLICE | `gateway/tests/test_paid_authorization_store.py` | — | — |
| SAME_PATH_DIVERGED | `gateway/tests/test_postgres_lifecycle_integration.py` | #51, #52, #55, #57 | — |
| SAME_PATH_DIVERGED | `gateway/tests/test_postgresql.py` | #51, #52, #53, #55, #57, #58 | — |
| EXACT_HEAD_BLOB | `gateway/tests/test_postgresql_backup_integrity.py` | #59 | #59 |
| EXACT_HEAD_BLOB | `gateway/tests/test_postgresql_oauth.py` | #58 | #58 |
| NOT_IN_PR_SLICE | `gateway/tests/test_provider_account_leases.py` | — | — |
| NOT_IN_PR_SLICE | `gateway/tests/test_provider_account_scope.py` | — | — |
| SAME_PATH_DIVERGED | `gateway/tests/test_registry.py` | #51 | — |
| NOT_IN_PR_SLICE | `policies/paid-execution-policy.yaml` | — | — |
| SAME_PATH_DIVERGED | `policies/repository-state.yaml` | #51 | — |
| NOT_IN_PR_SLICE | `src/gpu_control/default_paid_execution_policy.yaml` | — | — |
| NOT_IN_PR_SLICE | `src/gpu_control/repository_security.py` | — | — |
| NOT_IN_PR_SLICE | `tests/test_paid_authorization.py` | — | — |
| NOT_IN_PR_SLICE | `tests/test_paid_execution_policy.py` | — | — |
| SAME_PATH_DIVERGED | `tests/test_prompt_context_security.py` | #51 | — |
| SAME_PATH_DIVERGED | `tests/test_repository_state.py` | #51 | — |

## Interpretation for the next implementation pass

- The six exact file blobs belong to the P1 OAuth/DCR and P3 backup slices. This proves only content identity for those files.
- The 39 divergent same-path files need three-way review against their owning PR base/head before allocation to a new review head. In particular, schema and worker files span multiple slices; keep migration dependencies intact.
- The 47 unassigned paths include new acceptance records and P4/P5 authorization/account-lease code, policy, and tests. Assign them to explicit roadmap slices and review ownership; do not silently append them to the P1 release slice.
- Current production and ChatGPT gates are separate: production `/readyz` returned 404 in the live probe; ChatGPT OAuth/run/result acceptance remains NOT RUN. Preserve `mode: parked`, paid compute disabled, and RunPod live calls disabled.
- No source, GitHub, deployment, workspace, or provider state was changed by this comparison. No tests were run.
