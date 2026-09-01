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
| Structured exact human authorization | Ready for RunPod adapter boundary | Runtime validator and expiring `LiveExecutionPermit` exist; RunPod adapter construction/submission requires the exact unexpired permit. End-to-end paid workflow wiring remains absent. |
| Current RunPod REST v1 transport layer | Ready offline | Fixed `rest.runpod.io/v1` client, current create field names, List Pods array normalization, `desiredStatus`, `costPerHr`, machine cloud evidence, Network Volume identity, GET, and DELETE 204 are mock-tested. |
| Current RunPod pricing/availability evidence | Ready offline | Fixed GraphQL origin and Bearer auth, `securePrice`, VRAM, exact Network Volume datacenter, HIGH stock, 300-second maximum TTL, and content-digest binding are mock-tested. |
| RunPod REST v1 provider adapter | Ready offline for selected canary | Canonical adapter requires current pricing evidence, exact Network Volume DC, unexpired live permit, and v1-backed occupancy/reconciliation before create. |
| RunPod ambiguous create/cleanup reconciliation | Ready offline on current v1 transport | Bounded occupancy/reconciliation logic consumes the v1-normalized account inventory and remains fail-closed. Live verification is still pending. |
| Authenticated Orbitune completion v3 | Ready offline | Root signer binds exact result bytes and the observed process exit code into HMAC-SHA256 evidence; legacy v2 remains only during migration. |
| RunPod Network Volume/S3 result transport | Ready offline | Fixed RunPod S3 origin, trusted `/outputs` mount, exact two-object bounded collection, and v3 authentication are mock-tested. Live verification and real credentials/volume are pending. |
| Orbitune paid-canary result acceptance | Ready offline | Workload-specific acceptance accepts authenticated log-v2 or durable volume-v3 evidence and remains separate from provider cleanup/finalization. |
| Pre-cleanup result capture/finalization | Ready offline | Provider-neutral ephemeral-result capture is durable and bounded. |
| Production Pod-log SSE | Unavailable | Current RunPod evidence records the Pod-log SSE operation as dev-only/unavailable in production; it is not used as the live result path. |
| Paid GitHub Actions workflow | Not present yet | `main` contains CI and dry-run workflows only. It must not be added/enabled until external GitHub gates and initial live provider verification are complete. |
| Live paid GPU execution | Disabled | Repository state is `parked`; paid/provider/result live flags remain off. |

## Current selected canary

The repository currently records this canary workload:

- repository: `Unjuno/orbitune`
- source SHA: `fc131174a9b529a9825f54fccf1a7df4c63c9a1a`
- Dockerfile: `workloads/runpod-training-canary/Dockerfile`
- workload id: `orbitune-runpod-training-canary-v1`
- GPU profile: `cheap-24gb`
- maximum runtime: 30 minutes
- maximum cost ceiling: USD 0.30
- completion protocol: `gpu-control-hmac-sha256-v3`
- exact-main full pytest run: `33313993621` — passed
- exact-main RunPod canary smoke run: `33313993623` — passed

The source CI, root/non-root signer isolation, v3 signed exit-code envelope, current REST v1 adapter contract, current price/DC-stock contract, and central offline volume-transport tests are green. That does **not** mean the control plane is authorized to spend money today.

## Durable result transport

The old production-result blocker was the absence of a supported Pod-log API. That specific blocker now has a provider-supported alternative design:

1. a pre-existing RunPod Network Volume is mounted at trusted path `/outputs` when the Pod is created;
2. the workload writes `result.json` and root-signed `completion-v3.json` there;
3. the Pod may exit and be cleaned up without destroying the Network Volume;
4. the control plane reads exactly those two bounded objects through RunPod's S3-compatible API;
5. `completion-v3.json` authenticates the exact result digest **and the root wrapper-observed process exit code**;
6. only then may an otherwise ambiguous exited workload become `SUCCEEDED` or `FAILED`.

This transport is implemented and mock-tested, but not yet live-verified. Network Volume creation/resizing is deliberately not automated because it is a persistent billable resource.

## Provider-control and pricing path

The selected RunPod path is now complete at offline/mock level from price selection through result collection:

- current GPU price and VRAM come from a fixed-origin Bearer-authenticated GraphQL query;
- exact per-datacenter stock is checked for the Network Volume datacenter;
- current price/DC evidence is short-lived and content-digest bound;
- the approved plan carries the exact price/reference/time window;
- `RunPodV1Adapter` rechecks that evidence and the Network Volume DC immediately before submission;
- current REST v1 creates the Pod and v1 List Pods backs account occupancy/reconciliation;
- durable Network Volume/S3 result collection authenticates completion v3 after exit;
- cleanup remains explicit and reconciliation-backed.

No live provider call is enabled by these implementations. The remaining provider work is **live verification with real account evidence**, not another speculative API model.

## Why live paid execution is still disabled

`policies/repository-state.yaml` remains the source of truth. Important remaining activation requirements include:

- protected `gpu-control/main` with required CI checks;
- control-plane context integrity and prompt/context gates;
- an owner-only protected `paid-runpod` Environment;
- Environment-scoped `RUNPOD_API_KEY` plus separate RunPod S3 credentials;
- a pre-existing Network Volume in a supported S3 datacenter;
- immutable published canary-image identity;
- live read-only verification of current pricing, exact-datacenter stock, and account occupancy;
- live verification of ambiguous-create, result collection, and cleanup reconciliation;
- protected paid-workflow wiring that constructs the exact current `LiveExecutionPermit` from trusted runtime evidence.

The public repository currently reports `main` as unprotected. Do not treat repository access, a successful dry-run, or available budget as authorization to spend money.

## What "ready" means here

A feature marked **Ready** is usable from `main` for the stated offline/read-only purpose. It does not imply that a downstream live provider action is enabled.

**Offline/mock only** means executable code and tests exist but no real provider credential or billable action was used to verify it.

**Live disabled** means policy intentionally prevents provider calls even if local code could otherwise construct them.

## Source of truth

When documentation and machine state differ, prefer:

1. `policies/repository-state.yaml` for current activation state;
2. `policies/paid-execution-policy.yaml` for paid-path identity/security requirements;
3. `policies/runpod-rest-v1-policy.yaml` for the current Pod-control and pricing contract;
4. `policies/runpod-v2-policy.yaml` for legacy compatibility state and durable-result constraints;
5. tests and current `main` implementation for executable behavior.
