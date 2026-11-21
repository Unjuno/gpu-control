# Current release matrix — ChatGPT Sites + D1

Live state last refreshed 2026-11-22. The product path has exactly four compute
providers: Modal, RunPod, Kaggle and Hugging Face. Railway, Vercel, Neon, an
external PostgreSQL database and a separately hosted Gateway are not runtime
dependencies.

Passing tests or publishing a Site proves only that layer. Provider acceptance
requires an owner-confirmed real run, terminal result validation and cleanup.

| Gate | Current state | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | DEPLOYED; RUNPOD LIVE GPU ACCEPTED | The authenticated ChatGPT connector returned schema v2 capabilities with all four providers and five registered workloads, then completed the accepted RunPod canary below. Site visibility does not grant execution authority. |
| Source provenance | PASS for v65 | Site source commit `195cd79ce8a3ce28802c5cb2091b0bf74fc59de0` was saved as version 65 and deployed as `appgdep_6b01f82742e08191a03b9303b654752d` with `has_mcp=true`. |
| GitHub candidate | DRAFT; EXACT-HEAD CI REFRESHING | PR #68 contains the accepted RunPod lifecycle and migration fixes. Focused validation passes 81 Sites Worker tests. Exact-head CI and final independent review remain required after this evidence update. |
| D1 control plane | DEPLOYED | Migrations through `0017_free_provider_policies.sql` are applied. D1 owns plans, one-use authorization, budgets, provider handles, run state and cleanup evidence. |
| R2 result artifacts | ACCEPTED FOR BOUNDED MODAL RESULTS | Prior Modal result JSON was stored and digest-verified through owner-scoped bounded reads. Retention and orphan cleanup remain operational work. |
| Owner-only execution | IMPLEMENTED; CROSS-ACCOUNT ACCEPTANCE OPEN | Every stateful tool requires Sites authentication plus `GPU_CONTROL_ALLOWED_USER_IDS`; D1 operations are owner-scoped. A genuinely separate authenticated account and later revocation still need live verification. |
| Exact-plan confirmation | ACCEPTED FOR MODAL; IMPLEMENTED FOR ADAPTER | The destructive submit contains the reviewed plan and records a short-lived one-use authorization. Kaggle/HF live acceptance remains open. |
| Modal CPU | ENABLED; ONE BOUNDED RUN ACCEPTED | Earlier ChatGPT run `245d0349…6232f` produced a digest-verified artifact and confirmed cleanup. Fresh v46 repeatability/recovery acceptance is still open. Modal account billing is an independent boundary. |
| RunPod | LIVE GPU ACCEPTED | Endpoint `wwlos460xbfw5q` remains restricted to RTX 2000 Ada, one GPU, max worker 1, 5-second idle and 30-second execution timeout. Owner-confirmed run `a4284e1e…e31d71` created provider job `712b3b99…ffa25-u1`, returned `gpu_used=true` for one RTX 2000 Ada (compute capability 8.9) with the pinned source/image, succeeded, and confirmed cleanup. The plan estimate was `$0.049139` under the `$1.00` per-run ceiling; exact billed amount remains account-side evidence. See `docs/acceptance/2026-11-22-runpod-live-gpu-canary.md`. |
| Kaggle | PHONE VERIFIED; REPLACEMENT RUN BLOCKED ON ADAPTER DEPLOY | Account `UnjunoOrg` showed 30 included GPU hours and zero used before the test. Run `e3fe8dae…a337` failed closed when Kaggle did not allocate the requested L4; the workload rejected CPU fallback and cleanup was confirmed. The candidate now requests the generally available `NvidiaTeslaT4` pool (T4 x2), but that adapter change is not yet deployed. D1 keeps a separate `$0` policy with paid fallback forbidden. No live Kaggle GPU success is claimed. |
| Hugging Face artifact path | PRIVATE REPOSITORY AND TOKEN CONFIGURED; ROUND TRIP OPEN | Private repository `Unjuno/gpu-control-orbitune-artifacts` exists. Modal secret `gpu-control-worker` contains a masked `HF_ARTIFACT_WRITE_TOKEN`; provider settings redact it and forbid reuse as the Space read token. No exact revision/SHA-256 artifact round trip is accepted yet. |
| Hugging Face ZeroGPU | PRIVATE FREE SPACE DEPLOYED; EXECUTION OPEN | Private Space `Unjuno/gpu-control-orbitune-zero-gpu` is `Running on ZERO` at immutable revision `2e9df7d…a85ab`; the recomputed contract digest is pinned. Modal has a separate masked `HF_SPACE_READ_TOKEN`, and live capabilities report the provider configured. No recorded evaluation run is accepted yet. D1 enforces `$0` with paid fallback forbidden. |
| Provider adapter transport | DEPLOYED; RUNPOD ACCEPTED | Modal proxy authentication plus a second short-lived nonce-bound HMAC envelope are deployed. The RunPod relay completed one authenticated GPU result and cleanup. Kaggle and Hugging Face provider-specific acceptance remain open. |
| Provider-specific budgets | DEPLOYED | Modal: `$1.00` monthly internal ceiling and `$0.01` per Sandbox run; RunPod: `$1.00` per run with no internal monthly cap; Kaggle/HF: `$0` and no paid fallback. Provider-account billing limits remain independent. |
| Local Runner / Keychain | RETIRED | The former macOS Runner, Keychain bearer path and `/runner/*` routes must not be restored. Historical D1/R2 evidence is preserved. |
| Independent security review | PASS FOR CURRENT HEAD | Independent review of the RunPod relay, provider-runtime extraction, secret boundaries and PostgreSQL-free compatibility CI found no remaining Critical, High or Medium issue at `cc954ba`. This is source-review evidence, not live provider acceptance. |
| Legacy hosting retirement | NOT A RELEASE DEPENDENCY | Do not recreate Railway, Vercel, Neon or an external PostgreSQL Gateway. Historical evidence is retained under `docs/archive/` and dated acceptance records. |

## Current activation order

1. Keep all currently unconfigured providers fail-closed.
2. Issue a one-hour Modal deployment token, deploy the T4 x2 adapter without
   starting a provider workload, then revoke the token immediately.
3. Verify read-only capabilities and prepare a fresh exact Kaggle plan.
4. Run one explicitly approved free Kaggle canary through result and cleanup.
5. Run one explicitly approved private ZeroGPU canary through result and cleanup.
6. Retain the accepted RunPod evidence and verify account-side billed cost and
   zero live workers without broadening the endpoint-only key.
7. Complete an independent security review of the exact final head.
8. Verify another authenticated account is denied before treating owner
   isolation as accepted.

## Evidence sources

- [ChatGPT Sites setup and operations](CHATGPT_SETUP.md)
- [Four-provider architecture](architecture/sites-four-provider-control-plane.md)
- [Current project history](STATUS.md)
- [Modal CPU acceptance](acceptance/2026-11-15-sites-modal-cpu-success.md)
- [Sites Worker source](../sites/gpu-control-sites/README.md)
- [Historical release matrix](archive/RELEASE_MATRIX-legacy-gateway.md)
