# Current worktree security review — 2026-10-31

## Scope

- Repository: `Unjuno/gpu-control`
- Base and target revision: `a794438f42bd7246f463eaaa40d963af0aae9d13`
- Target: frozen uncommitted working tree
- Snapshot digest: `codex-security-snapshot/v1:sha256:4a92afc39317e7d2fe18724ffa27fccffb92cab622f642546058c6f870957936`
- Codex Security scan: `59df3764-a62a-4b0b-96d6-46278862151c`
- Coverage: all 18 changed source and policy review items; complete coverage, no deferred rows.

## Result

The completed scan recorded zero candidate findings across seven reviewed
surfaces: backup and artifact integrity; API authentication, admission and
OAuth; backend/configuration boundaries; paid/credit verifier bridges; schema
and account-scope logic; registry/service/store/worker lifecycle; and paid
execution/repository policy. Candidate validation and attack-path analysis had
zero items because discovery produced no candidates.

The source review confirmed that paid and credit verifier modules still have
no Gateway call site and RunPod paid/credit work still fails closed. Schema v12
and the Store persistence methods are not a complete paid execution path.

## Limits

This is a static review of the frozen worktree digest only. It did not exercise
the application, deployment, external GitHub settings, ChatGPT OAuth, a provider,
GPU allocation, billing, or cleanup. Zero findings does not establish product
readiness or replace independent GitHub review. Issuer/revocation integration,
P1 ChatGPT acceptance, P3 target-host acceptance, and live P4/P5 acceptance
remain open. Keep `mode: parked` and all spending gates closed.

Canonical report and sealed artifacts:
`/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/a794438f42bd7246f463eaaa40d963af0aae9d13_20261031T014349Z_p88ey1oc/report.md`.

## Follow-up Store read review

After strengthening paid-authorization reload, a second Codex Security scan
(`95ba8a1a-f608-4f28-9b71-aaf5f97f5e9f`) covered 18 changed source/policy
items at digest
`codex-security-snapshot/v1:sha256:67e0f386a5b1c494a3e37f30293c98f1b7b2253643f126ed914c398ea948430a`.
It completed with zero candidates and complete coverage. Its report is at:
`/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control/a794438f42bd7246f463eaaa40d963af0aae9d13_20261031T015307Z_70squbdn/report.md`.

A focused independent review then examined the small follow-up that allows the
Worker's `submitting` state and rejects cancellation already committed before
the authorization read. It confirmed the remaining time-of-check/time-of-use
window: cancellation can still commit after the read returns and before a later
provider call. The reader is not wired to Worker, so no currently reachable
paid execution path was found. Worker integration must handle the race and
post-acceptance cleanup before it can be used as an execution gate. The focused
Store suite passed **5/5** after this delta. No live authorization or provider
call occurred; paid execution remains parked.
