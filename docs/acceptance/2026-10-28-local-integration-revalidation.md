# Local Gateway integration revalidation — 2026-10-28

Status: **PASS for local CPU/MCP/PostgreSQL integration only; ChatGPT and production acceptance NOT RUN**.

## Environment and exact inputs

- Worktree branch: `codex/chatgpt-cpu-vertical`.
- Source commit at test time: `f15ab32` (documentation-only follow-up commits do not alter test code).
- Host: macOS with OrbStack Docker daemon.
- CPU image: `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`.
- Image OCI labels: repository `Unjuno/gpu-control`, fixture revision `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
- PostgreSQL image: `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97` (PostgreSQL 16).
- PostgreSQL ran in a disposable container bound only to `127.0.0.1:55439`; its database and container were removed after the run.

## Commands and observations

- Core: `uv run pytest -o addopts= -q` — **517 passed, 1 skipped**.
- Gateway offline plus real local integrations:
  `gateway/.venv/bin/python -m pytest -o addopts= -q -rs gateway/tests` — **274 passed, 2 skipped**, one Starlette deprecation warning, 19.51 seconds.
- The enabled integration suite exercised the digest-pinned CPU container, authenticated HTTP/MCP prepare/idempotency/submit/result/artifact retrieval, cancellation and recovery, and PostgreSQL-backed lifecycle behavior including a database outage after terminal capture and recovery of the same run.
- The only Gateway skips were the optional Torch check (`torch` not installed) and Modal backend check (`modal` not installed). Docker CPU and PostgreSQL integration cases were enabled and passed.
- An initial full Gateway run used a dynamically mapped host port. After the outage test stopped and restarted PostgreSQL, connections to the test's retained URL were refused and PostgreSQL-backed cases failed. The precise cause (port remapping versus readiness timing) was not isolated. Re-running the outage case and full suite on fixed loopback port `55439` passed. For this OrbStack setup, use a fixed loopback port for this stop/start test. The product database remains external to the worker and no production service was involved.
- `git diff --check` passed after recording this evidence. No GitHub Actions run, Vercel deployment, real ChatGPT OAuth/tool call, target Linux host, Neon migration, provider API call, GPU execution, or paid compute was involved.

## Scope boundary

This upgrades local CPU execution, MCP protocol integration, result/artifact retrieval, cancellation, and recovery evidence at the stated local scope. It does not pass `MCP_CONNECTIVITY` or `CHATGPT_TOOL_USABILITY`; the test client is not ChatGPT. It does not establish seven-day stability, production PostgreSQL recovery, second-operator restore, quota/alert delivery, free GPU, or paid GPU acceptance. Keep `policies/repository-state.yaml` parked.

## Current-worktree follow-up — 2026-10-28

- Base commit: `f054aebe96460fe033dde8d91d7e3bbab0255655`.
- Exact uncommitted diff digest at test time: `22602e3e8cc5ee01c05e63968025efebff93359584885c9ee4f54f6a719408dc` (`git diff --binary | shasum -a 256`). This rerun includes the crash-resistant write-probe ordering; its success-path regression verifies the directory entry is removed before writing through the still-open descriptor.
- CPU image: `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`; OCI source/revision labels matched `Unjuno/gpu-control` and fixture SHA `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
- PostgreSQL image: `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97` (PostgreSQL 16), in disposable container `gpu-control-postgres-accept-1028b`, published only at `127.0.0.1:55471`.
- Invocation: `GATEWAY_TEST_DATABASE_URL` pointed to the loopback-only dedicated database; `GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST`, source repository/SHA, and stoppable container name were set to the exact values above. From `gateway/`, ran `.venv/bin/python -m pytest -o addopts= -q`. The ephemeral database URL is omitted from this record.
- Result: **279 passed, 2 skipped**, one Starlette deprecation warning, 20.49 seconds. The skips were the optional Torch and Modal SDK checks. PostgreSQL parallel admission, lease fencing, v4-to-v7 additive migration, Docker lifecycle/retrieval, and the PostgreSQL outage-after-capture recovery case were enabled.
- Cleanup: the outage test stopped and restarted the same PostgreSQL container; after pytest it was running and healthy. The test container was then removed explicitly. A follow-up query found no matching container and no run-labeled CPU containers.
- This run validates the exact current source diff at the stated local scope. It does not validate Neon, a target Linux host, ChatGPT, production backup/restore, quota alerts, or GPU/provider execution.

