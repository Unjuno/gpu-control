# P1 CPU vertical stack rebase — 2026-10-31

## Scope

- PR: #51, `codex/chatgpt-cpu-vertical`.
- Candidate base: PR #57 rebased head
  `3fd9d54ca0cf8d202544542a39c59cf52cf62269`.
- Original PR #51 base: `51b88f6110e2fc12de1c475e6e3d07c5438eaa3b`.
- The 24 first-parent commits were replayed onto the new base; the final old
  merge commit was omitted because its only tree delta duplicates the updated
  base package-install workflow.
- Conflicts were resolved by preserving both the updated-base package install
  and PR #51's wheel, PostgreSQL, CPU smoke, and systemd CI checks; Store
  dispatch and provider-observation methods; and both test import groups.
- Candidate head: `11184e3da2acaa9da77f1cdc54118e44147a9b82`.

## Validation

Gateway suite, run from this candidate worktree's `gateway/` directory:

```text
/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **416 passed, 12 skipped**, one existing Starlette deprecation warning,
11.19 seconds.

Core suite, with imports directed to this candidate worktree:

```text
PYTHONPATH=/tmp/gpu-control-pr51-rebase-candidate/src /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **550 passed, 1 skipped**, 1.40 seconds. `git diff --check` passed.
Policy still reads `mode: parked`, with live paid compute, RunPod live calls,
RunPod adapter, and generic external container execution disabled.

## Limits

This is local rebase and test evidence. The candidate still needs GitHub CI,
independent review, and live ChatGPT OAuth/run/result acceptance. No paid or
provider execution was enabled.
