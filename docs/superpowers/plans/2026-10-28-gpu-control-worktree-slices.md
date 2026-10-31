# Current worktree review slices

## Current checkout reconciliation — 2026-10-31 latest turn

Rechecked the active checkout after adding the P4 signed credit verifier.
Branch `codex/chatgpt-cpu-vertical` remains at `a794438f42bd7246f463eaaa40d963af0aae9d13`;
against its configured upstream it is 55 commits ahead and 56 behind. The worktree
has **47 modified tracked and 21 untracked paths (68 total), none staged**.
The ownership table below now accounts for all 68 paths exactly once. P4 owns
the service/worker fail-closed hook and verifier/tests; P1 owns the new
exact-PR-#57 readiness candidate record. `git diff --check` passes.

Current Gateway offline suite from the dirty source tree: **484 passed, 15
skipped**, one existing Starlette deprecation warning. Skips are optional
Torch/Modal dependencies and unconfigured Docker/PostgreSQL integration
fixtures; this run is not the source-matched Docker/PostgreSQL acceptance.
Focused credit and paid-authorization suites passed **52 tests**. The earlier
six-group replay against PR #58 predates these P4 credit paths and is no longer
an exact-current-source patch set; regenerate it before publication. PRs #57
and #58 remain OPEN/DRAFT with no submitted GitHub reviews. No remote ref,
deployment, account, provider, or policy was changed; preserve `mode: parked`.

The PR #58 schema-v9 delta was tested on an isolated detached worktree at exact
PR #57 head `51b88f6`. Direct patch application failed in five overlapping
OAuth/migration paths. A three-way replay of PR #58's original commit also
conflicted because its base includes PR #51's schema-v8 provider-observation
migration and newer OAuth changes. The temporary worktree was removed; the
primary checkout and refs were unchanged. This confirms #58 is not an
independent follow-up to #57 as currently built. Keep schema-v9 behind the
schema-v8 dependency in the review sequence, or redesign and revalidate the
migration ordering before proposing a new stack.

## Current PR stack snapshot — 2026-10-31 refresh

Current checkout is branch `codex/chatgpt-cpu-vertical` at committed HEAD
`a794438f42bd7246f463eaaa40d963af0aae9d13`, 68 commits ahead of `origin/main`.
The branch's upstream also contains 56 commits absent locally, so the local
branch is not ready for a direct push. The worktree currently has 45 modified
tracked paths and 17 untracked paths (62 total); none are staged. `git diff
--check` passes. On this source, Gateway passed **480 / 2 skipped** with the
digest-pinned local CPU smoke image and PostgreSQL 16, and root/Core passed
**550 / 1 skipped**. The latest update repaired one test double to implement
the current candidate lifecycle contract; details are in
`docs/IMPLEMENTATION_PROGRESS.md`.

GitHub read-only PR refresh at 06:46 JST found PRs #51–#59 still OPEN and
Draft. #52 is `REVIEW_REQUIRED`; the other listed PRs had no review decision.
#57 is based on #56, #51 on #57, #58 on #51, and #59 on #57; #52 targets
`main`. The current heads are #51 `e3ffcef`, #52 `bc9b030`, #53 `f8ee5d0`,
#54 `113d7bf`, #55 `dc109cb`, #56 `34cc58c`, #57 `51b88f6`, #58 `561a6c7`,
and #59 `76c2a1a`. This refresh confirmed all seven Actions checks and Vercel
statuses pass on exact current heads #52 and #57–#59. #52 is
`REVIEW_REQUIRED` with an empty review list; #57–#59 also have empty review
lists. The PR list has no recorded review decision for #51 and #53–#59, while
#43 reports `REVIEW_REQUIRED`. A fresh protection API read confirms the
required approval/check configuration; details are in `docs/BASELINE_AUDIT.md`.

PR #52's original P1 Security Review did not cover its later workflow-only
required-check fix. PRs #57–#59 and #58 have separate local Security Review
records, which are not GitHub reviews. Production deployment and authenticated
ChatGPT acceptance remain unverified; prior public probes are historical and
do not establish current readiness. See `docs/CHATGPT_ACCEPTANCE.md`.

### Historical dirty-overlay ownership audit — 2026-10-31 (superseded)

The 68-path inventory and composition below describe an earlier snapshot and
are not the current worktree map. The current checkout has 91 dirty paths as
of 2026-10-31 02:24 UTC; its exact per-file comparison against live PR #51–#59
base/head ranges is in
`docs/acceptance/2026-10-31-pr-stack-reconciliation.md`. Use that newer
reconciliation before preparing review candidates.

Compared `git diff --name-only` and `git ls-files --others
--exclude-standard` against the current 61 worktree entries. Every path is
assigned exactly once below. This is an ownership map for composing the dirty
overlay with the older candidate stack; it does not make the broad cumulative
branch an independently reviewable PR. Shared `gateway/tests/test_postgresql.py`
stays with P1 because its current delta updates schema-v9 OAuth migration
expectations; P3 manifest-integrity coverage is isolated in its own module.

| Slice | Paths | Current-overlay ownership |
|---|---:|---|
| P1 OAuth/schema-v9 | 10 | `gateway/gpu_gateway/local_oauth.py`, `gateway/gpu_gateway/migrations.py`, `gateway/tests/test_local_oauth.py`, `gateway/tests/test_migrations.py`, `gateway/tests/test_postgresql.py`, `gateway/tests/test_postgresql_oauth.py`, `docs/acceptance/2026-10-31-p1-c817-source-provenance-suite.md`, `docs/acceptance/2026-10-31-p1-c824-candidate-suite.md`, `docs/acceptance/2026-10-31-p1-dcr-persistence-schema-v9.md`, `docs/acceptance/2026-10-31-p1-v9-source-matched-cpu-suite.md` |
| P1 local CPU readiness admission | 4 | `gateway/gpu_gateway/admission.py`, `gateway/gpu_gateway/app.py`, `gateway/tests/test_http_auth.py`, `docs/acceptance/2026-10-31-p1-readiness-review-candidate-on-57.md` |
| P2 worker crash recovery | 2 | `gateway/tests/test_postgres_lifecycle_integration.py`, `docs/acceptance/2026-10-31-postgres-container-crash-recovery.md` |
| P3 backup and operations | 11 | `gateway/deploy/backup_generation.py`, `gateway/tests/test_backup_generation.py`, `gateway/tests/test_postgresql_backup_integrity.py`, `docs/OPERATIONS.md`, `docs/acceptance/2026-10-28-atomic-backup-generation.md`, `docs/acceptance/2026-10-28-recovery-drill-record-template.md`, `docs/acceptance/2026-10-28-systemd-uid-boundary.md`, `docs/decisions/2026-10-28-p3-deployment-topology.md`, `docs/acceptance/2026-10-30-dirty-source-paired-restore.md`, `docs/acceptance/2026-10-31-p3-cccf-package-candidate-suite.md`, `docs/acceptance/2026-10-31-p3-d794-candidate-suite.md` |
| P4 candidate lifecycle/selection evidence | 11 | `gateway/gpu_gateway/backends.py`, `gateway/gpu_gateway/registry.py`, `gateway/gpu_gateway/service.py`, `gateway/gpu_gateway/worker.py`, `gateway/gpu_gateway/credit_authorization_bridge.py`, `gateway/tests/test_registry.py`, `gateway/tests/test_credit_authorization_bridge.py`, `docs/decisions/2026-10-28-p4-modal-readiness.md`, `docs/specs/p4-capability-selection-contract.md`, `docs/acceptance/2026-10-31-p4-adapter-receipt-signer.md`, `docs/acceptance/2026-10-31-p4-credit-authorization-verifier.md` (the receipt signer implementation and strict-projection fix are already committed at `3d82405..a794438`; the current diff separates CREDIT_BACKED authority from paid and adds an offline verifier, not an executable provider lane) |
| P5 offline paid-authority verifier | 11 | `gateway/gpu_gateway/config.py`, `gateway/gpu_gateway/paid_authorization_bridge.py`, `gateway/tests/test_paid_authorization_bridge.py`, `gateway/tests/test_experiment_api.py`, `docs/specs/p5-gateway-runpod-permit-bridge.md`, `docs/acceptance/2026-10-31-p5-paid-authorization-verifier.md`, `policies/paid-execution-policy.yaml`, `src/gpu_control/default_paid_execution_policy.yaml`, `src/gpu_control/repository_security.py`, `tests/test_paid_authorization.py`, `tests/test_paid_execution_policy.py` |
| Cross-cutting baseline/acceptance/handoff | 19 | `docs/BASELINE_AUDIT.md`, `docs/CHATGPT_ACCEPTANCE.md`, `docs/CHATGPT_SETUP.md`, `docs/IMPLEMENTATION_PROGRESS.md`, `docs/PARKED_MODE.md`, `docs/REPOSITORY_SECURITY.md`, `docs/STATUS.md`, `docs/RELEASE_MATRIX.md`, `docs/acceptance/2026-10-28-local-integration-revalidation.md`, `docs/acceptance/2026-10-30-current-worktree-source-matched-suite.md`, `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`, `docs/acceptance/2026-10-31-pr51-full-current-candidate.md`, `docs/superpowers/plans/2026-10-28-gpu-control-luna-handoff.md`, `docs/superpowers/plans/2026-10-28-gpu-control-roadmap.md`, `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`, `gateway/README.md`, `policies/repository-state.yaml`, `tests/test_repository_state.py`, `tests/test_prompt_context_security.py` |
| **Total** | **68** | **47 modified tracked + 21 untracked** |

Composition order is P1 → P2 → P3 → P4 → P5 → cross-cutting. P1/P2/P3
changes need to be reconciled against their candidate ranges before making
review heads; P4 already exists as two local commits; P5 remains an offline
verifier only and must not be described as worker-integrated authority.
Cross-cutting docs should be regenerated against whichever exact candidate
heads are ultimately submitted. No commit, push, PR edit, deployment, or mode
change was made during this ownership audit.

### Exact full-source reconstruction on current PR #51 head — 2026-10-31

The grouped 61-path overlay patches above do not include committed changes
that distinguish primary HEAD `a794438` from PR #51 head `e3ffcef`; therefore
they are not full candidate patches by themselves. An initial test of only
those overlays on `e3ffcef` passed Gateway 471/2 skipped and Core 559/1 skipped,
but it is partial-scope evidence and must not be presented as current-source
candidate validation.

