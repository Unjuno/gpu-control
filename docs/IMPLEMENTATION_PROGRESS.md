# Implementation progress

```text
current_phase: P0 baseline audit complete; P1 T1-T2 complete; T3 admission policy primitives in progress
current_task: T3 persist policy authorization distinctly from browser approval, enforce on submit/worker, and verify revocation before execution
base_sha: 24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e
working_branch: codex/chatgpt-cpu-vertical
implemented: plan/spec copied into repository; PR #43 disposition audited; README canary SHA and completion version reconciled to repository policy; core pytest upgraded from vulnerable 8.4.2 to locked 9.1.1; additive Gateway v2 Plan/Result contracts and explicit idempotent v1-to-v2 migration added; seven canonical MCP tools advertised while six legacy names remain callable; canonical owner-scoped envelopes, source/device checks, exact-fingerprint submit, bounded filtered listing with owner-bound cursor, pending/simulation result handling added; compatibility period documented; T3 added a fail-closed local CPU admission evaluator, disabled-by-default policy file, local CPU workload image digest/profile constraints, schema v3 nullable admission field, and prepare-time policy checks that create no run unless later persistence work is implemented
tests_and_commands: `uv sync --locked --extra dev && uv run pytest -o addopts='' -q` (452 passed, 1 skipped); T2 Gateway suite (166 passed, 3 skipped); current Gateway suite (174 passed, 3 skipped); T3 admission/service/migration targeted suite (29 passed). Migration tested on SQLite; dedicated PostgreSQL test was skipped because no test DB URL was configured.
real_execution_evidence: no Gateway deployment, real container, provider, or ChatGPT call executed; CPU owner-comment path unit tests passed but are not real ChatGPT/MCP acceptance
release_matrix_changes: MCP_CONNECTIVITY, CHATGPT_TOOL_USABILITY, CPU_EXECUTION, RECOVERY, CANCELLATION, RESULT_RETRIEVAL remain unverified; paid/GPU remains blocked by parked policy
remaining_blockers: T3-T7; local admission is not yet persisted or revalidated on submit/worker; inspect current ChatGPT workspace availability and deployed Gateway/OAuth/DB/worker configuration before real acceptance; main protection is disabled; PostgreSQL migration has not been exercised
next_task: finish T3 policy-bound local plan persistence, idempotency, worker revalidation and revocation tests before T4 container work
```

Update this record only with observed implementation and validation evidence. Do not describe mock/provider tests as real integration acceptance.
