# P1 local CPU readiness review candidate on PR #57 — 2026-10-31

Status: **PASS for exact-base local Gateway regression only.** This is a
review candidate for admission-aware `/readyz`; no PR, deployment, or ChatGPT
acceptance was created.

## Candidate identity

- Base: PR #57 exact head `51b88f6110e2fc12de1c475e6e3d07c5438eaa3b`.
- Isolated detached worktree: `/tmp/gpu-control-p1-readiness-on-57`.
- Candidate patch: `/tmp/gpu-control-p1-readiness-on-57.patch`.
- Patch SHA-256: `03edebebd511a341272b6cd66bcdd5c597d69a8f7c5ff84bd40d54fe738eb118`.
- Paths: `gateway/gpu_gateway/admission.py`,
  `gateway/gpu_gateway/app.py`, and `gateway/tests/test_http_auth.py`.
- The app endpoint reports artifact storage and local CPU policy blockers;
  readiness fails closed when an enabled registered CPU workload is not
  currently admissible or lacks source identity. The negative tests cover
  workload allowlist and source-identity refusals.

## Source-matched validation

- Confirmed imports before testing:
  `gpu_gateway.app.__file__` resolved inside the candidate worktree's
  `gateway/gpu_gateway/app.py`; `gpu_control.__file__` resolved inside the
  candidate worktree's `src/gpu_control/__init__.py`.
- Command from the candidate `gateway/` directory:
  `PYTHONPATH=/tmp/gpu-control-p1-readiness-on-57/gateway:/tmp/gpu-control-p1-readiness-on-57/src /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts= -q -rs tests`
- Result: **246 passed, 9 skipped**, one existing Starlette deprecation
  warning. The skips cover optional Torch/Modal packages and Docker/PostgreSQL
  integration fixtures not configured for this invocation.
- `git diff --check` passed on the candidate.
- An earlier run resolved `gpu_control` from the primary checkout and is
  superseded; only the rerun above is source-matched evidence.

## Remaining gates

The patch has no GitHub Actions result or independent review and is not part of
PR #57's published head. It does not verify a deployed worker, durable database,
authenticated ChatGPT tools, real CPU execution from ChatGPT, or cross-
conversation result retrieval. The local test result is not deployment or
product acceptance. Preserve `mode: parked` and all provider/spending gates.

## Independent clean replay

- Created a second fresh detached worktree at the same exact PR #57 head and
  reapplied the patch with `git apply --check` before applying it.
- Reproduced the same three paths and 118 insertions / 5 deletions. The patch
  SHA-256 remained
  `03edebebd511a341272b6cd66bcdd5c597d69a8f7c5ff84bd40d54fe738eb118`.
- Reconfirmed both Python imports resolved inside the replay worktree, then ran
  the full Gateway suite with the same source-matched `PYTHONPATH`.
- Result: **246 passed, 9 skipped** in 8.80 seconds, with one existing
  Starlette deprecation warning. Skip reasons are unchanged: optional Torch
  and Modal dependencies, unconfigured CPU Docker smoke image, and unconfigured
  PostgreSQL test services.
- This replay confirms reproducible local regression evidence only. The
  independent security review, GitHub CI on a published head, and deployment
  and ChatGPT acceptance gates remain open.
- Read-only independent Security Review of this uncommitted candidate found no
  issues. This local review is not a submitted GitHub PR review.

## P1 integration replay on PR #58 schema-v9 head

