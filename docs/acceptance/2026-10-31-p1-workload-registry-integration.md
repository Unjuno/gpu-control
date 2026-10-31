# P1 workload registry integration acceptance

## Change

The P1 worker now checks a local CPU run against the current operator workload
registry before starting its provider. Real Docker integration fixtures now pass
the same registry explicitly, and the subprocess crash-recovery test loads that
registry from `GATEWAY_WORKLOADS_FILE`, matching the worker entry point. The crash
fixture also asserts the dispatch phase recorded by the current lease fence.

## Local verification

- OrbStack Docker 29.8.2, Linux/aarch64.
- Built the trusted CPU smoke fixture from `gateway/workloads/cpu-smoke` with its
  pinned Python base image; test image ID: `sha256:9f7fd246ba7663ea5a745bc9aa13c3622a4cc9eb11cff18b991dd5960f619aab`.
- Ran the full Gateway suite with that image and a dedicated temporary PostgreSQL
  16 test container: `280 passed, 1 skipped, 38 subtests passed`.
- Ran the Core suite: `515 passed, 1 skipped`.
- Targeted Docker worker-crash recovery, ChatGPT MCP CPU result/artifact retrieval,
  and PostgreSQL outage recovery tests passed.
- Removed only the test-owned PostgreSQL container after the run. The pre-existing
  `gpu-control-ci-postgres-pr51` container was not touched. The locally built smoke
  image remains available for repeat verification.

These are local integration results. They do not establish a deployed Gateway,
ChatGPT workspace connection, or paid/GPU execution. `mode: parked` remains in
force.
