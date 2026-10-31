# Current working-tree full-suite revalidation — 2026-10-31

## Latest full Gateway/Core rerun — 2026-10-31 02:36 UTC

- Checkout HEAD: `a794438f42bd7246f463eaaa40d963af0aae9d13`; at invocation the
  dirty tree had 49 modified tracked paths and 43 untracked paths, with no
  staged files. This run covers the current P4/P5 Worker, account-lease,
  credit/paid authorization, and migration sources listed by hash below.
- Gateway command from `gateway/` used
  `GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55497/postgres`,
  the dedicated stoppable PostgreSQL container
  `gpu-control-active-goal-p5-20261031` from pinned image
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  and CPU smoke image
  `sha256:e82806277a195971ba3a0fc443650f47e4e15ddd913df6fb26a9ef7f07348922`
  labelled for source `Unjuno/gpu-control` / `a794438f42bd7246f463eaaa40d963af0aae9d13`.
- Gateway result: **534 passed, 2 skipped**, one existing Starlette
  deprecation warning, 27.38 seconds. Only optional Torch and Modal tests were
  skipped. The suite exercised PostgreSQL migrations and OAuth, worker crash
  and outage recovery, account-lease persistence/concurrency, local Docker CPU
  lifecycle/MCP, signed credit/paid envelope checks, and candidate receipt
  validation. It did not call a live GPU or paid provider.
- Core command from the repository root:
  `./.venv/bin/python -m pytest -o addopts= -q -rs`; result:
  **559 passed, 1 skipped** in 0.93 seconds. The skip is the Python 3.11-only
  malformed RunPod log reproducer; runtime was Python 3.12.
- Test setup note: the first invocation passed the dedicated PostgreSQL
  container name without creating that container and failed 11 tests with
  connection errors. This was a harness setup error. The successful rerun
  created the named PostgreSQL container on loopback, then removed that exact
  container; no listener remained on port 55497.
- Source hashes at successful test time:
  - `gateway/gpu_gateway/worker.py` — `12e93041d4468e13461358fa419d89de563bed34071cbcc50e2cc3d965a7467f`
  - `gateway/gpu_gateway/store.py` — `126d246a796129a1869c3a082f734e28667cbb98b5e38b755743f32a0a65cd1a`
  - `gateway/gpu_gateway/config.py` — `2c24578951cfab3f3732d0e17a5801857888ec304b3325e7a7be80c767785d9f`
  - `gateway/gpu_gateway/migrations.py` — `2cbdd00746eb83d554fb0c99d897a9bf3678c28301aff6d84d7626c0008dd72e`
  - `gateway/tests/test_experiment_api.py` — `de13ec4811c90fdd2015606b6ee269d3a78e93946bcac766f6b71d2091923af6`
  - `gateway/tests/test_provider_account_leases.py` — `1a7be6f5ab84f1be06cffbf90bea83fa19b04c2d36cc1f71254eec34567305f3`
  - `gateway/tests/test_provider_account_scope.py` — `5e29a7e59ee026bcd3686498bb921994aea409326a69003bdaafeb1a0cec2578`
  - `gateway/tests/test_paid_authorization_bridge.py` — `0db7a50918539c30fa417f82b70356b4964a2c9a5ec25496080e473148c7ceb3`
  - `gateway/tests/test_credit_authorization_bridge.py` — `9c5f2dd79335bfc90e7f1f86f6f059fefe80083c879d75505395ed5102156fdf`
- This is local source/runtime evidence only. It does not establish GitHub
  review/CI, production readiness, ChatGPT OAuth/tool acceptance, target-host
  operation, real GPU, or paid execution. Repository mode remains `parked`.

## Follow-up revalidation — 2026-10-31 09:46 JST

### Source-bound CPU + PostgreSQL full Gateway rerun — 09:51 JST

- Git HEAD was `a794438f42bd7246f463eaaa40d963af0aae9d13`; the tested dirty
  snapshot had 48 modified tracked paths and 30 untracked paths, with nothing
  staged. Tracked diff SHA-256 at test time:
  `b665bbcb1989b82a6491d35c7f1a17facb80718d65b7ee68e851cd2f2cd913c1`.
