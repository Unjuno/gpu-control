# P1 DCR persistence stack rebase — 2026-10-31

## Scope

- PR: #58, `codex/gpu-control-p1-dcr-v9-review`.
- New base: PR #51 CPU vertical candidate
  `cc09bb56a77aadf65471a21acccb1c26e83ffe28`.
- DCR feature commit: `d5a30985d8f2df0e7221476f47f1dfecff2faedb`.
- Validation record commit: `b8028841df5b3df6d3b957be402397639d2c326a`.
- The stale merge commit from the prior PR #51 head was not carried forward.
- The resulting PR-specific diff is seven files: OAuth persistence, schema
  migration, PostgreSQL coverage, and acceptance evidence.

## Validation

Gateway suite, run from this candidate worktree's `gateway/` directory:

```text
/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **419 passed, 13 skipped**, one existing Starlette deprecation warning,
10.82 seconds. After moving PR #51 to `cc09bb5`, the full suite was rerun with
the exact-source CPU smoke image described below: **429 passed, 3 skipped**,
one existing Starlette deprecation warning, 18.07 seconds.

The real-container smoke used an image built from the DCR feature source SHA
`d5a30985d8f2df0e7221476f47f1dfecff2faedb`; image digest:
`sha256:07da90a98f66cca25c1afe3208cde7928012f6bdf1fdee9d5e9939c50cf7d32f`.
GitHub Actions reruns for PR #51 after the CI fixes all passed (9 checks).

Core suite, with imports directed to this candidate worktree:

```text
PYTHONPATH=/tmp/gpu-control-pr58-rebase-candidate/src /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/.venv/bin/python -m pytest -o addopts='' -q
```

Result: **550 passed, 1 skipped**, 0.98 seconds. `git diff --check` passed.

## Limits

This is local rebase and test evidence. The rebased PR needs fresh GitHub CI
and review. It does not establish live ChatGPT OAuth or real execution
acceptance.
