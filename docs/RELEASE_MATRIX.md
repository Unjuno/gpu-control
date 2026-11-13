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
| ChatGPT Sites MCP | Version 28 deployed; source drift and cross-account acceptance open | Version 28 is bound to a separate Cloudflare artifact Git repository at `237c0bed24277cf7c808f8c0e9946c71d517288c`, not the GitHub candidate history. Live ChatGPT prepare returns `approval_required=false`, no authorization URL; `experiment_submit` makes a Modal health request without human authorization. Do not submit. Admission remains disabled. The read-only D1 overview lists `plans`, `runner_heartbeats`, and `runs`; authorization tables are absent. The source checkout's own Worker suite passed 22 tests, but it is the older behavior. No separate-account/plugin-install test has passed. See [`Sites source reconciliation`](acceptance/2026-11-13-sites-source-reconciliation.md). |
| D1/R2 control plane | PASS for prior bounded lifecycles; preservation and recovery gates remain | D1/R2 hold owner-bound run and artifact records from earlier accepted runs. Preserve these records during migration. Backup/restore, current provider lifecycle/reconciliation, and separate-account owner isolation remain open. |
| Real CPU model inference | Historical local Runner inference accepted; current Modal inference not accepted | Older ChatGPT-originated inference and R2 artifact retrieval used the retired local Runner; they are historical CPU evidence, not current Modal acceptance. The latest Modal run `e9330c5bb5454f42bb3dabe058091dc0` failed with `MODAL_WORKLOAD_EXIT_2`; the current ChatGPT status call confirms cleanup and no result/artifact. |
| Local Runner / Keychain | RETIRED | LaunchAgent, local runtime, Worker routes, and obsolete Site secret are removed. D1/R2 history is preserved. |
| Modal CPU execution | Diagnostic candidate in PR #68; not deployed; inference unaccepted | Production still advertises the older fingerprint `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`; the PR candidate computes `0fc60d1890c26a646330a0d848750a0dedc03ff8a56a6e6dd214dba1e3471560`. The bounded line-to-exit diagnostic was locally exercised against the fixed inference file, but was not deployed to Modal. Admission remains closed. Sandbox estimate is `$0.0013` with a `$0.01` Sandbox-only ceiling; separate Modal control-function charges are excluded. A new reviewed deployment/fingerprint configuration and fresh exact-run authorization are required before live inference. |
| Result artifacts | PARTIAL; eight bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Eight complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
| Owner isolation and revocation | NOT ACCEPTED | Local Worker unit checks cover owner-bound prepare, submit, list, status, result, cancel, and artifact queries using a D1-shaped fake. An unauthenticated direct request with a forged owner header received HTTP 401. These checks do not prove cross-owner separation between authenticated Site users. Test a genuinely separate Site account and verify access revocation. Evidence: [`Sites owner-scope checks`](acceptance/2026-11-12-sites-owner-scope-unit-tests.md). |
| GPU provider execution | NOT ACCEPTED | RunPod REST v2 exists in the offline core library, but no RunPod provider route is exposed through the Sites MCP Worker. No real GPU run has been accepted through ChatGPT. Keep GPU admission disabled until the Sites route, provider identity, result authentication, recovery, and cleanup are verified. |
| RunPod API contract | v2 reviewed offline; provider execution unverified | Canonical transport and pricing now use REST v2, including cursor-complete account inventory and exact Network Volume datacenter stock. REST v1 and its GraphQL pricing path are legacy offline-only. Live RunPod calls remain disabled until separate account, security, result, recovery, and cleanup acceptance. |
| Paid execution | PARKED | No paid path is enabled. Preserve independent authorization, exact price/quota checks, approval expiry/revocation, cancellation, cleanup, and security gates. |
| Repository P0 security audit | OPEN | PR #68 exact head `11f5f11` has all six Actions checks green but no independent review. Fresh Semgrep reports the reviewed Git-blob SHA-1 compatibility warning; redacted worktree-only Gitleaks reports four pinned tokenizer SHA-256 occurrences and one test fixture, with no live credential verified. Earlier full-history scan found 11 reviewed matches. Dependency auditing found and fixed vulnerable/unbounded Starlette resolution in the Modal API image and is now a required CI step; the lock currently audits without known advisories. GitHub Code Scanning has no analysis and Dependabot alerts are disabled. These checks do not replace the repository-wide Codex Deep Scan, which still requires the managed read-only filesystem profile unavailable in the current session, or independent PR review. Details: [`Current goal recheck`](STATUS.md#current-goal-recheck--2026-11-13-0542-utc). |
| Vercel and Neon retirement | PARTIAL; Vercel project deleted, Neon soft-deleted | Neither is a target dependency. Vercel project `gpu-control` has been deleted and is absent from the Vercel project list. Its pre-deletion optional failure remains only on older PR commits; latest head `6f31aa5` has all six Actions checks successful and no external statuses. Neon project `delicate-smoke-00521013` is removed from the active project list and remains recoverable until `2026-11-19T05:19:58Z`, after which permanent purge is expected. No Neon row contents were read or exported. Evidence: [`2026-11-12-resource-retirement-inventory.md`](acceptance/2026-11-12-resource-retirement-inventory.md). |

## Current implementation boundary

The current product path is the public ChatGPT Sites Worker → authenticated
owner-scoped MCP → D1/R2 → ChatGPT. The former Runner has been retired. The
Modal diagnostic is a PR candidate and has not been deployed. Current
production still uses the prior fingerprint, and its latest Modal attempt
failed with exit code 2 and confirmed cleanup.
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