- Ran the full Gateway suite from `gateway/` with a dedicated PostgreSQL 16
  container bound only to `127.0.0.1:55494`, plus the commit-bound CPU image
  `sha256:e82806277a195971ba3a0fc443650f47e4e15ddd913df6fb26a9ef7f07348922`
  built from exact HEAD. PostgreSQL image digest:
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
- Command: `GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55494/postgres GPU_CONTROL_POSTGRES_CONTAINER=gpu-control-current-recheck-postgres-20261031-p1-source GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST=sha256:e82806277a195971ba3a0fc443650f47e4e15ddd913df6fb26a9ef7f07348922 GPU_CONTROL_CPU_SMOKE_SOURCE_SHA=a794438f42bd7246f463eaaa40d963af0aae9d13 GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY=Unjuno/gpu-control ./.venv/bin/python -m pytest -o addopts= -q -rs tests`.
- Result: **513 passed, 2 skipped, 1 existing Starlette deprecation warning**
  in 26.19 seconds. Only optional Torch and Modal SDK tests skipped. PostgreSQL
  migration/OAuth, spawned-process account-lease race, outage/recovery and
  local Docker CPU/MCP integrations ran. The MCP integration retrieved the
  result and artifact from a second client and verified the artifact digest.
- Source hashes: worker `f44eafb006b2a7d7e9eaa0a3a7cc08954869d34e1280cf788040a41e02b14991`,
  Store `4db23d94b38127efbc29e0afc85e22c14d5d9e578de4bd9f6db0a0556d25fcfd`,
  config `7a750b327e599911aca0033901c49ab426ba378f560af3e197dd1cf7e63eb7da`,
  migrations `8251f6aa4c05c4d9d7d551a04bee8d6acc7526f7c31a60914e5d17b069130bf5`.
  Relevant test hashes are the source-bound P1 backend/lifecycle/MCP tests
  `3c4b8f512d6d68675f01448b0508743dcc291021c4bebc5397c4468aae7641cc`,
  `21e6ec9b5c9a25f25529329cc920baa7ddee75a95527d3f554b2088608561489`,
  `f507e312e37f81ae1e049b01d95203dbcdf1f2769d2bae9178cee61229fbdd57`,
  PostgreSQL core tests `7497daa810ca4a655bb4dcdc9779807a4209f0a4bf464ed7e02b40955ffc975b`,
  and outage/lifecycle tests `94ae8b1838cdd99c80f87a68d6e25a5c1ea8c18d8231a49699e1392dcf6a8bf0`.
- Additional untracked files exercised in this full suite: credit bridge
  `537ee44b77add57207fabbb58331b32c1a1d683434b80194e6f93709091af72f`, paid
  authorization bridge
  `8922a435690d5db2bed9c89c0904eb534714457ffa537be64ea618a9a6e5df72`,
  account-scope derivation
  `fad8c4249693080ebfc9000e2bc53e43503c55b45e22a1c5a188a3a824e463a4`, and
  their credit/paid/PostgreSQL OAuth/PostgreSQL backup/account-scope tests:
  `9c5f2dd79335bfc90e7f1f86f6f059fefe80083c879d75505395ed5102156fdf`,
  `0db7a50918539c30fa417f82b70356b4964a2c9a5ec25496080e473148c7ceb3`,
  `7f48ac06139142399d7865c5237d11a78f824a2d89264764db6ae46d19d129c3`,
  `133e21b9b62922723cfc6ad940924e118db12016ae06d0976c5d2fde50a5bebe`,
  `7204eff7c710d6573ca28f1091efdc03ff7be5228e8e295d7d3fb79cfc0e5ffd`.
- The exact test-created database container and anonymous volume were removed;
  no listener remained on port 55494. This proves local current-worktree
  behavior only. It does not prove production/Neon or target-host operation,
  actual ChatGPT OAuth/tunnel use, live GPU, or paid execution. Keep mode
  parked.

### P1 real local CPU vertical — 09:48 JST

