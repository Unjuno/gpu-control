# Current release matrix — ChatGPT Sites + D1

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | PASS for the private Site and repeated provenance-valid inference runs | The private Site and generated plugin are published. Version 15 is deployed and MCP-ready. ChatGPT prepared, submitted, polled, and retrieved registered TinyStories results through Sites → D1 → Runner → D1. Six complete result artifacts have been retrieved and SHA-256 verified through ChatGPT. The Site remains owner-private. |
| D1 control plane | PASS for bounded provenance-valid inference lifecycles; more acceptance remains | D1 stores owner-scoped plans/runs, idempotency, leases, Runner heartbeats, and R2 artifact references. Post-restart run `6c817aa27a8842eda0bc07c7e5396776` was persisted and its complete 1,005-byte R2 artifact retrieved; its SHA-256 matched D1 metadata. Complete backup/export and restore rehearsal, separate-account owner isolation, and live failure recovery remain open. |
| Real CPU model inference | PASS for repeated provenance-valid bounded end-to-end runs | TinyStories 15M is pinned by upstream revision and SHA-256. Latest run `6c817aa27a8842eda0bc07c7e5396776` used source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`, prompt `A tiny lantern glowed beneath the winter moon.`, seed `719241`, and 8 generated tokens in 330 ms. It passed source/model/parameter and container-isolation checks, returned `gpu_used=false`, confirmed cleanup, and incurred `$0.00` provider cost. This does not establish broad model quality or GPU capability. |
| Runner security and recovery | PARTIAL | Version 15 is deployed and has served provenance-valid CPU inference. A live cancel request reached a running run; D1 recorded `cancelled`/`caller_cancelled`, cleanup was confirmed, and free CPU readiness returned. A planned LaunchAgent stop/start with admission closed returned to ready, followed by a successful ChatGPT inference. The Runner uses a fixed image, bounded parameters, non-root/no-network/read-only container settings, and identity-labelled cleanup. Its macOS LaunchAgent reads credentials from login Keychain; live process and Keychain items exist, plist/runtime files have mode `0600`, and running source hashes match published source. Static security review found no actionable issue in the reviewed diff. Forced process-death/lease recovery, reconciliation, Keychain ACL/rotation, and crash recovery remain open. |
| Result artifacts | PARTIAL; six bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Six complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
| Owner isolation and revocation | NOT ACCEPTED | Site authentication and per-run ownership checks exist. Test authenticated access from a distinct account and verify access revocation; a forged-header rejection alone is insufficient. |
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