Generated `/tmp/gpu-control-full-current-on-e3ffcef.patch` from the complete
tree delta `e3ffcef..a794438` plus all 16 current untracked files. SHA-256:
`c0a4b9e9deb8ecf7fe5b24e401ce6da777291c469845dd3175101d9b94c5f8d7`.
Applied it to a fresh detached worktree at `e3ffcef`; the resulting 339-file
tree matched the primary checkout byte-for-byte with zero missing, extra, or
mismatched files. `git apply --check` and `git diff --check` passed.

On that exact candidate, Gateway passed 482 tests with two optional skips
(Torch and Modal) against PostgreSQL 16 and the digest-identified local CPU
smoke image; Core passed 559 tests with one Python-3.11-specific skip. Exact
inputs and scope limits are in
`docs/acceptance/2026-10-31-pr51-full-current-candidate.md`. This is local
candidate evidence only; no GitHub CI/review or deployment acceptance covers
the patch. Keep the broad PR unchanged until a reviewable replacement stack is
mapped and each proposed head receives its own checks and approval.

### `origin/main`-based stacked candidate patch reconstruction — 2026-10-31

Reconstructed the existing candidate sequence in a detached worktree starting
at current `origin/main` (`24ecb9b`). Each patch below was generated from its
exact base/head tree pair, passed `git apply --check`, applied in sequence,
then compared against the target commit's complete file tree, bytes, and
executable bits. `git diff --check` passed at every checkpoint. This gives
Luna reproducible candidate patches without rewriting commits or touching the
primary checkout. The known failing intermediate `7c4454b` is intentionally
skipped; the sixth candidate combines through its schema-v7 fix at `c8172c0`.

| Stack | Base → head | Changed paths | Target files verified | Patch artifact / SHA-256 |
|---:|---|---:|---:|---|
| 1 CPU vertical | `origin/main` → `c824b90` | 40 | 234 | `/tmp/gpu-control-main-p1-cpu-vertical.patch` / `b04cf9277a42b4c1780859fcc8f65be275e0ae92ad9133652e2a81c82f469728` |
| 2 readiness/worker | `c824b90` → `6646401` | 19 | 242 | `/tmp/gpu-control-main-p2-readiness-worker.patch` / `9d7905c346147b5189759816bbb45a1b1406cd9a819352e9b5c563e4b921612e` |
| 3 artifact ownership | `6646401` → `2a6f21a` | 21 | 246 | `/tmp/gpu-control-main-p2-artifact-owner-retrieval.patch` / `f1fb7acdbdaf5e3ea8db87e84d8e29381243adc4ae57b37a5425d10b7f3e1d91` |
| 4 artifact readiness | `2a6f21a` → `0d02058` | 38 | 249 | `/tmp/gpu-control-main-p2-artifact-readiness.patch` / `cba2e14a3830ec0097069c614e6cde58748a1d50d2609ff0d455cbbdfdc0dc53` |
| 5 HTTP boundary/final CPU | `0d02058` → `311d6a9` | 25 | 252 | `/tmp/gpu-control-main-p2-http-boundary-final-cpu.patch` / `92aa392d1e93c9e1ec15698c7a83ac56c0c98af90fb323bb477ddba36423cc54` |
| 6 OAuth/migration + CPU recovery | `311d6a9` → `c8172c0` | 52 | 264 | `/tmp/gpu-control-main-p1-oauth-migration-and-cpu-recovery.patch` / `333e732a71e3f29bc6af4cacb7de186838acf3f7199e69be9e4041faf326baa3` |
| 7 backup/operations | `c8172c0` → `d794c13` | 13 | 276 | `/tmp/gpu-control-main-p3-backup-operations.patch` / `f5f0856cdc05500b197ba51c17ec5beb5e7eed3cff8447e47bfc331e0de621ae` |
| 8 CI/package | `d794c13` → `cccfcb8` | 8 | 277 | `/tmp/gpu-control-main-p0-ci-packaging.patch` / `bd26a1f5c98a6dc47c754edcebbc3ceea811144b18190a4bae7c2f102f502812` |
| 9 P4 selection | `cccfcb8` → `f15ab32` | 5 | 279 | `/tmp/gpu-control-main-p4-selection.patch` / `57438236a379e87e2d8c717f29668569b1e1d1dd3788bba386ba229d8fec9562` |
| 10 foundation evidence | `f15ab32` → `f054aebe` | 15 | 281 | `/tmp/gpu-control-main-p0-foundation-evidence.patch` / `a971102833f9185dd17ac84427fa01e9652e4bc5f65b538528e385e0297de9b1` |

The detached cumulative worktree is at
`/tmp/gpu-control-main-p1-p2-candidate-stack` and currently reproduces
`f054aebe`. Existing local evidence covers full Gateway/Core suites for
`c824b90` and `c8172c0`, plus the exact changed-test subsets recorded below
for later checkpoints. This patch reconstruction itself ran no tests and
creates no GitHub CI/review evidence. Later follow-up overlays from `f054aebe`
through PR #51 and the current dirty changes are composed below. No branch,
commit, push, PR, deployment, or policy state changed.

### Current PR #51 review-range coverage audit — 2026-10-31

Recomputed the exact ancestry and changed-path sets for the ten main-based
candidate ranges above plus `f054aebe..aa681f4`. All eleven ranges are
ancestor-valid and sequential. Their path-set union covers all **169** files
in the current pushed PR diff, with one additional path that exists only in
an intermediate range: `gateway/deploy/worker.env.example`, deleted before
`aa681f4`. Do not include that historical file in the final review inventory.
Range path counts are 40, 19, 21, 38, 25, 52, 13, 8, 5, 15, and 117. This
proves path coverage and history order only; it does not prove each range is
independently mergeable, tested, reviewed, or accepted. PR #51 remains one
169-file Draft until a reviewed merge strategy is carried out.

### Exact current-source candidate reconstructed from `origin/main` — 2026-10-31

Starting from the verified `f054aebe` tree above, applied the exact
`f054aebe..aa681f4` tree delta, then `aa681f4..a794438`, then the current
40-path dirty overlay present at the time of this reconstruction. The
authoritative current overlay is 41 paths as shown above; the additional path
is the later `2026-10-31-current-snapshot-full-suite.md` record. The detached
candidate was refreshed against all current files and now matches the primary
source tree byte-for-byte and by executable bit: **339 paths, zero missing,
zero mismatched, zero extra**. The refreshed patch generated from this exact
candidate against `origin/main` is
`/tmp/gpu-control-main-full-current-20261031-final6.patch`. Applied that patch
to a fresh detached worktree at `origin/main`: `git apply --check` passed and
the resulting 339-file tree matched the primary checkout with zero missing,
extra, or mismatched files. Verify the patch artifact's SHA-256 directly before
reuse.

The cumulative candidate is at
`/tmp/gpu-control-main-full-current-20261031-final3`; the current single replay
patch is `final20.patch`. This is a source reconstruction artifact, not a small
review slice or a committed PR head. No tests were rerun by the reconstruction
itself; current-source local suite and focused-test evidence remains in the
acceptance records above. GitHub CI and GitHub review still do not cover this
current source tree. No remote ref or repository policy changed.

Required-check trigger audit (2026-10-31): the current protected `main` API
response requires exactly seven Actions contexts: Python 3.11/3.12/3.13,
Trusted reference container, Gateway offline tests, Gateway comment bridge
tests, and Project bridge tests; strict up-to-date branches are enabled. Each
corresponding workflow has an unfiltered `pull_request` trigger, so every
review-sized PR candidate is expected to run all seven checks even when its
changed paths do not concern that workflow. Vercel is a separate reported
status and is not among the seven branch-protection required contexts. The
actual check result must still be observed on each published head; no result
from PR #51 or local test run transfers to another candidate.

### P1 schema-v9 OAuth overlay candidate — 2026-10-31

Isolated the current P1 ownership row (10 paths) from the dirty overlay and
prepared `/tmp/gpu-control-p1-schema-v9-overlay-on-aa681.patch` (SHA-256
`a99aeb1184d5f6298c48d64d43a7148632642ddc1a953705f3a50c12a7a6ac1f`). The
patch applies cleanly to exact PR #51 head `aa681f4062dac6b73bcf380a38a4258b96a47e1`
and contains only the 10 assigned paths. It does **not** apply to `c8172c0`:
that checkpoint predates intervening OAuth owner-consent, ChatGPT redirect,
and migration-boundary changes to the same files. Do not stack schema v9 on
that stale checkpoint; use the matching current PR head or reconstruct a new
base after those prerequisite commits.

This patch is a review candidate for the follow-up delta only. Its base is
already a 169-path OPEN/DRAFT PR with no submitted review, so reviewing this
10-path delta does not make the cumulative change independently mergeable to
`main`. The current complete dirty source has local full-suite evidence (480/2
Gateway, 550/1 Core) and a sequential source-only Security Review with zero
findings; this isolated patch did not receive a separate full-suite run or
independent review. No push or GitHub mutation occurred.

### P2/P3 current-overlay follow-up candidates — 2026-10-31

The remaining recovery and operations overlays were split from the same
dirty snapshot and each was checked against exact PR #51 head `aa681f4`:

| Slice | Paths | Patch | SHA-256 | Result |
|---|---:|---|---|---|
| P2 worker crash after container start | 2 | `/tmp/gpu-control-p2_worker_crash-overlay.patch` | `cf9e8471f6fc3539a663d0263cc0ddabafa58f77ea88eae06e5f2ae370bd587a` | `git apply --check` passed; only assigned paths changed. |
| P3 backup integrity and operations follow-up | 11 | `/tmp/gpu-control-p3_backup_operations-overlay.patch` | `b5ac894808cf414436681cfeb2b63f3b3af70ee0cb0a419e4abf9f4c65872998` | `git apply --check` passed; only assigned paths changed. |

These are follow-up overlays on the broad Draft PR, not standalone
main-based PRs. The current full local suite includes these changes, but no
suite was rerun per isolated candidate and no GitHub CI/review was created.
Keep P3 runtime claims scoped to local PostgreSQL/Docker evidence until the
selected host, alert path, second operator, and measured RPO/RTO are accepted.
Applied the P1, P2, and P3 patches in order to a fresh detached worktree at
`aa681f4`; the composition changed exactly the 23 owned paths and matched the
current checkout byte-for-byte with zero mismatches. This confirms patch
composition only, not isolated-candidate runtime behavior.