- Ran three repository-owned Docker integration tests with the existing
  `linux/arm64` CPU smoke image digest
  `sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b`.
  The image labels identify source `Unjuno/gpu-control` and synthetic fixture
  revision `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
- Command from `gateway/`:
  `GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST=sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b GPU_CONTROL_CPU_SMOKE_SOURCE_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY=Unjuno/gpu-control ./.venv/bin/python -m pytest -o addopts= -q -rs tests/test_local_backend_integration.py tests/test_local_lifecycle_integration.py tests/test_local_mcp_integration.py`
- Result: **3 passed** in 7.00 seconds. Coverage includes real local Docker
  CPU execution and cleanup, the authenticated MCP prepare/submit/worker/result
  path, a second MCP client retrieving the result and artifact with digest
  verification, and lifecycle recovery cases in the selected tests.
- This is local MCP integration evidence against a synthetic source identity;
  it does not prove a ChatGPT account can connect, remote HTTPS tunnel or
  deployment readiness, real workload source provenance, GPU execution, or
  paid-provider behavior. The repository remains parked.

### P1 commit-bound CPU image follow-up — 09:48 JST

- Built `gateway/workloads/cpu-smoke` from a `git archive` of exact HEAD
  `a794438f42bd7246f463eaaa40d963af0aae9d13`, using its digest-pinned
  `python:3.12-slim-bookworm` base. No source from the dirty worktree was
  included in the build context. The resulting local `linux/arm64` image ID
  and digest is
  `sha256:e82806277a195971ba3a0fc443650f47e4e15ddd913df6fb26a9ef7f07348922`.
  OCI labels report source `Unjuno/gpu-control` and that exact commit.
- Repeated the same three real Docker CPU backend/lifecycle/MCP tests with the
  commit SHA and image digest above: **3 passed** in 7.00 seconds. The MCP
  test exercised authenticated prepare/submit, Worker execution and cleanup,
  then result and artifact retrieval from a second client with SHA-256 checks.
- This ties the CPU workload image to a real immutable repository commit. The
  Gateway/control-plane source under test is still the dirty local worktree,
  and the MCP clients are in-process test clients; it does not establish
  ChatGPT account/tunnel/deployment acceptance. No provider or GPU was used.
  The test removed its containers; a read-only Docker listing found no
  remaining container using this image.

- Re-ran the Gateway suite from the current working tree at HEAD
  `a794438f42bd7246f463eaaa40d963af0aae9d13`, with 48 tracked paths modified
  and 30 untracked paths; no changes were staged. `git diff --check` passed.
- Command: `cd gateway && ./.venv/bin/python -m pytest -o addopts= -q -rs tests`.
  Result: **499 passed, 16 skipped, 1 existing Starlette deprecation warning**
  in 11.13 seconds. The current run exercised the SQLite account-lease tests.
  Skips were optional Torch/Modal dependencies, unconfigured local CPU image,
  and unconfigured dedicated PostgreSQL test service/container.
- Core command: `./.venv/bin/python -m pytest -o addopts= -q -rs` from the
  repository root. Result: **559 passed, 1 skipped** in 1.01 seconds. The skip
  is the Python 3.11-specific malformed RunPod log reproducer (this runtime is
  Python 3.12).
- Source hashes: `gateway/gpu_gateway/worker.py`
  `f44eafb006b2a7d7e9eaa0a3a7cc08954869d34e1280cf788040a41e02b14991`;
  `gateway/gpu_gateway/store.py`
  `4db23d94b38127efbc29e0afc85e22c14d5d9e578de4bd9f6db0a0556d25fcfd`;
  `gateway/tests/test_provider_account_leases.py`
  `bf7e678d2362d3c9d683c507fa84213440f941da614211b2774b246c591f535d`.
- This validates local Gateway behavior only. The lease primitives remain
  unwired to Worker/RunPod dispatch; no account-scope HMAC configuration,
  provider challenge reconciliation, provider cleanup confirmation,
  PostgreSQL race check, ChatGPT call, deployment, or provider/GPU call was
  performed. Keep the repository parked and spending gates closed.

Status: **PASS for local Gateway and Core tests at the current source snapshot.** This
does not establish GitHub CI/review, hosted readiness, ChatGPT acceptance,
selected-host recovery, GPU execution, or paid execution.

## Latest current-worktree revalidation — 2026-10-31

- Git HEAD remained `a794438f42bd7246f463eaaa40d963af0aae9d13`; the primary
  checkout had 47 modified/deleted tracked paths and 22 untracked paths (69
  total) when tested. The current diff passed `git diff --check`.
- Gateway was run from `gateway/` with PostgreSQL and the real local CPU
  container integrations enabled. PostgreSQL 16 used image digest
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  in task-created container `gpu-control-current-recheck-postgres-20261031`,
  bound only to `127.0.0.1:55487`. CPU smoke image was
  `sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b`
  with synthetic source SHA `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
