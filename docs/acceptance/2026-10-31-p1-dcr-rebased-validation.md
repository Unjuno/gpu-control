# P1 DCR persistence stack rebase — 2026-10-31

## Scope

- PR: #58, `codex/gpu-control-p1-dcr-v9-review`.
- New base: PR #51 CPU vertical candidate
  `69ef1cfd5b201c21c4bb7eae2492846ed20b44fd`.
- The original DCR feature commit was replayed onto the new base as
  `4fb51beabd98bf50d52fa7d45fbc46bde0a09cd5`; the old merge commit containing the previous PR #51 head was not
  carried forward.
- The resulting PR-specific diff is seven files: OAuth persistence, schema
  migration, PostgreSQL coverage, and acceptance evidence.

## Validation

Gateway suite, run from this candidate worktree's `gateway/` directory:

```text
/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **419 passed, 13 skipped**, one existing Starlette deprecation warning,
10.82 seconds.

Core suite, with imports directed to this candidate worktree:

```text
PYTHONPATH=/tmp/gpu-control-pr58-rebase-candidate/src /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **550 passed, 1 skipped**, 1.34 seconds. `git diff --check` passed.

## Limits

This is local rebase and test evidence. The rebased PR needs fresh GitHub CI
and review. It does not establish live ChatGPT OAuth or real execution
acceptance.