## Current-worktree follow-up — 2026-10-28 artifact probe fixtures

- Gateway diff digest at test time:
  `09f57882bc17184533c95f83428a18dfce2c98f65eada9ab5951b71a80a0a23e`
  (`git diff --binary -- gateway | shasum -a 256`). This hashes the then-current
  tracked Gateway changes and excludes repository documentation.
- The first full integration attempt exposed three fixture failures. The MCP
  vertical and both worker recovery fixtures created an artifact root without
  the now-required `.gpu-control-probes` directory, so the worker correctly
  refused admission with `ARTIFACT_STORAGE_UNAVAILABLE`. Added that directory
  to all three fixtures; the product check remains fail-closed.
- Re-ran the entire Gateway suite against a disposable PostgreSQL 16 container
  bound only to `127.0.0.1:55542`, using the pinned CPU image and synthetic
  source identity above. Result: **296 passed, 2 skipped**, one Starlette
  deprecation warning, 20.93 seconds. Skips were optional Torch and Modal SDK
  checks.
- The actual Docker worker-crash-after-container-start recovery test passed
  separately (1 passed, 3.58 seconds), as did PostgreSQL-outage-after-terminal-
  capture recovery (1 passed, 5.05 seconds). Both were also included in the
  full suite.
- The dedicated PostgreSQL container was removed after the suite. Follow-up
  inventory found neither that named container nor any run-labeled CPU
  containers. No unrelated container was changed.
- Root suite on the same worktree: `.venv/bin/pytest -o addopts= -q` —
  **532 passed, 1 skipped**. `git diff --check` passed.

This strengthens local container lifecycle, artifact-readiness fixture, and
PostgreSQL outage recovery evidence only. It does not pass ChatGPT,
production-host, Neon, seven-day operations, alert-delivery, or GPU acceptance.
Keep the repository parked.

## Current continuation refresh — 2026-10-28, full root and Gateway suites

- Worktree base: `f054aebe96460fe033dde8d91d7e3bbab0255655`; changes remained
  unstaged and uncommitted. `git diff --check` passed.
- Root suite: `./.venv/bin/python -m pytest -o addopts= -q` — **550 passed,
  1 skipped**.
- Gateway ordinary suite: **413 passed, 12 skipped**. The skips included the
  Docker/real-PostgreSQL paths because no test fixtures were configured, so
  this run alone was not counted as lifecycle integration evidence.
- Then ran the full Gateway suite with a newly built local CPU smoke image from
  the pinned Docker base and a disposable PostgreSQL 16 container, published
  only on loopback port 55499. The build arguments set source identity to
  `Unjuno/gpu-control` / `f054aebe96460fe033dde8d91d7e3bbab0255655`; the
  resulting image ID was passed directly to the tests and its temporary tag
  was removed after the run.
  Result: **423 passed, 2 skipped**, one Starlette deprecation warning, 23.75
  seconds. The only skips were the optional Torch and Modal SDK checks.
- The first integration attempt used an ephemeral Docker host port. The
  PostgreSQL outage test stopped and restarted its container; the retained
  connection URL then refused connections, causing seven PostgreSQL-backed
  failures. Repeating the same suite on fixed loopback port 55499 passed.
  This reproduces the known OrbStack requirement to use a fixed published port
  for stop/restart integration drills; it does not identify whether remapping
  or forwarding readiness caused the ephemeral-port failure.
- The passing run covers local CPU worker execution, worker crash recovery,
  MCP/HTTP result and artifact retrieval, PostgreSQL concurrency, v1-to-v8
  migration, OAuth rotation rollback, and PostgreSQL outage recovery. The
  uniquely named test container and image tag were removed by the exit trap;
  unrelated Docker objects were not changed.

This remains local evidence. It does not establish ChatGPT connection/tool
acceptance, Neon behavior, production migration or restore, target-host systemd,
seven-day stability, live notifications, GPU, or paid execution. Keep
`policies/repository-state.yaml` parked.


## Current continuation refresh — 2026-10-28

