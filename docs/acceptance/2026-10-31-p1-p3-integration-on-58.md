# P1 + P2 base + P3 local integration candidate on PR #58 — 2026-10-31

Status: **PASS for source-matched local Gateway regression only.** This is a
review candidate and does not authorize a PR update, deployment, or provider
activation.

## Branch and source identity

- Base: PR #58 exact head `561a6c7ac697dfdf22f304b60e313fccb2c806a4`.
- PR #58 is based on PR #51 head `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`.
- PR #53, #54, #55, #56 and #57 heads are ancestors of #58; their recovery,
  owner-scoped artifact and readiness work is present in the base history.
- PR #59 head `76c2a1a1b4439cf093c4e6efdd39d5121eb08959` is not an ancestor of
  #58. The direct #59 patch cannot be applied to #58 because it treats files
  already present in #58 as additions and diverged in 12 of its 14 changed
  paths. Two paths were byte-identical. Do not merge that branch wholesale.

## Candidate overlay

- Applied the P1 readiness patch
  `/tmp/gpu-control-p1-readiness-on-58.patch` (SHA-256
  `8437253e113d0bf8f81fc3a27721b0157c02f5ddfef7aa081646fe1933fb6918`), then
  the current-source P3 operations slice
  `/tmp/gpu-control-slice-p3_operations-on-561a6c7.patch` (SHA-256
  `e70747ef9b481ca49647f2ca776ce4b2f65dbec505f33bef0348e1844f8e0e11`). Both
  applied cleanly to the intended base/sequence.
- Complete combined patch: `/tmp/gpu-control-p1-p3-on-58-complete.patch`,
  SHA-256
  `5c0acf229ccc0f07a32155ab5498c4685a8c9791c1a31fc4f5d7848b144319b8`.
  It includes all 14 changed paths: P1 admission-aware readiness; P3
  operations, backup generation, PostgreSQL integrity test and three P3
  acceptance records; and related regression coverage. The P2
  recovery/artifact-read history is inherited from #58's ancestors.
- The first exported patch omitted four untracked P3 acceptance/test files.
  Rebuilt it from the staged complete candidate and applied it to a second
  fresh worktree at the exact #58 base. Candidate and replay each contain 328
  source/evidence paths, with zero missing, extra, content-mismatched or
  executable-mode-mismatched paths. Use only the `-complete.patch` artifact.
- Confirmed `gpu_gateway.app` and `gpu_control` import from the candidate
  worktree. `git diff --check` passed.

## Validation

Ran the complete Gateway suite on this candidate with its worktree first on
`PYTHONPATH`: **420 passed, 14 skipped**, one existing Starlette deprecation
warning, in 11.06 seconds. Skips include optional Torch/Modal, an unconfigured
CPU smoke Docker image, and unconfigured PostgreSQL test services. Therefore the
PostgreSQL-backed artifact-manifest test was not exercised in this run. A
separate current-schema-v9 paired dump/restore record exists at
`docs/acceptance/2026-10-28-atomic-backup-generation.md`; it is local-only and
does not establish target-host, Neon, alerting, or measured RPO/RTO acceptance.

## Remaining review and product gates

- A separate read-only Security Review of the complete 14-path P1+P3 staged
  candidate found no actionable issues. The reviewer explicitly included the
  four newly staged P3 evidence/test files. No tests were run during review;
  local validation results above are from the earlier exact same tree.
- GitHub CI and submitted review are absent for this unpushed combined patch.
  Green checks on PR #58 cover its published head only.
- Deployment/runtime readiness and authenticated ChatGPT CPU execution,
  status, artifact retrieval and cross-conversation retrieval remain unaccepted.
- P3 target-host service/backup/restore, off-host retention, second-operator
  recovery, alert delivery, and measured RPO/RTO remain open. Preserve
  `policies/repository-state.yaml mode: parked` and all spending gates.

## PostgreSQL-backed P3 regression follow-up

