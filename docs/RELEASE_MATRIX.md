# Current release matrix — ChatGPT Sites + D1

Live state last refreshed 2026-11-21. The product path has exactly four compute
providers: Modal, RunPod, Kaggle and Hugging Face. Railway, Vercel, Neon, an
external PostgreSQL database and a separately hosted Gateway are not runtime
dependencies.

Passing tests or publishing a Site proves only that layer. Provider acceptance
requires an owner-confirmed real run, terminal result validation and cleanup.

| Gate | Current state | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | DEPLOYED | Public Site v46 is active at `gpu-control-sites.unjuno.chatgpt.site`; its authenticated MCP endpoint and generated plugin are available. Site visibility does not grant execution authority. |
| Source provenance | PASS for v46 | Site source commit `b425de54315dedb88a0303d5cce2f47a3e026834` was built from pushed GitHub candidate `6fb1be4`; the later GitHub commits update migration coverage and operations documentation only. |
| GitHub candidate | PASSING; DRAFT | PR #68 head `6bb16a5` has seven successful exact-head checks. It remains Draft and has no current independent security approval. |
| D1 control plane | DEPLOYED | Migrations through `0017_free_provider_policies.sql` are applied. D1 owns plans, one-use authorization, budgets, provider handles, run state and cleanup evidence. |
| R2 result artifacts | ACCEPTED FOR BOUNDED MODAL RESULTS | Prior Modal result JSON was stored and digest-verified through owner-scoped bounded reads. Retention and orphan cleanup remain operational work. |
| Owner-only execution | IMPLEMENTED; CROSS-ACCOUNT ACCEPTANCE OPEN | Every stateful tool requires Sites authentication plus `GPU_CONTROL_ALLOWED_USER_IDS`; D1 operations are owner-scoped. A genuinely separate authenticated account and later revocation still need live verification. |
| Exact-plan confirmation | ACCEPTED FOR MODAL; IMPLEMENTED FOR ADAPTER | The destructive submit contains the reviewed plan and records a short-lived one-use authorization. Kaggle/HF live acceptance remains open. |
| Modal CPU | ENABLED; ONE BOUNDED RUN ACCEPTED | Earlier ChatGPT run `245d0349…6232f` produced a digest-verified artifact and confirmed cleanup. Fresh v46 repeatability/recovery acceptance is still open. Modal account billing is an independent boundary. |
| RunPod | DISABLED; LIVE BLOCKED | REST v2, fixed workload and D1 lease primitives exist. No API key is configured in Sites. Admission also requires a registered image, current price evidence, exact-plan confirmation and an authenticated live completion transport. No real RunPod run is accepted. |
| Kaggle | DISABLED; CONNECTION BLOCKED | The fixed private 100-step workload, exact source/resource identity, reconciliation and cleanup contract are implemented behind the Modal adapter. The adapter is not connected. D1 enforces a separate `$0` policy with paid fallback forbidden. No live Kaggle canary is accepted. |
| Hugging Face artifact path | DISABLED; CONNECTION BLOCKED | Private artifact write/read tokens remain inside the Modal adapter boundary and are never supplied to Kaggle or ChatGPT. The adapter is not connected and no current private round trip is accepted. |
| Hugging Face ZeroGPU | DISABLED; CONNECTION BLOCKED | The fixed private Space/revision and free-only plan contract are implemented. D1 enforces a separate `$0` policy with paid fallback forbidden. No live ZeroGPU canary is accepted. |
| Provider adapter transport | IMPLEMENTED; NOT CONFIGURED | Modal proxy authentication plus a second short-lived nonce-bound HMAC envelope are implemented. `PROVIDER_ADAPTER_*` settings and the adapter deployment are still missing. |
| Provider-specific budgets | DEPLOYED | Modal: `$1.00` monthly internal ceiling and `$0.01` per Sandbox run; RunPod: `$1.00` per run with no internal monthly cap; Kaggle/HF: `$0` and no paid fallback. Provider-account billing limits remain independent. |
| Local Runner / Keychain | RETIRED | The former macOS Runner, Keychain bearer path and `/runner/*` routes must not be restored. Historical D1/R2 evidence is preserved. |
| Independent security review | CURRENT DIFF NOT COMPLETED | The historical repository scan covered revision `26c1def`, not the current head. The current Codex Security diff scanner twice rejected valid worktrees with `Review changes requires a non-bare Git worktree with a resolvable HEAD`; do not claim a current independent pass. |
| Legacy hosting retirement | NOT A RELEASE DEPENDENCY | Do not recreate Railway, Vercel, Neon or an external PostgreSQL Gateway. Historical evidence is retained under `docs/archive/` and dated acceptance records. |

## Current activation order

1. Keep all currently unconfigured providers fail-closed.
2. Create and connect the Modal adapter HMAC and proxy credentials.
3. Deploy the adapter without starting a provider workload.
4. Verify read-only capabilities and exact blockers.
5. Run one explicitly approved free Kaggle canary through result and cleanup.
6. Run one explicitly approved private ZeroGPU canary through result and cleanup.
7. Configure RunPod only after its completion transport is verified against the
   live account; then run one explicitly approved canary under the `$1` cap.
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
