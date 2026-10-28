# Baseline audit for ChatGPT experiment control

Date: 2026-10-28 (Asia/Tokyo)

## Audited identities

- Repository: `Unjuno/gpu-control`
- Main commit: `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` (`Tolerate bounded GitHub runner queue delays (#50)`)
- Main protection read from GitHub API: disabled (`protected: false`). This is recorded only; no settings changed.
- Follow-up settings read: repository rulesets are empty; GitHub `Production` and `Preview` Environments have no protection rules or deployment-branch policy. Connected account has repository admin permission; no settings or secrets were changed/read.
- Additional GitHub connector refresh on 2026-10-28: PR #43 is still OPEN/DRAFT at the same base/head SHAs, and the repository rulesets endpoint still returns an empty list. The connector receives HTTP 403 for the `main` branch-protection endpoint, so this connection cannot independently confirm the current legacy branch-protection setting. The earlier direct settings read above remains the recorded source for `protected: false`; recheck through an authorized settings view before relying on that value.
- Current implementation branch: `codex/chatgpt-cpu-vertical` at `89ea42efd45154e832858d14293cd29bb66cab41`, pushed for Draft PR [#51](https://github.com/Unjuno/gpu-control/pull/51) against the unchanged main SHA above. The PR has 120 changed files and remains unreviewed. GitHub Actions runs `40609696199` (CI), `40609696197` (Gateway comment bridge), `40609696193` (Gateway offline), and `40609696388` (Project bridge) all completed successfully at this head; Vercel preview deployment `dpl_8297EDuZphLShPAUgHqW8qjmLUCJ` is READY. No review or thread comments are present. This is not production deployment or ChatGPT acceptance.
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

## Current implementation baseline

- `gateway/gpu_gateway/protocol.py`: six existing MCP tools: integrations list, experiment prepare/submit/get/list/cancel. Responses include `structuredContent`.
- `service.py`: owner-bound run ids, plan fingerprint, idempotency key, strict registered parameters, short-lived browser approval. It rejects zero cost, and prepare currently sends every run to `awaiting_approval`.
- `worker.py`: database leases and provider reconciliation; ambiguous start is not blindly retried. Terminal backend observation is documented to mean billable resources have been released. Current result persistence and terminal cleanup semantics require targeted review before local container support.
- `config.py`: workload cost must be positive; default GPU field is T4; provider, image and argv come from operator config.
- `backends.py`/`registry.py`: demo, Modal Sandbox and optional factory bridge to an existing RunPod path. No local CPU gateway backend is registered.
- `gateway/project_control/runner.py`: registered source verification and constrained Docker CPU execution exist for the GitHub comment route. Existing CPU limits include no network, non-root user, read-only root, 256 MiB, one CPU, 32 PIDs, 30 seconds and bounded output. It uses an attach-oriented, `log-driver=none` path and needs changes before worker restart recovery can rely on retrieving output.
- `gateway/gpu_gateway/store.py`: explicit `metadata.create_all` bootstrap; no versioned Gateway schema migration mechanism was found.
- `policies/repository-state.yaml`: parked; paid workflow, provider secrets, live RunPod calls and generic external container execution are forbidden while parked.

## Next implementation action

Status refreshed on 2026-10-28: GitHub `main` remains
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`; PR #43 remains OPEN/DRAFT at
`1699b75df8262023501d41279e83bf429dca1be4`. The local implementation branch
has completed the P1 versioned contracts, canonical MCP tools, local CPU
admission/backend, real-container result and recovery path (T1-T5); its current
full Gateway suite passed 247 tests with real Docker and disposable PostgreSQL
integration enabled. See `docs/IMPLEMENTATION_PROGRESS.md` and the first
vertical plan for scoped evidence. These are local branch results, not GitHub
CI or deployed/ChatGPT acceptance.

Next, confirm that the intended ChatGPT account/workspace permits custom MCP
write actions, then select and validate a persistent HTTPS Gateway, PostgreSQL,
worker/supervisor and fixed-size artifact volume. Keep the CPU admission policy
disabled until the independent recovery review, target-host security checks,
backup/restore, quota/alert and ChatGPT acceptance gates pass. Do not change
parked mode, paid secrets or provider switches. PR #43 remains a stale Draft;
do not merge it wholesale. Its relevant security behavior remains an audit
input for independent review rather than an untracked cherry-pick request.
Before publishing a release candidate, review and configure GitHub main-branch
protection and Production Environment approval rules. Their current absence is
a verified gap; the connected account's admin permission does not itself
authorize a configuration change.