The trusted-reference workload job has also been replayed locally from the
current checkout with the same container constraints and sentinel check; it
passed on local arm64. The Gateway comment bridge and Project bridge workflow
payloads also passed locally: 81/1 skipped plus the bounded tiny-LM container,
and 19/19 plus the project-owned Docker smoke. These local runs do not transfer
to GitHub Actions or another PR head.
The trusted-reference workload job has also been replayed locally from the
current checkout with the same container constraints and sentinel check; it
passed on local arm64. The run record explicitly excludes GitHub Actions and
independent review evidence.

Historical run at the earlier `aa681f4` checkout on 2026-10-31 JST passed
Gateway 427 tests with two skips (optional PyTorch bridge and Modal backend);
it used a disposable PostgreSQL 16 container on a dynamic loopback-only port
and the digest-pinned CPU smoke image. It includes the current PostgreSQL
backup-integrity and OAuth suites, real local Docker execution, and recovery
integration tests. The prior progress entry that attributed 550/1 to the
Gateway suite is corrected by this reproducible 427/2 run; the separate
root/core suite result was 550/1. This Gateway run is superseded for current
source counts by the `a794438` 480/2 result in the authoritative snapshot above.
The current uncommitted diff then received a read-only Security Review with no
actionable findings. The temporary database container was removed by the test
command's exit trap. `git diff --check` passes. Fresh `uv sync --project
gateway --locked --no-dev` and imports also pass in a temporary runtime
environment. At that earlier snapshot, Vercel Preview was READY from pushed
`aa681f4` but protected by SSO; names-only env listing was
403 and no temporary share link was created. Treat the local results as
integration evidence only, not hosted readiness or ChatGPT acceptance.

P2 recovery coverage at the `aa681f4` snapshot was extended on 2026-10-31 with a PostgreSQL-backed worker
process crash after real Docker start. The fresh supervisor adopted the same
run-labeled container and produced its result/artifact with confirmed cleanup;
the two PostgreSQL lifecycle integration tests passed, followed by the then
current Gateway suite at 427 passed / 2 skipped. The current `a794438` source
has a focused worker-crash rerun of 1/1 and a full suite of 480/2 as recorded
above. This remains local integration evidence, not target-host RPO/RTO or
seven-day operations acceptance.

At the pushed `aa681f4` snapshot, the exact published
`origin/main...aa681f4` diff contained **169 paths**: 90 under
`gateway`, 40 under `docs`, 16 under root `tests`, 13 under `src`, 4 under
`.github`, 3 at repository root, 2 under `policies`, and 1 under `.superpowers`.
The historical path-set audit covered the full published diff. It combines the 117-path
follow-up ownership map from `f054aebe` to `aa681f4` and 53 foundation-only paths;
the reverted `gateway/deploy/worker.env.example` is excluded. At that snapshot, the uncommitted OAuth-test decomposition and PostgreSQL backup-integrity
test added two paths, and the new P2 recovery acceptance record added one path,
making the local inventory 172 paths. The baseline-audit edit at that time changed
an already-inventoried tracked path. The owner-list comparison later
found one stale historical deletion (`gateway/deploy/worker.env.example`), which
is excluded from the publishable inventory and candidate patches based on
`main`.
At that snapshot, the branch had 66 commits after `origin/main`. Existing candidate ranges below
anchor a linear review sequence; no branch was rewritten, created, pushed, or
retargeted during this audit.

The user's prior selection authorized Security Review. Earlier read-only
reviews covered the P1 OAuth slice and the `origin/main` branch diff; the
latest read-only review covered the complete current uncommitted diff after the
PostgreSQL test URL moved from argv to stdin and found no actionable security
findings. This local diff review is separate from GitHub review, CI, preview
runtime, and ChatGPT acceptance.

## Local candidate ref ancestry audit — 2026-10-31

Read each candidate commit's actual parent and ran `git merge-base
--is-ancestor` for every adjacent pair. All 20 refs are ordered ancestors, but
some commits have intermediate first parents, so a branch name or first-parent
range must not be mistaken for the explicit review boundary. The PR base/head
sequence is the checkpoint table below, not a sequence of 20 independently
publishable PRs.

| Ref | Head | Actual commit parent |
|---:|---|---|
| 1 | `b3cb04d` | `24ecb9b` |
| 2 | `195de19` | `b3cb04d` |
| 3 | `2440897` | `82d0954` |
| 4 | `3e1c31c` | `2ccb869` |
| 5 | `c824b90` | `aac8336` |
| 6 | `2090bbd` | `c824b90` |
| 7 | `cc1e263` | `4324f07` |
| 8 | `6646401` | `be9173c` |
| 9 | `42b986e` | `4a05649` |
| 10 | `7761e14` | `4f2e909` |
| 11 | `2a6f21a` | `7761e14` |
| 12 | `f58e24b` | `64afcd7` |
| 13 | `aff28cd` | `bccfb74` |
| 14 | `0d02058` | `1987dca` |
| 15 | `311d6a9` | `eff04c5` |
| 16 | `c8172c0` | `7c4454b` |
| 17 | `d794c13` | `c8172c0` |
| 18 | `cccfcb8` | `d794c13` |
| 19 | `f15ab32` | `cccfcb8` |
| 20 | `f054aebe` | `b7e2f9e` |

This audit only establishes graph ancestry and commit metadata. It does not
establish that each checkpoint is an independent PR, that its changed-path
count matches a planned review unit, or that its tests/CI pass. Use exact
base/head tree comparisons from the checkpoint and ownership tables before
forming candidate patches. In particular, refs 15 and 16 are not direct
parent/child: `311d6a9` is an ancestor of `c8172c0`, whose direct parent is
`7c4454b`.

### Focused changed-test revalidation for later checkpoints — 2026-10-31

Ran the changed-test subsets in isolated detached worktrees and set
`PYTHONPATH` to each candidate checkout, with dependencies reused from the
primary Gateway Python 3.12 environment:

| Checkpoint range | Candidate-source result | Scope limit |
|---|---:|---|
| `0d02058..311d6a9` | 92 passed | Changed HTTP security, worker recovery, provider, RunPod, and source tests; no GitHub CI. |
| `7c4454b..c8172c0` | 22 passed | Changed OAuth, auth, migration, and owner-migration modules; PostgreSQL-only concurrency not part of this invocation. |
| `c8172c0..d794c13` | 21 passed | Existing focused backup-generation and deployment-unit result, reproduced earlier on this exact checkpoint. |
| `d794c13..cccfcb8` | 6 passed | Four workflow-security and two package-metadata tests, reproduced earlier on this exact checkpoint. |
| `cccfcb8..f15ab32` | No changed test files | Documentation/specification checkpoint; review its policy and roadmap claims. |
| `f15ab32..f054aebe` | 6 passed | Candidate-local OAuth and packaging-metadata tests; one existing Starlette deprecation warning. |

For the new 92-, 22-, and 6-test runs, candidate modules resolved from the
detached worktree; temporary worktrees were removed. Existing 21- and 6-test
results are the exact-checkpoint revalidations recorded elsewhere in this
handoff. These results close focused changed-test coverage for these checkpoint
ranges, not full suite per PR, clean locked-environment builds, Linux CI,
independent GitHub reviews, live ChatGPT/OAuth acceptance, or production
deployment.

### First P1 candidate cumulative suite — `origin/main..c824b90`

The exact initial P1 candidate was then checked with the complete suites from a
detached worktree at `c824b90`: Gateway **198 passed / 2 optional skips** with
a digest-pinned PostgreSQL 16 container and real digest-pinned CPU smoke image;
root/Core **452 passed / 1 Python-version skip**. Full environment and
limitations are in
[`2026-10-31 P1 candidate suite record`](../../acceptance/2026-10-31-p1-c824-candidate-suite.md).
An earlier fresh-venv run of this same exact candidate passed Gateway
**199/1 skipped**, WebMCP **3/3**, `compileall`, and the same root/Core result.
The new repeat used the primary venv without optional `modal`, so its extra skip
accounts for the 198/2 result; both Gateway runs total 200 tests and pass. This
confirms local full-suite confidence for the first P1 review candidate only.
The next proposed cumulative integration head still requires the same
candidate-source review and complete suite before it is ready for CI/review.

Read-only Security Review was also run on the exact `origin/main..c824b90`
branch in a dedicated worktree; the reviewer reported no reportable issues.
No files were changed and no tests were run by that review. It covers the
first P1 candidate source diff only and does not replace required GitHub CI,
GitHub approval, or ChatGPT/production acceptance.

Prior 117-path composition validation (2026-10-30): a detached worktree at
`f054aebe` received P1, P3, P4, P5, and cross-cutting patches in owner order.
The first attempt imported primary-checkout code and is invalid. The corrected
attempt pointed `PYTHONPATH` to the candidate `gateway/` and `src/`, confirmed
module paths, and matched the then-committed 117 files byte-for-byte. It passed
focused composed-worktree tests: P1/P3 Gateway **131 passed / 9 skipped**, P4
Gateway **135 passed**, root/core P4 **167 passed**, and P5 policy **4 passed**.
This was not validation of individual GitHub PR heads or the full CI matrix.
The path ownership was then adjusted after `test_deploy_units.py` revealed its
dependency on `gateway/deploy/provider-evidence.env.example`, which moved from
P4 to P3. The current 120-path local overlay and 169/172-path full inventory
are recorded in the sections below; do not use the earlier 117-path counts as
the current totals.

## P1 OAuth review candidate — 2026-10-30

A three-path review candidate was applied to a detached worktree at exact base
`f054aebe96460fe033dde8d91d7e3bbab0255655`. The patch was byte-for-byte
reproduced from the current `HEAD` and untracked OAuth PostgreSQL test on
2026-10-30; its SHA-256 is
`7a3cd15ac07c222fda75c1cbc868c98e0c4beb62759d46183131d1cf67b8cdea`.
Regenerate it while these inputs remain unchanged with:

```sh
python3 - <<'PY'
import subprocess
from pathlib import Path
base = "f054aebe96460fe033dde8d91d7e3bbab0255655"
tracked = ["gateway/gpu_gateway/local_oauth.py", "gateway/tests/test_local_oauth.py"]
parts = [subprocess.run(["git", "diff", "--binary", base, "HEAD", "--", *tracked], check=True, capture_output=True).stdout]
parts.append(subprocess.run(["git", "diff", "--no-index", "--binary", "--", "/dev/null", "gateway/tests/test_postgresql_oauth.py"], capture_output=True).stdout)
Path("/tmp/gpu-control-p1-oauth-review.patch").write_bytes(b"".join(parts))
PY
```

`gateway/tests/test_local_oauth.py` plus
`gateway/tests/test_postgresql_oauth.py` passed **7 tests, 0 skipped** against a
dedicated digest-pinned PostgreSQL 16 container. An isolated read-only Security
Review found no actionable findings. Dependencies came from the primary
Gateway venv; this was not GitHub CI or a locked clean environment.

This closes the local P1 OAuth code-review candidate check only. PR #51 still
requires GitHub approval and the candidate has not been pushed. ChatGPT account
eligibility, OAuth grant/tool discovery, deployed revision/readiness, actual
ChatGPT CPU execution, cross-conversation result retrieval, and owner-isolation
acceptance remain open. Preserve `mode: parked`.

Exact replay (2026-10-31): regenerated the three-file patch from the current
worktree; SHA-256 remained
`7a3cd15ac07c222fda75c1cbc868c98e0c4beb62759d46183131d1cf67b8cdea`. Applied
it to a fresh detached worktree at `f054aebe`, confirmed
`gpu_gateway.local_oauth.__file__` resolved inside that candidate, and reran
`test_local_oauth.py` plus `test_postgresql_oauth.py` with a fresh digest-pinned
PostgreSQL 16 container: **7 passed, 0 skipped**. The container and temporary
worktree were removed. This verifies candidate reproducibility and local P1
regressions, not full GitHub CI or live ChatGPT OAuth.

The current P3 backup-integrity candidate at base
`aa681f4062dac6b73bcf380a38a4258b96a47e1` applies cleanly. Its three-path
code/test patch SHA-256 is
`d36b3a575a7f9944bfcf7718cfe3d827d7619365f8897adbd940591967d3768a`; the
backup-generation tests plus PostgreSQL-backed integrity regression passed
**25/25** against pinned PostgreSQL 16. This supersedes the earlier patch
fingerprint `e5c05d1fa65a175747673e22a778f8b882cac6eb29ed9681a9ee31e2b16b0375`.
To regenerate while the candidate inputs are unchanged:

```sh
python3 - <<'PY'
import subprocess
from pathlib import Path
tracked = ["gateway/deploy/backup_generation.py", "gateway/tests/test_backup_generation.py"]
parts = [subprocess.run(["git", "diff", "--binary", "HEAD", "--", *tracked], check=True, capture_output=True).stdout]
parts.append(subprocess.run(["git", "diff", "--no-index", "--binary", "--", "/dev/null", "gateway/tests/test_postgresql_backup_integrity.py"], capture_output=True).stdout)
Path("/tmp/gpu-control-p3-backup-integrity.patch").write_bytes(b"".join(parts))
PY
```

This is local P3 evidence only. GitHub CI, Linux target-host operation, Neon,
independent production restore, and measured RPO/RTO remain open.

Exact replay (2026-10-31): regenerated the three-path patch from the current
worktree; SHA-256 remained
`e5c05d1fa65a175747673e22a778f8b882cac6eb29ed9681a9ee31e2b16b0375`. Applied
it to a fresh detached worktree at `aa681f4`, confirmed both `gpu_gateway` and
`backup_generation` imported from that candidate, and reran
`test_backup_generation.py` plus `test_postgresql_backup_integrity.py` with a
fresh pinned PostgreSQL 16 container: **25 passed, 0 skipped**. The temporary
container and worktree were removed. An initial standalone import probe omitted
`gateway/deploy` from `sys.path`; the corrected probe resolved the module from
the candidate, and the test module's own import path worked throughout pytest.
This verifies candidate reproducibility and local integrity regressions, not
GitHub CI or production restore acceptance.

## Existing commit checkpoints for a non-rewritten review series

The branch history already has cumulative checkpoints that can anchor stacked
PR branches without rewriting the current branch. Path counts below are
`git diff --name-only origin/main...<checkpoint>` counts, not review/CI results.

| Checkpoint | Purpose indicated by commit | Cumulative changed paths from `origin/main` | Paths changed since prior checkpoint |
|---|---|---:|---:|
| `c824b90` | Local CPU experiment vertical and recovery | 40 | 40 |
| `7c4454b` | Integrated local CPU vertical/recovery follow-up | 89 | 79 |
| `c8172c0` | OAuth lifecycle and owner migration | 97 | 11 |
| `d794c13` | Paired backup and Linux operations | 109 | 13 |
| `cccfcb8` | Required Gateway checks and wheel build | 117 | 8 |
| `f15ab32` | P4 selection contract and roadmap | 119 | 5 |
| `f054aeb` | Production OAuth/readiness evidence | 121 | 15 |
| `4a05977` | CPU operations and GPU evidence gates | 169 | 117 |
| `aa681f4` | Latest acceptance/roadmap state refresh | 169 | 5 |

This suggests a review sequence of the six foundation ranges below, followed
by OAuth, backup/operations, CI/package, P4 contract/readiness, and the
117-path follow-up split by the ownership slices below. The six foundation
ranges are chronological and each changed-test subset passed locally when the
candidate source was imported explicitly. However, checkpoint `74f004a` failed
two assertions because the code had changed the blocker to
`NO_QUEUEABLE_RESOURCE` while tests still expected `NO_EXECUTABLE_WORKLOAD`.
Checkpoint `0d02058` updates those assertions and passes, so it replaces
`74f004a` as the fourth-stage candidate. All tests reused installed dependency
environments and are not CI evidence. The 40-, 38-, and 41-path ranges and the
117-path follow-up remain substantial; these boundaries need internal review
and potential further subdivision. No branch has been created, pushed, or
retargeted by this inventory work.

### Foundation stack decomposition candidates

The first 121-path `origin/main...f054aebe` foundation can be staged at these
existing linear-history commits. Path counts and changed test-file counts were
measured per exact adjacent range; `git diff --check` passed for all six
ranges. Focused tests for each candidate were run in a detached worktree with
`PYTHONPATH` set to that worktree's source. The 74f004a intermediate failed the
two blocker-reason assertions described above and is intentionally skipped.
These are focused local checks against installed dependencies, not locked
environment or full CI results.

| Stack order | Base → head | Changed paths | Changed test files | Focused result | Review focus |
|---:|---|---:|---:|---|---|
| 1 | `origin/main` → `c824b90` | 40 | 12 | 77 passed / 5 skipped | CPU experiment contract, trusted admission, local worker, initial recovery. |
| 2 | `c824b90` → `6646401` | 19 | 5 | 30 passed / 4 skipped | Readiness setup, dedicated worker units, recovery supervisor. |
| 3 | `6646401` → `2a6f21a` | 21 | 4 | 24 passed | Owner-scoped artifact reads, expiry/pruning, worker cleanup behavior. |
| 4 | `2a6f21a` → `0d02058` | 38 | 12 | 64 passed / 6 skipped | Artifact/readiness integration, heartbeat and workload availability evidence. |
| 5 | `0d02058` → `311d6a9` | 25 | 11 | 92 passed | HTTP egress boundary and RunPod allocation checks, plus readiness regressions. |
| 6 | `311d6a9` → `7c4454b` | 41 | 15 | 150 passed / 7 skipped | Final local CPU vertical/recovery integration and end-to-end regressions. |

The existing tested ranges are not all suitable final PR sizes. Commit-history
inspection gives the following smaller candidate boundaries for the first
40-path vertical and the recovery/artifact follow-ups. Counts are exact
path/test-file changes between adjacent existing commits; the exact changed-
test subsets were independently run on 2026-10-30 as recorded below. Keep paired code,
migrations, docs, and regression tests together when assembling each candidate.

| Order | Base → head | Changed paths | Changed test files | Candidate scope |
|---:|---|---:|---:|---|
| 1 | `origin/main` → `b3cb04d` | 14 | 2 | CPU vertical baseline and database contracts. |
| 2 | `b3cb04d` → `195de19` | 9 | 3 | Canonical experiment MCP tools and local OAuth/API contracts. |
| 3 | `195de19` → `2440897` | 14 | 4 | Fail-closed CPU admission and prepare/submit enforcement. |
| 4 | `2440897` → `3e1c31c` | 19 | 5 | Isolated local CPU backend and persist-before-cleanup behavior. |
| 5 | `3e1c31c` → `c824b90` | 13 | 6 | Submission intent, leases, crash recovery, cancellation and outage regressions. |
| 6 | `c824b90` → `2090bbd` | 6 | 1 | Readiness and ChatGPT setup contract. |
| 7 | `2090bbd` → `cc1e263` | 5 | 0 | Dedicated worker deployment templates and boundary docs. |
| 8 | `cc1e263` → `6646401` | 17 | 5 | Recovery supervisor, deployment/readiness integration and recovery tests. |
| 9 | `6646401` → `42b986e` | 3 | 1 | Supervisor crash during cleanup regression. |
| 10 | `42b986e` → `7761e14` | 5 | 1 | Timeout cancellation preservation during cleanup retry. |
| 11 | `7761e14` → `2a6f21a` | 18 | 2 | Owner-scoped artifact retrieval and result/API tests. |
| 12 | `2a6f21a` → `f58e24b` | 16 | 5 | Artifact retention and CPU smoke result persistence. |
| 13 | `f58e24b` → `aff28cd` | 18 | 5 | Fail-closed missing provider results and persistent artifact state for recovery. |
| 14 | `aff28cd` → `0d02058` | 14 | 3 | Readiness, cost and heartbeat boundaries with corrected regression expectations. |

The 40-path, 38-path, and 41-path parent ranges retain their prior focused-test
results as integration evidence only; those results do not validate the
subdivided candidate heads. Validate each assembled candidate's exact patch,
imports, migrations, focused tests and required GitHub CI before opening a PR.
The 41-path `7c4454b` commit and 117-path `4a05977` commit each contain one
large commit, so Git history offers no smaller boundaries there; use the
existing file-ownership map to propose a split, then check cross-slice imports
and shared contracts in isolated worktrees. Preserve PR #51 until replacements
pass their own checks and reviews; closing or retargeting it is a separate
GitHub action.

Do not use `74f004a` as a PR head: its changed blocker response and the matching
test expectation are inconsistent. The `aff28cd` → `0d02058` candidate includes
the `74f004a` feature, heartbeat fixes, and the corrected expectation/tests from
`0d02058` in one review unit.

Candidate-source preflight (2026-10-30): created detached worktrees at
`b3cb04d`, `195de19`, `2440897`, `3e1c31c`, `c824b90`, `2090bbd`, `cc1e263`,
`6646401`, `42b986e`, `7761e14`, `2a6f21a`, `f58e24b`, `aff28cd`, and
`0d02058`. `git diff --check` passed for all exact adjacent ranges, with path
counts matching the table. `importlib.find_spec` resolved representative
Gateway modules from each candidate's own `gateway/` source (`contracts` /
`migrations`; `experiment_api` / `auth` / `local_oauth`; `admission` /
`experiment_api` / `migrations`; `local_backend` / `worker` / `experiment_api`;
`worker` / `store` / `experiment_api`; `app` / `config`; `worker` / `store` /
`app`; `worker`; `worker`; `artifacts` / `experiment_api` / `worker`; and
`artifacts` / `worker`, `experiment_api` / `worker` / `migrations`, and
`experiment_api` / `health` / `worker`, respectively). This catches accidental
imports from the primary checkout but does not establish runtime behavior:
pytest, migrations, Docker, PostgreSQL, and GitHub CI were not run for these
smaller ranges. Temporary worktrees were removed after inspection.

### Candidate-range changed-test execution — 2026-10-30

Re-ran the changed-test subset for each of the 14 exact adjacent ranges above
in one temporary detached worktree, checking out each candidate head in turn.
`PYTHONPATH` pointed at that candidate's own `gateway/` and `src/` trees; the
Gateway Python 3.12 environment was reused from the primary checkout. The
cached CPU smoke image
`sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`
was supplied with the test fixture's synthetic all-`a` source SHA so Docker
integration cases in the changed-test subsets ran where applicable.

| # | Base → head | Changed-test result |
|---:|---|---:|
| 1 | `origin/main` → `b3cb04d` | 13 passed |
| 2 | `b3cb04d` → `195de19` | 37 passed |
| 3 | `195de19` → `2440897` | 37 passed |
| 4 | `2440897` → `3e1c31c` | 33 passed |
| 5 | `3e1c31c` → `c824b90` | 18 passed (PostgreSQL rerun) |
| 6 | `c824b90` → `2090bbd` | 24 passed |
| 7 | `2090bbd` → `cc1e263` | no changed test files |
| 8 | `cc1e263` → `6646401` | 34 passed (PostgreSQL rerun) |
| 9 | `6646401` → `42b986e` | 4 passed |
| 10 | `42b986e` → `7761e14` | 4 passed |
| 11 | `7761e14` → `2a6f21a` | 16 passed |
| 12 | `2a6f21a` → `f58e24b` | 15 passed (PostgreSQL rerun) |
| 13 | `f58e24b` → `aff28cd` | 47 passed (PostgreSQL rerun) |
| 14 | `aff28cd` → `0d02058` | 22 passed |

The first pass totaled 294 passed / 10 skipped; the skips were all PostgreSQL
tests requiring a dedicated DB/stoppable container. Re-ran the four affected
ranges (5, 8, 12, 13) with a fresh PostgreSQL 16 container for each, pinned to
`sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
and bound only to `127.0.0.1:55494`. Set both
`GATEWAY_TEST_DATABASE_URL` and `GPU_CONTROL_POSTGRES_CONTAINER`; all four
reruns passed with no skips: 18, 34, 15, and 47 cases. Effective final
changed-test scope: **304 passed, 0 skipped, 0 failed**; candidate 7 contained
no changed test files. The run emitted one existing Starlette
`BlockingPortal` deprecation warning per pytest invocation. All temporary
containers and the detached worktree were removed; primary branch/worktree
refs were unchanged. This validates candidate-source focused behavior with
reused dependencies and local Docker/PostgreSQL fixtures; it is not a clean
locked-environment build, full suite per candidate, GitHub CI, independent
review, or approval to publish/merge stacked PRs.

