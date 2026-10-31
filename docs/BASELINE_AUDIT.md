# Baseline audit for ChatGPT experiment control

Date: 2026-10-28 (Asia/Tokyo)

## Audited identities

- Repository: `Unjuno/gpu-control`
- Main commit: `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` (`Tolerate bounded GitHub runner queue delays (#50)`)
- Main protection read from GitHub API: disabled (`protected: false`). This is recorded only; no settings changed.
- PR #43: OPEN, DRAFT, base `main`, head `1699b75df8262023501d41279e83bf429dca1be4`, base SHA `a96a24818a5f8bc03b479c35b5e3f957f08dbe04`, 35 changed files.
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

## PR #43 disposition against current main

`git cherry -v origin/main refs/remotes/origin/pr-43/head` marks all three PR commits with `+`: no commit was cherry-picked or merged as the same patch. Main later added files in the same product area, so do not merge the stale branch wholesale. Re-evaluate each behavior and its regression evidence against current main before reusing code.

| PR #43 area | Current-main evidence | Disposition |
|---|---|---|
| pytest temporary-directory security fix | main baseline pinned pytest 8.4.2 (`pytest>=8,<9`); PR changed to 9.0.3 | Applied on this implementation branch as `pytest>=9.0.3,<10`, currently locked to 9.1.1. The official advisory says versions before 9.0.3 are affected. Core tests passed under the locked dev environment. |
| HTTP security helpers and regressions | PR adds `src/gpu_control/http_security.py`, tests for redirect/response/body/timeout bounds; current Gateway has separate HTTP clients in `auth.py`, `local_oauth.py`, and `ci_bridge.py` | Review as behavioral requirements. Do not transplant a core helper without checking whether each Gateway client has the same risks and contract. Add narrowly scoped tests for relevant clients. |
| RunPod allocation and recovery | PR hardens allocation-time permit/price rechecks, redirects and receipt-bound recovery; main is newer than PR base and contains Gateway/worker plus RunPod REST v1 / pricing / volume work | No equivalent cherry-pick detected. Review each invariant against current core adapters and Gateway bridge. Paid activation remains parked; offline regression tests/docs are allowed. |
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

Proceed with P1 T1 only after this baseline is carried into the active implementation checkout. Preserve v1 run rows and exact identity. Do not change parked mode, paid secrets or provider switches. The next work item is a focused versioned Gateway data contract and migration that maintains old MCP/Web/CI behavior.
