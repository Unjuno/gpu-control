# Current release matrix — ChatGPT Sites + D1

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | PASS for the private Site and repeated provenance-valid inference runs | The private Site and generated plugin are published. Version 15 is deployed and MCP-ready. ChatGPT prepared, submitted, polled, and retrieved registered TinyStories results through Sites → D1 → Runner → D1. Seven complete result artifacts have been retrieved and SHA-256 verified through ChatGPT. The Site remains owner-private. |
| D1 control plane | PASS for bounded provenance-valid inference lifecycles; more acceptance remains | D1 stores owner-scoped plans/runs, idempotency, leases, Runner heartbeats, and R2 artifact references. Post-recovery run `aa45b7d899de4c9aaff2ee73fa985cc6` was persisted and its complete 999-byte R2 artifact retrieved; its SHA-256 matched D1 metadata. A killed in-flight run expired after its 180-second lease and became `runner_lost_recovered`, attempt 1, cleanup confirmed, with no replay. Complete backup/export and restore rehearsal and separate-account owner isolation remain open. |
| Real CPU model inference | PASS for repeated provenance-valid bounded end-to-end runs | TinyStories 15M is pinned by upstream revision and SHA-256. Latest ChatGPT run `4b5ece4beca94113a8282608974f241b` used source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`, prompt `A quiet blue bird rested.`, seed `61120`, and 4 generated tokens in 180 ms. It passed all nine source/model/parameter and container-isolation checks, returned `gpu_used=false`, confirmed cleanup, and incurred `$0.00` cost. ChatGPT retrieved the complete 968-byte R2 artifact and locally computed SHA-256 `ff019e509b806088d099c5f3b5a85faf571ca287a746b60de088fa811cf9d31b`, matching D1/R2 metadata. This does not establish broad model quality or GPU capability; details: [`live inference refresh`](acceptance/2026-11-12-sites-d1-tinystories-chatgpt-inference.md). |
| Runner security and recovery | PARTIAL | Version 15 is deployed and has served provenance-valid CPU inference. Live caller cancellation reached `cancelled`/`caller_cancelled` with cleanup confirmed. A planned admission-gated stop/start returned to ready and completed a new inference. One active-run process-loss test killed the Runner while its exact workload container was running; after lease expiry D1 recorded `runner_lost_recovered`, attempt 1, cleanup confirmed, no retry, and no leftover container. launchd restarted the Runner and a fresh inference succeeded. Static security review found no actionable issue in the reviewed diff. Repeated crash windows, cross-owner isolation, Keychain ACL/rotation, backup/restore, and orphan reconciliation remain open. The Runner host currently has 14 exited historical containers (zero mounts, absent from current D1); disposal is pending owner choice. |
| Result artifacts | PARTIAL; seven bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Seven complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
| Owner isolation and revocation | NOT ACCEPTED | Local Worker unit checks cover owner-bound prepare, submit, list, status, result, cancel, and artifact queries using a D1-shaped fake. An unauthenticated direct request with a forged owner header received HTTP 401. These checks do not prove cross-owner separation between authenticated Site users. Test a genuinely separate Site account and verify access revocation. Evidence: [`Sites owner-scope checks`](acceptance/2026-11-12-sites-owner-scope-unit-tests.md). |
| GPU provider execution | NOT ACCEPTED | No real GPU run has been accepted through ChatGPT. Preserve provider adapters as compute integrations, but keep GPU admission disabled until provider identity, result authentication, recovery, and cleanup are verified. |
| Paid execution | PARKED | No paid path is enabled. Preserve independent authorization, exact price/quota checks, approval expiry/revocation, cancellation, cleanup, and security gates. |
| Vercel and Neon retirement | PARTIAL; owner deletion confirmation remains | Neither is a target dependency. Current read-only inventory: Vercel is `live=false` with its latest deployment `BLOCKED`; Neon compute is suspended. Neon contains no auth users, OAuth clients/codes/tokens, or Gateway runs, but one OAuth session, three Gateway singleton rows, and one Neon Auth config row remain. No row contents were read. The exact inventory and owner-action links are recorded in [`2026-11-12-resource-retirement-inventory.md`](acceptance/2026-11-12-resource-retirement-inventory.md). |

## Current implementation boundary

The product path is ChatGPT Sites Worker → D1 → separately isolated Runner →
D1 → ChatGPT. The Worker does not execute model code. The active workload is
one registered free local CPU inference path. D1 is the selected database for this path. Reconsider a
different database only if measured workload or product requirements exceed
D1's documented limits.

No Vercel deployment status is a required check or evidence for this release
path. Historical Actions/Vercel/PostgreSQL results are not erased; they remain
available in the archived matrix and dated acceptance records.

## Evidence sources

- [Current operations](OPERATIONS.md)
- [ChatGPT Sites setup](CHATGPT_SETUP.md)
- [Sites + D1 architecture decision](decisions/2026-11-11-sites-d1-architecture-pivot.md)
- [Project status](STATUS.md)
- [Sites source and Runner contract](../sites/gpu-control-sites/README.md)
