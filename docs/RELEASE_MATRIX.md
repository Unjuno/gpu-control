# Current release matrix — ChatGPT Sites + D1

Live status last refreshed 2026-11-13. The production Site and the
unmerged PR candidate are reported separately below.

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | Version 29 deployed; source is synchronized; cross-account acceptance open | Version 29 source commit `6144d58acf6de609c8ac42d0b06542e29d89b1ab` was synchronized from GitHub candidate `01dd2a6e9c51795396418c8e77156f4d574c21e3`. Live capability reports exact-plan confirmation required and authorization storage ready; D1 schema includes the authorization tables. Admission remains disabled. Browser confirmation by an independently authenticated user and separate-account denial remain unverified. See [`Sites Version 29 deployment`](acceptance/2026-11-13-sites-v29-production-deploy.md). |
| D1/R2 control plane | PASS for prior bounded lifecycles; preservation and recovery gates remain | D1/R2 hold owner-bound run and artifact records from earlier accepted runs. Preserve these records during migration. Backup/restore, current provider lifecycle/reconciliation, and separate-account owner isolation remain open. |
| Real CPU model inference | Historical local Runner inference accepted; current Modal inference not accepted | Older ChatGPT-originated inference and R2 artifact retrieval used the retired local Runner; they are historical CPU evidence, not current Modal acceptance. The latest Modal run `e9330c5bb5454f42bb3dabe058091dc0` failed with `MODAL_WORKLOAD_EXIT_2`; the current ChatGPT status call confirms cleanup and no result/artifact. |
| Local Runner / Keychain | RETIRED | LaunchAgent, local runtime, Worker routes, and obsolete Site secret are removed. D1/R2 history is preserved. |
| Modal CPU execution | API deployed; readiness and inference unaccepted | PR #68 head `496e28c` deployed to Modal `unjuno/main`; unauthenticated `/v1/health` returns 401, so authenticated readiness is unverified. Candidate source fingerprint is `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`; Sites still advertises `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577` and prior digest `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`. Rebuilt OCI digest is not verified/registered. Admission remains closed; no Sandbox was started. Modal displayed `$0.10` usage and `$0` charges under a `$1` workspace limit; see [deployment acceptance](acceptance/2026-11-13-modal-main-deploy.md). |
| Result artifacts | PARTIAL; eight bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Eight complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
| Owner isolation and revocation | NOT ACCEPTED | Local Worker unit checks cover owner-bound prepare, submit, list, status, result, cancel, and artifact queries using a D1-shaped fake. An unauthenticated direct request with a forged owner header received HTTP 401. These checks do not prove cross-owner separation between authenticated Site users. Test a genuinely separate Site account and verify access revocation. Evidence: [`Sites owner-scope checks`](acceptance/2026-11-12-sites-owner-scope-unit-tests.md). |
| GPU provider execution | NOT ACCEPTED | RunPod REST v2 exists in the offline core library, but no RunPod provider route is exposed through the Sites MCP Worker. No real GPU run has been accepted through ChatGPT. Keep GPU admission disabled until the Sites route, provider identity, result authentication, recovery, and cleanup are verified. |
| RunPod API contract | v2 reviewed offline; provider execution unverified | Canonical transport and pricing now use REST v2, including cursor-complete account inventory and exact Network Volume datacenter stock. REST v1 and its GraphQL pricing path are legacy offline-only. Live RunPod calls remain disabled until separate account, security, result, recovery, and cleanup acceptance. |
| Paid execution | PARKED | No paid path is enabled. Preserve independent authorization, exact price/quota checks, approval expiry/revocation, cancellation, cleanup, and security gates. |
| Repository P0 security audit | OPEN | PR #68 remains Draft with no independent review; the latest full six-job CI run passed, and the only changes since the last code update are documentation. Fresh Semgrep reports the reviewed Git-blob SHA-1 compatibility warning; redacted worktree-only Gitleaks reports four pinned tokenizer SHA-256 occurrences and one test fixture, with no live credential verified. Earlier full-history scan found 11 reviewed matches. Dependency auditing found and fixed vulnerable/unbounded Starlette resolution in the Modal API image and is now a required CI step; the lock currently audits without known advisories. GitHub Code Scanning has no analysis and Dependabot alerts are disabled. These checks do not replace the repository-wide Codex Deep Scan, which still requires the managed read-only filesystem profile unavailable in the current session, or independent PR review. Details: [`Current goal recheck`](STATUS.md#current-goal-recheck--2026-11-13-0546-utc). |
| Vercel and Neon retirement | PARTIAL; Vercel project deleted, Neon soft-deleted | Neither is a target dependency. Vercel project `gpu-control` has been deleted and is absent from the Vercel project list. Its pre-deletion optional failure remains only on older PR commits; latest head `6f31aa5` has all six Actions checks successful and no external statuses. Neon project `delicate-smoke-00521013` is removed from the active project list and remains recoverable until `2026-11-19T05:19:58Z`, after which permanent purge is expected. No Neon row contents were read or exported. Evidence: [`2026-11-12-resource-retirement-inventory.md`](acceptance/2026-11-12-resource-retirement-inventory.md). |

## Current implementation boundary

The current product path is the public ChatGPT Sites Worker → authenticated
owner-scoped MCP → D1/R2 → ChatGPT. The former Runner has been retired. The Modal API candidate is deployed, while
the workload image identity and authenticated readiness remain unverified; the
latest prior Modal attempt failed with exit code 2 and confirmed cleanup.
Admission is closed. The target path
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
