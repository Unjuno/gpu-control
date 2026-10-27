# Implementation progress

```text
current_phase: P0 baseline audit complete; P1 T1-T3 complete; T4 local CPU container backend in progress
current_task: implement detached local Docker CPU smoke execution with bounded result capture and cleanup evidence
base_sha: 24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e
working_branch: codex/chatgpt-cpu-vertical
implemented: plan/spec copied into repository; PR #43 disposition audited; README canary SHA and completion version reconciled to repository policy; core pytest upgraded from vulnerable 8.4.2 to locked 9.1.1; additive Gateway v2 Plan/Result contracts and explicit idempotent v1-to-v3 migration added; seven canonical MCP tools advertised while six legacy names remain callable; canonical owner-scoped envelopes, source/device checks, exact-fingerprint submit, bounded filtered listing with owner-bound cursor, pending/simulation result handling added; compatibility period documented; T3 added a fail-closed local CPU admission evaluator, disabled-by-default policy file, immutable image digest and smoke profile constraints, distinct durable local-policy authorization, prepare/submit/worker policy and fingerprint validation, and revocation-before-start behavior
tests_and_commands: `uv sync --locked --extra dev && uv run pytest -o addopts='' -q` (452 passed, 1 skipped); T2 Gateway suite (166 passed, 3 skipped); current Gateway suite (179 passed, 3 skipped); T3 admission/service/API/migration targeted suite (45 passed). Migration tested on SQLite; dedicated PostgreSQL test was skipped because no test DB URL was configured.
real_execution_evidence: no Gateway deployment, real container, provider, or ChatGPT call executed; CPU owner-comment path unit tests passed but are not real ChatGPT/MCP acceptance
release_matrix_changes: MCP_CONNECTIVITY, CHATGPT_TOOL_USABILITY, CPU_EXECUTION, RECOVERY, CANCELLATION, RESULT_RETRIEVAL remain unverified; paid/GPU remains blocked by parked policy
remaining_blockers: T4-T7; no real container or ChatGPT/MCP acceptance has run; policy defaults disabled and no production local_cpu backend is registered; inspect current ChatGPT workspace availability and deployed Gateway/OAuth/DB/worker configuration before real acceptance; PostgreSQL migration has not been exercised
next_task: implement T4 Docker container execution, safe output capture, and real CPU smoke evidence; do not enable the local CPU policy until the backend passes isolated acceptance
```

Update this record only with observed implementation and validation evidence. Do not describe mock/provider tests as real integration acceptance.
