# Current worktree local validation — 2026-11-04

Status: **PASS for local CPU container, MCP protocol, PostgreSQL runtime-role,
and recovery integration only. Actual ChatGPT, Modal GPU, hosted deployment,
and paid-provider acceptance remain NOT RUN.**

## Source and scope

- Checkout: `codex/gpu-control-current-p5-on-pr58`, HEAD
  `534c84402f7e1ba8bcef246a06bfae7d29622e22`.
- The checkout had pre-existing uncommitted P1/P5 changes. This validation
  included that working tree; no source files were edited during the test run.
- The CPU smoke container used synthetic source revision
  `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`; this is a test fixture identity,
  not a claim about a real source commit. Its local image ID was
  `sha256:7e45235b90d6fb9ce03ea881f860918aab22631eaa0055fc9bf02836ff4838bc`.

## Results

- Tiny bigram training ran locally and in a Docker container for 40 steps.
  Both reported `initial_loss=2.564949357461535`,
  `final_loss=1.8011487310380074`, and `gpu_used=false`.
- Three repository-owned Docker integration tests passed. They exercised the
  real local CPU worker and cleanup, authenticated MCP prepare/submit/result
  flow, and retrieval of the result and bounded artifact from a second MCP
  client with digest verification.
- Sixteen PostgreSQL 17 tests passed, including the changed database runtime
  role grants, OAuth migrations, and PostgreSQL store operations under the API
  and worker roles.
- Full Gateway suite with the digest-pinned local CPU image, disposable
  PostgreSQL database, Modal SDK 1.5.5, and stoppable test database: **563
  passed, 1 skipped**. The skip was the optional Torch-dependent CI bridge test
  because Torch is not installed in this environment. One existing Starlette
  deprecation warning was emitted.
- WebMCP registration tests: **3 passed**.
- `git diff --check`: passed.

## Follow-up security regression checks — 2026-11-04

- Current full Gateway suite: **543 passed, 25 skipped**. The skips require
  external/environment setup, including provider-backed and PostgreSQL cases.
- Current PostgreSQL 17.11 role, store, provider-lease, migration and OAuth
  integration set: **87 passed** against a fresh disposable database. The
  container was removed after the run.
- A deterministic OAuth concurrency test now races revocation by a rotated
  predecessor against refresh of its current successor. It confirms that
  revocation blocks on the grant-family lock and revokes all six persisted
  predecessor/current/successor access and refresh tokens.
- Hosted API-only client-IP key validation no longer prevents worker,
  supervisor or migration processes from starting with the documented common
  `gateway.env` file.
- Client IP throttling buckets now use secret-keyed HMAC. Hosted API settings
  reject the development default and missing/short keys.
- Vercel-header behavior coverage: the documented client IP header may contain
  repeated identical entries; distinct conflicting entries fail closed.
  [Official Vercel header documentation](https://vercel.com/docs/headers/request-headers).
- WebMCP registration tests: **3 passed**. `git diff --check` and Python
  `compileall` passed. Independent Codex Security Diff Scan remains incomplete;
  tests and manual source review do not replace it.

The first combined PostgreSQL run was invalid because it reused a database
already populated by a prior role test and used an auto-removing container that
could not be restarted by the database-outage tests. It produced 16 failures.
The test fixture was recreated with an empty disposable database and a
restartable container; the full rerun above passed. No application-code change
was made in response to that fixture error.

## Cleanup and limits

- The disposable PostgreSQL container and its anonymous volume were removed.
- The test-created CPU container was removed. Older unrelated exited
  `gpu-control` containers were left untouched.
- The local test images remain cached in Docker; no remote registry push was
  made.
- The MCP client was the repository's local TestClient, not ChatGPT. The tests
  do not establish a ChatGPT OAuth grant, public HTTPS/tunnel connection, or
  hosted worker readiness.
- The Tiny LM test used CPU only. No Modal account API call, GPU allocation,
  credit use, or paid compute occurred.

Keep `policies/repository-state.yaml` in `parked` mode.
