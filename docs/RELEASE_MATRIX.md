# Current release matrix — ChatGPT Sites + D1

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | PASS for the private Site and seven provenance-valid inference runs | The private Site and generated plugin are published. ChatGPT prepared, submitted, polled, and retrieved registered TinyStories results through Sites → D1 → Runner → D1. Three result artifacts were also retrieved through the ChatGPT artifact tool. The Site remains owner-private. |
| D1 control plane | PASS for seven provenance-valid inference lifecycles; more acceptance remains | D1 stores owner-scoped plans/runs, idempotency, leases, Runner heartbeats, and R2 artifact references. Seven inference results and bounded metadata were retrieved successfully. Complete backup/export and restore rehearsal, separate-account owner isolation, and live failure/recovery acceptance. |
| Real CPU model inference | PASS for seven provenance-valid bounded end-to-end runs | TinyStories 15M is pinned by upstream revision and SHA-256. Earlier accepted runs and artifact checks are listed in the acceptance record. Run `6b4cabf7b6aa4aea826c4c8e672705b3` generated 32 tokens in 631 ms with seed 61117, passed identity/sandbox checks, and confirmed cleanup. Latest run `5447466fe7f9413980d2b47a2b079289` used source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, image `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`, prompt `A tiny red fox`, seed 61117, and four generated tokens in 150 ms. It passed source, model digest, bounded parameters, non-root/no-secret/no-Docker-socket/read-only/no-network checks, returned `gpu_used=false`, and confirmed cleanup at `$0.00`. This does not establish broad model quality or GPU capability. |
| Runner security and recovery | PARTIAL | The Runner uses a fixed image, bounded parameters, non-root/no-network/read-only container settings, and identity-labelled cleanup. Saved Site Version 13 (source `52416ec02fcf3b755e1763edc617cd0a67f4ab91`) adds a D1-persisted cancellation protocol gate; legacy Runner heartbeats cannot restore readiness or claim work. Its Worker suite passes 24 tests and its Runner contract/security suite passes 12 tests. Build and artifact validation pass. Version 13 is not deployed; the current production deployment remains Version 11. Live restart, interruption/cancellation, lease expiry, reconciliation, and secret rotation remain open. |
| Result artifacts | PARTIAL; three bounded R2 results accepted | A production R2 binding stores the verified result JSON. D1 records its artifact ID, digest and byte size; the ChatGPT artifact tool checks owner/run binding, metadata and content digest before returning bounded base64 chunks. Three complete run artifacts were retrieved and SHA-256 verified. R2 retention and orphan cleanup policy, larger artifacts and a broader lifecycle remain open. |
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
