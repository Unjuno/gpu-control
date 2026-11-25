# P1 CPU recovery stack rebase — 2026-10-31

## Scope

- PR: #57, `codex/gpu-control-p1-04-cpu-oauth-recovery`.
- New base: PR #56 rebased head
  `8dec15986592a390b5cde768507ac5e1a6bccb8d`.
- Original PR #57 base: `34cc58c08f9a3aa52ea04b02b03bfe0e5c1a6fac`.
- Three PR #57 commits were replayed. One import conflict was resolved by
  preserving both the P2 `Worker` import and the P1 workload requirement
  imports.
- The candidate retains the updated P2 dispatch expiry guard from its base.

## Validation

Gateway suite, run from this candidate worktree's `gateway/` directory:

```text
/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **247 passed, 9 skipped**, one existing Starlette deprecation warning,
8.80 seconds.

Core suite, with imports directed to this candidate worktree:

```text
PYTHONPATH=/tmp/gpu-control-pr57-rebase-candidate/src /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **515 passed, 1 skipped**, 1.24 seconds. `git diff --check` passed.

## Limits

This is local rebase and test evidence. The candidate needs fresh GitHub CI and
review. ChatGPT live OAuth/result acceptance and all paid/provider execution
remain separate gates.
