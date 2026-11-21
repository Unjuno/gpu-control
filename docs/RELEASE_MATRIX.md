# Current release matrix — ChatGPT Sites + D1

Live state last refreshed 2026-11-21. The product path has exactly four compute
providers: Modal, RunPod, Kaggle and Hugging Face. Railway, Vercel, Neon, an
external PostgreSQL database and a separately hosted Gateway are not runtime
dependencies.

Passing tests or publishing a Site proves only that layer. Provider acceptance
requires an owner-confirmed real run, terminal result validation and cleanup.

| Gate | Current state | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | DEPLOYED | Public Site v50 is active at `gpu-control-sites.unjuno.chatgpt.site`; its authenticated MCP endpoint and generated plugin are available. Site visibility does not grant execution authority. |
| Source provenance | PASS for v50 | Site source commit `7b57370c9df90bc93d76043bf170e3e5be3e7e24` was saved as version `appgver_2f9d7b00ecb08191889188d55cfc9605` and deployed as `appgdep_6b01b41efa20819191e6ef27c0e935ea`. The deployed worker keeps delegated prepared/expired plans local rather than calling a provider. |
| GitHub candidate | PASSING; DRAFT | PR #68 runtime code head `44cc450` has all eight exact-head checks successful. Focused post-fix validation passed 44 Python provider tests and 71 Sites Worker tests. It remains Draft and has no final exact-head independent security approval. |
| D1 control plane | DEPLOYED | Migrations through `0017_free_provider_policies.sql` are applied. D1 owns plans, one-use authorization, budgets, provider handles, run state and cleanup evidence. |
| R2 result artifacts | ACCEPTED FOR BOUNDED MODAL RESULTS | Prior Modal result JSON was stored and digest-verified through owner-scoped bounded reads. Retention and orphan cleanup remain operational work. |
| Owner-only execution | IMPLEMENTED; CROSS-ACCOUNT ACCEPTANCE OPEN | Every stateful tool requires Sites authentication plus `GPU_CONTROL_ALLOWED_USER_IDS`; D1 operations are owner-scoped. A genuinely separate authenticated account and later revocation still need live verification. |
| Exact-plan confirmation | ACCEPTED FOR MODAL; IMPLEMENTED FOR ADAPTER | The destructive submit contains the reviewed plan and records a short-lived one-use authorization. Kaggle/HF live acceptance remains open. |
| Modal CPU | ENABLED; ONE BOUNDED RUN ACCEPTED | Earlier ChatGPT run `245d0349…6232f` produced a digest-verified artifact and confirmed cleanup. Fresh v46 repeatability/recovery acceptance is still open. Modal account billing is an independent boundary. |
| RunPod | ENDPOINT DEPLOYED; ADMISSION CLOSED | Endpoint `wwlos460xbfw5q` is restricted to RTX 2000 Ada, one GPU, max worker 1, active workers 0, 5-second idle timeout and 30-second execution timeout. It uses the immutable image digest `sha256:0f952a…b1c49`, matching source SHA `44cc450…58a1`; after configuration the UI showed no live worker and `$0.00` billed. Sites still lacks an endpoint-scoped key, authenticated completion transport has not been accepted, and no real RunPod run is accepted. |
| Kaggle | PHONE VERIFIED; REPLACEMENT RUN BLOCKED ON ADAPTER DEPLOY | Account `UnjunoOrg` showed 30 included GPU hours and zero used before the test. Run `e3fe8dae…a337` failed closed when Kaggle did not allocate the requested L4; the workload rejected CPU fallback and cleanup was confirmed. The candidate now requests the generally available `NvidiaTeslaT4` pool (T4 x2), but that adapter change is not yet deployed. D1 keeps a separate `$0` policy with paid fallback forbidden. No live Kaggle GPU success is claimed. |
| Hugging Face artifact path | PRIVATE REPOSITORY CREATED; CONNECTION BLOCKED | Private repository `Unjuno/gpu-control-orbitune-artifacts` exists. No artifact or write/read token is configured and no private round trip is accepted. Tokens remain inside the Modal adapter boundary and are never supplied to Kaggle or ChatGPT. |
| Hugging Face ZeroGPU | PRIVATE FREE SPACE DEPLOYED; EXECUTION BLOCKED | Private Space `Unjuno/gpu-control-orbitune-zero-gpu` is `Running on ZERO` at immutable revision `2e9df7d…a85ab`; the recomputed contract digest is pinned. It has the allowlisted artifact-repository variable, no read secret, and no recorded evaluation run. D1 still enforces `$0` with paid fallback forbidden. |
| Provider adapter transport | IMPLEMENTED; DEPLOY REFRESH REQUIRED | Modal proxy authentication plus a second short-lived nonce-bound HMAC envelope are implemented. The live adapter must be redeployed from runtime code head `44cc450` before preparing the replacement Kaggle T4 x2 plan. |
| Provider-specific budgets | DEPLOYED | Modal: `$1.00` monthly internal ceiling and `$0.01` per Sandbox run; RunPod: `$1.00` per run with no internal monthly cap; Kaggle/HF: `$0` and no paid fallback. Provider-account billing limits remain independent. |
| Local Runner / Keychain | RETIRED | The former macOS Runner, Keychain bearer path and `/runner/*` routes must not be restored. Historical D1/R2 evidence is preserved. |
| Independent security review | CURRENT DIFF NOT COMPLETED | The historical repository scan covered revision `26c1def`, not the current head. The current Codex Security diff scanner twice rejected valid worktrees with `Review changes requires a non-bare Git worktree with a resolvable HEAD`; do not claim a current independent pass. |
| Legacy hosting retirement | NOT A RELEASE DEPENDENCY | Do not recreate Railway, Vercel, Neon or an external PostgreSQL Gateway. Historical evidence is retained under `docs/archive/` and dated acceptance records. |

## Current activation order

1. Keep all currently unconfigured providers fail-closed.
2. Issue a one-hour Modal deployment token, deploy the T4 x2 adapter without
   starting a provider workload, then revoke the token immediately.
3. Verify read-only capabilities and prepare a fresh exact Kaggle plan.
4. Run one explicitly approved free Kaggle canary through result and cleanup.
5. Run one explicitly approved private ZeroGPU canary through result and cleanup.
6. Issue an endpoint-scoped RunPod key, register it in Sites with admission
   closed, and verify exact offer and completion-transport identity.
7. Run one explicitly approved RunPod canary under the `$1` per-run cap and
   confirm terminal cleanup, zero live workers and billed cost.
8. Complete an independent security review of the exact final head.
9. Verify another authenticated account is denied before treating owner
   isolation as accepted.

## Evidence sources

- [ChatGPT Sites setup and operations](CHATGPT_SETUP.md)
- [Four-provider architecture](architecture/sites-four-provider-control-plane.md)
- [Current project history](STATUS.md)
- [Modal CPU acceptance](acceptance/2026-11-15-sites-modal-cpu-success.md)
- [Sites Worker source](../sites/gpu-control-sites/README.md)
- [Historical release matrix](archive/RELEASE_MATRIX-legacy-gateway.md)