### Fresh Python environment and worker-unit validation — 2026-10-30

Created a disposable Python 3.12.13 venv and installed
`requirements-test.txt` plus `requirements-worker.txt` from `gateway/`, matching
the Gateway workflow's install command. `pip check` passed; resolved pytest was
9.2.0 and Modal 1.5.5. Re-ran all 14 candidate changed-test subsets from the
same detached candidate-source worktree pattern, with fresh loopback PostgreSQL
containers for ranges 5, 8, 12, and 13. Results matched the table above:
**304 passed, 0 skipped, 0 failed**. This is a clean dependency install from
the workflow's unpinned requirements, not `uv sync --locked` or GitHub Actions.
The CPU image still uses the synthetic fixture SHA described above.

Candidate 7 has no Python test-file changes. Its `cc1e263` worker service
template was separately mounted read-only into the cached Debian 12/systemd
252.39 container with `--network none`; inert user/group/path placeholders were
created inside the container and `systemd-analyze verify` passed without
diagnostics. No service was started. This adds unit syntax/reference evidence
for that slice, not runtime sandbox, Docker daemon, or selected-host acceptance.
The temporary venv, candidate worktree, and PostgreSQL containers were removed;
the primary branch and refs were unchanged.

Ownership-slice patch preflight (2026-10-30): regenerated the five path-owned
patches from `f054aebe` to committed `HEAD`, applied them sequentially in a
fresh detached worktree, and compared every resulting path with the committed
HEAD blob or expected deletion. All five patches applied; exact content and
existence matched for all 117 owned paths (74 modified, 42 added, 1 deleted).
This confirms patch assembly and ownership coverage, not isolated testability:
no tests or CI were run on the five individual patches.

