# P3 operations stack rebase — 2026-10-31

## Scope

- PR: #59, `codex/gpu-control-p3-ops-candidate`.
- New base: PR #57 rebased head
  `3fd9d54ca0cf8d202544542a39c59cf52cf62269`.
- Original PR #59 base: `51b88f6110e2fc12de1c475e6e3d07c5438eaa3b`.
- Both PR #59 commits were replayed without conflict.

## Validation

Gateway suite, run from this candidate worktree's `gateway/` directory:

```text
/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **280 passed, 10 skipped**, one existing Starlette deprecation warning,
9.12 seconds.

Core suite, with imports directed to this candidate worktree:

```text
PYTHONPATH=/tmp/gpu-control-pr59-rebase-candidate/src /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **515 passed, 1 skipped**, 1.29 seconds. `git diff --check` passed.

## Limits

This is local rebase and test evidence. The candidate needs fresh GitHub CI and
review. Repository mode remains parked; this does not authorize live provider
or paid execution.
