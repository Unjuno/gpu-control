# PR #58 current-tree integration validation — 2026-10-31

## Candidate

- Base: latest PR #58 head `8fa533332099d5248bff55be82912891a780b3d8`.
- The candidate overlays the current `codex/chatgpt-cpu-vertical` source
  snapshot, including P1/P2/P3 follow-ups, P4 provider-contract work, P5
  authorization and provider-account leases, and the associated policy and
  acceptance records.
- The primary dirty checkout was not edited, staged, reset, or committed.

## Integration changes

- Preserved the PR #58 DCR/schema migration behavior while integrating schema
  versions 10–12 and paid-authorization/provider-account lease persistence.
- Restored the non-account-lease dispatch fence after durable submission intent
  creation. Recovery accepts the persisted `provider_call_started` phase.
- Updated PostgreSQL migration expectations to use the current schema version
  and updated the PostgreSQL Docker-crash test to assert the dispatch phase.
- Retained the PostgreSQL OAuth refresh/revocation race tests alongside the
  process-level provider-account lease test.

## Verification

- Focused Worker, Store, PostgreSQL, account-lease, and authorization persistence
  suites: **77 passed**, one existing Starlette deprecation warning.
- Gateway full suite against a dedicated PostgreSQL 16 container and the
  digest-pinned local CPU smoke image: **541 passed, 2 skipped** (optional Torch
  and Modal SDK tests), one existing Starlette deprecation warning, 26.94 sec.
- Core suite: **559 passed, 1 skipped** (Python 3.11-only malformed RunPod log
  reproducer), 1.27 sec.
- The full Gateway run included local Docker CPU/MCP execution and artifact
  retrieval, PostgreSQL migration/OAuth, process-level lease contention, and
  database/worker recovery tests.
- `git diff --check` passed after the conflict resolution and test updates.

## Security and release limits

- The source/policy Security Review recorded in
  `2026-10-31-current-worktree-security-review.md` applies to its recorded
  frozen snapshot. A new diff scan for this rebased candidate was attempted
  twice, but the scan tool returned “Working-tree contents changed after they
  were selected. Select Uncommitted changes again.” Both attempts returned no
  scan ID; this candidate has no new formal scan result.
- No GitHub CI or human PR review covers this candidate yet. The scan tool
  response is not a security pass.
- `policies/repository-state.yaml` remains `mode: parked`; live paid compute,
  RunPod live calls, and live paid execution remain disabled.
- No ChatGPT OAuth session, deployed target host, real GPU allocation, paid
  provider call, or production deployment was exercised.
