# Current release matrix — ChatGPT Sites + D1

Live state in the table below was last refreshed 2026-11-22. It is historical
and does not describe current deployment state. The current source candidate
and its release boundary are recorded separately below. The last verified
production source had four compute providers: Modal, RunPod, Kaggle and Hugging
Face. PR #70 source adds Google Colab as a fifth candidate compute provider;
it is not yet a production route. Railway, Vercel, Neon, an
external PostgreSQL database and a separately hosted Gateway are not runtime
dependencies.

Passing tests or publishing a Site proves only that layer. Provider acceptance
requires an owner-confirmed real run, terminal result validation and cleanup.

## Current source candidate — 2026-11-28

| Gate | Current evidence | Release meaning |
| --- | --- | --- |
| Source | PR #70 branch `codex/owner-training-workloads`, head `e391116d48ba322303979e671cbd582467bff1ed` | Open and unmerged; candidate source is not deployed. |
| GitHub review | PR remains open; current review state is not asserted by this release record | Refresh review state directly before merge. |
| CI | All seven checks passed at exact source head `e391116d48ba322303979e671cbd582467bff1ed` | Source-level checks only; passing CI is not deployment or provider acceptance. |
| Security review | No independent review covers the Colab attestation/migration update. The Codex Security scanner could not initialize on the linked worktree. | Do not claim a scan or independent approval for the current head. |
| Owner-selected repository code | Modal and hosted Colab MCP are implemented in candidate source | Admission remains disabled; neither is a live user capability. |
| Policy | `policies/repository-state.yaml` says `parked` | No paid/external compute admission is implied. |
| Hosted Site and D1 | Not refreshed in this checkpoint; source contains migrations through `0039_colab_positive_cu_attestation.sql` | Deployment version and applied migration level must be checked live before release claims. |

The architecture map lives in [docs/architecture/repository-map.md](architecture/repository-map.md).

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
| Kaggle | LIVE GPU TRAINING ACCEPTED | Run `87d37302…de87` completed the fixed 100-step Orbitune workload on a Tesla T4 with `gpu_used=true`, validation loss `5.315847873687744`, checkpoint reload verification, fixed source/image identities and `cleanup_state=confirmed`. Known cost was `$0` under `FREE_QUOTA`. See `docs/acceptance/2026-11-22-kaggle-huggingface-live-gpu-chain.md`. |
| Hugging Face artifact path | PRIVATE IMMUTABLE ROUND TRIP ACCEPTED | Kaggle published `runs/87d37302…de87/orbitune-output.zip` to private model repository `Unjuno/gpu-control-orbitune-artifacts` at revision `23591e1…cfa4`; SHA-256 `d5328a0…f28a2`, size 1,737,429 bytes. The Space uses a separate fine-grained read token restricted to this repository. |
| Hugging Face ZeroGPU | LIVE GPU EVALUATION ACCEPTED | Private Space `Unjuno/gpu-control-orbitune-zero-gpu` remained `Running on ZERO` at immutable revision `2e9df7d…a85ab`. Run `58ca7f86…117a` evaluated the exact Kaggle artifact on `NVIDIA RTX PRO 6000 Blackwell Server Edition MIG 2g.48gb`, returned score `5.315847873687744`, `gpu_used=true`, the matching checkpoint checksum, known cost `$0`, and confirmed cleanup. |
| Normal ChatGPT Kaggle E2E | ACCEPTED INCLUDING PRIVATE ARTIFACT VERIFY | On 2026-11-23, a normal ChatGPT conversation used one execution instruction to prepare, submit, monitor, retrieve and confirm cleanup for run `0fb72577…9da1`. Kaggle reported a Tesla T4, 100/100 steps, validation loss `5.315847873687744`, checkpoint SHA-256 `b990b146…6e0`, known cost `$0`, and `cleanup_state=confirmed`. Sites Version 79 then used `experiment_artifact` to re-download the private 1,737,429-byte ZIP at its exact immutable revision, verify full-file SHA-256 `4e4ee008…7a1e5`, and return two consecutive bounded chunks without persisting their bytes in D1. |
| Provider adapter transport | DEPLOYED; FOUR PROVIDERS ACCEPTED | Modal proxy authentication plus a second short-lived nonce-bound HMAC envelope are deployed. RunPod, Kaggle and Hugging Face completed authenticated provider results and cleanup; Modal completed its direct bound GPU canary. |
| Provider-specific budgets | DEPLOYED | Modal: `$1.00` monthly internal ceiling and `$0.01` per Sandbox run; RunPod: `$1.00` per run with no internal monthly cap; Kaggle/HF: `$0` and no paid fallback. Provider-account billing limits remain independent. |
| Local Runner / Keychain | RETIRED | The former macOS Runner, Keychain bearer path and `/runner/*` routes must not be restored. Historical D1/R2 evidence is preserved. |
| Independent security review | PASS FOR CURRENT CODE HEAD | Independent review found no Critical, High or Medium issue at `02dd2bf`. It verified that the outer `$30` Workspace evidence and inner D1 `$1` monthly/`$0.01` per-run ledgers are enforced independently without weakening owner, replay, lease or cleanup boundaries. This is source-review evidence, not live provider acceptance. |
| Legacy hosting retirement | NOT A RELEASE DEPENDENCY | Do not recreate Railway, Vercel, Neon or an external PostgreSQL Gateway. Historical evidence is retained under `docs/archive/` and dated acceptance records. |

## Current activation order

1. Keep all unconfigured or disabled provider lanes fail-closed.
2. Run the final normal ChatGPT-chat acceptance against the published Sites
   version and verify all four accepted runs appear owner-scoped.
3. Complete an independent security review of the exact final head after the
   remaining acceptance records are committed.
4. Verify another authenticated account is denied before treating owner
   isolation as accepted.

## Evidence sources

- [ChatGPT Sites setup and operations](CHATGPT_SETUP.md)
- [Four-provider architecture](architecture/sites-four-provider-control-plane.md)
- [Current project history](STATUS.md)
- [Modal CPU acceptance](acceptance/2026-11-15-sites-modal-cpu-success.md)
- [Sites Worker source](../sites/gpu-control-sites/README.md)
- [Historical release matrix](archive/RELEASE_MATRIX-legacy-gateway.md)
