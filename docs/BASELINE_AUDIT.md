# Baseline audit for ChatGPT experiment control

Date: 2026-10-28 (Asia/Tokyo)

## Audited identities

- Repository: `Unjuno/gpu-control`
- Main commit: `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` (`Tolerate bounded GitHub runner queue delays (#50)`)
- Main protection read from GitHub API: disabled (`protected: false`). This is recorded only; no settings changed.
- Follow-up settings read: repository rulesets are empty; GitHub `Production` and `Preview` Environments have no protection rules or deployment-branch policy. Connected account has repository admin permission; no settings or secrets were changed/read.
- Additional GitHub connector refresh on 2026-10-28: PR #43 is still OPEN/DRAFT at the same base/head SHAs, and the repository rulesets endpoint still returns an empty list. The connector receives HTTP 403 for the `main` branch-protection endpoint, so this connection cannot independently confirm the current legacy branch-protection setting. The earlier direct settings read above remains the recorded source for `protected: false`; recheck through an authorized settings view before relying on that value.
- Current pushed branch head (refreshed 2026-10-28): `codex/chatgpt-cpu-vertical` at `f054aebe96460fe033dde8d91d7e3bbab0255655`, Draft PR [#51](https://github.com/Unjuno/gpu-control/pull/51) against unchanged main `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. GitHub reports all listed checks successful at this pushed head and no submitted reviews. The local worktree has additional uncommitted changes, so those remote checks do not cover current worktree state. The previously inspected Vercel preview had liveness/package imports but no configured DB/OAuth/worker and is not ChatGPT acceptance. Main protection still needs an authorized settings-path recheck because the connected integration returned HTTP 403 for that endpoint.
- PR #43: OPEN, DRAFT, base `main`, head `1699b75df8262023501d41279e83bf429dca1be4`, base SHA `a96a24818a5f8bc03b479c35b5e3f957f08dbe04`, 35 changed files.
- PR #51 live review refresh on 2026-10-28: no submitted reviews and no review threads. Its checks are current-head runs listed above. PR #43 retains its historical review/check state and remains a separate Draft audit input.
- PR #43 merge base is `a96a24818a5f8bc03b479c35b5e3f957f08dbe04`.
- PR #43 commits absent from main according to `git cherry`:
  - `4abfbec` Add isolated wheel and source-distribution release checks
  - `c653e63` Harden release boundaries and add reproducible offline acceptance
  - `1699b75` Fix known pytest temporary-directory vulnerability

The pull request description reports earlier successful CI and package runs. Those are historical PR evidence, not current-main or current-head verification. This audit did not run the repository test suite or independently repeat those runs.

## What main has added since the PR base

Main includes PRs #44 through #50, including:

- Remote MCP Streamable HTTP, FastAPI Gateway, operator workload registry, durable database queue and independent worker;
- built-in single-owner OAuth 2.1 with PKCE and refresh support;
- owner-account GitHub comment bridge and a registered external-source CPU check in a fixed CPU-only container;
- ingress tests denying non-demo execution while repository mode is parked.

The GitHub comment CPU route is a distinct interface. It demonstrates an existing constrained CPU execution capability, but does not satisfy ChatGPT-to-MCP-to-result acceptance. The Gateway currently registers demo, Modal Sandbox and an operator-supplied RunPod bridge. The default workload is demo. Demo explicitly returns `simulation=true` and `gpu_used=false`.

GitHub Issue #48 remains OPEN. Its comments record a successful `orbitune-tokenizer`
CPU receipt from workflow run `36136518003` on control-plane SHA
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, plus `integrations` and `list`
receipts from runs `36137003454` and `36137013212`. This is CPU-only evidence
from the Issue/comment workflow. The Issue body explicitly says that the normal
ChatGPT path is not yet enabled until the relevant PR is merged and deployed;
these receipts do not prove ChatGPT OAuth, MCP tool discovery, the current local
branch, or cross-conversation retrieval.

## PR #43 disposition against current main

`git cherry -v origin/main refs/remotes/origin/pr-43/head` marks all three PR commits with `+`: no commit was cherry-picked or merged as the same patch. Main later added files in the same product area, so do not merge the stale branch wholesale. Re-evaluate each behavior and its regression evidence against current main before reusing code.

| PR #43 area | Current-main evidence | Disposition |
|---|---|---|
| pytest temporary-directory security fix | main baseline pinned pytest 8.4.2 (`pytest>=8,<9`); PR changed to 9.0.3 | Applied on this implementation branch as `pytest>=9.0.3,<10`, currently locked to 9.1.1. The official advisory says versions before 9.0.3 are affected. Core tests passed under the locked dev environment. |
| HTTP security helpers and regressions | PR adds `src/gpu_control/http_security.py`, tests for redirect/response/body/timeout bounds; Gateway clients are separate | `auth.py` bounds external OIDC token/JWKS JSON at 64 KiB, rejects compressed/ambiguous JSON, and disables redirects. Core `source.py` bounds GitHub API bodies at 2 MiB and rejects redirects. RunPod REST v1/v2, pricing GraphQL, and result-object reads use the shared no-redirect transport and bounded bodies (2 MiB for API JSON, per-result cap for S3). Both adapters recheck permit, price validity, and occupancy evidence immediately before create. Injected tests cover these boundaries; no live IdP/provider compatibility is established. |
| RunPod allocation and recovery | PR hardens allocation-time permit/price rechecks, redirects and receipt-bound recovery; main is newer than PR base and contains Gateway/worker plus RunPod REST v1 / pricing / volume work | This local worktree now rechecks permit, pricing freshness, and the same short-lived occupancy evidence immediately before create; injected-clock regression evidence is recorded in `docs/IMPLEMENTATION_PROGRESS.md`. The patch is uncommitted and has no live provider compatibility evidence. PR #43's trusted receipt-bound recovery-only behavior remains unverified/unimplemented here and stays in P5; account-wide submit serialization is a separate remaining gate. Do not cherry-pick the stale branch wholesale. |
| validation, source and policy hardening | PR has focused changes/tests in core `validation.py`, `source.py`, `policy.py`; main's Gateway introduces a separate registered workload and source-check path | Review current core callers and external CPU route independently; do not assume one validator covers both. |
| wheel/sdist completeness | PR adds `MANIFEST.in`, `scripts/check_distribution.py`, package-check workflow and isolated install tests; current main has no these paths | Useful for standalone CLI release, but separate from the first ChatGPT CPU vertical. Schedule after T1 or before publishing a package. |
| release and parked-mode documentation | PR adds independent acceptance/addendum and edits README/PARKED_MODE; main README is stale relative to `policies/repository-state.yaml` and `docs/STATUS.md` | Adopt corrected facts selectively. Do not copy old release claims as current evidence. |

## Inconsistencies fixed during the audit

The current policy and `docs/STATUS.md` select Orbitune SHA `fc131174a9b529a9825f54fccf1a7df4c63c9a1a` and completion protocol v3. The README named SHA `38594057d1b118a7acf6c843e39d7d8a25571316` and protocol v2. README now follows the machine policy and STATUS. This is a documentation correction; it does not enable the workload or provider.

The pytest dependency update addresses [GHSA-6w46-j5rx-g56g / CVE-2025-71176](https://github.com/advisories/GHSA-6w46-j5rx-g56g), which lists pytest versions below 9.0.3 as affected. The current lock resolves pytest 9.1.1. This does not claim that all project dependencies are vulnerability-free.

## Current worktree and acceptance baseline (refreshed 2026-10-28)

- Local branch: `codex/chatgpt-cpu-vertical` at `f054aebe96460fe033dde8d91d7e3bbab0255655`, with 63 modified/untracked worktree paths at the latest refresh (44 tracked paths with diffs and 19 untracked paths). They are not covered by PR #51's remote checks, and no changes were staged, committed, pushed, or merged during the refresh.
- Submit and the queued local worker now revalidate current registered workload identity against the exact approved plan before container start. Missing/unreadable registry fails closed. Focused local-admission regression: 16 passed; API/MCP/lifecycle/PostgreSQL modules: 23 passed / 3 skipped because Docker image/PostgreSQL integration inputs were not configured.
- Gateway now exposes canonical ChatGPT tools for capability discovery, prepare, submit, status, result, cancel, list, and bounded artifact reads. Registered `local_cpu` runs use exact operator manifests, a zero-cost local admission policy, a separate Docker worker, immutable image/source/plan binding, and owner-bound result/artifact retrieval. Current offline/local container/PostgreSQL evidence is recorded in `docs/IMPLEMENTATION_PROGRESS.md` and `docs/acceptance/2026-10-28-local-integration-revalidation.md`; it proves local test-host behavior only.
- P1 is not accepted as a ChatGPT product flow: the live ChatGPT workspace's custom MCP write-action eligibility, OAuth connection, tool discovery/refresh, actual experiment call, and retrieval from a separate conversation have not been verified. The GitHub Issue #48 project-control route did complete tokenizer CPU workflow run `36136518003` on main and returned a receipt, but that distinct GitHub-comment interface does not establish ChatGPT MCP acceptance.
- P2 lifecycle, worker recovery, paired database/artifact backup, and synthetic PostgreSQL restore paths have local evidence. Production/Neon restore, target-host recovery, second-operator execution, and measured RPO/RTO remain open.
- P3 has a documented dedicated-Linux/systemd + managed-PostgreSQL topology, split service identities/configuration, guarded unit verification, and local filesystem/UID evidence. No host/provider/region/monthly cost ceiling/public origin is selected; units are not installed on a target host; TLS, persistent quota/alerts, deployed readiness, seven-day operation, and production recovery acceptance remain open.
- P4 core workload/cost/quota evidence types and deterministic selector exist offline. The Modal billing-only observation adapter reads only injected `billing.rates()` and `summary()` values, explicitly lacks quota evidence, and is selection-ineligible. Gateway now verifies signed provider observations, maps exact candidates into PlanV2, and revalidates the same candidate at prepare/submit/worker-intent boundaries. No provider registration is accepted for candidate-bound execution, and no live Modal account/quota/GPU evidence exists.
- `policies/repository-state.yaml` remains `mode: parked`; Modal/RunPod paid execution and generic external container execution remain disabled. No provider credential, paid compute, production deployment, or mode change was performed.

## Next implementation action

The current 116-path worktree is assigned to five sequential review slices in [`2026-10-28-gpu-control-worktree-slices.md`](superpowers/plans/2026-10-28-gpu-control-worktree-slices.md); the latest machine check found exactly 116 actual and 116 assigned paths, with no missing or stale entries. Current local evidence is 423 Gateway tests passed / 2 optional SDK skips with PostgreSQL 16 and local Docker CPU, plus 550 root/core tests passed / 1 skip. PR #51 remains Draft on remote head `f054aebe`; its checks do not include the local worktree and no independent GitHub review is present. The ChatGPT web session is currently logged out, so the intended workspace role/permissions remain unknown. The product owner still needs to provide authenticated target-workspace access and select the persistent host, region, public HTTPS origin, notification route/SLO, and cost ceiling for live P0/P1/P3 acceptance. Keep those gates open, continue offline work, and keep the admission policy parked with no paid providers enabled.

## Latest read-only baseline refresh (2026-10-28 11:27 UTC)

- GitHub REST branch metadata for `main` returned SHA
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, `protected: true`, and seven
  required status contexts: Python 3.11/3.12/3.13, Trusted reference
  container, Gateway offline tests, Gateway comment bridge tests, and Project
  bridge tests. The repository rulesets endpoint returned an empty list. The
  direct `/branches/main/protection` endpoint remains unavailable to the
  connector (403), so the current check confirms the protected flag and status
  contexts only; the required-review settings remain supported by the earlier
  successful 09:44 readback recorded below, not this connector response.
- PR #51 is still OPEN/DRAFT/unmerged, base
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, pushed head
  `f054aebe96460fe033dde8d91d7e3bbab0255655`; latest review and inline-thread
  queries returned none. The clean remote head remains separate from local
  worktree changes.
- Current worktree: 74 tracked modified/deleted paths plus 42 untracked paths,
  116 total; zero staged paths. The slice inventory has 116 entries with no
  missing or stale paths. `git diff --check` passes. Current root suite is
  550 passed / 1 skipped; current full Gateway suite with the fixed-port,
  disposable PostgreSQL 16 and real local CPU image is 423 passed / 2 optional
  SDK skips. Exact commands and the dynamic-port failure/retry are recorded in
  `docs/acceptance/2026-10-28-local-integration-revalidation.md`.
- No remote refs, branch rules, PR state, deployment, provider, or paid-compute
  setting was changed in this refresh. `policies/repository-state.yaml`
  remains `mode: parked`.

## Latest P0/P1 state refresh (2026-10-28 04:55 UTC)

- GitHub PR #51 remains OPEN/DRAFT and unmerged, base SHA `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, head SHA `f054aebe96460fe033dde8d91d7e3bbab0255655`; its remote head matches local HEAD. The pull request has 60 commits and 121 changed files. The four pull-request workflow runs at that head (CI, Gateway offline, Gateway comment bridge, Project bridge) are completed successfully. GitHub reports zero submitted reviews and zero inline review threads. These checks cover only the pushed head, not the 63 local worktree paths.
- A fresh unauthenticated production-alias probe returned `/healthz` 200 with local OAuth configured, `/readyz` 404, and `/mcp` 401. It establishes liveness and the unauthenticated boundary only. No OAuth grant, ChatGPT connection, experiment, deployment identity, or production readiness was verified; P1 acceptance remains NOT RUN.
- No change was staged, committed, pushed, merged, deployed, or made to `policies/repository-state.yaml`; the policy remains parked.

## Continuation revalidation (2026-10-28)

- Re-read the current worktree at branch `codex/chatgpt-cpu-vertical`, HEAD
  `f054aebe96460fe033dde8d91d7e3bbab0255655`: 56 tracked paths have diffs and
  33 untracked paths are present (89 total). The GitHub PR #51 still points to
  that pushed HEAD, remains OPEN/DRAFT against `main` at
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, and reports zero reviews. Its
  listed PR checks are successful; they do not cover any local worktree path.
- A read-only security review of the uncommitted P1 ChatGPT-to-local-CPU and
  authorization changes returned no actionable findings in that scope. It did
  not review all 89 paths or substitute for a repository-level review of the
  composed changes. No tests were run during this continuation.
- The previous artifact-readiness concern about a zero free-space threshold is
  resolved in the current code: `inspect_artifact_storage` always requires a
  dedicated filesystem and performs the bounded write probe, independently of
  the configured capacity floor. This is source inspection, not target-host
  mount acceptance.
- No current ChatGPT workspace access, role, app permission, tunnel association,
  or tool invocation is available from this checkout or its GitHub state. P0's
  workspace gate and P1's real ChatGPT acceptance therefore remain NOT RUN.
- Repository policy is still `mode: parked`. No staging, commit, push, merge,
  deployment, provider call, or paid execution occurred.

## Current continuation refresh (2026-10-28)

- Local state remains branch `codex/chatgpt-cpu-vertical` at base
  `f054aebe96460fe033dde8d91d7e3bbab0255655`. The current worktree has 111
  changed paths (70 modified/deleted and 41 untracked); all are assigned once
  in [`2026-10-28-gpu-control-worktree-slices.md`](superpowers/plans/2026-10-28-gpu-control-worktree-slices.md).
  Automated set comparison found no missing, extra, or duplicated paths.
- GitHub read-only refresh: PR #51 remains OPEN/DRAFT, base
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, remote head
  `f054aebe96460fe033dde8d91d7e3bbab0255655`, 60 commits and 121 remote files.
  Its four Actions workflows remain successful on that remote head (CI
  `40614634054`, Gateway offline `40614633953`, Gateway comment bridge
  `40614633965`, Project bridge `40614633942`). They do not cover this local
  worktree. PR remains a draft; no local changes were pushed.
- Current local suites passed: Gateway **403 / 2 optional skips** with
  PostgreSQL 16 and digest-pinned CPU containers; root/core **549 / 1 optional
  skip**. Exact environment and the corrected stoppable-DB harness are recorded
  in `docs/acceptance/2026-10-28-local-integration-revalidation.md`.
- ChatGPT MCP account/workspace eligibility and real OAuth/tool execution
  remain NOT RUN. P3 host, public origin, cost ceiling, notification delivery,
  and seven-day operation remain open. P4 has no accepted live GPU backend.
  P5 authority is design-only. `policies/repository-state.yaml` remains
  `mode: parked`; no provider API, GPU allocation, or paid execution occurred.


## Authenticated preview runtime refresh (2026-10-28 09:00 UTC)

Vercel protected-URL fetch (temporary share access, read-only GETs) observed
the PR preview `/healthz`=200 with `configured=false` and
`auth_configured=false`; `/readyz`=503 with all six readiness components false;
protected-resource metadata=503 `configuration_required`. Preview runtime is
reachable but unconfigured and not ready. No app credentials, OAuth grant,
ChatGPT connection, deployment/configuration change, or paid resource was used.
Production alias observation remains separate; `policies/repository-state.yaml`
remains `mode: parked`.

## P0 baseline recheck (2026-10-28 09:43 UTC)

Read-only GitHub API refresh confirmed repository `Unjuno/gpu-control` is
public, `main` is the default branch, and the connected account has repository
admin permission. `GET /repos/Unjuno/gpu-control/branches/main/protection`
returned HTTP 404 `Branch not protected`; therefore the earlier recorded
unprotected state is current, and no required pull request review or required
status-check enforcement has been independently observed. No settings were
changed.

PR #51 remains OPEN/DRAFT, base `main` at
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, head
`f054aebe96460fe033dde8d91d7e3bbab0255655`, with 60 commits and 121 changed
files. The four PR-triggered workflows for that pushed head completed
successfully: CI `40614634054`, Gateway offline `40614633953`, Gateway comment
bridge `40614633965`, and Project bridge `40614633942`. These checks do not
cover the 111 dirty local paths, do not constitute independent review, and do
not satisfy a required-check branch rule while `main` has no protection.
The current combined status endpoint separately reports Vercel success; that
is build/deployment status only, not a ready Gateway runtime. PR #51 remains
unmerged and draft. No branch setting, PR state, deployment, or local worktree
content was changed by this inspection. Do not integrate the local changes
without independent review; at this observation time, required GitHub gates
were not configured. The following subsection records their later configuration
and verification.

### `main` protection configured and re-read (2026-10-28 09:44 UTC)

After the read-only audit identified the missing protection, configured GitHub
branch protection on `main` and fetched it again from the API. The confirmed
rules require a PR, one approval from someone other than the latest pusher,
automatic dismissal of stale approvals, resolved review conversations, linear
history, up-to-date branch status, and all seven successful GitHub Actions
checks observed on the current PR head: Python 3.11/3.12/3.13, Trusted reference
container, Gateway offline tests, Gateway comment bridge tests, and Project
bridge tests. The checks are scoped to GitHub Actions app ID 15368. Admins are
also subject to the rule; force-push and deletion are disabled.

Post-change read confirmed each setting. PR #51 remains OPEN/DRAFT at the same
base/head SHAs; GitHub reports `REVIEW_REQUIRED` and no submitted reviews, so
the new gate is active and correctly prevents merging until independent review.
The four workflows on its pushed head are successful; Vercel remains a
non-required deployment status. The dirty local worktree is not covered by
those checks and has not been pushed. The protection change does not alter
`policies/repository-state.yaml`, which remains parked; no deployment, provider
call, GPU allocation, or paid execution occurred.