- Worktree base: `f054aebe96460fe033dde8d91d7e3bbab0255655`; current tracked
  Gateway diff SHA-256: `09f57882bc17184533c95f83428a18dfce2c98f65eada9ab5951b71a80a0a23e`
  (`git diff --binary -- gateway | shasum -a 256`). This includes all current
  tracked Gateway changes at test time; root P4 selector changes are covered by
  the separate core/root test record, not this digest.
- Re-ran the entire Gateway suite with the digest-pinned local CPU image
  `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`
  and disposable PostgreSQL 16
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  bound only to `127.0.0.1:55543`. Invocation from `gateway/`:
  `.venv/bin/python -m pytest -o addopts= -q -rs tests`, with
  `GATEWAY_TEST_DATABASE_URL`, `GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST`, synthetic
  source identity, and the stoppable test-container name set for the suite.
  Result: **296 passed, 2 skipped**, one Starlette deprecation warning, 20.11s.
  Optional skips were Torch and Modal SDK checks.
- The dedicated PostgreSQL container was removed by an exit trap. Follow-up
  `docker ps -a` checks found no container with the test name and no
  `io.unjuno.gpu-control.run-id` containers. `git diff --check` passed.
- Scope: current local Gateway, Docker CPU worker, and PostgreSQL integration
  only. This is not ChatGPT connectivity/tool-call acceptance, target-host,
  Neon, seven-day operations, or GPU/provider acceptance.

## Current continuation run — full Gateway with Docker/PostgreSQL — 2026-10-28

- Re-ran the current Gateway suite using the same digest-pinned CPU image and
  PostgreSQL 16 image above. A first attempt used Docker's dynamically assigned
  loopback port and ended with 4 failures / 338 passes / 2 optional skips when
  the outage-recovery case stopped and restarted PostgreSQL; subsequent
  database-backed tests could not reconnect at the retained port. The
  disposable container was removed by the exit trap.
- Confirmed fixed loopback port `127.0.0.1:55543` was unused, then created a
  uniquely named disposable PostgreSQL container bound only to that address.
  From `gateway/`, ran `.venv/bin/python -m pytest -o addopts= -q -rs tests`
  with the pinned CPU image, synthetic source identity, and that dedicated
  stoppable container configured.
- Result: **342 passed, 2 skipped**, one existing Starlette deprecation
  warning, 21.48 seconds. Optional skips were the Torch and Modal SDK checks.

## Current-worktree full rerun after MCP compatibility fixture correction — 2026-10-28

- The first rerun surfaced two tests that expected `structuredContent` while
  sending unversioned requests. Unversioned requests intentionally select MCP
  2025-03-26, which omits that field. Updated the affected authenticated HTTP
  and Docker CPU integration fixtures to request 2025-06-18 or 2025-11-25,
  respectively, matching the structured output contract under test.
- Re-ran from `gateway/` with the PostgreSQL 16 image pinned at
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  bound only to `127.0.0.1:55496`, and CPU image
  `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`.
  Invocation: `.venv/bin/python -m pytest -o addopts= -q -rs tests`.
- Result: **409 passed, 2 skipped**, one existing Starlette deprecation
  warning, 22.57 seconds. Optional skips were the Torch and Modal SDK checks.
  The disposable PostgreSQL container was removed after completion.
- This is local MCP, authenticated Docker CPU, artifact, and PostgreSQL
  integration evidence. It does not establish ChatGPT workspace acceptance,
  deployed readiness, selected-host operation, or production recovery.
- The disposable PostgreSQL container was removed by an exit trap. Scope is
  local Docker CPU lifecycle and PostgreSQL recovery only; this does not prove
  ChatGPT connectivity, target-host operation, Neon behavior, GPU execution,
  provider billing, or production acceptance.

## Current worktree after readiness filesystem-boundary fix — 2026-10-28

- Independent review found that artifact readiness enforced a separate
  filesystem only when `minimum_free_bytes > 0`, even though the capacity
  monitor and deployment model require a dedicated artifact mount. Changed
  readiness to require separation unconditionally when local CPU is enabled.
  Added a regression for same-filesystem rejection at a zero capacity floor;
  the test failed before the fix and passed after it. Test-only integration
  fixtures now model a distinct device identity so they continue to exercise
  real Docker lifecycle behavior without claiming the temporary directory is
  a deployed mount.