- The direct #57 patch did not apply to PR #58 because the OAuth/schema-v9
  follow-up had changed `app.py` and `admission.py`. Replayed it with a
  three-way application and resolved the readiness logic against #58's current
  schema-v9 app. The resulting candidate is based on exact head
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4` and is saved at
  `/tmp/gpu-control-p1-readiness-on-58.patch` (SHA-256
  `8437253e113d0bf8f81fc3a27721b0157c02f5ddfef7aa081646fe1933fb6918`).
- Updated the two earlier artifact-storage readiness test fixtures to carry
  source identity and a valid, time-bounded zero-cost local CPU policy. This
  keeps those tests focused on storage while preserving the fail-closed
  admission requirement. The initial integrated run exposed these fixture
  assumptions; after correcting them, the full Gateway suite passed:
  **418 passed, 13 skipped**, one existing Starlette deprecation warning.
- Verified `gpu_gateway.app` and `gpu_control` both import from the candidate
  worktree. `git diff --cached --check` passed. Skips were optional Torch and
  Modal, unconfigured local CPU Docker smoke image and dedicated PostgreSQL
  services.
- At initial integration replay, this #58-based overlay had not yet had a
  Security Review. PR #58's green checks cover its published head, not this
  candidate; GitHub CI, submitted PR review, deployment, and ChatGPT acceptance
  remain outstanding. Preserve `mode: parked`.
- Follow-up read-only Security Review of this exact #58-based overlay found no
  issues in the three changed files. The candidate remained at the same base
  and patch SHA during review. This review did not run tests and is not a
  submitted GitHub PR review or CI result.

## Refreshed P1 candidate patch on exact PR #58 head — 2026-10-31 11:43 JST

- Applied the current review patch
  `/tmp/gpu-control-slice-p1_oauth_readiness-on-561a6c7.patch` (SHA-256
  `853b4a7177318bcee87b1608b592ad54229bac6974accebeac8355cad5cc27c4`) to a
  clean detached worktree at exact base
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4`. It applies cleanly and
  `git diff --check` passes.
- The candidate's `admission.py` and `app.py` byte hashes match the earlier
  reviewed #58 candidate exactly. `test_http_auth.py` differs, so the earlier
  418-test result is not claimed for this exact patch.
- Confirmed Python imports resolve to this candidate worktree, then ran only
  its changed HTTP/auth module:
  `PYTHONPATH=/tmp/gpu-control-p1candidate-on-561a6c7/gateway:/tmp/gpu-control-p1candidate-on-561a6c7/src /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts= -q -rs tests/test_http_auth.py`
- Result: **32 passed**, one existing Starlette deprecation warning, in 3.09
  seconds. This validates that module on the reconstructed local candidate;
  it is not a full Gateway suite, GitHub CI, a submitted PR review, deployment,
  or ChatGPT acceptance. Those gates remain open and mode stays `parked`.

## Full Gateway suite on the exact refreshed candidate — 2026-10-31 11:44 JST

- Candidate base and overlay are unchanged from the replay above. The code
  hashes are `admission.py`
  `5a6b1cc3e8debe30f706520ec462b3a17abfd562493e66a123b5a858e13c1c3d`,
  `app.py` `288912a723bb77992c55c445cd80a1131fb392df8bb9932f4eead8e09f05160d`,
  and `test_http_auth.py`
  `e3f94eed25fae0659e41f5e5df5d1a0fefb08758fa5be917af4eab514965026e`.
- Ran the complete `gateway/tests` suite from
  `/tmp/gpu-control-p1candidate-on-561a6c7/gateway` with imports resolved from
  that candidate, a loopback-only PostgreSQL 16 container, and a locally built
  digest-identified CPU smoke image. Command:
  `GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://postgres:p1-local-test@127.0.0.1:55498/gateway_test GPU_CONTROL_POSTGRES_CONTAINER=gpu-control-p1-candidate-pg-20261031 GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST=sha256:36866d5fa6b3f7be60ea4316c2a6b5ec1a172d857a27360d35be712ca6681c0f GPU_CONTROL_CPU_SMOKE_SOURCE_SHA=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY=Unjuno/gpu-control /Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python -m pytest -o addopts= -q -rs tests`
- Result: **429 passed, 2 skipped**, one existing Starlette deprecation
  warning, in 24.05 seconds. Skips were optional Torch and Modal dependencies.
  This includes the current readiness regressions and the local PostgreSQL,
  worker, and CPU container integration coverage in `gateway/tests`.
- The PostgreSQL container and CPU smoke image were removed after the run;
  port 55498 was confirmed closed. No provider, GPU, or paid resource was
  used. This remains local candidate evidence only; GitHub CI, independent PR
  approval, deployment readiness, and ChatGPT-originated CPU/result acceptance
  remain outstanding. Preserve `mode: parked`.
