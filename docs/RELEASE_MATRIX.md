# Current release matrix — ChatGPT Sites + D1

Live status last refreshed 2026-11-15. The production Site and the
unmerged PR candidate are reported separately below.

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | Version 35 deployed; public audience; CPU admission enabled | Production deployment `appgdep_6af8e7ce2cec81919ad697365bed2d7b` succeeded from Site source `0eb4fe4`. The connected owner can read capabilities and owned run history. Provider health remains deferred until a fresh exact plan is confirmed. Cross-account denial remains unverified. Evidence: [`P0 scan and Sites Version 35`](acceptance/2026-11-15-p0-scan-and-sites-v35.md). |
| In-chat exact-plan approval | DEPLOYED; prepare accepted, submit confirmation pending | Version 35 includes migration `0011` and makes `experiment_submit` a destructive MCP write whose arguments contain the exact reviewed plan. A fresh goal turn loaded that schema and prepared an exact owner-bound plan without a separate browser login. The user was away, so the destructive write was not confirmed or submitted. A later fresh plan must verify the actual confirmation UI, trusted identity provenance, one-use consumption, result and cleanup. Evidence: [`Version 35 native plan preparation`](acceptance/2026-11-15-sites-v35-native-plan-prepare.md). |
| D1/R2 control plane | PASS for prior bounded lifecycles; preservation and recovery gates remain | D1/R2 hold owner-bound run and artifact records from earlier accepted runs. Preserve these records during migration. Backup/restore, current provider lifecycle/reconciliation, and separate-account owner isolation remain open. |
| Real CPU model inference | Current Modal inference not yet accepted | Older ChatGPT-originated inference and R2 artifact retrieval used the retired local Runner; they are historical CPU evidence. The five recorded Modal-origin failures occurred on November 12, before the November 13 Docker `CMD` correction. Source analysis points to the old image `ENTRYPOINT` bypassing the fixed bootstrap; the correction was deployed, but no post-correction Sandbox run has verified it. A successful owner-confirmed run must verify result, artifact digest and cleanup. |
| Local Runner / Keychain | RETIRED | LaunchAgent, local runtime, Worker routes, and obsolete Site secret are removed. D1/R2 history is preserved. |
| Modal CPU execution | NOT ACCEPTED; post-correction run pending | Sites advertises fingerprint `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`. The code hard-limits CPU to 1 core and memory to 512 MiB for up to 30 seconds. Sites currently reports admission enabled and requires exact owner confirmation per run. The five recorded exit-2 failures predate the deployed Docker `CMD` correction; no Sandbox run has verified the correction. Provider health, actual deployed image identity, result artifact and cleanup on the corrected path remain unverified. |
| Result artifacts | PARTIAL; eight bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Eight complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
| Owner isolation and revocation | NOT ACCEPTED | Local Worker unit checks cover owner-bound prepare, submit, list, status, result, cancel, and artifact queries using a D1-shaped fake. An unauthenticated direct request with a forged owner header received HTTP 401. These checks do not prove cross-owner separation between authenticated Site users. Test a genuinely separate Site account and verify access revocation. Evidence: [`Sites owner-scope checks`](acceptance/2026-11-12-sites-owner-scope-unit-tests.md). |
| GPU provider execution | NOT ACCEPTED | RunPod REST v2, the root-owned completion signer contract, fixed-origin Network Volume result authentication, and ambiguous create/cleanup reconciliation exist in the offline core library. Submission now refuses incomplete signer/result/recovery configuration. No RunPod provider route is exposed through the Sites MCP Worker, and no real GPU run has been accepted through ChatGPT. Keep GPU admission disabled until the D1 lease is wired atomically to provider intent and the live provider identity, secret scrubbing, result, recovery, and cleanup path is verified. |
| RunPod API contract | v2 reviewed offline; provider execution unverified | Canonical transport and pricing now use REST v2, including cursor-complete account inventory and exact Network Volume datacenter stock. REST v1 and its GraphQL pricing path are legacy offline-only. Live RunPod calls remain disabled until separate account, security, result, recovery, and cleanup acceptance. |
| Paid execution | Modal CPU is usage-billed and currently blocked; RunPod parked | Public Starter pricing does not reveal this Workspace's balance or usage cap. The authorized project testing budget is `$1` aggregate through completion, not per run. Credits may offset eligible compute but do not make the provider free or guarantee zero charges. The `$0.01` Sandbox ceiling excludes separately billed control-function calls. Check current account billing before any provider call. |
| Repository P0 security audit | PASS for revision `26c1def` | Codex Security Standard scan `622fe374-d961-4ee7-8ced-15281ac89ebe` completed and sealed with zero source-backed findings. It used the 348-file inventory, three independent review packets, and Semgrep security/secrets rules over 295 parsable tracked targets. Live Sites identity provenance and provider behavior remain separate runtime gates. Evidence: [`P0 scan and Sites Version 35`](acceptance/2026-11-15-p0-scan-and-sites-v35.md). |
| Vercel and Neon retirement | PARTIAL; Vercel project deleted, Neon soft-deleted | Neither is a target dependency. Vercel project `gpu-control` has been deleted and is absent from the Vercel project list. Its pre-deletion optional failure remains only on older PR commits; latest head `6f31aa5` has all six Actions checks successful and no external statuses. Neon project `delicate-smoke-00521013` is removed from the active project list and remains recoverable until `2026-11-19T05:19:58Z`, after which permanent purge is expected. No Neon row contents were read or exported. Evidence: [`2026-11-12-resource-retirement-inventory.md`](acceptance/2026-11-12-resource-retirement-inventory.md). |

## Current implementation boundary

The current product path is the public ChatGPT Sites Worker → authenticated
owner-scoped MCP → D1/R2 → ChatGPT. The former Runner has been retired. The
Modal API is deployed and the fixed CPU workload is gated by owner-bound
one-use plan confirmation; admission is currently reported enabled. The
recorded Modal failures predate the deployed Docker `CMD` correction. No
post-correction run has verified the fix. Authenticated health, image digest
reconciliation, successful inference and cleanup remain unverified. The target path
uses Modal as the first fixed compute provider and
RunPod later for GPU execution. Modal is already the Sites compute path;
RunPod remains an offline core library plus an unwired D1 lease primitive and
is gated independently. D1 is the current database, and R2 stores bounded
artifacts.

No Vercel deployment status is a required check or evidence for this release
path. Historical Actions/Vercel/PostgreSQL results are not erased; they remain
available in the archived matrix and dated acceptance records.

## Evidence sources

- [Current operations](OPERATIONS.md)
- [ChatGPT Sites setup](CHATGPT_SETUP.md)
- [Sites + D1 architecture decision](decisions/2026-11-11-sites-d1-architecture-pivot.md)
- [Project status](STATUS.md)
- [Sites, Modal, and Runpod delivery plan](SITES_MODAL_RUNPOD_DELIVERY.md)
- [Sites source and Runner contract](../sites/gpu-control-sites/README.md)
