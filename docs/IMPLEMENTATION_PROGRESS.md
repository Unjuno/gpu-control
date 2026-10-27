# Implementation progress

```text
current_phase: P0 baseline audit complete; P1 T1-T2 data contract and canonical MCP surface complete
current_task: T3 free-first CPU admission policy; prepare remains blocked until policy/backend implementation
base_sha: 24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e
working_branch: codex/chatgpt-cpu-vertical
implemented: plan/spec copied into repository; PR #43 disposition audited; README canary SHA and completion version reconciled to repository policy; core pytest upgraded from vulnerable 8.4.2 to locked 9.1.1; additive Gateway v2 Plan/Result contracts and explicit idempotent v1-to-v2 migration added; seven canonical MCP tools advertised while six legacy names remain callable; canonical owner-scoped envelopes, source/device checks, exact-fingerprint submit, bounded filtered listing with owner-bound cursor, pending/simulation result handling added; compatibility period documented
tests_and_commands: `uv sync --locked --extra dev && uv run pytest -o addopts='' -q` (452 passed, 1 skipped); `gateway/.venv/bin/python -m pytest -o addopts='' -q` from `gateway/` (166 passed, 3 skipped); Gateway v2 contract/migration subset (13 passed); `gateway/.venv/bin/python -m unittest discover -s gateway/project_control/tests -v` (19 passed); `git diff --check` passed. Migration tested on SQLite; dedicated PostgreSQL test was skipped because no test DB URL was configured.
real_execution_evidence: no Gateway deployment, real container, provider, or ChatGPT call executed; CPU owner-comment path unit tests passed but are not real ChatGPT/MCP acceptance
release_matrix_changes: MCP_CONNECTIVITY, CHATGPT_TOOL_USABILITY, CPU_EXECUTION, RECOVERY, CANCELLATION, RESULT_RETRIEVAL remain unverified; paid/GPU remains blocked by parked policy
remaining_blockers: T3-T7; inspect current ChatGPT workspace availability and deployed Gateway/OAuth/DB/worker configuration before real acceptance; main protection is disabled; PostgreSQL migration has not been exercised
next_task: implement local_cpu-only free_first admission, idempotency, policy digest and expiry; continue rejecting GPU and paid providers
```

Update this record only with observed implementation and validation evidence. Do not describe mock/provider tests as real integration acceptance.
