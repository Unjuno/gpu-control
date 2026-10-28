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