- Artifact storage and HTTP readiness: **40 passed**. Gateway offline suite:
  **337 passed, 9 skipped**. The full Gateway suite with the pinned CPU image
  and disposable PostgreSQL 16 on fixed loopback `127.0.0.1:55543` passed:
  **344 passed, 2 skipped**, one existing Starlette deprecation warning,
  21.25 seconds. Optional skips were Torch and Modal SDK checks.
- The DB container used a uniquely named explicit Docker volume so its
  stop/restart recovery test retained data; both container and volume were
  removed after the run. No unrelated Docker container or volume was changed.
- This revalidation covers local CPU/Docker/PostgreSQL behavior and the
  readiness mount invariant only. ChatGPT, selected Linux host, production
  backup/restore, alert delivery, Neon, GPU, and paid-provider acceptance
  remain NOT RUN.

## Current worktree after capacity-poller serialization — 2026-10-28

- Worktree base: `f054aebe96460fe033dde8d91d7e3bbab0255655`. The current
  state-machine and regression test file SHA-256 values were
  `906e9f2c92edef8674055e45c96104031aaff4ebb1ee4152fc76b562ec2d5a58` and
  `46ea01ff3b8627516b08faa3ceb381bae546250dfcf0e281f9b594dba445d62e`.
- First full-suite attempt used a tmpfs-backed PostgreSQL data directory. It
  completed 344 tests with 2 optional skips but the outage-recovery test could
  not confirm PostgreSQL recovery after stop/start. This attempt is not counted
  as a pass.
- Repeated with the digest-pinned PostgreSQL 16 image on fixed loopback
  `127.0.0.1:55543` and its default anonymous data volume. A preflight stop/start
  and readiness check passed. The complete Gateway suite then passed **345
  tests, 2 optional skips**, and one existing Starlette deprecation warning
  (20.64 seconds). The digest-pinned CPU image and synthetic source SHA above
  were used; this includes local Docker lifecycle and PostgreSQL outage
  recovery as well as the new poller concurrency regression.
- The disposable PostgreSQL container was removed with its anonymous volume.
  Both exited CPU containers created by these suite attempts were identified by
  creation time, CPU image digest, and synthetic source labels, then removed by
  exact name. Follow-up inventory found no test PostgreSQL container and no
  run-labeled CPU containers.
- This is local CPU/Docker/PostgreSQL integration evidence only. No live Linux
  journal, systemd service, ChatGPT connection, target host, Neon, GPU, or paid
  resource was exercised. Root/core tests were not rerun. Parked mode remains.

## Digest-pinned Docker follow-up after prepare-idempotency fix — 2026-10-28 08:06 UTC

- Worktree base: `f054aebe96460fe033dde8d91d7e3bbab0255655`; tested the
  current uncommitted working tree. Relevant file SHA-256 values:
  `gateway/gpu_gateway/service.py`:
  `c99117b60acea98123c04418c76dfee1afa69a18deb8d03860ee6eda682d0137`,
  `gateway/gpu_gateway/experiment_api.py`:
  `97d86ac23e470cdf8195673f69644f6e44606695066d815732fde2c5ccc6a162`, and
  `gateway/tests/test_experiment_api.py`:
  `93e8b5946202352a827fd003a12aa36f5c84b3af733953a7619dc00be91aade1`.
- Invocation from `gateway/` used the local OrbStack daemon and existing
  `gpu-control-cpu-smoke:provenance-test` image
  `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`,
  labeled for repository `Unjuno/gpu-control` and fixture SHA `a` repeated 40
  times. Ran:
  `.venv/bin/python -m pytest -o addopts= -q tests/test_local_backend_integration.py tests/test_local_lifecycle_integration.py tests/test_local_mcp_integration.py -ra`.
- Result: **3 passed**, one existing Starlette deprecation warning, 7.05
  seconds. This covers the real local container contract, worker crash/recovery,
  and authenticated MCP CPU run plus artifact retrieval through a second local
  client. These are local Docker/TestClient results, not a ChatGPT conversation.
- Post-run inventory found one run-labeled Exited container created at
  `2026-10-28 16:40:58 +0900`, before this test invocation. It was preserved;
  no new run-labeled test container remained. No PostgreSQL integration,
  deployment, provider, GPU, or paid resource was used. The existing full
  PostgreSQL 16 evidence above predates this idempotency change and was not
  repeated in this follow-up.

