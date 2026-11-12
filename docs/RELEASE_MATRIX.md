# Current release matrix — ChatGPT Sites + D1

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | Version 27 deployed; cross-account ChatGPT acceptance open | Public access, source `64d2646815be198b0173877b821264cf3efc10a6`, environment revision 27, MCP-ready. Current capabilities report `provider_ready=true`, `available=false`, `admission_enabled=false`; Modal health is ready while admission remains deliberately closed. Anonymous HTTP probes returned edge HTTP 403, which does not verify Worker authentication. No second-account/plugin-install test has passed. |
| D1/R2 control plane | PASS for prior bounded lifecycles; preservation and recovery gates remain | D1/R2 hold owner-bound run and artifact records from earlier accepted runs. Preserve these records during migration. Backup/restore, current provider lifecycle/reconciliation, and separate-account owner isolation remain open. |
| Real CPU model inference | Historical local Runner inference accepted; current Modal inference not accepted | Run `eacc26ff2ad54cf69a1ee7665325b197` completed the registered TinyStories workload through the retired local Runner under Sites Version 16. Its R2 artifact was retrieved and digest-verified; this is not Modal evidence. Two Modal attempts failed before the dashboard v4 deployment. The latest ChatGPT-originated Modal run `b3380814d0854d93a5d978799d670013` failed after the current deployment with exit code 2 and confirmed cleanup. No successful inference after v4 is recorded. |
| Local Runner / Keychain | RETIRED | LaunchAgent, local runtime, Worker routes, and obsolete Site secret are removed. D1/R2 history is preserved. |
| Modal CPU execution | Diagnostic deployed; current-deployment inference unaccepted | Modal app `gpu-control-sites` was redeployed to `unjuno/main` from branch head `780ba73` at 12:49 UTC; CLI returned success and the dashboard showed zero live Sandboxes. This deploy includes diagnostic commit `d1dd4fe`, which adds a bounded preflight line marker. The diagnostic has not been exercised by a new inference. ChatGPT runs `0f2a3ddaa7da40648600bae21ccd9ed1` and `b3380814d0854d93a5d978799d670013` failed with exit code 2 and confirmed cleanup; neither produced an artifact. Site Version 27 remains in place with admission false. A fresh one-run authorization is required before another Sandbox. |
| Result artifacts | PARTIAL; eight bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Eight complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
| Owner isolation and revocation | NOT ACCEPTED | Local Worker unit checks cover owner-bound prepare, submit, list, status, result, cancel, and artifact queries using a D1-shaped fake. An unauthenticated direct request with a forged owner header received HTTP 401. These checks do not prove cross-owner separation between authenticated Site users. Test a genuinely separate Site account and verify access revocation. Evidence: [`Sites owner-scope checks`](acceptance/2026-11-12-sites-owner-scope-unit-tests.md). |
| GPU provider execution | NOT ACCEPTED | RunPod REST v2 exists in the offline core library, but no RunPod provider route is exposed through the Sites MCP Worker. No real GPU run has been accepted through ChatGPT. Keep GPU admission disabled until the Sites route, provider identity, result authentication, recovery, and cleanup are verified. |
| RunPod API contract | v2 reviewed offline; provider execution unverified | Canonical transport and pricing now use REST v2, including cursor-complete account inventory and exact Network Volume datacenter stock. REST v1 and its GraphQL pricing path are legacy offline-only. Live RunPod calls remain disabled until separate account, security, result, recovery, and cleanup acceptance. |
| Paid execution | PARKED | No paid path is enabled. Preserve independent authorization, exact price/quota checks, approval expiry/revocation, cancellation, cleanup, and security gates. |
| Vercel and Neon retirement | PARTIAL; Vercel project deleted, Neon soft-deleted | Neither is a target dependency. Vercel project `gpu-control` has been deleted and is absent from the Vercel project list. Its pre-deletion optional failure remains only on older PR commits; latest head `6f31aa5` has all six Actions checks successful and no external statuses. Neon project `delicate-smoke-00521013` is removed from the active project list and remains recoverable until `2026-11-19T05:19:58Z`, after which permanent purge is expected. No Neon row contents were read or exported. Evidence: [`2026-11-12-resource-retirement-inventory.md`](acceptance/2026-11-12-resource-retirement-inventory.md). |

## Current implementation boundary

The current product path is the public ChatGPT Sites Worker → authenticated
owner-scoped MCP → D1/R2 → ChatGPT. The former Runner has been retired. The
Modal preflight diagnostic is now deployed, but current-deployment inference is
unaccepted. The previous
success belongs to the retired local Runner. Two Modal failures predate v4 and
the latest Modal attempt failed with exit code 2 and confirmed cleanup.
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
