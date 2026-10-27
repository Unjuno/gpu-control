# MCP tool migration

The canonical `tools/list` surface contains eight `experiment_*` tools. The six
pre-existing `integrations_list` / `experiments_*` names remain callable as
compatibility routes, but are not advertised. This lets existing clients
continue to call their saved tool names while new clients discover the stable
ChatGPT-facing contract.

Keep the legacy call routes for at least one release after the canonical tools
are deployed. Removal requires a separate release decision after checking
usage and updating the Web UI, GitHub comment bridge, and any documented MCP
clients. A migration period does not make the legacy route a second execution
implementation: both surfaces must retain the same service owner checks,
approval rules, and provider gates.

Canonical responses use `schema_version: 2` and the fields `status`,
`human_summary`, `machine_state`, `next_allowed_actions`, and
`blocking_reason`. A pending result is not a successful result. A simulation
result is returned as blocked and must not count as real execution. Tool
visibility follows OAuth scopes; the browser approval endpoint remains
separate from MCP.

`experiment_capabilities` reports workload-level availability, provider cost
classification, approval mode, source identity, resource limits, worker and
recovery-supervisor heartbeat age, and configured concurrency. A local CPU
workload is queueable only when its source and current operator policy are valid,
both background roles have fresh heartbeats, and an admission slot is available.
`execution_capacity` remains `UNVERIFIED` until the worker can report live host
capacity; local concurrency is not a free-quota or physical-capacity claim.
Local provider cost `0` covers provider charges only, not electricity, hardware,
database or Gateway hosting. A non-local price is classified and estimated only
while its quote reference and expiry are current; otherwise cost is `UNKNOWN`.
Provider availability and quota remain unverified until separately accepted.
The demo workload is always marked `simulation_only`.

`experiment_artifact` accepts only a run ID, an artifact ID already present in
that run's result manifest, and a bounded byte range. It returns base64 chunks
with the manifest digest and size. The API checks run ownership and confirmed
cleanup before reading from the shared artifact directory; callers cannot
provide filesystem paths or URLs.

`experiment_prepare` blocks simulation-only workloads, GPU-required workloads
without a verified GPU lane, and local CPU workloads that fail operator policy
or backend checks. A successful prepare persists a plan and never starts a
provider. `experiment_submit` still requires the matching fingerprint and the
corresponding server-side authorization path.