## Full Gateway Docker/PostgreSQL revalidation after prepare-idempotency fix — 2026-10-28

- Tested the current uncommitted working tree based on
  `f054aebe96460fe033dde8d91d7e3bbab0255655`.
- Used the existing digest-pinned CPU smoke image
  `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`
  with repository `Unjuno/gpu-control` and synthetic fixture SHA `a` repeated
  40 times. PostgreSQL 16 image was
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  in a uniquely named disposable container published only on
  `127.0.0.1:55546`.
- From `gateway/`, ran the complete suite with
  `.venv/bin/python -m pytest -o addopts= -q -rs tests`, setting
  `GATEWAY_TEST_DATABASE_URL` to the loopback-only `postgresql+psycopg://`
  URL, `GPU_CONTROL_POSTGRES_CONTAINER`, and the CPU image/source identity
  variables above. The first attempt used `postgresql://`, which selected the
  absent psycopg2 driver and failed four PostgreSQL cases at initialization;
  rerunning with the project's declared psycopg 3 driver succeeded.
- Result: **395 passed, 2 skipped**, one existing Starlette deprecation
  warning, 22.47 seconds. The skips were optional Torch and Modal SDK checks.
  This includes the prepare-idempotency change plus the enabled PostgreSQL,
  Docker CPU, lifecycle, recovery, and MCP integration tests.
- The disposable PostgreSQL container was removed by the command's exit trap.
  No persistent database or unrelated container was changed.
- Scope remains local CPU/Docker/PostgreSQL. This does not establish a real
  ChatGPT conversation, deployed-host readiness, provider/GPU behavior, or paid
  execution; parked mode remains unchanged.

## Current worktree revalidation — 2026-10-28 OAuth and P4 integration follow-up

- Base commit: `f054aebe96460fe033dde8d91d7e3bbab0255655`.
- Complete changed-worktree inventory: 110 paths (70 modified/deleted, 40 untracked). Content/status digest: `61134cb0665c99cd8e3673e506b6a753ee60193a10df200f5a2a5f4b013be075`.
- PostgreSQL image: `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97` (PostgreSQL 16), dedicated container on loopback-only port `55546`.
- CPU smoke image: `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`; OCI source/revision labels matched `Unjuno/gpu-control` and fixture SHA `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
- From `gateway/`, ran `.venv/bin/python -m pytest -o addopts= -q -rs tests` with the dedicated PostgreSQL URL, stoppable container name, and pinned CPU image/source identity configured.
- Result: **403 passed, 2 skipped**, one existing Starlette deprecation warning, 22.69 seconds. The skips were optional Torch and Modal SDK checks. This run includes PostgreSQL refresh-token concurrency, P4 candidate evidence and exact-resource revalidation, real local CPU/MCP/artifact flows, PostgreSQL outage-after-capture recovery, and the additive migration test.
- The first invocation mistakenly used Docker `--rm`, so the intentional database stop in the outage-recovery test removed the container and caused that case plus later PostgreSQL tests to fail. The run was discarded as invalid harness setup; rerunning without `--rm` passed the full suite. The named DB container was removed by the exit trap. Two pre-existing run-labeled containers remained unchanged; no new test-labeled CPU container remained.
- `git diff --check` passed and `policies/repository-state.yaml` remained `mode: parked`. This validates local Docker/PostgreSQL behavior only; it does not prove ChatGPT, Neon, a target host, real GPU, or paid execution acceptance.

## Current-worktree full Gateway rerun — 2026-10-28 continuation

Re-ran the complete Gateway suite from the current 111-path dirty worktree at
base `f054aebe96460fe033dde8d91d7e3bbab0255655`, using the digest-pinned
PostgreSQL 16 image, the existing digest-pinned CPU smoke image
`sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`, and
a new PostgreSQL container on loopback-only port 55548. The URL used the
repository-declared `postgresql+psycopg://` driver. The outage/recovery test was
enabled with the container name and could stop/restart the same disposable DB.

Result: **403 passed, 2 optional skips**, one existing Starlette deprecation
warning, 22.31 seconds. Skips were optional Torch and Modal SDK checks. The
container was removed by the exit trap; post-run inspection found no matching
container or test-labeled run container. `git diff --check` passed and
`policies/repository-state.yaml` remains `mode: parked`. This repeats local
Docker CPU/PostgreSQL lifecycle and recovery evidence; it does not establish
ChatGPT connectivity, Neon behavior, a selected target host, production restore,
GPU execution, or paid acceptance.
## Current-schema migration follow-up — PostgreSQL 16 v4 to v8

