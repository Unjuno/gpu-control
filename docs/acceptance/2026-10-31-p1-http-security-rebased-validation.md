# P1 HTTP security stack rebase — 2026-10-31

## Scope

- PR: #56, `codex/gpu-control-p1-03-http-security`.
- New base: PR #55 rebased head
  `080466dc4b1bdff1ba5458f5abedd7b05bc61ed3`.
- Original PR #56 base: `dc109cba978e2d8609e3899fa37c412a8a60eca4`.
- Six PR #56 commits were replayed without conflicts.
- The candidate preserves the P2 dispatch freshness fix inherited from its
  updated base.

## Validation

Gateway suite, run from this candidate worktree's `gateway/` directory:

```text
/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **217 passed, 8 skipped**, one existing Starlette deprecation warning,
8.00 seconds.

Core suite, with imports directed to this candidate worktree:

```text
PYTHONPATH=/tmp/gpu-control-pr56-rebase-candidate/src /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **463 passed, 1 skipped**, 1.17 seconds. `git diff --check` passed.

## Limits

This is local rebase and test evidence. The candidate needs fresh GitHub CI and
review. Provider execution and spending gates remain closed.