Snapshot: branch `codex/chatgpt-cpu-vertical`, base `f054aebe96460fe033dde8d91d7e3bbab0255655`, 2026-10-28; refreshed after the schema-v8 isolated systemd backup/restore drill.
This is a file-ownership map for independent review, not a claim that these changes are approved or ready to merge.
It supersedes the earlier 63-path inventory in the Luna handoff. At this historical snapshot, no files were staged, committed, pushed, or deployed.

Historical inventory revalidation (2026-10-28): `git diff --name-only` reported 75 tracked
paths and `git ls-files --others --exclude-standard` reported 42 untracked
paths. A path-set audit against the lists below found exactly 117 actual paths,
117 unique ownership entries, no missing/stale paths, and no duplicates.
`git diff --check` passed. GitHub currently reports PR #51 OPEN/DRAFT at this
base/head, `REVIEW_REQUIRED`, with 121 files in its full base-to-head diff;
that remote PR inventory is separate from these 116 uncommitted worktree paths.
No repository or GitHub mutation was performed during this audit.

Historical snapshot revalidation (2026-10-28 11:38 UTC): the worktree had 75
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
| 1 | P1 OAuth refresh rotation, scope validation, and PostgreSQL concurrent use | 5 paths at the historical snapshot | Check atomic rollback, one-time refresh, and owner/scope boundaries. Offline evidence only; real ChatGPT OAuth remains NOT RUN. |
| 2 | P3 artifact readiness, backup/recovery, systemd identities, and capacity bridge | 52 paths at the historical snapshot | Review together with the operational docs and provider-evidence environment example used by the deployment regression. Validate local tests and guarded Linux unit checks; no target host, sink, quota, or alert acceptance. |
| 3 | P4 RunPod v2 API contract, provider observations, candidate selection, result receipts, worker revalidation, and shared P1 T2 Gateway tool contract | 50 paths at the historical snapshot | Review exact-resource/fingerprint/expiry checks and every unknown-evidence refusal. Also review the outputSchema/status-log projection together with pre-existing P4 changes in shared `experiment_api.py` and its tests. No candidate backend is accepted, no live provider call or GPU run occurred. |
| 4 | P5 paid authority design and policy gate | 3 paths at the historical snapshot | Review the trust chain and ensure the repository remains parked. Design only; no issuer, permit, spending, or live provider authorization is implemented. |
| 5 | Cross-cutting acceptance and Luna handoff | 15 paths at the historical snapshot | Reconcile status wording only after code slices are reviewed; preserve evidence scope and current blockers. |

At the historical `aa681f4` snapshot, the full review inventory was 178 paths: 169 tracked paths in
`origin/main...HEAD`, all 19 modified tracked worktree paths overlap that set,
and nine untracked files add nine paths. The owner slices below assign 125
follow-up/local paths: P1=5, P3=52, P4=50, P5=3, cross-cutting=15. Together
with the 53 foundation-only paths below and excluding the single reverted path,
the inventory covers all 178 paths exactly once. `gateway/deploy/worker.env.example` remains in the
historical `f054aebe..HEAD` reconstruction range because that checkpoint
deletes it, but it is absent from both `origin/main` and final `HEAD`; exclude
that deletion from the publishable review inventory and candidate patches
based on `main`. The OAuth-specific PostgreSQL cases are isolated in the added
P1 test module; the shared PostgreSQL migration integration test stays with P4
because it imports P4-owned migration helpers. The new P2 recovery acceptance
record belongs to the cross-cutting evidence slice. The v8 restore refresh and
current restore-runbook delta are assigned to the P3 operational slice. The P1
status-log overlay also touches P4-owned `experiment_api.py` and its existing
test file, so their full combined diff remains within the P4 single-owner
slice.
Review sequentially because several contracts span Gateway, core, migrations, and tests. Keep shared files wholly within their assigned slice.

These five ownership slices are independent review scopes; they are not all
standalone full-CI PR boundaries. Reconstructed the P1-only candidate on
`f054aebe` with its three changed paths and the local OAuth-test split. Its
focused OAuth/PostgreSQL tests passed **7/7** using a dedicated PostgreSQL 16
container. The base already provides schema v7 and `grant_id`; the OAuth slice
does not require the later P4 migration. By contrast, the earlier full Gateway
run of cumulative P1+P3 without P4 had four failures in artifact-capacity and
prepare cases. The cumulative P1+P3+P4 candidate then passed Gateway **419/6
skipped**. Therefore prepare PR heads as: (1) P1 alone; (2) P3+P4 together as
one cumulative integration candidate (99 changed paths in the current local
overlay), with P1 already in its base; (3) P5 parked-policy design; and (4)
cross-cutting acceptance/handoff updates with the relevant final code head.
Each proposed head still needs its complete required CI and independent GitHub
review. Do not split P3/P4 into separate merge candidates unless a full-suite
candidate proves the earlier failures are resolved without deferring required
behavior or tests.

