# Current release matrix — ChatGPT Sites + D1

This matrix describes the supported product path. Historical Vercel,
PostgreSQL, and legacy Gateway evidence is preserved in
[`archive/RELEASE_MATRIX-legacy-gateway.md`](archive/RELEASE_MATRIX-legacy-gateway.md).
Passing a local test or publishing a Site does not close a separate runtime,
identity, recovery, or provider acceptance gate.

| Gate | State | Evidence and remaining work |
| --- | --- | --- |
| ChatGPT Sites MCP | PASS for the private Site and previous CPU smoke | The private Site and generated plugin are published. ChatGPT completed a registered CPU checksum smoke, retrieved its result, confirmed cleanup, and repeated submit without creating another run. The current deployed version still advertises `cpu-smoke-v1`. |
| D1 control plane | PASS for the existing smoke lifecycle; more acceptance remains | D1 stores owner-scoped plans/runs, idempotency, leases, and Runner heartbeats. The inference candidate uses the same D1 path. Complete backup/export and restore rehearsal, separate-account owner isolation, and failure/recovery acceptance. |
| Real CPU model inference | IN PROGRESS | A TinyStories 15M checkpoint is pinned by upstream revision and digest. A local isolated image produced deterministic text. The candidate is not committed, registered, or deployed; verify the actual generated result from ChatGPT before marking this gate passed. |
| Runner security and recovery | PARTIAL | The Runner uses a fixed image, bounded parameters, non-root/no-network/read-only container settings, and identity-labelled cleanup. Local recovery regression tests exist. Live restart, interruption, cancellation race, lease expiry, reconciliation, and secret rotation remain open. |
| Result artifacts | NOT ACCEPTED | Results are currently bounded inline records. Implement R2 storage and verify size, digest, run binding, owner binding, retrieval, and cleanup. |
| Owner isolation and revocation | NOT ACCEPTED | Site authentication and per-run ownership checks exist. Test authenticated access from a distinct account and verify access revocation; a forged-header rejection alone is insufficient. |
| GPU provider execution | NOT ACCEPTED | No real GPU run has been accepted through ChatGPT. Preserve provider adapters as compute integrations, but keep GPU admission disabled until provider identity, result authentication, recovery, and cleanup are verified. |
| Paid execution | PARKED | No paid path is enabled. Preserve independent authorization, exact price/quota checks, approval expiry/revocation, cancellation, cleanup, and security gates. |
| Vercel and Neon retirement | NOT STARTED | Neither is a target dependency. Classify/export Neon auth/run data and preserve rollback evidence, then remove unused credentials and retire old resources after Sites acceptance. |

## Current implementation boundary

The product path is ChatGPT Sites Worker → D1 → separately isolated Runner →
D1 → ChatGPT. The Worker does not execute model code. The active workload is
free local CPU; real model inference is still pending the hosted ChatGPT
acceptance above. D1 is the selected database for this path. Reconsider a
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
