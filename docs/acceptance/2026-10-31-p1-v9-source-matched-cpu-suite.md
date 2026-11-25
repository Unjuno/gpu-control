# P1 schema-v9 source-matched local CPU integration

Status: **PASS for local Gateway/Core suites at this worktree snapshot.** This
does not establish GitHub CI/review, hosted deployment, ChatGPT workspace, or
target-host acceptance.

## Source and runtime inputs

- Git base/head: `aa681f4062dac6b73bcf380a38a4258b96a47e1d` with uncommitted
  worktree changes. Gateway dirty-source fingerprint (tracked Gateway binary
  diff plus sorted untracked Gateway paths and bytes):
  `eb86232729dcdb6a52281bfa000b331ec57ece8b8a1955bd4feba9daed564e5b`.
- CPU smoke image built from `gateway/workloads/cpu-smoke/Dockerfile` with
  pinned Python base
  `python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753`,
  and source labels `Unjuno/gpu-control` plus the fixture SHA of 40 `a`
  characters. Local image ID/digest:
  `sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b`
  (linux/arm64). This fixture identity does not claim a published source SHA.
- Image `/app/smoke.py` SHA-256:
  `bab9a5e10a516a631d8a7a12ed004d9c64e7efd639fe7ff6c64614bfb09e2d9a`;
  `/app/supervise.py` SHA-256:
  `89874c0924102322e223a285d6ba64a72774b99300ba7ed752c5b46fae1440bb`.
  Both match the build-context files.
