# Current release matrix — ChatGPT Sites + D1

Live state last refreshed 2026-11-22. The product path has exactly four compute
providers: Modal, RunPod, Kaggle and Hugging Face. Railway, Vercel, Neon, an
external PostgreSQL database and a separately hosted Gateway are not runtime
dependencies.

Passing tests or publishing a Site proves only that layer. Provider acceptance
requires an owner-confirmed real run, terminal result validation and cleanup.

| Gate | Current state | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | DEPLOYED; RUNPOD AND MODAL LIVE GPU ACCEPTED | The authenticated ChatGPT connector returned schema v2 capabilities with all four providers and five registered workloads, then completed the accepted RunPod and Modal T4 canaries below. Site visibility does not grant execution authority. |
| Source provenance | PASS for v72 | Site source commit `fbd59498c33e49c5aea8b3b6713555ac270241a7` was saved as version 72 and deployed with `has_mcp=true`. The common one-use plan confirmation window is ten minutes; provider execution bounds are unchanged. |
| GitHub candidate | DRAFT; EXACT-HEAD CI PASS | PR #68 contains the accepted provider lifecycle, budget and reconciliation fixes. All required checks passed at `02dd2bf`; focused validation passes 82 Sites Worker tests. |
| D1 control plane | DEPLOYED | Migrations through `0017_free_provider_policies.sql` are applied. D1 owns plans, one-use authorization, budgets, provider handles, run state and cleanup evidence. |
| R2 result artifacts | ACCEPTED FOR BOUNDED MODAL RESULTS | Prior Modal result JSON was stored and digest-verified through owner-scoped bounded reads. Retention and orphan cleanup remain operational work. |
| Owner-only execution | IMPLEMENTED; CROSS-ACCOUNT ACCEPTANCE OPEN | Every stateful tool requires Sites authentication plus `GPU_CONTROL_ALLOWED_USER_IDS`; D1 operations are owner-scoped. A genuinely separate authenticated account and later revocation still need live verification. |
| Exact-plan confirmation | ACCEPTED FOR MODAL; IMPLEMENTED FOR ADAPTER | The destructive submit contains the reviewed plan and records a short-lived one-use authorization. Kaggle/HF live acceptance remains open. |
| Modal CPU | ENABLED; ONE BOUNDED RUN ACCEPTED | Earlier ChatGPT run `245d0349…6232f` produced a digest-verified artifact and confirmed cleanup. Fresh v46 repeatability/recovery acceptance is still open. Modal account billing is an independent boundary. |
| Modal GPU | LIVE GPU ACCEPTED | Owner-authorized run `d9df87e1…82be` returned `gpu_used=true` for one Tesla T4 (compute capability 7.5), a bound result checksum and `cleanup_state=confirmed`. The outer Workspace usage limit observed before planning was `$30.00`; D1 independently retained the stricter `$1.00` monthly and `$0.01` per-run project limits. See `docs/acceptance/2026-11-22-modal-live-gpu-canary.md`. |
| RunPod | LIVE GPU ACCEPTED | Endpoint `wwlos460xbfw5q` remains restricted to RTX 2000 Ada, one GPU, max worker 1, 5-second idle and 30-second execution timeout. Owner-confirmed run `a4284e1e…e31d71` created provider job `712b3b99…ffa25-u1`, returned `gpu_used=true` for one RTX 2000 Ada (compute capability 8.9) with the pinned source/image, succeeded, and confirmed cleanup. The provider page subsequently showed zero running/idle/initializing workers, zero queued/in-progress jobs and a rounded endpoint total billed of `$0.00`. The plan estimate was `$0.049139` under the `$1.00` per-run ceiling. See `docs/acceptance/2026-11-22-runpod-live-gpu-canary.md`. |
| Kaggle | LIVE ATTEMPT FAILED; PROVIDER QUEUE BLOCKER | Two owner-authorized T4 x2 versions remained queued beyond the five-minute runtime plus fifteen-minute grace window. Versions 6 and 7 were cancelled in Kaggle, the connector recorded terminal failure with `cleanup_state=confirmed`, and replacement submission stayed disabled until cleanup. No GPU execution evidence was produced; a successful real-GPU run remains open. |
| Hugging Face artifact path | PRIVATE REPOSITORY AND TOKEN CONFIGURED; ROUND TRIP OPEN | Private repository `Unjuno/gpu-control-orbitune-artifacts` exists. Modal secret `gpu-control-worker` contains a masked `HF_ARTIFACT_WRITE_TOKEN`; provider settings redact it and forbid reuse as the Space read token. No exact revision/SHA-256 artifact round trip is accepted yet. |
| Hugging Face ZeroGPU | PRIVATE FREE SPACE DEPLOYED; EXECUTION OPEN | Private Space `Unjuno/gpu-control-orbitune-zero-gpu` is `Running on ZERO` at immutable revision `2e9df7d…a85ab`; the recomputed contract digest is pinned. Modal has a separate masked `HF_SPACE_READ_TOKEN`, and live capabilities report the provider configured. No recorded evaluation run is accepted yet. D1 enforces `$0` with paid fallback forbidden. |
| Provider adapter transport | DEPLOYED; RUNPOD ACCEPTED | Modal proxy authentication plus a second short-lived nonce-bound HMAC envelope are deployed. The RunPod relay completed one authenticated GPU result and cleanup. Kaggle and Hugging Face provider-specific acceptance remain open. |
| Provider-specific budgets | DEPLOYED | Modal: `$1.00` monthly internal ceiling and `$0.01` per Sandbox run; RunPod: `$1.00` per run with no internal monthly cap; Kaggle/HF: `$0` and no paid fallback. Provider-account billing limits remain independent. |
| Local Runner / Keychain | RETIRED | The former macOS Runner, Keychain bearer path and `/runner/*` routes must not be restored. Historical D1/R2 evidence is preserved. |
| Independent security review | PASS FOR CURRENT CODE HEAD | Independent review found no Critical, High or Medium issue at `02dd2bf`. It verified that the outer `$30` Workspace evidence and inner D1 `$1` monthly/`$0.01` per-run ledgers are enforced independently without weakening owner, replay, lease or cleanup boundaries. This is source-review evidence, not live provider acceptance. |
| Legacy hosting retirement | NOT A RELEASE DEPENDENCY | Do not recreate Railway, Vercel, Neon or an external PostgreSQL Gateway. Historical evidence is retained under `docs/archive/` and dated acceptance records. |

## Current activation order

1. Keep all unconfigured or disabled provider lanes fail-closed.
2. Retry the free Kaggle canary only when Kaggle can allocate the registered
   T4 x2 resource; do not create overlapping replacement versions.
3. Use its immutable private artifact to run one ZeroGPU canary through result
   and cleanup.
4. Complete an independent security review of the exact final head after the
   remaining acceptance records are committed.
5. Verify another authenticated account is denied before treating owner
   isolation as accepted.

## Evidence sources

- [ChatGPT Sites setup and operations](CHATGPT_SETUP.md)
- [Four-provider architecture](architecture/sites-four-provider-control-plane.md)
- [Current project history](STATUS.md)
- [Modal CPU acceptance](acceptance/2026-11-15-sites-modal-cpu-success.md)
- [Sites Worker source](../sites/gpu-control-sites/README.md)
- [Historical release matrix](archive/RELEASE_MATRIX-legacy-gateway.md)
