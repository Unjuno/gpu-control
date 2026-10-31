# P2 readiness stack rebase — 2026-10-31

## Scope

- PR: #55, `codex/gpu-control-p2-03-readiness-heartbeat`.
- New base: PR #54 rebased head
  `4cf365a19e68b0caa48c3f7008825e32dd3167c9`.
- Original PR #55 base: `113d7bf22665ebb4a3b2d91637020a8a2aea331a`.
- Ten PR #55 commits were replayed. One import conflict in
  `gateway/tests/test_experiment_api.py` was resolved by retaining the Worker
  import required by the P2 dispatch regression tests. No other conflict
  occurred.

## Validation

Executed from this candidate worktree's `gateway/` directory:

```text
/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **215 passed, 8 skipped**, one existing Starlette deprecation warning,
7.48 seconds. Imports resolved to this candidate worktree. `git diff --check`
passed after rebase.

## Limits

This is local rebase and test evidence. The candidate still needs fresh GitHub
CI and review. Repository spending gates remain closed.