- PostgreSQL 16 image:
  `postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
  Test container was published only on `127.0.0.1:55439`; a fixed port is
  required because the outage integration test stops/restarts the container.

## Results

- Gateway: **431 passed, 2 skipped, 1 warning** in 24.48 seconds. Command:
  `./.venv/bin/python -m pytest -o addopts= -q -rs tests` from `gateway/` with
  the database/container/image/source environment variables described above.
  The skips are optional Torch and Modal dependencies. Coverage includes real
  Docker CPU execution, owner-authenticated MCP result/artifact retrieval,
  worker death after container start and same-run recovery, PostgreSQL outage
  recovery, and schema v9 OAuth/migration tests.
- Core suite: **550 passed, 1 skipped** in 0.96 seconds. The skip is specific
  to the Python 3.11 malformed-log reproducer; this run used Python 3.12.
- `git diff --check` passed after recording this evidence.

## Excluded attempts and limits

One first Gateway attempt supplied a 65-character image identifier and failed
five tests during digest validation. A second attempt used a dynamically
assigned host port; the database restart changed that port, causing later DB
connections to fail. Both attempts are harness failures and excluded. The
passing run used the exact 64-character local image ID and stable loopback port.

These checks are local macOS/OrbStack arm64 integration evidence. They do not
prove Ubuntu GitHub CI, actual ChatGPT OAuth/tool calls, deployment readiness,
selected-host operations, or a GPU/provider result. No provider account,
GPU, or paid resource was used. Keep `policies/repository-state.yaml` at
`mode: parked`.

## Reconstructed P1/P2/P3 overlay candidate — 2026-10-31

Reconstructed a detached candidate at PR #51 pushed head
`aa681f4062dac6b73bcf380a38a4258b96a47e1` by applying the P1 schema-v9,
P2 worker-crash, and P3 backup-integrity code/test patches in that order. All
10 changed Gateway code/test files matched the current dirty worktree
byte-for-byte; the cumulative 11 paths include the P2 acceptance record.
Each overlay applied cleanly and the combined `git diff --check` passed.

The complete Gateway suite passed **431 passed / 2 skipped / 1 warning** in
25.24 seconds on this candidate. It used the digest-pinned PostgreSQL 16 image
above on `127.0.0.1:55477` without Docker `--rm`, and local CPU image
`sha256:81a53ab7aa2b1ae7f3cc685457c73b98f66c456a5baba204a139397f856db31b`.
The skips were optional Torch and Modal dependencies. The outage-recovery
test stopped and restarted the same named DB container; the runner then
removed it and verified the port was closed.

One excluded attempt passed 421 tests but failed 10 PostgreSQL tests because
the runner used Docker `--rm`; the outage test's `docker stop` deleted that
container before it could restart. This was a harness error, not a candidate
code failure. The corrected run above omitted `--rm` and passed. This is local
macOS/OrbStack candidate evidence, not GitHub CI/review, hosted deployment, or
ChatGPT acceptance.

## Exact committed-source local MCP CPU run — 2026-10-31 JST

Built the repository-owned smoke workload from the unchanged files at Gateway
HEAD `a794438f42bd7246f463eaaa40d963af0aae9d13`, using the Dockerfile's pinned
Python base. The resulting linux/arm64 image ID was
`sha256:15acf11d33636ac3dfd92eee59df028f9d65eae2524cdfd7cbda44bdf361b59b`;
OCI labels name source `Unjuno/gpu-control` and that exact commit. No provider
image, credential, GPU, or paid resource was used.

Ran `tests/test_local_mcp_integration.py` against this image from the current
Gateway worktree: **1 passed** (one Starlette deprecation warning). The test
used a temporary SQLite database, synthetic owner JWT, short-lived test-only
local CPU admission policy, and two independent MCP HTTP TestClients. It
listed tools, prepared and idempotently replayed a registered workload,
submitted it, executed the real container, then retrieved the result and
artifact through the second client. The test asserted run/source/plan/image
identity, `simulation=false`, `gpu_used=false`, `cost_classification=LOCAL`,
successful cleanup, and exact artifact bytes/hash.

A redacted receipt was captured from a second invocation of the exact test
function. UTC start `2026-10-30T19:05:44Z`; run ID
`bd23cb1f3c4b4165aa069cd8646f0125`; plan fingerprint
`d1f66a5dc034e02e9bdc2ac49d5fc2e25771479a45cf796f0d7b828b2aba4859`;
terminal state `succeeded`; artifact `cpu-smoke-result.json`, 568 bytes,
SHA-256 `e87a396a59b5c99f17ad0b32893875a935873c6e606b689f0346d9b35a6055fd`.
The result retrieval returned that same digest with `complete=true`. A
post-run Docker query for the exact run label returned no containers.

The same single-test acceptance was rerun from the complete `origin/main`-based
candidate at `/tmp/gpu-control-main-full-current-20261031-exact`. Before
running pytest, `gpu_gateway.__file__` resolved inside that candidate's
`gateway/` directory. With `PYTHONPATH` set to the candidate's `gateway/` and
`src/`, the real-container MCP test passed **1/1** in 1.24 seconds (same
Starlette warning). This confirms the reconstructed candidate, rather than an
editable install from the primary checkout, exercised the local MCP/CPU path.

The full Gateway suite was then run from the complete candidate at
`/tmp/gpu-control-main-full-current-20261031-final3`; `gpu_gateway.__file__`
resolved inside that candidate. It used the same digest-pinned CPU image and a
disposable PostgreSQL 16 container bound only to `127.0.0.1:55478`, with test
database `gateway_test`. Result: **480 passed, 2 optional skips, 1 warning** in
24.44 seconds. The skips were optional Torch and Modal dependencies.

The initial full-suite attempt used database name `gateway`, while the
PostgreSQL lifecycle tests expect `gateway_test`; 10 DB-backed tests failed
with “database does not exist.” Inspection of the tests confirmed the expected
database name. After creating `gateway_test`, the previously failing outage
recovery test passed **1/1**, and the full suite passed **480/2**. The exact
test container was removed and port 55478 had no listener afterward. This was
a disposable test-harness configuration failure; no source change was made.

Scope limits: this used an in-process FastAPI MCP route and synthetic test
OAuth, not ChatGPT or a deployed endpoint. The artifact filesystem device check
was stubbed by the integration fixture. OrbStack was the shared developer
daemon, so this does not prove a dedicated worker host or production storage.
It strengthens local CPU/MCP execution evidence only; OAuth interoperability,
ChatGPT tool calls, second-conversation acceptance, and target-host operations
remain unverified. The smoke container itself runs with no network, read-only
root, non-root UID 10001, dropped capabilities, no-new-privileges, 1 CPU,
256 MiB memory, and a 32-process limit.
