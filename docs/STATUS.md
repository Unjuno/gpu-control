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
| RunPod Pod-control transport | Migration required | The checked-in client still implements the older public REST v2 beta shape at `api.runpod.io/v2`. Current official stable Pod REST is v1 at `rest.runpod.io/v1`; live use is forbidden until the client/adapter and tests are migrated and revalidated. |
| RunPod ambiguous create/cleanup reconciliation | Ready offline on legacy contract | Fresh bounded Pod inventory can reconcile one exact execution identity and prove cleanup absence/termination. It must be adapted to the current v1 List Pods array shape before live use. |
| Authenticated Orbitune completion v3 | Ready offline | Root signer binds exact result bytes and the observed process exit code into HMAC-SHA256 evidence; legacy v2 remains only during migration. |
| RunPod Network Volume/S3 result transport | Ready offline | Fixed RunPod S3 origin, trusted `/outputs` mount, exact two-object bounded collection, and v3 authentication are mock-tested. Live verification and real credentials/volume are pending. |
| Orbitune paid-canary result acceptance | Ready offline | Workload-specific acceptance accepts authenticated log-v2 or durable volume-v3 evidence and remains separate from provider cleanup/finalization. |
| Pre-cleanup result capture/finalization | Ready offline | Provider-neutral ephemeral-result capture is durable and bounded. |
| Production Pod-log SSE | Unavailable | Current RunPod evidence records the Pod-log SSE operation as dev-only/unavailable in production; it is not used as the live result path. |
| Paid GitHub Actions workflow | Not present yet | `main` contains CI and dry-run workflows only. It must not be added/enabled until the provider-control migration and external GitHub gates are complete. |
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

The source CI, root/non-root signer isolation, v3 signed exit-code envelope, and central offline volume-transport tests are green. That does **not** mean the control plane is authorized to spend money today.

## Durable result transport

The old production-result blocker was the absence of a supported Pod-log API. That specific blocker now has a provider-supported alternative design:

1. a pre-existing RunPod Network Volume is mounted at trusted path `/outputs` when the Pod is created;
2. the workload writes `result.json` and root-signed `completion-v3.json` there;
3. the Pod may exit and be cleaned up without destroying the Network Volume;
4. the control plane reads exactly those two bounded objects through RunPod's S3-compatible API;
5. `completion-v3.json` authenticates the exact result digest **and the root wrapper-observed process exit code**;
6. only then may an otherwise ambiguous exited workload become `SUCCEEDED` or `FAILED`.

This transport is implemented and mock-tested, but not yet live-verified. Network Volume creation/resizing is deliberately not automated because it is a persistent billable resource.

## Provider-control migration blocker

The durable result transport and the Pod-control API are separate contracts. The result transport can be developed offline while Pod control remains disabled.

The checked-in provider client currently targets the older public REST v2 beta origin `https://api.runpod.io/v2`. The current official stable Pod REST contract is v1 at `https://rest.runpod.io/v1`. The current v1 contract differs materially from the implementation, including request/response field names and the List Pods response shape.

Therefore:

- the existing v2 client is an offline compatibility implementation, not the current live contract;
- policy explicitly records `implementation_matches_current_official_rest_contract: false`;
- live enablement while the adapter still targets legacy v2 beta is forbidden;
- the next provider-control implementation step is migration to current REST v1 with offline/mock tests;
- pricing/catalog must also be revalidated against current supported APIs before live use.

## Why live paid execution is still disabled

`policies/repository-state.yaml` remains the source of truth. Important remaining activation requirements include:

- protected `gpu-control/main` with required CI checks;
- control-plane context integrity and prompt/context gates;
- an owner-only protected `paid-runpod` Environment;
- Environment-scoped `RUNPOD_API_KEY` plus separate RunPod S3 credentials;
- a pre-existing Network Volume in a supported S3 datacenter;
- immutable published canary-image identity;
- migration/revalidation of Pod control to the current official RunPod REST v1 contract;
- current provider pricing/catalog revalidation and live account-occupancy verification;
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
3. `policies/runpod-v2-policy.yaml` for the legacy implementation contract plus current-provider migration blockers;
4. tests and current `main` implementation for executable behavior.
