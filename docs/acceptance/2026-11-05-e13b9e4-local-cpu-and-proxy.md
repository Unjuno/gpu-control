# Exact PR #60 head local CPU and proxy validation — 2026-11-05

Scope: code at `e13b9e4b38b5a895b500b57cdede34fa94d3486a`. This records local
execution and proxy-security evidence only; it does not establish hosted or
ChatGPT acceptance, GPU execution, or paid-provider readiness.

## Real local CPU/MCP vertical

- Docker/OrbStack server reported version 29.8.2.
- Built the repository-owned `gateway/workloads/cpu-smoke` image with labels
  `org.opencontainers.image.source=Unjuno/gpu-control` and
  `org.opencontainers.image.revision=e13b9e4b38b5a895b500b57cdede34fa94d3486a`.
- Image ID: `sha256:c8b636e29abab6af19ff754bcda88f02cb924fe494cf28e8ec2bb4107c417536`.
- `gateway/tests/test_local_mcp_integration.py` passed against that exact image
  and revision. It exercised structured MCP discovery and calls; idempotent
  prepare; queued submit; the real isolated Docker CPU worker; result and
  artifact retrieval from a second MCP client; artifact digest/byte matching;
  and completed worker cleanup. The result asserted `simulation=false`,
  `gpu_used=false`, and local cost classification.
- The smoke workload is bounded deterministic CPU validation. It is not a
  model-training or GPU result, and the MCP client is local `TestClient`, not
  ChatGPT.
- The test removed only its run-labeled execution container. A pre-run and
  post-run inventory showed the same unrelated exited `gpu-control` containers;
  they were left untouched. The local test image remains cached.

## Proxy and log security

- Pinned Caddy image `caddy@sha256:cc447f149425221422153c6cdf33a123b3f458839679f950298f68a690a54a5b`
  accepted `gateway/deploy/Caddyfile.example` with `caddy validate`.
- Opt-in real-Caddy integration test passed. It covered local HTTPS, OAuth
  metadata/setup/login, secure session cookie flags, CSRF and Origin rejection,
  invalid bearer rejection, forwarded-IP spoof resistance in login throttling,
  and upstream failure handling. Synthetic setup-token/OAuth-code canaries and
  the generated setup token were absent from Caddy and API container logs.
- The API systemd unit disables Uvicorn access logs; Caddy's default logger
  drops the request URI and credential-bearing headers.
- The complete Gateway test suite and the deployment-unit suite passed on this
  worktree. `git diff --check` passed.
- Independent read-only Security Review of the exact uncommitted proxy/log
  delta reported no actionable issue. This source review does not substitute
  for a GitHub approval or runtime configuration review.

## PostgreSQL recovery integration

- At 2026-11-04 18:50 UTC, a fresh disposable PostgreSQL container using the
  CI-pinned image and a separately named disposable volume was used with the
  exact CPU image above.
- The runtime-role schema test ran first, followed by both tests in
  `gateway/tests/test_postgres_lifecycle_integration.py`: database outage
  after terminal result capture, and worker process death immediately after
  starting the CPU container. All three passed. The recovery path retained the
  same run, collected and verified its artifact, completed cleanup, and
  released the admission slot.
- An initial lifecycle-only invocation failed because it omitted the
  prerequisite runtime-role/schema DDL setup and therefore lacked
  `gpu_control_release_finished_slot(text,text)`. Re-running with the suite's
  schema prerequisite first passed. This was test setup order, not an
  application change.
- The disposable PostgreSQL container and named volume were removed afterward.

## Remote state and limits

- PR #60 is OPEN, Draft, and mergeable at the exact commit above. Python 3.11,
  3.12, and 3.13 CI, trusted reference container, Gateway offline tests, Gateway
  comment bridge tests, Project bridge tests, Vercel Preview, and Preview
  Comments all passed for this head.
- Repository mode remains `parked`; paid-compute and RunPod live-call flags
  remain false. No provider API call, token issuance, billing change, public
  deployment promotion, or paid resource was used.
- The Modal browser is currently at its sign-in screen. The Preview runtime
  still lacks its required isolated database/API configuration and worker
  heartbeats, and ChatGPT OAuth, tool discovery, and a ChatGPT-originated CPU
  run/result retrieval remain unverified.

## ChatGPT tool OAuth challenge compatibility

- OpenAI's current plugin authentication guidance requires per-tool
  `securitySchemes`, protected-resource metadata, and a runtime tool result
  carrying `_meta["mcp/www_authenticate"]` with `error` and
  `error_description` to trigger the ChatGPT OAuth linking UI:
  https://developers.openai.com/plugins/build/auth
- The gateway already published protected-resource metadata and declared the
  scope for each ChatGPT tool. This change adds the runtime challenge for
  unauthenticated calls and insufficient-scope tool calls, while retaining
  HTTP `WWW-Authenticate` for discovery and other MCP requests.
- Verification on 2026-11-11: `uv run --project gateway pytest -q
  gateway/tests/test_http_auth.py gateway/tests/test_protocol_validation.py`
  passed (38 tests), and `uv run --project gateway pytest -q gateway/tests`
  passed (592 passed, 27 skipped).
- Independent read-only Security Review of the uncommitted OAuth challenge
  change found no actionable issue.
- This is local protocol compatibility evidence only. The hosted Preview still
  redirects unauthenticated health checks to Vercel SSO, and this environment's
  computer-control setting disables access to the user's browser. ChatGPT
  account linking, tool discovery, and a ChatGPT-originated experiment remain
  unverified.