Standalone P1 full-suite rerun (2026-10-30): on a fresh detached worktree at
`f054aebe`, applied only the P1 `local_oauth.py`, `test_local_oauth.py`, and
new `test_postgresql_oauth.py` changes. Left P4-owned `test_postgresql.py` at
the base version. With a dedicated PostgreSQL 16 container and the pinned CPU
smoke image, the complete Gateway suite passed **273 passed / 6 skipped** with
one existing Starlette deprecation warning. This reused the installed Gateway
venv on macOS arm64; it is not a fresh locked environment or GitHub CI. The
focused P1 OAuth/PostgreSQL modules also passed 7/7 in the same base setup.
Temporary worktree and PostgreSQL container were removed by the cleanup trap.

## P1 — OAuth refresh and PostgreSQL concurrency (5 current local paths)

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

- `gateway/gpu_gateway/local_oauth.py`
- `gateway/tests/test_local_oauth.py`
- `gateway/tests/test_postgresql_oauth.py` (uncommitted test-only split; move the two OAuth cases from the shared PostgreSQL integration module here)
- `docs/acceptance/2026-10-31-p1-c817-source-provenance-suite.md`
- `docs/acceptance/2026-10-31-p1-c824-candidate-suite.md`

## P3 — CPU operations, artifact storage, and recovery (52 current local paths)

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
- `gateway/deploy/provider-evidence.env.example`
- `gateway/deploy/verify_systemd_units_ci.sh`
- `gateway/deploy/worker-secrets.env.example`
- `gateway/gpu_gateway/app.py`
- `gateway/gpu_gateway/artifacts.py`
- `gateway/tests/test_artifact_permission_migration.py`
- `gateway/tests/test_artifact_storage.py`
- `gateway/tests/test_backup_generation.py`
- `gateway/tests/test_postgresql_backup_integrity.py` (uncommitted P3 regression for current-schema artifact manifest query and paired byte integrity)
- `docs/acceptance/2026-10-30-dirty-source-paired-restore.md`
- `docs/acceptance/2026-10-31-p3-cccf-package-candidate-suite.md`
- `docs/acceptance/2026-10-31-p3-d794-candidate-suite.md`
- `gateway/tests/test_capacity_event_state.py`
- `gateway/tests/test_deploy_units.py`
- `gateway/tests/test_http_auth.py`
- `gateway/tests/test_local_lifecycle_integration.py`
- `gateway/tests/test_local_mcp_integration.py`
- `gateway/tests/test_postgres_lifecycle_integration.py`

## P4 — Provider evidence, selection, GPU contracts, and shared P1 T2 Gateway tool contract (50 paths in the aa681f4-era inventory)

- `docs/acceptance/2026-10-28-result-plan-binding.md`
- `docs/acceptance/2026-10-28-runpod-api-v2-revalidation.md`
- `docs/decisions/2026-10-28-p4-modal-readiness.md`
- `docs/specs/chatgpt-native-experiment-control-plane.md`
- `docs/specs/p4-candidate-execution-receipt-contract.md`
- `docs/specs/p4-capability-selection-contract.md`
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
- `gateway/tests/test_postgresql.py`
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

## Cross-cutting evidence and Luna handoff (15 current local paths)

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
- `docs/acceptance/2026-10-28-oauth-refresh-atomicity.md`
- `docs/acceptance/2026-10-31-postgres-container-crash-recovery.md`
- `docs/acceptance/2026-10-30-current-worktree-source-matched-suite.md`

## Suggested verification order

1. OAuth targeted modules and PostgreSQL one-time refresh regression, then the full Gateway suite with a stoppable PostgreSQL 16 container and digest-pinned CPU image.
2. P3 artifact/backup/capacity tests, `git diff --check`, and the guarded `systemd-analyze verify` helper in an isolated Linux runner. Do not treat this as target-host acceptance.
3. Root/core suite for P4 selector and RunPod v2 contracts; inspect candidate receipt/result tests separately from provider attestation claims.
4. Confirm `policies/repository-state.yaml` is still `parked`; no provider credentials, public settings, spend, or deployment changes.
5. Refresh the full-worktree inventory and exact content digest after any review fix. Run GitHub CI/security review only on the final composed revision before integration.

Current product gates still requiring owner/environment input: intended ChatGPT workspace write-action entitlement and access; selected Linux host, region, public origin, and cost ceiling; notification sink/route/SLO; account-specific free-GPU/quota evidence. Those gates do not stop the offline review work but they prevent claiming live acceptance.

## Sequential patch applicability refresh — 2026-10-30

The owner map was rechecked against `f054aebe..aa681f4` after finding two stale
counts: P1's OAuth acceptance record was already present at the base, so P1 has
three changed paths; cross-cutting has 13 changed paths after including that
record's follow-up update. The map now covers exactly 117 unique changed paths.

Applied each owner patch in P1 → P3 → P4 → P5 → cross-cutting order to fresh
detached worktrees at `f054aebe`. Every cumulative patch applied cleanly, and
all cumulative owned files matched the final HEAD byte-for-byte, including the
intentional deletion of `gateway/deploy/worker.env.example`. This verifies
sequential patch applicability and content fidelity only. It does not establish
standalone slice tests, independent review, GitHub CI for the local docs delta,
or merge readiness.

## Full review-stack reconstruction — 2026-10-30

From a fresh detached worktree at `origin/main` (`24ecb9b`), applied the seven
existing checkpoint diffs in order:
`c824b90` → `7c4454b` → `c8172c0` → `d794c13` → `cccfcb8` → `f15ab32` →
`f054aebe`. Then applied the five follow-up ownership patches in P1 → P3 → P4
→ P5 → cross-cutting order to reach `aa681f4`. The reconstructed tree matched
the final committed tree exactly across all 322 tracked files: path set, file
bytes, and executable bits. The disposable worktree was removed; no branch or
remote ref was created or changed.

This proves these existing checkpoint and ownership patches can be composed to
recreate the current source snapshot. The 79-path CPU/recovery interval now has
five sequential candidate boundaries; the final unit must extend through
`c8172c0` to include the schema-v7 migration fix. Those candidates passed local
full Gateway suites except the intentionally rejected `7c4454b` intermediate.
The separate 117-path follow-up still needs review heads materialized. All
candidates require GitHub CI and reviews. Keep PR #51 intact until replacement
heads pass their required checks and reviews.

## Review sequence for the CPU/recovery follow-up and OAuth migration fix

The `c824b90..7c4454b` interval changes 79 paths. Its last candidate boundary
was not independently acceptable: `7c4454b` adds a PostgreSQL migration test
for schema v7 while its migration implementation remains at v6. The fix first
appears in `c8172c0`. Keep the first four boundaries below, then combine the
41-path CPU integration interval with the 11-path OAuth migration follow-up
into a single final candidate. Results distinguish earlier focused changed-test
runs from this turn's full candidate runs.

| Order | Candidate source boundary | Paths | Full candidate Gateway suite | Review scope |
|---:|---|---:|---|---|
| 1 | `c824b90..6646401` | 19 | Head `6646401`: 204 passed / 1 skipped | Dedicated worker, readiness, supervisor setup |
| 2 | `6646401..2a6f21a` | 21 | Head `2a6f21a`: 209 passed / 1 skipped | Owner-scoped artifact read and cleanup |
| 3 | `2a6f21a..0d02058` | 38 | Head `0d02058`: 219 passed / 1 skipped | Readiness, heartbeat, workload availability, artifact integration |
| 4 | `0d02058..311d6a9` | 25 | Head `311d6a9`: 221 passed / 1 skipped | Outbound HTTP boundary and RunPod allocation checks |
| 5 | `311d6a9..c8172c0` | 52 | Gateway 252/1 skipped (fresh env); source-matched rerun 251/2 skipped; root/Core 515/1 skipped | Final CPU lifecycle/recovery plus schema-v7 OAuth migration fix |

These are source boundaries for a proposed sequential review series, not
pre-created branches or independent PRs. The `0d02058` head includes the test
correction for the `74f004a` blocker-reason change; do not publish `74f004a` as
a head. Do not publish `7c4454b` as the last CPU candidate head: the current
full PostgreSQL + Docker CPU run at that commit failed 1 migration test (236
passed, 1 skipped). Combining through `c8172c0` passed the full Gateway suite
(252 passed, 1 skipped) and the root/core suite (515 passed, 1 skipped). The
2026-10-30 full-stack reconstruction applied the source ranges in parent order
and reproduced all 322 files at current HEAD. These remain local candidate
checks; no GitHub CI or human review was produced.

The earlier first candidate `origin/main..c824b90` also passed the full Gateway suite (199 passed / 1 skipped), WebMCP 3/3, and root/core 452 passed / 1 skipped. The earlier full-stack candidate runs in this section also passed WebMCP 3/3 and `compileall`; the 2026-10-31 source-image reruns did not repeat those two checks.

Exact source-image follow-up (2026-10-31): rebuilt the image at `c8172c0`
from its own Dockerfile, pinned Python base, and matching OCI source/revision
labels. With that digest and a loopback PostgreSQL 16 container, Gateway passed
**251 / 2 skipped** and root/Core **515 / 1 skipped**. The optional Modal
dependency was unavailable in the reused venv; the earlier fresh-venv result
was **252 / 1 skipped**. The first candidate `c824b90` was also rerun with a
source-matched image built from its own Dockerfile: **198 / 2 skipped** and
Core **452 / 1 skipped**. Exact image digests, hashes and limits are in the
dated acceptance records. This corrects the intervening `c824b90` rerun that
used a cached smoke image with one differing `smoke.py` serialization line;
that run is not treated as source-matched evidence.

P3 backup/operations candidate exact-source suite (2026-10-31): built a
candidate-labeled CPU image from `d794c13`, then ran the full suites on a fresh
detached worktree at that head. Gateway passed **272 / 2 skipped** with a
loopback PostgreSQL 16 container; root/Core passed **515 / 1 skipped**. Exact
inputs and scope are in
[`2026-10-31 P3 candidate suite record`](../../acceptance/2026-10-31-p3-d794-candidate-suite.md).
The next source checkpoint `cccfcb8` changes CI and package metadata; its
candidate-specific CI/workflow boundary still needs checking.

The repository requires linear history. After each accepted PR is integrated,
rebase the next source slice onto the new `main`, regenerate its diff, and rerun
its focused tests plus required CI before review. Do not assume the original
checkpoint SHA remains an ancestor after a squash/rebase merge. Keep PR #51
open and unchanged until a replacement sequence has passed checks and reviews;
closing or retargeting it is separate work.

### Cumulative P1+P3+P4 validation and OAuth test split — 2026-10-30

