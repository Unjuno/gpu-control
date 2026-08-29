# Project status

This document describes what `gpu-control` on `main` can do today. It deliberately distinguishes implemented offline/control-plane contracts from live paid GPU execution.

## Readiness summary

| Capability | Status | Notes |
| --- | --- | --- |
| Installable standalone CLI | Ready | Python 3.11+, locked dependencies, offline self-test. |
| Request/resource-policy validation | Ready | `gpu-control validate`; no network or GPU required. |
| Public GitHub source verification | Ready | `gpu-control verify-source`; verifies public repository, exact 40-character SHA, and Dockerfile path. |
| Synthetic provider contract self-test | Ready | `gpu-control provider-self-test`; no network or billing. |
| Trusted repository-owned container isolation fixture | Ready | CI exercises a bounded, secret-free reference container. |
| Generic external workload container execution | Not enabled | External Dockerfiles are not generally executed by this repository yet. |
| Decision/context security policy | Ready at policy/CI level | Action constitution, source-to-sink trust policy, failure catalog, and adversarial fixtures are present. |
| Approved execution plan contracts | Ready offline | Immutable/fingerprinted plans, pricing evidence, durable lifecycle state, cleanup state, and bounded result manifests are implemented. |
| Structured exact human authorization | Partial | Schema/policy exists; complete live runtime binding is still an activation prerequisite. |
| RunPod REST v2 control-plane contract | Offline/mock only | Provider-facing contracts are tested without credentials or live paid calls. |
| Authenticated Orbitune completion parsing | Ready offline | Bounded completion/result markers are authenticated and validated offline. |
| Orbitune paid-canary result acceptance | Ready offline | Workload-specific result acceptance is separate from provider-finalized success. |
| Pre-cleanup result capture/finalization | Ready offline | Provider-neutral ephemeral-result capture is durable and bounded. |
| Production RunPod completion transport | Blocked | No production-supported authenticated collection transport is currently verified for the selected canary path; production Pod-log SSE is recorded as unavailable. |
| Paid GitHub Actions workflow | Not present | `main` contains CI and dry-run workflows only. |
| Live paid GPU execution | Disabled | Repository state is `parked`; paid/provider live flags remain off. |

## Current selected canary

The repository currently records this canary workload:

- repository: `Unjuno/orbitune`
- source SHA: `38594057d1b118a7acf6c843e39d7d8a25571316`
- Dockerfile: `workloads/runpod-training-canary/Dockerfile`
- workload id: `orbitune-runpod-training-canary-v1`
- GPU profile: `cheap-24gb`
- maximum runtime: 30 minutes
- maximum cost ceiling: USD 0.30
- completion protocol: `gpu-control-hmac-sha256-v2`

Its source CI and authenticated completion contract are green. That does **not** mean the control plane is authorized or able to start a paid RunPod execution today.

## Why live paid execution is still disabled

`policies/repository-state.yaml` is the source of truth. Important remaining activation requirements include:

- protected `main` with required CI checks;
- control-plane context integrity and prompt/context gates;
- an owner-only protected paid environment and environment-scoped provider credential;
- structured DecisionRecord and exact human-authorization binding to the live plan;
- immutable published-image identity;
- current provider API revalidation;
- live account-occupancy evidence and ambiguous-create reconciliation;
- a production-supported authenticated completion/result transport;
- verified live completion-secret injection and result collection;
- idempotent/reliable cleanup.

The public repository currently reports `main` as unprotected. Do not treat repository access or a successful dry-run as authorization to spend money.

## What "ready" means here

A feature marked **Ready** is usable from `main` for the stated offline/read-only purpose. It does not imply that a downstream live provider action is enabled.

A feature marked **Partial** has meaningful implementation or policy support but still lacks one or more runtime/live bindings.

A feature marked **Blocked** depends on an external or provider capability that has not been verified as available for the intended production path.

## Source of truth

When documentation and machine state differ, prefer:

1. `policies/repository-state.yaml` for current activation state;
2. `policies/paid-execution-policy.yaml` for paid-path identity/security requirements;
3. `policies/runpod-v2-policy.yaml` for provider-specific constraints;
4. tests and current `main` implementation for executable behavior.