- Gateway result: **498 passed, 2 skipped, 1 existing Starlette deprecation
  warning** in 24.83 seconds. Skips were optional Torch and Modal SDK tests.
  This includes PostgreSQL migrations/OAuth, artifact integrity, outage recovery,
  real local Docker CPU/MCP flows, and the positive fake candidate-bound P4
  receipt/cleanup lifecycle regression.
- Core result: **559 passed, 1 skipped** in 0.98 seconds. The skip is the
  Python 3.11-specific malformed RunPod log reproducer; the runtime was Python
  3.12.
- The exact task-created PostgreSQL container was removed. No listener remained
  on `127.0.0.1:55487`; older unrelated run-labeled containers were preserved.
  `policies/repository-state.yaml` remained `mode: parked`.
- Scope is local macOS/OrbStack `arm64` with a synthetic source identity. This
  is not hosted or ChatGPT acceptance and does not establish live GPU or paid
  execution.

The P4 fake candidate regression uses a synthetic provider inventory, device,
and signer. Its separate scope record is
[`2026-10-31-p4-fake-candidate-lifecycle.md`](2026-10-31-p4-fake-candidate-lifecycle.md).

## Earlier current-worktree run

## Source and runtime inputs

- Git HEAD: `a794438f42bd7246f463eaaa40d963af0aae9d13`, with the 40-path
  uncommitted working tree present at test time.
- Current-worktree source snapshot used by the contemporaneous Security Review:
  `codex-security-snapshot/v1:sha256:d332334f41caf2e150bcbac547639307710aeb004e1ccddd7c675191b19404e6`.
  The review covered five changed runtime-source files; this acceptance record
  was added after that scan, so it is not part of that snapshot digest.
- CPU smoke image: local `linux/arm64` image
  `sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b`,
  with the synthetic test source SHA `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
- PostgreSQL image:
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
  The dedicated test container published PostgreSQL only on
  `127.0.0.1:55483`; it had a unique task name and was removed after testing.

## Results

- Gateway command from `gateway/`:
  `./.venv/bin/python -m pytest -o addopts= -q -rs tests`, with
  `GATEWAY_TEST_DATABASE_URL`, `GPU_CONTROL_POSTGRES_CONTAINER`,
  `GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST`, `GPU_CONTROL_CPU_SMOKE_SOURCE_SHA`,
  and `GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY` bound to the disposable test
  resources and synthetic fixture above.
- Gateway: **480 passed, 2 skipped, 1 warning** in 25.64 seconds. The skips
  were optional PyTorch and Modal dependencies. Real Docker CPU/MCP tests,
  PostgreSQL migrations and OAuth, artifact integrity, and PostgreSQL outage
  recovery were enabled.
- Core command from the repository root:
  `./.venv/bin/python -m pytest -o addopts= -q -rs`.
- Core: **550 passed, 1 skipped** in 1.01 seconds. The skip is a Python
  3.11-specific malformed-log reproducer; this run used Python 3.12.
- The existing Starlette `BlockingPortal` deprecation warning remains.
- The test container was removed. No listener remained on `127.0.0.1:55483`.
  `git diff --check` passed after recording the result.

## Scope limits

This is local macOS/OrbStack `arm64` evidence with a synthetic workload source
identity. It does not exercise a ChatGPT account, a deployed Gateway, the
production database, a dedicated target host, a GPU, or a provider account.
The repository remains at `mode: parked`.
