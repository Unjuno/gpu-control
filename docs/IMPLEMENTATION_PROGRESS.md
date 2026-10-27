# Implementation progress

```text
current_phase: P0 baseline audit complete; P1 T1-T4 implementation complete; T5 recovery/cancel/cleanup acceptance in progress
current_task: persist execution intent and make worker restart, cancellation, result-before-cleanup, and cleanup failure safe
base_sha: 24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e
working_branch: codex/chatgpt-cpu-vertical
implemented: plan/spec copied into repository; PR #43 disposition audited; README canary SHA and completion version reconciled to repository policy; core pytest upgraded from vulnerable 8.4.2 to locked 9.1.1; additive Gateway v2 Plan/Result contracts and explicit idempotent v1-to-v3 migration added; seven canonical MCP tools advertised while six legacy names remain callable; canonical owner-scoped envelopes, source/device checks, exact-fingerprint submit, bounded filtered listing with owner-bound cursor, pending/simulation result handling added; compatibility period documented; T3 added fail-closed local CPU admission, disabled-by-default policy, immutable image digest and smoke profile constraints, separate durable local-policy authorization, prepare/submit/worker policy and fingerprint validation, and revocation-before-start behavior; T4 added digest-pinned CPU smoke image, detached local Docker backend with runtime hardening, strict bounded result validation, label-bound reconciliation, cancellation, and trusted supervisor deadline enforcement
tests_and_commands: `uv sync --locked --extra dev && uv run pytest -o addopts='' -q` (452 passed, 1 skipped); Gateway suite: 189 passed, 4 skipped; Docker integration with image `sha256:7127dd8799c41c5c5d90001242bb90aefebbb957f578ff95a835cf5651402798`: 1 passed, including normal CPU result, supervisor timeout, runtime inspection, reconciliation, and cleanup; project_control suite: 19 passed. PostgreSQL test remains skipped because no test DB URL was configured.
real_execution_evidence: local OrbStack Docker CPU container ran on linux/arm64; verified non-root UID, network none, read-only root, dropped capabilities, PID/CPU/memory limits, no mounts, source/fingerprint binding, simulation=false, gpu_used=false, deterministic checks/checksum, timeout exit 124, and container removal. No deployed Gateway, provider, or real ChatGPT/MCP call executed.
release_matrix_changes: CPU_EXECUTION has isolated local-container evidence only; MCP_CONNECTIVITY, CHATGPT_TOOL_USABILITY, RECOVERY, CANCELLATION, RESULT_RETRIEVAL remain unverified; paid/GPU remains blocked by parked policy
remaining_blockers: T5-T7; no real ChatGPT/MCP acceptance has run; policy defaults disabled; inspect ChatGPT workspace availability and deployed Gateway/OAuth/DB/worker configuration before real acceptance; PostgreSQL migration has not been exercised
next_task: implement T5 crash recovery, cancellation, result persistence before cleanup, cleanup-failure slot retention, and worker restart acceptance
```

Update this record only with observed implementation and validation evidence. Do not describe mock/provider tests as real integration acceptance.