- Ran `tests/test_postgresql_backup_integrity.py` against the same integrated
  candidate and a fresh disposable PostgreSQL 16 container using pinned image
  digest `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
  The host port was bound only to `127.0.0.1:55485`.
- Result: **1 passed** in 0.35 seconds. The test creates unique synthetic rows,
  exercises the real artifact-manifest SQL and byte/digest checks, and cleans up
  its rows. The current candidate's backup module and test hashes match the
  tested primary source files exactly.
- Stopped the task-created container after the run; `docker ps` confirmed no
  running container with that name. This closes only the PostgreSQL-backed
  manifest/integrity regression. It does not rerun the whole Gateway suite with
  PostgreSQL, or prove target-host restore, Neon, off-host retention, alerting,
  or measured RPO/RTO.

## Real local CPU MCP vertical on the integrated candidate

- Ran `tests/test_local_mcp_integration.py` from the exact #58-based candidate
  with its `gateway/` and `src/` paths first on `PYTHONPATH`, image digest
  `sha256:15acf11d33636ac3dfd92eee59df028f9d65eae2524cdfd7cbda44bdf361b59b`,
  and image-matching source revision
  `a794438f42bd7246f463eaaa40d963af0aae9d13`.
- Result: **1 passed** in 1.13 seconds, one existing Starlette warning. The
  integration used a local SQLite database, synthetic owner JWT, temporary
  zero-cost policy, and two independent MCP HTTP clients. It listed tools,
  prepared and replayed the request idempotently, submitted it, ran the real
  network-disabled CPU container, then fetched the result and artifact through
  the second client.
- Captured local run ID `675d173fdce540668667bd740c126bfa`: terminal state
  `succeeded`, `cleanup_state=complete`, `simulation=false`, `gpu_used=false`,
  source SHA `a794438f42bd7246f463eaaa40d963af0aae9d13`. The 568-byte
  `cpu-smoke-result.json` artifact has SHA-256
  `2a72f26082461ba058e4773c6f481f4573f369e9c01903f5d73055d3908c4819`; the
  second client verified exact bytes and digest. A post-run Docker query for
  that run label returned no container.
- An initial invocation was excluded: it used the fixture's default source SHA
  (`a` repeated 40 times) against an image labelled with revision `a794438…`.
  The backend correctly refused that identity mismatch and left the run
  `submit_unknown`; the test's exact-run cleanup removed the container. Setting
  `GPU_CONTROL_CPU_SMOKE_SOURCE_SHA` to the image's actual OCI revision made the
  rerun pass. No source code changed between attempts.
- This is exact-candidate local MCP/Docker evidence only. The token and MCP
  clients were synthetic in-process test fixtures; this is not a ChatGPT
  conversation, deployed endpoint, public source checkout, or real user
  cross-conversation acceptance.

## Exact-candidate systemd template verification

- Mounted `/tmp/gpu-control-p1-p3-on-58/gateway/deploy` read-only into a
  disposable Linux container with networking disabled. The pinned base image
  was
  `sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`
  (Debian 12, systemd 252.39).
- Created only inert users/groups, empty 0600 environment placeholders and
  executable placeholders inside the ephemeral container, then ran
  `systemd-analyze verify` on all eight candidate units: DB check/migration,
  API, worker, supervisor, artifact capacity service/timer and capacity bridge.
  Command exited 0 with no diagnostics.
- No unit was started; no host account, systemd configuration, mount, database,
  or credential was touched. This verifies syntax and references only; it does
  not prove target-host mount filtering, boot/restart behavior, DB connectivity,
  worker availability, or actual alert delivery.

## Full Gateway PostgreSQL and CPU integration revalidation — 2026-10-31

- Re-ran the full Gateway suite against this exact #58-based P1+P3 candidate,
  with the candidate worktree as the current directory. The test runner was
  `/Users/taka/Documents/ChatGPT/Gpuラッパリポジトリ/gpu-control/gateway/.venv/bin/python`.
- Configured a task-created PostgreSQL 16 container from image digest
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  database `gateway_test`, and host binding `127.0.0.1:55486`. The container
  was deliberately not launched with `--rm` because the outage/recovery test
  stops and restarts it. A test-only password was used and omitted here.
- Enabled the CPU smoke integration with image digest
  `sha256:15acf11d33636ac3dfd92eee59df028f9d65eae2524cdfd7cbda44bdf361b59b`,
  source repository `Unjuno/gpu-control`, and matching image source revision
  `a794438f42bd7246f463eaaa40d963af0aae9d13`.
- Command: `python -m pytest -o addopts= -q -rs tests` from `gateway/`, with
  `GATEWAY_TEST_DATABASE_URL`, `GPU_CONTROL_POSTGRES_CONTAINER`,
  `GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST`, `GPU_CONTROL_CPU_SMOKE_SOURCE_SHA`, and
  `GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY` set as described above.
- Result: **432 passed, 2 skipped**, one existing Starlette deprecation
  warning, in 23.02 seconds. The skips were optional Torch and Modal SDK tests.
  This run exercised the PostgreSQL outage-after-capture recovery path and
  enabled real local Docker CPU paths alongside the rest of the Gateway suite.
- The exact task-created PostgreSQL container was removed after the run. The
  five older run-labeled containers observed before cleanup remained untouched.
- This strengthens local candidate evidence only. GitHub CI/review for the
  combined patch, deployment readiness, authenticated ChatGPT invocation,
  ChatGPT-originated CPU execution, and cross-conversation retrieval remain
  unaccepted. `policies/repository-state.yaml` remains parked.