The P1 PostgreSQL OAuth race/rollback cases were moved out of the P4-owned
shared `test_postgresql.py` into `test_postgresql_oauth.py`. This keeps P1's
OAuth regression module independent of P4's migration helper imports. The
prior local ownership inventory was 120 paths: P1=3, P3=50, P4=50, P5=3,
cross-cutting=14. The original committed 117-path inventory remains unchanged.
At that historical snapshot, the local overlay had nine untracked paths: the OAuth and backup
integrity test modules, the P2 crash-recovery record, two P1 candidate records,
three P3 candidate/restore records, and one current-worktree suite record.
The ownership totals at that historical snapshot were P1=5, P3=52, P4=50,
P5=3, and cross-cutting=15.

An initial P1+P3-only full Gateway attempt had four failures in artifact
capacity/prepare tests. That partial candidate omitted the subsequent P4
experiment API contract. Reconstructed the cumulative P1+P3+P4 candidate from
`f054aebe`, including the changed Gateway and core source, the Gateway CI
workflow, and the OAuth test split. With candidate paths first in `PYTHONPATH`,
a dedicated PostgreSQL 16 container, and the digest-pinned CPU smoke image, the
full Gateway suite passed **419 tests / 6 skipped** with one existing
Starlette deprecation warning. The earlier four failures did not reproduce in
the cumulative candidate. The candidate used the installed Gateway venv; this
is local macOS validation, not a fresh locked environment or GitHub CI.

The checkout used for that 2026-10-30 cumulative validation passed the full
root/core suite: **550 tests / 1 skipped**.
`git diff --check` passed after the ownership-map update. Temporary candidate
worktrees and PostgreSQL containers were removed by the run's cleanup trap.
This evidence covers offline source tests only; live ChatGPT, production,
independent GitHub review, selected-host acceptance, real GPU execution, and
paid execution remain unverified.


### Candidate migration-boundary full-suite result — 2026-10-30

A fresh Python 3.12.13 venv with Gateway CI test/worker requirements was used
for both candidate runs. At `7c4454b`, the wheel build succeeded and the full
Gateway suite with PostgreSQL 16 plus a candidate-SHA Docker CPU image returned
**236 passed, 1 skipped, 1 failed**. The failure is
`test_postgres_v4_to_v7_additive_recovery_and_oauth_fields`: this commit added
the test's `DROP COLUMN grant_id` and v7 expectations while
`gateway/gpu_gateway/migrations.py` still declares schema version 6 and creates
no `grant_id` column. `git blame` attributes the test change to `7c4454b`;
`c8172c0` adds migration version 7.

At `c8172c0`, reran the full Gateway suite with a dedicated PostgreSQL 16
container bound to `127.0.0.1:55499` and a Docker CPU image labeled with the
exact candidate SHA: **252 passed, 1 skipped**, one existing Starlette
deprecation warning. The same candidate's WebMCP contract passed 3/3 and
Python entrypoint compilation passed. Its root/core suite passed **515 passed,
1 skipped** using the candidate `src/` with the existing Python 3.12.10 root
venv; the skip is the Python 3.11-specific malformed-RunPod-log reproducer.
All candidate worktrees, the dedicated PostgreSQL container, and tagged CPU
images were removed. This is local candidate validation on macOS arm64, not
GitHub CI, Linux CI, production, or ChatGPT acceptance.


## Full PR #51 path-coverage reconciliation — 2026-10-30

The published PR diff `origin/main...aa681f4` contains 169 paths. The exact
comparison is: `origin/main...f054aebe` has 121 paths; `f054aebe...aa681f4`
has 117 paths; they overlap on 68 paths. Their union is 170 paths because
`gateway/deploy/worker.env.example` was reverted to the base-tree state and is
absent from the final PR diff. The follow-up ownership map above covers the
117-path incremental range. Assign the 53 foundation-only paths below to the
last existing checkpoint range that changed each path; combined with the
follow-up map and excluding the reverted path, this accounts for all 169
published paths exactly once. The current uncommitted OAuth test split and P3 PostgreSQL backup-integrity
test and P2 acceptance record add three local-only paths, so the full local
review inventory is 172 paths. The owner lists compared with
`git diff f054aebe96460fe033dde8d91d7e3bbab0255655 HEAD` plus untracked files
contain 120 unique entries, with no missing, duplicate, or stale paths.

| Foundation-only owner range | Paths | Review unit |
|---|---:|---|
| `origin/main..c824b90` | 6 | P1 trusted CPU admission, container boundary, source validation, and package root |
| `c824b90..6646401` | 1 | P2 worker/recovery integration and local configuration |
| `6646401..2a6f21a` | 0 | Its paths are shared with later ranges/follow-up ownership |
| `2a6f21a..0d02058` | 6 | P2 readiness, smoke workload, recovery supervisor tests, and migration docs |
| `0d02058..311d6a9` | 12 | P1/P2 HTTP egress boundary and RunPod v1 hardening; RunPod call path remains disabled |
| `311d6a9..7c4454b` | 12 | P1 real CPU backend and P2 recovery integration; review together with schema-v7 fix at `c8172c0` |
| `7c4454b..c8172c0` | 6 | P1 owner/OAuth migration and recovery review handoff |
| `c8172c0..d794c13` | 2 | P3 capacity timer and local CPU policy template |
| `d794c13..cccfcb8` | 5 | P0 workflow checks and package dependency/security regression |
| `cccfcb8..f15ab32` | 0 | No foundation-only paths last changed in this range |
| `f15ab32..f054aebe` | 3 | P0 wheel/package metadata and lockfile |
| **Total** | **53** | Foundation-only paths; shared paths stay with the follow-up owner map |

Exact foundation-only path list:

- `origin/main..c824b90`: `gateway/gpu_gateway/container_runtime.py`, `gateway/policies/local-cpu.json`, `gateway/project_control/runner.py`, `gateway/workloads/cpu-smoke/supervise.py`, `pyproject.toml`, `uv.lock`.
- `c824b90..6646401`: `gateway/.env.example`.
- `2a6f21a..0d02058`: `README.md`, `docs/MCP_TOOL_MIGRATION.md`, `docs/acceptance/2026-10-28-recovery-supervisor.md`, `gateway/gpu_gateway/health.py`, `gateway/tests/test_health.py`, `gateway/workloads/cpu-smoke/smoke.py`.
- `0d02058..311d6a9`: `src/gpu_control/http_security.py`, `src/gpu_control/providers/runpod_network_volume.py`, `src/gpu_control/providers/runpod_v1.py`, `src/gpu_control/providers/runpod_v1_adapter.py`, `src/gpu_control/source.py`, `tests/test_http_security.py`, `tests/test_provider_selftest.py`, `tests/test_runpod_current_pricing.py`, `tests/test_runpod_v1.py`, `tests/test_runpod_v1_adapter.py`, `tests/test_runpod_v2_list_pods.py`, `tests/test_source.py`.
- `311d6a9..7c4454b`: `docs/acceptance/2026-10-28-postgres-restore-drill.md`, `docs/acceptance/RECOVERY_REVIEW_CHECKLIST.md`, `gateway/Dockerfile`, `gateway/Dockerfile.worker`, `gateway/docker-compose.yml`, `gateway/examples/workloads.json`, `gateway/gpu_gateway/local_backend.py`, `gateway/tests/test_local_backend_integration.py`, `gateway/tests/test_recovery_supervisor.py`, `gateway/tests/test_service.py`, `gateway/tests/test_worker_recovery.py`, `gateway/workloads/cpu-smoke/Dockerfile`.
- `7c4454b..c8172c0`: `docs/acceptance/2026-10-28-owner-issuer-migration.md`, `docs/acceptance/2026-10-28-recovery-review-handoff.md`, `gateway/gpu_gateway/auth.py`, `gateway/gpu_gateway/owner_migration.py`, `gateway/tests/test_external_auth.py`, `gateway/tests/test_owner_migration.py`.
- `c8172c0..d794c13`: `gateway/deploy/gpu-control-artifact-capacity.timer`, `gateway/examples/local-cpu-workloads.template.json`.
- `d794c13..cccfcb8`: `.github/workflows/ci.yml`, `.github/workflows/gateway-bridge-ci.yml`, `.github/workflows/project-checks-ci.yml`, `gateway/requirements.txt`, `tests/test_workflow_security.py`.
- `f15ab32..f054aebe`: `gateway/pyproject.toml`, `gateway/tests/test_packaging_metadata.py`, `gateway/uv.lock`.

The ranges are review units, not permission to publish them as-is: the
repository requires linear history, so after each reviewed change is merged,
rebase its successor onto the new `main`, regenerate the patch, rerun tests and
required CI, and obtain an independent GitHub review. The known `7c4454b`
standalone migration failure must be resolved by including the `c8172c0` schema
v7 fix before accepting that combined CPU/recovery unit. No branch creation,
commit, push, PR retarget, or merge was performed for this path-map refresh.

## Materialized local roadmap review refs — 2026-10-30 16:04 UTC

Created twenty local-only branch refs at the existing linear-history
candidate heads. Their stacked PR bases are the immediately preceding ref; no
checkout, worktree, remote ref, PR, commit, or merge was changed.