- Updated the PostgreSQL additive-migration regression to cover the current
  Gateway schema version 8, including creation of
  `gateway_provider_observations_v1` after resetting a disposable database to
  the v4 shape and removing v5-v8 additions.
- SQLite migration suite: **4 passed**.
- PostgreSQL integration: **1 passed**, using the digest-pinned PostgreSQL 16
  image `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  in a uniquely named container published only on `127.0.0.1:55489`. The test
  confirmed the resulting schema version and provider-observation columns.
- The disposable container was removed after the test. This extends the
  earlier synthetic PostgreSQL v1-to-v7 evidence through a PostgreSQL v4-to-v8
  upgrade; it does not establish a direct PostgreSQL v1-to-v8 rehearsal,
  Neon/production migration, or authorize production schema changes.

## Direct unversioned v1-to-v8 migration regression — PostgreSQL 16

- Added `test_postgres_v1_to_current_preserves_legacy_run_and_oauth_rows`.
  It creates a unique temporary PostgreSQL schema, builds the existing
  unversioned v1 fixture there, migrates twice to schema v8, and checks run
  identity/plan/result, OAuth token retention, `grant_id`, and provider
  observation columns. The schema is dropped in a `finally` block.
- Focused invocation: from `gateway/`,
  `.venv/bin/python -m pytest -o addopts= -q
  tests/test_postgresql.py::test_postgres_v1_to_current_preserves_legacy_run_and_oauth_rows`.
- Result: **1 passed**, one existing Starlette deprecation warning. PostgreSQL
  16 used pinned image
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  on loopback-only port `127.0.0.1:55497`; the container was removed.
- This closes the direct legacy-shape-to-current-version local PostgreSQL
  regression gap. It does not validate PostgreSQL 17, Neon behavior, production
  data, operator rollback, or authorize a production migration.

## Full Gateway rerun including direct v1-to-v8 migration — PostgreSQL 16

- After adding the isolated-schema migration regression, reran the complete
  Gateway suite with the digest-pinned PostgreSQL 16 and CPU smoke images.
  PostgreSQL was bound only to `127.0.0.1:55498`; the stoppable container was
  removed after the run.
- Invocation from `gateway/`:
  `.venv/bin/python -m pytest -o addopts= -q -rs tests` with the dedicated
  PostgreSQL URL, CPU image digest, fixture repository/SHA, and container name.
- Result: **410 passed, 2 skipped**, one existing Starlette deprecation warning,
  22.34 seconds. The optional skips were Torch and Modal SDK checks.
- Scope is the current local Gateway, Docker CPU, PostgreSQL, and migration
  integration. ChatGPT, Vercel runtime acceptance, Neon, selected-host
  operations, real GPU, and paid execution remain unverified.

## Full Gateway compatibility rerun — PostgreSQL 17.11

- Repeated the same full Gateway invocation and pinned Docker CPU smoke image
  against PostgreSQL 17.11, matching the major version observed on the existing
  Neon project. PostgreSQL used pinned image
  `sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27`
  on loopback-only port `127.0.0.1:55499`; its disposable container was removed.
- Result: **410 passed, 2 skipped**, one existing Starlette deprecation warning,
  21.90 seconds. The optional skips were Torch and Modal SDK checks. This
  includes the unversioned v1-to-v8 migration regression, Docker CPU lifecycle,
  PostgreSQL recovery, and concurrent access tests.
- This adds local PostgreSQL 17.11 compatibility evidence. It does not exercise
  Neon networking, roles, extensions, branch behavior, existing production
  data, production migration, or recovery procedures.

## Gateway rerun after adding read-only migration preflight — PostgreSQL 17.11

- Added the operator-only `--check-db` preflight and wired it as
  `ExecStartPre` for the manual migration service. The preflight is included in
  the PostgreSQL v1 fixture test and is proven not to create the version table
  or change the legacy OAuth row before `migrate()` runs.
- Re-ran from `gateway/` with the pinned PostgreSQL 17.11 image
  `sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27`
  on loopback-only port `127.0.0.1:55500` and the digest-pinned CPU image used
  above. Invocation: `.venv/bin/python -m pytest -o addopts= -q -rs tests`.
- Result: **415 passed, 2 skipped**, one existing Starlette deprecation
  warning, 22.71 seconds. Optional skips were Torch and Modal SDK checks. The
  disposable PostgreSQL container was removed.
- This is local PostgreSQL 17.11 and CPU integration evidence. Neon itself was
  only queried read-only; no live database schema or state was changed.

## Gateway rerun after adding read-only migration preflight — PostgreSQL 16

- Repeated the same complete invocation against pinned PostgreSQL 16 image
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  on loopback-only port `127.0.0.1:55501` and the digest-pinned CPU image.
- Result: **415 passed, 2 skipped**, one existing Starlette deprecation warning,
  22.50 seconds. Optional skips were Torch and Modal SDK checks. The disposable
  database container was removed.
- Current read-only preflight, all migrations, Docker CPU, and recovery paths
  therefore pass on both PostgreSQL 16 and 17.11. Neon runtime/branch semantics
  remain a separate unverified boundary.


## Current Gateway rerun after PostgreSQL URL preservation fix — 2026-10-28

- The full PostgreSQL v1-to-v8 regression exposed a test harness issue:
  converting SQLAlchemy's URL object to `str` masked the password as `***` for
  the second `Store` engine. The test now explicitly renders the URL with its
  password preserved; no production code changed for this issue.
- Re-ran the complete Gateway suite against digest-pinned PostgreSQL 16
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  and PostgreSQL 17.11
  `sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27`.
  Each disposable DB was bound only to loopback and removed with its uniquely
  named container and volume. The digest-pinned CPU image and synthetic source
  identity documented above were used for Docker integration.
- Invocation from `gateway/` for both runs: `.venv/bin/python -m pytest -o
  addopts= -q -rs tests`. PostgreSQL 16 result: **416 passed, 2 skipped**, one
  Starlette deprecation warning, 22.95 seconds. PostgreSQL 17.11 result:
  **416 passed, 2 skipped**, one Starlette deprecation warning, 22.82 seconds.
  Optional skips were the Torch and Modal SDK checks.
- The run includes PostgreSQL v1-to-v8 row-preservation migration, v4-to-v8
  upgrade, concurrent refresh consumption, CPU Docker lifecycle, and outage
  recovery. It remains local integration evidence and does not establish Neon,
  ChatGPT, target-host, GPU, paid-provider, or production acceptance.

## Current continuation run — 2026-10-28, full Gateway with Docker/PostgreSQL

- Base commit: `f054aebe96460fe033dde8d91d7e3bbab0255655`.
- Tracked Gateway diff SHA-256 at test time:
  `84e484f6243b21f01f2cade0e45a6f460ce83809a50c0d28d435995870f019f3`
  (`git diff --binary -- gateway | shasum -a 256`).
- Environment: Docker 29.8.2 on linux/arm64; digest-pinned CPU image
  `sha256:687f52cf7292fc7109cb8df2469cfa9b1296d0d0b5bf1894582cf738c4d8481e`;
  PostgreSQL 16 image
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`
  in a uniquely named disposable container published only on
  `127.0.0.1:55489`. CPU source identity was the synthetic fixture
  `Unjuno/gpu-control` / `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
- Invocation from `gateway/`: `.venv/bin/python -m pytest -o addopts= -q
  -rs tests`, with the test-only PostgreSQL URL, pinned image digest, source
  identity, and disposable container name supplied through environment
  variables. Result: **418 passed, 2 skipped**, one existing Starlette
  deprecation warning, 23.23 seconds. The skips were optional Torch and Modal
  SDK checks.
- The suite includes real local Docker CPU execution, worker crash recovery,
  artifact retrieval, and PostgreSQL-backed lifecycle/outage recovery. The
  PostgreSQL test container was removed by the exit trap. Two exited
  run-labeled CPU containers visible after the run had creation times 2–3 hours
  before this run; they were not created by this run and were left untouched.
- Scope is local Docker/PostgreSQL integration. It does not establish ChatGPT,
  Neon, target-host, production recovery, seven-day operation, GPU, or paid
  provider acceptance. No provider call or production mutation occurred.
