# PR #51 based full current source candidate — 2026-10-31

Status: **PASS for exact source reconstruction and local Gateway/Core suites.**
The candidate is local only. It has no GitHub CI or GitHub review result and is
not deployed or accepted by ChatGPT.

## Source reconstruction

- Base: exact current PR #51 head `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`.
- Source: primary checkout `codex/chatgpt-cpu-vertical` at
  `a794438f42bd7246f463eaaa40d963af0aae9d13`, including all current tracked
  and untracked files.
- Reproducible patch: `/tmp/gpu-control-full-current-on-e3ffcef.patch`.
  SHA-256: `c0a4b9e9deb8ecf7fe5b24e401ce6da777291c469845dd3175101d9b94c5f8d7`.
- At the time of the test, the patch contained 50 tracked-path changes plus
  16 new paths. It was applied to a fresh detached worktree at the exact base
  after `git apply --check`.
- That test-time tree had 339 files in both source and candidate, with zero
  missing, extra, or byte-mismatched files. `git diff --check` passed.
- Candidate worktree: `/tmp/gpu-control-full-candidate`. It was created only
  for validation; no branch/ref or GitHub state was changed.

## Local validation

- Gateway suite from the candidate Gateway source using the repository's
  existing Python 3.12 Gateway environment: **482 passed, 2 skipped, 1
  Starlette deprecation warning**. PostgreSQL 16 and real local Docker CPU/MCP
  integration were enabled. Skips were optional Torch and Modal tests.
- Core suite using the candidate `src/`: **559 passed, 1 skipped**. The skip is
  a Python 3.11-specific malformed RunPod log reproducer; this run used Python
  3.12.
- PostgreSQL image:
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  bound only to `127.0.0.1:55483` in disposable container
  `gpu-control-full-candidate-postgres`.
- CPU smoke image ID: `sha256:c315fb4e8ac8899d7dc47d0e7189dc99b0d7caa5c4303875d8733490578a33ee`,
  built from the candidate's `gateway/workloads/cpu-smoke` Dockerfile and
  scripts with synthetic all-`a` source SHA. This is test-fixture evidence,
  not a published artifact or production source provenance.
- Log files: `/tmp/gpu-control-full-candidate-gateway.log` and
  `/tmp/gpu-control-full-candidate-core.log`.

## Scope limits and next gates

After the test run, this record and other evidence/planning documents were
updated. The same `/tmp` patch path was regenerated to include those later
documentation changes and the then-current 62-path dirty worktree; that
read-only replay matched the 340-file current tree exactly. The later doc-only
changes did not alter Gateway/Core runtime or test files, so the recorded test
results still cover the current implementation files. The test-time SHA above
is historical; the patch currently at that path has a different SHA.

The tests exercise the reconstructed local macOS/OrbStack source and a
synthetic CPU workload. They do not establish GitHub Actions results for this
candidate, independent GitHub approval, live OAuth/ChatGPT execution,
cross-conversation retrieval, target-host operations, real GPU execution, or
paid execution. Production `/readyz` and authenticated ChatGPT acceptance
remain separate deployment/account gates. `policies/repository-state.yaml`
remains parked; no provider enablement, paid resource, deployment, PR edit, or
push was performed.

The base for the full-suite run recorded above is PR #51, whose parent is PR
#57. The later exact-source replay found PR #58 to be the better current review
base; it is documented below. Before publishing or proposing PR edits,
reconcile the current full diff with the existing PR #52–#59 stack and review
ranges; the aggregate candidate is not a replacement for independent slice
review.

## PR #58 base replay refresh — 2026-10-31 07:47 JST

Reconstructed the current source on a fresh detached worktree at PR #58 head
`561a6c7ac697dfdf22f304b60e313fccb2c806a4` by applying the six current slices
listed in `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`.
The first replay matched 337/340 files; the only differences were the three
acceptance/progress/roadmap documents updated after the slice patches were
generated. Applied a doc-only replay refresh to those files, then compared all
tracked and untracked source paths plus executable bits: **340 files, zero
missing, extra, byte-mismatched, or mode-mismatched paths**. `git apply
--check` and `git diff --check` passed. Candidate worktree:
`/tmp/gpu-control-review-candidate-561`.

From the candidate's `gateway/` directory, ran
`/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python
-m pytest -o addopts= -q tests/test_http_auth.py`: **32 passed**, one existing
Starlette deprecation warning. Runtime and test source files are identical to
the previously full-tested current candidate; this refresh changed only
acceptance/progress/roadmap text, so the full-suite results above remain the
available full-scope evidence. This exact replay is still local-only: no PR
head, GitHub review, deployment, or ChatGPT runtime acceptance was created.
