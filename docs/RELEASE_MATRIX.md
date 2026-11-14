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
| ChatGPT Sites MCP | Version 34 deployed; public audience; CPU admission enabled | The connected owner can read capabilities and owned run history. Provider health is deferred until a fresh exact plan is confirmed by the owner; the confirmation page requires ChatGPT sign-in. Cross-account denial remains unverified. Current live state is recorded in [`Project status`](STATUS.md#project-status). |
| In-chat exact-plan approval | Candidate implemented in PR #68; not deployed | `experiment_submit` is a destructive MCP write with the exact plan echoed in its arguments and a one-use, owner-bound D1 authorization. The intended path uses ChatGPT's write-confirmation UI and avoids a separate browser sign-in. Verify host behavior, trusted identity provenance, migration, and cancellation/cleanup before publishing. |
| D1/R2 control plane | PASS for prior bounded lifecycles; preservation and recovery gates remain | D1/R2 hold owner-bound run and artifact records from earlier accepted runs. Preserve these records during migration. Backup/restore, current provider lifecycle/reconciliation, and separate-account owner isolation remain open. |
| Real CPU model inference | Current Modal inference not yet accepted | Older ChatGPT-originated inference and R2 artifact retrieval used the retired local Runner; they are historical CPU evidence. The five recorded Modal-origin failures occurred on November 12, before the November 13 Docker `CMD` correction. Source analysis points to the old image `ENTRYPOINT` bypassing the fixed bootstrap; the correction was deployed, but no post-correction Sandbox run has verified it. A successful owner-confirmed run must verify result, artifact digest and cleanup. |
| Local Runner / Keychain | RETIRED | LaunchAgent, local runtime, Worker routes, and obsolete Site secret are removed. D1/R2 history is preserved. |
| Modal CPU execution | NOT ACCEPTED; post-correction run pending | Sites advertises fingerprint `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`. The code hard-limits CPU to 1 core and memory to 512 MiB for up to 30 seconds. Sites currently reports admission enabled and requires exact owner confirmation per run. The five recorded exit-2 failures predate the deployed Docker `CMD` correction; no Sandbox run has verified the correction. Provider health, actual deployed image identity, result artifact and cleanup on the corrected path remain unverified. |
| Result artifacts | PARTIAL; eight bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Eight complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
| Owner isolation and revocation | NOT ACCEPTED | Local Worker unit checks cover owner-bound prepare, submit, list, status, result, cancel, and artifact queries using a D1-shaped fake. An unauthenticated direct request with a forged owner header received HTTP 401. These checks do not prove cross-owner separation between authenticated Site users. Test a genuinely separate Site account and verify access revocation. Evidence: [`Sites owner-scope checks`](acceptance/2026-11-12-sites-owner-scope-unit-tests.md). |
| GPU provider execution | NOT ACCEPTED | RunPod REST v2 exists in the offline core library, but no RunPod provider route is exposed through the Sites MCP Worker. No real GPU run has been accepted through ChatGPT. Keep GPU admission disabled until the Sites route, provider identity, result authentication, recovery, and cleanup are verified. |
| RunPod API contract | v2 reviewed offline; provider execution unverified | Canonical transport and pricing now use REST v2, including cursor-complete account inventory and exact Network Volume datacenter stock. REST v1 and its GraphQL pricing path are legacy offline-only. Live RunPod calls remain disabled until separate account, security, result, recovery, and cleanup acceptance. |
| Paid execution | Modal CPU is usage-billed and currently blocked; RunPod parked | Public Starter pricing does not reveal this Workspace's balance or usage cap. The authorized project testing budget is `$1` aggregate through completion, not per run. Credits may offset eligible compute but do not make the provider free or guarantee zero charges. The `$0.01` Sandbox ceiling excludes separately billed control-function calls. Check current account billing before any provider call. |
| Repository P0 security audit | OPEN | PR #68 remains Draft with no independent review; the latest full six-job CI run passed, and the only changes since the last code update are documentation. Fresh Semgrep reports the reviewed Git-blob SHA-1 compatibility warning; redacted worktree-only Gitleaks reports four pinned tokenizer SHA-256 occurrences and one test fixture, with no live credential verified. Earlier full-history scan found 11 reviewed matches. Dependency auditing found and fixed vulnerable/unbounded Starlette resolution in the Modal API image and is now a required CI step; the lock currently audits without known advisories. GitHub Code Scanning has no analysis and Dependabot alerts are disabled. These checks do not replace the repository-wide Codex Deep Scan, which still requires the managed read-only filesystem profile unavailable in the current session, or independent PR review. Details: [`Current goal recheck`](STATUS.md#current-goal-recheck--2026-11-13-0546-utc). |
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
Runpod later for GPU execution; both remain separate from the Sites control
plane and gated independently. D1 is the current database, and R2 stores bounded
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
