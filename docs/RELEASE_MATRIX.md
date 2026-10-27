# Release acceptance matrix

This matrix reports evidence on the current working branch. It does not infer
readiness from mocks, source inspection, or a green test suite alone.

| Axis | Status | Current evidence | Remaining acceptance |
| --- | --- | --- | --- |
| `MCP_CONNECTIVITY` | UNCERTAIN | Gateway protocol and OAuth flows have automated tests; no deployed HTTPS endpoint has been connected from ChatGPT. | Deploy a supported endpoint, complete real OAuth and tool discovery/calls in the intended ChatGPT account. |
| `CHATGPT_TOOL_USABILITY` | UNCERTAIN | Canonical experiment tools implement prepare/submit/status/result/artifact/cancel/list contracts and have service-level tests. | Complete a real CPU run through ChatGPT without CLI/Issue interaction, including a second conversation. |
| `CPU_EXECUTION` | PASS (local lane only) | Digest-pinned CPU container ran on OrbStack Linux/arm64 with bounded runtime, isolation settings, result binding, and cleanup. See `docs/acceptance/2026-10-28-recovery-supervisor.md` and `docs/IMPLEMENTATION_PROGRESS.md`. | Repeat on the selected persistent deployment host and workload; current evidence is local and not seven-day operational acceptance. |
| `FREE_GPU_EXECUTION` | BLOCKED | No GPU backend has been live-verified with device, quota, additional-cost, cancellation, and cleanup evidence. | Verify an eligible provider/account and run a bounded real GPU smoke with cost and cleanup proof; preserve `FREE_FIRST` gates. |
| `PAID_GPU_EXECUTION` | BLOCKED | Paid mode remains parked; no current exact human authorization or live provider execution. | Complete P5 controls and obtain separate explicit authorization for a bounded canary before any spend. |
| `RECOVERY` | PASS (local CPU lane only) | Real Docker recovery reconciled the same run after execution-worker exit before handle persistence. PostgreSQL restart and supervisor restart during `cleanup_pending` are covered. The latter process-exit boundary uses a fake backend. Timeout-cancellation intent is retained through a cleanup failure. See acceptance record. | Exercise the selected deployed host and provider; verify the full crash matrix and no duplicate resources there. |
| `CANCELLATION` | PASS (local CPU lane only) | Existing CPU container was cancelled and removed by the recovery supervisor while execution-worker ticks were stopped. | Repeat against the deployment host and, for GPU, its real provider resource. |
| `RESULT_RETRIEVAL` | UNCERTAIN | A real digest-pinned local CPU smoke run emits a validated JSON report; worker recovery persists it to owner-scoped storage and retrieves its exact bytes. PostgreSQL outage recovery preserves the run; artifact chunk API/storage tests and local shared-volume checks pass. No deployed API or real ChatGPT conversation was used. | Verify an actual run and exact plan/source binding from a second ChatGPT conversation, including returned artifact digest and bytes; test a deployed persistent volume and set a quota/alert policy. See `docs/acceptance/2026-10-28-artifact-storage.md`. |
| `SECURITY` | UNCERTAIN | Input contracts, owner scoping, local CPU admission, Docker hardening, and targeted adversarial/recovery tests exist. | Complete independent provider-independent review, deployed OAuth/owner-boundary acceptance, target-host permissions review, and operational security checks. This is scoped evidence, not a claim of complete safety. |

## Operational gates

- P2 recovery work remains in progress: durable owner-scoped artifact storage
  and local CPU report retrieval are implemented and locally exercised;
  provider-independent recovery review, deployed storage/quota controls, and
  ChatGPT retrieval acceptance remain incomplete. Unsupported artifacts must
  not be represented as retrievable.
- P3 remains pending: systemd units are templates only; there is no selected
  deployed Gateway/worker host, real ChatGPT connection, seven-day observation,
  or timed production restore drill.
- Paid and GPU paths stay parked until their separate evidence and authorization
  gates are satisfied. Local CPU evidence does not satisfy either gate.

Update this table only when new evidence is produced. Link acceptance artifacts
and state the scope of each PASS.
