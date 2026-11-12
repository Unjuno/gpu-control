# Project status

## Hosted Sites and provider status — refreshed 2026-11-12

Latest refresh — 2026-11-12 12:35 UTC: the public ChatGPT Sites MCP Worker is
deployed as Version 27 from Site source commit
`64d2646815be198b0173877b821264cf3efc10a6`, with production environment
revision 27 and D1/R2. Current ChatGPT capabilities report
`provider_ready=true`, all provider identity/health checks true,
`admission_enabled=false`, and `available=false` for `modal_cpu`. Paid
execution remains parked. The owner's ChatGPT connection has called the Site;
cross-account plugin access remains unverified.

The latest 16-token ChatGPT-initiated Modal Sandbox run
`b3380814d0854d93a5d978799d670013` failed with exit code 2; cleanup was
confirmed and no artifact was produced. Modal Usage last showed a `$1`
Workspace limit, `$0.04` credits used, and `$0` charges. Commit `d1dd4fe`
pushed to `codex/sites-modal-runner` adds a bounded preflight line diagnostic,
but it has not been deployed. The previous one-run authorization is consumed;
keep admission disabled until a fresh authorization, diagnostic deployment,
and one bounded run are completed.

The Modal dashboard's deployment timeline showed v4 at 2026-11-12 18:06 JST,
but its history row did not identify a source commit. The successful ChatGPT
run `eacc26ff2ad54cf69a1ee7665325b197` generated four tokens in 142 ms and its
complete R2 artifact was verified, but the run was performed by the local
Runner under Sites Version 16; it is not Modal evidence. Two Modal runs
(`96d7efef9542463d9fc51f47ffbfd5d7` and
`599473dcc1ed4034a42d849bcb42e261`) failed with cleanup confirmed before v4.
No successful inference after v4 is recorded. Site Version 24 now stores a
bounded Modal exit-code failure code without provider stderr, but no live run
has tested that diagnostic. A fresh ChatGPT capability read reports provider
health ready, admission disabled, and unavailable. Modal's account page
previously showed `$0.01` usage this cycle. The temporary deploy token was
deleted; Modal's API-token page showed zero tokens. The Sites Worker has no
RunPod route; live RunPod and paid GPU execution remain parked.

The personal-host CPU Runner and its Keychain authentication path are retired.
Do not restore them. Older TinyStories successes remain historical evidence;
they do not establish current Modal execution success.

Before retirement, a ChatGPT-originated TinyStories 15M inference completed on
Sites Version 15 after a Runner process-loss recovery test.
Run `aa45b7d899de4c9aaff2ee73fa985cc6` used the registered workload source commit
`3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288` and image
`sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
With prompt `A little bird found a bright blue feather.`, seed `719243`, and an
8-token limit, it generated 8 tokens in 291 ms, passed identity/sandbox checks,
returned `gpu_used=false`, and confirmed cleanup at `$0.00`. Its complete
999-byte R2 artifact was retrieved through ChatGPT; its locally computed
SHA-256 matches D1 metadata. A separate active-run process-loss probe expired
after 180 seconds and recovered as `runner_lost_recovered` with cleanup
confirmed, no retry, and no leftover container. A follow-up inference proved
the free CPU slot was available again.

This does not establish general model quality, repeated crash-window coverage,
cross-owner isolation, or GPU capability. The local Runner result is historical;
the two Modal failures predate v4, and there is no accepted post-v4 inference.
Modal recovery and real RunPod GPU acceptance remain open. Full evidence and gates are tracked in
[`decisions/2026-11-11-sites-d1-architecture-pivot.md`](decisions/2026-11-11-sites-d1-architecture-pivot.md).
The current staged plan is [`SITES_MODAL_RUNPOD_DELIVERY.md`](SITES_MODAL_RUNPOD_DELIVERY.md).
Run evidence: [`Modal and CPU inference chronology`](acceptance/2026-11-12-modal-and-cpu-inference-chronology.md).

The rest of this document records standalone CLI and provider-adapter status on
`main`; it does not supersede the hosted Sites acceptance snapshot above.

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
| Current RunPod REST v2 transport layer | Ready offline | Fixed `api.runpod.io/v2` client, cursor-paginated List Pods with bounded complete inventory, v2 create/get/delete, trusted Network Volume attachment, and response identity checks are mock-tested. |
| Current RunPod pricing/availability evidence | Ready offline | Fixed REST v2 GPU catalog, secure price/capacity, VRAM, exact Network Volume datacenter, HIGH stock, 300-second maximum TTL, and content-digest binding are mock-tested. |
| RunPod REST v2 provider adapter | Ready offline for selected canary | Canonical v2 adapter requires current pricing evidence, exact Network Volume DC, unexpired live permit, and v2-backed occupancy/reconciliation before create. |
| RunPod ambiguous create/cleanup reconciliation | Ready offline on REST v2 transport | Bounded occupancy/reconciliation consumes every cursor page and remains fail-closed. Provider behavior and cleanup remain unverified live. REST v1 is retained for offline compatibility only and is forbidden for live calls. |
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

The source CI, root/non-root signer isolation, v3 signed exit-code envelope, current REST v2 adapter contract, current v2 price/DC-stock contract, and central offline volume-transport tests are green. That does **not** mean the control plane is authorized to spend money today.

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

- current GPU price and VRAM come from the fixed-origin REST v2 GPU catalog;
- exact per-datacenter stock is checked for the Network Volume datacenter;
- current price/DC evidence is short-lived and content-digest bound;
- the approved plan carries the exact price/reference/time window;
- `RunPodV2CurrentAdapter` rechecks that evidence and the Network Volume DC immediately before submission;
- current REST v2 creates the Pod and cursor-paginated v2 List Pods backs account occupancy/reconciliation;
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

The 2026-10-31 GitHub API audit confirms `main` is protected with the seven
required Actions checks, one approval including approval after the last push,
strict/up-to-date checks, conversation resolution, linear history, and admin
enforcement. This satisfies the branch-protection prerequisite only; P1 PR #52
still awaits its independent approval. The same audit found no Environment
protection rules or deployment-branch policy on `Production` or `Preview`, and
no dedicated `paid-runpod` Environment. Do not treat repository access, a
successful dry-run, or available budget as authorization to spend money.

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
