# Release acceptance matrix

Evidence snapshot: 2026-11-02 on branch
`codex/pr58-cpu-vertical-reconcile-20261102`, based on PR #58 head
`90bd6d8c84e319365d66951ca96c7ccceff40998`. Candidate commit
`1cb8d025a1f454b14b59004ea55871a71ba69fad` passed GitHub CI on draft PR #66:
Gateway offline and comment bridge, Project bridge, Python 3.11/3.12/3.13,
trusted reference container, and Vercel Preview checks. The Preview is not a
Gateway runtime deployment; no GitHub approval or production acceptance has
been recorded. This matrix does not infer readiness from mocks, source
inspection, or a green test suite alone.

| Axis | Status | Current evidence | Remaining acceptance |
| --- | --- | --- | --- |
| `MCP_CONNECTIVITY` | UNCERTAIN | Read-only probe on 2026-11-02: production alias `/healthz` 200 (`configured=true`, `auth_configured=true`, `auth_mode=local_oauth`, health check did not start GPU); `/readyz` 404; anonymous `/mcp` 401; OAuth discovery endpoints 200 and advertise PKCE S256, authorization-code/refresh grants, `offline_access`, and read/run/cancel scopes. These responses do not identify the deployed revision or prove a ChatGPT OAuth flow. Local official MCP SDK interop is recorded in `docs/acceptance/2026-10-31-mcp-sdk-interop.md`. | Deploy the reviewed CPU vertical with persistent worker/database/artifact storage, expose and verify readiness, then complete real OAuth, tool discovery and calls in the intended ChatGPT account. |
| `CHATGPT_TOOL_USABILITY` | UNCERTAIN | Canonical experiment tools implement prepare/submit/status/result/artifact/cancel/list contracts and have service-level tests. | Complete a real CPU run through ChatGPT without CLI/Issue interaction, including a second conversation; record it in [`docs/CHATGPT_ACCEPTANCE.md`](CHATGPT_ACCEPTANCE.md). |
| `CPU_EXECUTION` | PASS (local lane only) | On 2026-11-02, real Docker/OrbStack CPU backend, worker-crash recovery, authenticated local MCP HTTP path and PostgreSQL outage recovery all passed using a digest-pinned CPU image; four focused integration tests and the complete Gateway suite passed. See `docs/acceptance/2026-11-02-p1-cpu-docker-recovery-revalidation.md`. Image source labels are operator metadata, not signed supply-chain attestations. | Repeat on the selected persistent deployment host and reviewed workload; current evidence is local and not seven-day operational acceptance. |
| `FREE_GPU_EXECUTION` | BLOCKED | No GPU backend has been live-verified with device, quota, additional-cost, cancellation, and cleanup evidence. | Verify an eligible provider/account and run a bounded real GPU smoke with cost and cleanup proof; preserve `FREE_FIRST` gates. |
| `PAID_GPU_EXECUTION` | BLOCKED | Paid mode remains parked; no current exact human authorization or live provider execution. | Complete P5 controls and obtain separate explicit authorization for a bounded canary before any spend. |
| `RECOVERY` | PASS (local CPU lane only) | Real Docker recovery reconciled the same run after worker exit before handle persistence. PostgreSQL outage retained the run slot and container, then recovered the same run after restart. On 2026-11-02, a current schema-v9 PostgreSQL 16 DB/artifact backup generation was verified and restored into a separate database; OAuth grant/revocation state and artifact bytes were checked, and the SECURITY DEFINER owner/ACL were reapplied. See `docs/acceptance/2026-11-02-p1-cpu-docker-recovery-revalidation.md` and `docs/acceptance/2026-11-02-p3-restore-definer-owner.md`. The restore drill used an injected stopped-service attestation; it is not target-host evidence. | Exercise the selected deployed host and provider; verify the full crash matrix and no duplicate resources there. Production backup retention, target-host recovery, second-operator reproduction and measured RPO/RTO remain open. |
| `CANCELLATION` | PASS (local CPU lane only) | Existing CPU container was cancelled and removed by the recovery supervisor while execution-worker ticks were stopped. | Repeat against the deployment host and, for GPU, its real provider resource. |
| `RESULT_RETRIEVAL` | UNCERTAIN | A real digest-pinned local CPU run emits a validated result and owner-scoped artifact; local MCP test clients retrieve it through the authenticated HTTP path. PostgreSQL outage recovery preserves the same run. Current schema-v9 paired restore recovered synthetic run/OAuth/artifact state. No deployed API or real ChatGPT conversation was used. | Verify an actual run and exact plan/source binding from a second ChatGPT conversation, including returned artifact digest and bytes; test a deployed persistent volume and set a quota/alert policy. See the 2026-11-02 P1 acceptance records. |
| `SECURITY` | UNCERTAIN | Candidate adds separate API/worker/migration PostgreSQL roles, column-scoped Worker updates, a lease-checked slot-release function, and restore ownership repair for that SECURITY DEFINER function. PostgreSQL ACL and no-owner restore regressions pass; the full Gateway suite is 365 passed, 1 skipped. An independent source review of the current staged and unstaged changes found no actionable security issues. It does not verify live deployment, host permissions, OAuth setup, or provider behavior. | Complete deployed OAuth/owner-boundary and target-host permissions review, and verify live provider compatibility only when separately authorized. This is scoped evidence, not a claim of complete safety. |

## Operational gates

- P2 recovery work is locally exercised on Docker and PostgreSQL 16, including
  worker crash, cancellation, DB outage, schema-v9 paired restore, and runtime
  ACL reapplication. Provider-independent recovery review, deployed
  storage/quota/alert controls, and ChatGPT retrieval remain incomplete.
  Unsupported artifacts must not be represented as retrievable.
- P3 remains pending: systemd units are templates only; there is no selected
  deployed Gateway/worker host, real ChatGPT connection, seven-day observation,
  or target-host timed restore drill. The 2026-11-02 paired restore exercises
  current schema-v9 data, OAuth grant state, artifact bytes, and restored DB
  function ownership locally; the service-stop attestation was injected, and
  the source/restore databases shared a disposable PostgreSQL cluster.
  Encrypted off-host retention, second-operator restore, worker/resource
  reconciliation, and measured RPO/RTO remain required. Recheck hosted database
  state and migration plan before any live database mutation.
- Paid and GPU paths stay parked until their separate evidence and authorization
  gates are satisfied. Local CPU evidence does not satisfy either gate.

Update this table only when new evidence is produced. Link acceptance artifacts
and state the scope of each PASS.
