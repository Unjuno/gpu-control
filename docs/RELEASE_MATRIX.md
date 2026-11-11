# Current release matrix — ChatGPT Sites + D1

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | PASS for the private Site and one provenance-valid inference | The private Site and generated plugin are published. ChatGPT prepared, submitted, polled, and retrieved a registered TinyStories result through Sites → D1 → Runner → D1. The Site remains owner-private. |
| D1 control plane | PASS for the checksum smoke and one provenance-valid inference lifecycle; more acceptance remains | D1 stores owner-scoped plans/runs, idempotency, leases, and Runner heartbeats. The provenance-valid inference result and bounded metadata were retrieved successfully. Complete backup/export and restore rehearsal, separate-account owner isolation, and failure/recovery acceptance. |
| Real CPU model inference | PASS for one provenance-valid bounded end-to-end run | TinyStories 15M is pinned by upstream revision and SHA-256. ChatGPT run `d17dcc650783466088bacb734826bcdb` used the actual pushed root commit `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288` and image `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`; it generated 24 tokens in 430 ms with seed 61112, passed identity/checksum validation, returned `gpu_used=false`, cost `$0.00`, and confirmed cleanup. Two earlier outputs with a non-resolving source SHA are excluded. This does not establish broad model quality or GPU capability. |
| Runner security and recovery | PARTIAL | The Runner uses a fixed image, bounded parameters, non-root/no-network/read-only container settings, and identity-labelled cleanup. Local recovery regression tests exist. Live restart, interruption, cancellation race, lease expiry, reconciliation, and secret rotation remain open. |
| Result artifacts | NOT ACCEPTED | Results are currently bounded inline records. Implement R2 storage and verify size, digest, run binding, owner binding, retrieval, and cleanup. |
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