| Stack | Candidate ref | Base → head | Changed paths | Existing focused-test record |
|---:|---|---|---:|---|
| 1 | `codex/gpu-control-p1-01-baseline` | `origin/main` → `b3cb04d` | 14 | 13 passed |
| 2 | `codex/gpu-control-p1-02-mcp-contract` | `codex/gpu-control-p1-01-baseline` → `195de19` | 9 | 37 passed |
| 3 | `codex/gpu-control-p1-03-admission` | `codex/gpu-control-p1-02-mcp-contract` → `2440897` | 14 | 37 passed |
| 4 | `codex/gpu-control-p1-04-local-backend` | `codex/gpu-control-p1-03-admission` → `3e1c31c` | 19 | 33 passed |
| 5 | `codex/gpu-control-p1-05-recovery` | `codex/gpu-control-p1-04-local-backend` → `c824b90` | 13 | 18 passed (PostgreSQL rerun) |
| 6 | `codex/gpu-control-stack-06-chatgpt-readiness` | `codex/gpu-control-p1-05-recovery` → `2090bbd` | 6 | 24 passed |
| 7 | `codex/gpu-control-stack-07-worker-units` | `codex/gpu-control-stack-06-chatgpt-readiness` → `cc1e263` | 5 | no changed test files |
| 8 | `codex/gpu-control-stack-08-recovery-supervisor` | `codex/gpu-control-stack-07-worker-units` → `6646401` | 17 | 34 passed (PostgreSQL rerun) |
| 9 | `codex/gpu-control-stack-09-supervisor-cleanup` | `codex/gpu-control-stack-08-recovery-supervisor` → `42b986e` | 3 | 4 passed |
| 10 | `codex/gpu-control-stack-10-cancel-cleanup` | `codex/gpu-control-stack-09-supervisor-cleanup` → `7761e14` | 5 | 4 passed |
| 11 | `codex/gpu-control-stack-11-artifact-read` | `codex/gpu-control-stack-10-cancel-cleanup` → `2a6f21a` | 18 | 16 passed |
| 12 | `codex/gpu-control-stack-12-artifact-retention` | `codex/gpu-control-stack-11-artifact-read` → `f58e24b` | 16 | 15 passed (PostgreSQL rerun) |
| 13 | `codex/gpu-control-stack-13-artifact-recovery` | `codex/gpu-control-stack-12-artifact-retention` → `aff28cd` | 18 | 47 passed (PostgreSQL rerun) |
| 14 | `codex/gpu-control-stack-14-readiness-heartbeat` | `codex/gpu-control-stack-13-artifact-recovery` → `0d02058` | 14 | 22 passed |
| 15 | `codex/gpu-control-stack-15-http-security` | `codex/gpu-control-stack-14-readiness-heartbeat` → `311d6a9` | 25 | 92 passed (existing focused range) |
| 16 | `codex/gpu-control-stack-16-cpu-oauth-migration` | `codex/gpu-control-stack-15-http-security` → `c8172c0` | 52 | Full Gateway 252 / 1 skipped; root/core 515 / 1 skipped |
| 17 | `codex/gpu-control-stack-17-backup-operations` | `codex/gpu-control-stack-16-cpu-oauth-migration` → `d794c13` | 13 | 21 passed (backup/deploy-unit tests) |
| 18 | `codex/gpu-control-stack-18-ci-packaging` | `codex/gpu-control-stack-17-backup-operations` → `cccfcb8` | 8 | 6 passed (workflow/security + package metadata) |
| 19 | `codex/gpu-control-stack-19-p4-selection` | `codex/gpu-control-stack-18-ci-packaging` → `f15ab32` | 5 | Documentation-only; no runtime tests |
| 20 | `codex/gpu-control-stack-20-foundation-evidence` | `codex/gpu-control-stack-19-p4-selection` → `f054aebe` | 15 | 31 passed (HTTP auth + OAuth + package metadata) |

All twenty exact commit ranges passed `git diff --check` in this checkout.
Stages 17, 18, and 20 were revalidated in temporary detached worktrees with
`PYTHONPATH` pointing at each candidate's `gateway/` and `src/`: stage 17
passed 21 backup/deploy-unit tests, stage 18 passed 4 workflow-security and 2
package-metadata tests, and stage 20 passed 31 HTTP-auth/OAuth/package-metadata tests.
The tests used the existing Python 3.12 environments; the candidate-specific
changed modules were resolved from each candidate path. Stage 19 changes only
documentation and has no runtime test target. Temporary worktrees were removed
and the primary checkout/refs remain unchanged. The latest current-worktree
Gateway integration result is 427 passed / 2 skipped in the 2026-10-31
revalidation above; the separate root/core result is 550 passed / 1 skipped.
These are local candidate checks only; all refs still need required GitHub CI
and independent GitHub review after publication. Keep PR #51 open and
unchanged until replacements pass their own gates.

## Refreshed GitHub PR range map — 2026-10-31

Read-only `gh pr view` refresh found #51–#59 all OPEN/DRAFT. All nine reported
status entries per PR were successful (seven protected Actions checks plus
two Vercel statuses in this query); all nine had zero submitted reviews. PR
#52 alone reports `REVIEW_REQUIRED`. Current base/head and changed-path counts:

| PR | Base → head | Paths | Review decision |
|---:|---|---:|---|
| #51 | #57 `51b88f6` → `e3ffcef` | 100 | none |
| #52 | `main` `24ecb9b` → `bc9b030` | 43 | review required |
| #53 | #52 `bc9b030` → `f8ee5d0` | 19 | none |
| #54 | #53 `f8ee5d0` → `113d7bf` | 21 | none |
| #55 | #54 `113d7bf` → `dc109cb` | 38 | none |
| #56 | #55 `dc109cb` → `34cc58c` | 25 | none |
| #57 | #56 `34cc58c` → `51b88f6` | 54 | none |
| #58 | #51 `e3ffcef` → `561a6c7` | 7 | none |
| #59 | #57 `51b88f6` → `76c2a1a` | 14 | none |

PR #51 and #59 have the same base. Their changed-path sets overlap on 13 of
#59's 14 paths; exact blob comparison shows only
`gateway/deploy/gpu-control-artifact-capacity.timer` and
`gateway/examples/local-cpu-workloads.template.json` are identical at both
heads. The other 12 overlapping paths differ, including backup generation,
PostgreSQL artifact-integrity coverage, deployment units, and operational
evidence. Therefore neither PR is a duplicate copy of the other; the P3
changes must be reconciled before selecting a replacement head. PR #58's
7-path schema-v9 OAuth delta remains a separate follow-up on #51.

Compared each PR head's final blob on every changed path against the current
primary checkout (including its uncommitted source). Exact-content matches:
PR #51 **64/100**, #52 **6/43**, #53 **0/19**, #54 **1/21**, #55 **6/38**,
#56 **12/25**, #57 **18/54**, #58 **6/7**, and #59 **5/14**. The mismatch set
includes runtime code as well as documentation, so these counts are not a
code-quality score; they show which remote head contents already equal the
current candidate tree. PR #58's only mismatch is its acceptance evidence
file; PR #59's unmatched contents include backup/service behavior. Rebuild
candidate diffs from the intended exact base and source tree instead of
assuming that the existing stack's final blobs reproduce the current local
state.

This read-only range map creates no approval. The next candidate map must
compare exact commits/blobs and required checks on proposed heads, preserve the
linear-history rule, and keep the full source candidate as evidence rather
than turning broad PR #51 into the default merge unit.

## Current full-source candidate split and local validation — 2026-10-31

Generated six disjoint patch groups from exact PR #51 base
`e3ffcef580d4b7b13ec12f1b6c53014bbca254b1` to the current source tree.
Applying them in order to a fresh detached worktree reproduced all 340 files
byte-for-byte (zero missing, mismatched, or extra files); every
`git apply --check` and final `git diff --check` passed. Patch files are in
`/tmp` for review/candidate replay. Paths and SHA-256:

| Order | Candidate slice | Paths | Patch SHA-256 | Focused result |
|---:|---|---:|---|---|
| 1 | P1 OAuth schema-v9 + local CPU readiness | 13 | `70306e7d90d2636c2572492c1771785d68a8ce5f058cee27c6ce8f1718e383c1` | 56 passed |
| 2 | P2 worker crash recovery | 2 | `67fb68d464202d3a1be905873712b4f73d6fa8155aa330589c99eea5d3c17850` | 1 passed, 1 deselected |
| 3 | P3 backup operations/integrity | 11 | `16ddf1b73d19e1257613bc3cbe06649571ed2173ced6f0bbd0e8431eef79a840` | Tested cumulatively with P4 below |
| 4 | P4 provider contract/receipt follow-up | 9 | `f45f0e7b84057e83945e200a1176be0cd6ec83cd6adcde7d0d1c6eb70a51e9fb` | P3+P4 focused set: 48 passed |
| 5 | P5 offline paid authorization | 11 | `9e499e360a115c518122bcfe34512e4593dca836cf3c894002803c25e7181ba5` | Gateway 77 passed; Core 38 passed |
| 6 | Cross-cutting evidence and CI workflow updates | 21 | generated at `/tmp/gpu-control-slice-cross_cutting_and_ci-on-e3ffcef.patch` | Documentation/workflow only; full source replay matched |

P1 focused command covered OAuth, migration, HTTP readiness/auth, PostgreSQL
migration, and OAuth PostgreSQL tests. P2's crash-after-Docker-start test was
first skipped because the dedicated container-name variable was absent; after
setting it to the live disposable PostgreSQL container, the same test passed
1/1. P3+P4 tests covered backup generation, PostgreSQL artifact integrity,
registry requirements, and candidate receipts. P5 Gateway tests covered the
authorization verifier and experiment API; Core tests covered the verifier
and paid policy. PostgreSQL 16 was bound only to loopback; CPU image and
database resources were removed after the run.

The earlier full candidate suite result remains Gateway 482 passed / 2
optional skips and Core 559 passed / 1 Python-version-specific skip, on code
files unchanged by this documentation/range-map update. This candidate split
is locally replayable and source-matched, but each proposed published head
still needs its own required GitHub CI and independent approval. No PR or
branch was edited, and parked/spending gates remain unchanged.

### Rebase candidate onto PR #58 schema-v9 head — 2026-10-31

PR #58's exact head `561a6c7ac697dfdf22f304b60e313fccb2c806a4` is a better
candidate base than PR #51 `e3ffcef`: six of PR #58's seven changed-path final
blobs already match the current local source, including the schema-v9 OAuth
implementation. Its remaining mismatch is the acceptance record. Replayed the
full current source on #58 with
`/tmp/gpu-control-full-current-on-561.patch` (test-time SHA-256
`cd23fe4c2f0c6a98b4d54c2ebaca6578e753b611d59226e681a9bde8aa945c29`); all 340
files matched exactly. The `gateway/tests/test_postgresql_oauth.py` file was
untracked in the primary checkout but already byte-identical at the #58 base;
the replay handled the index/worktree difference and made no final content
change to that path.

Regenerated the same six logical slices against #58. Their actual final-tree
diff is **61 paths**: P1 OAuth/readiness 7, P2 recovery 2, P3 operations 11,
P4 provider contract 9, P5 offline authorization 11, and cross-cutting/CI 21.
Sequential `git apply --check` and application recreated the exact 340-file
current tree. The focused P1 suite was rerun on the #58-based candidate and
passed **56 tests**. Earlier focused P2 1/1, P3+P4 48/48, P5 Gateway 77/77 and
Core 38/38, plus the full Gateway/Core suite, exercise identical final code
blobs. Their exact commands and local-only scope are recorded above and in the
acceptance ledger.

This is the current best local review stack: PR #58's schema-v9 content first,
then P1 readiness, P2, combined P3+P4, P5 offline verifier, and cross-cutting
CI/evidence. It does not imply approval of #58 or authorization to change any
GitHub PR; the stack remains Draft and requires independent review/checks.
