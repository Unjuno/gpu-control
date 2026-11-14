# Current release matrix — ChatGPT Sites + D1

Live status last refreshed 2026-11-14. The production Site and the
unmerged PR candidate are reported separately below.

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | Version 33 deployed; environment revision 35; CPU admission disabled | The connected owner can read capabilities and owned run history. Capabilities report `available=false`, `admission_enabled=false`, and `CPU_WORKLOAD_ADMISSION_DISABLED`. The Site requires exact-plan, one-use confirmation, but no execution is currently admitted. Cross-account denial remains unverified. Current live state is recorded in [`Project status`](STATUS.md#project-status). |
| D1/R2 control plane | PASS for prior bounded lifecycles; preservation and recovery gates remain | D1/R2 hold owner-bound run and artifact records from earlier accepted runs. Preserve these records during migration. Backup/restore, current provider lifecycle/reconciliation, and separate-account owner isolation remain open. |
| Real CPU model inference | Current Modal inference not yet accepted | Older ChatGPT-originated inference and R2 artifact retrieval used the retired local Runner; they are historical CPU evidence. The five latest Modal-origin attempts failed with `MODAL_WORKLOAD_EXIT_2`; the newest cleanup was confirmed and no artifact was produced. A successful owner-confirmed run must verify result, artifact digest and cleanup after the candidate deployment and fingerprint are reconciled. |
| Local Runner / Keychain | RETIRED | LaunchAgent, local runtime, Worker routes, and obsolete Site secret are removed. D1/R2 history is preserved. |
| Modal CPU execution | NOT ACCEPTED; admission closed | Site advertises fingerprint `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`; current candidate fingerprint is `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`. Five latest Modal-origin attempts failed with `MODAL_WORKLOAD_EXIT_2`; the newest cleanup is confirmed and no artifact exists. Candidate CPU/memory hard limits and deployed image digest remain unverified. Keep admission disabled pending deployment and live reconciliation. |
| Result artifacts | PARTIAL; eight bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Eight complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
| Owner isolation and revocation | NOT ACCEPTED | Local Worker unit checks cover owner-bound prepare, submit, list, status, result, cancel, and artifact queries using a D1-shaped fake. An unauthenticated direct request with a forged owner header received HTTP 401. These checks do not prove cross-owner separation between authenticated Site users. Test a genuinely separate Site account and verify access revocation. Evidence: [`Sites owner-scope checks`](acceptance/2026-11-12-sites-owner-scope-unit-tests.md). |
| GPU provider execution | NOT ACCEPTED | RunPod REST v2 exists in the offline core library, but no RunPod provider route is exposed through the Sites MCP Worker. No real GPU run has been accepted through ChatGPT. Keep GPU admission disabled until the Sites route, provider identity, result authentication, recovery, and cleanup are verified. |
| RunPod API contract | v2 reviewed offline; provider execution unverified | Canonical transport and pricing now use REST v2, including cursor-complete account inventory and exact Network Volume datacenter stock. REST v1 and its GraphQL pricing path are legacy offline-only. Live RunPod calls remain disabled until separate account, security, result, recovery, and cleanup acceptance. |
| Paid execution | Modal CPU is usage-billed and currently blocked; RunPod parked | Modal's general Starter pricing advertises `$30` monthly compute, while this Workspace dashboard currently shows `$1` of `$30/mo` available and `$1` in its Credits tab. Usage & Billing shows `$0.10` credit usage, `$0` charges, and a `$1` Workspace usage limit, leaving at most `$0.90` usage headroom under the cap. Credits may offset eligible compute but do not make the provider free or guarantee zero charges. The `$0.01` Sandbox ceiling excludes separately billed control-function calls. No payment method was added. |
| Repository P0 security audit | OPEN | PR #68 remains Draft with no independent review; the latest full six-job CI run passed, and the only changes since the last code update are documentation. Fresh Semgrep reports the reviewed Git-blob SHA-1 compatibility warning; redacted worktree-only Gitleaks reports four pinned tokenizer SHA-256 occurrences and one test fixture, with no live credential verified. Earlier full-history scan found 11 reviewed matches. Dependency auditing found and fixed vulnerable/unbounded Starlette resolution in the Modal API image and is now a required CI step; the lock currently audits without known advisories. GitHub Code Scanning has no analysis and Dependabot alerts are disabled. These checks do not replace the repository-wide Codex Deep Scan, which still requires the managed read-only filesystem profile unavailable in the current session, or independent PR review. Details: [`Current goal recheck`](STATUS.md#current-goal-recheck--2026-11-13-0546-utc). |
| Vercel and Neon retirement | PARTIAL; Vercel project deleted, Neon soft-deleted | Neither is a target dependency. Vercel project `gpu-control` has been deleted and is absent from the Vercel project list. Its pre-deletion optional failure remains only on older PR commits; latest head `6f31aa5` has all six Actions checks successful and no external statuses. Neon project `delicate-smoke-00521013` is removed from the active project list and remains recoverable until `2026-11-19T05:19:58Z`, after which permanent purge is expected. No Neon row contents were read or exported. Evidence: [`2026-11-12-resource-retirement-inventory.md`](acceptance/2026-11-12-resource-retirement-inventory.md). |

## Current implementation boundary

The current product path is the public ChatGPT Sites Worker → authenticated
owner-scoped MCP → D1/R2 → ChatGPT. The former Runner has been retired. The
Modal API is deployed and the fixed CPU workload is enabled behind owner-bound
one-use plan confirmation. Authenticated health, image digest reconciliation,
post-deploy inference, and cleanup remain unverified. The target path
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
