# MCP tool migration

The canonical `tools/list` surface contains seven `experiment_*` tools. The six
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

The current staged implementation intentionally reports prepare as blocked
until an operator-registered and policy-admitted backend exists. No provider
is started by `experiment_prepare`.
