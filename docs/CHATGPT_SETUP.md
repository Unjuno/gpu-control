# ChatGPT custom MCP connection and acceptance

This document describes the live connection gate for the Gateway. Repository and
container tests do not count as a ChatGPT connection test.

## Account and workspace gate

The current [OpenAI Help Center instructions](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
say full MCP support, including write actions, is available on ChatGPT Business,
Enterprise and Edu on the web. Pro can connect custom MCP servers for read/fetch
only. This Gateway exposes run and cancel operations, so a read-only Pro connection
cannot satisfy product acceptance. The account plan and workspace permissions for
this project have not been verified from the repository; an authorized workspace
admin or owner must confirm access to create and test a custom MCP server.

The current role rules are stricter than plan availability alone: in Business,
only workspace admins/owners can create and publish a custom MCP app. In
Enterprise/Edu, admins/owners can create and test; an admin may grant selected
members permission to create/test through RBAC, while only admins/owners can
publish the app. Record the actual tester's role, the workspace's `Create
plugins with MCPs` permission, write-action permission, and the publisher role
in the acceptance evidence. A plan name by itself does not prove these gates
are satisfied. The current Plugins flow does not require enabling Developer
Mode first; use the connection flow visible in the intended workspace and
record any difference from the current guide.

For a permitted workspace, the current UI flow is **Plugins → + → Add custom MCP
server**, then enter a public HTTPS MCP endpoint (or select an already configured
Secure MCP Tunnel), choose authentication, acknowledge the risk prompt, create the
plugin and inspect discovered tools. Install it before starting a conversation;
use `@` to select the plugin. Tool-list changes are not automatically applied to a
published connection: an admin must refresh/review the tool snapshot; new or
changed actions may need to be explicitly enabled. ChatGPT may ask the user to
confirm a write action based on its context. Such confirmation is a ChatGPT UI
step and does not replace Gateway-side owner, scope, policy, or plan checks. See OpenAI's
[custom MCP server guide](https://developers.openai.com/api/docs/guides/custom-mcp-server)
and [Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

### Development-only private tunnel path

Secure MCP Tunnel is a supported path for testing a private MCP server from
ChatGPT without a public inbound endpoint. It can shorten the first live
ChatGPT CPU smoke: run the Gateway locally and keep the tunnel client running
beside it while discovering tools and making calls. This still requires an
eligible ChatGPT workspace and its custom-MCP permissions. Separately, the
Platform organization must create/manage the tunnel (Tunnels Read + Manage),
the caller must have Tunnels Read + Use, and the tunnel must be associated with
the target ChatGPT workspace. Tunnel access does not grant MCP/OAuth access to
the Gateway and does not replace its owner, scope, or admission checks.

Tunnel setup also requires a `tunnel_id` and a runtime API key for
`tunnel-client`, plus a local MCP server reachable by that client over stdio or
HTTP. Install the current client from the Platform tunnel settings or the
[official tunnel-client releases](https://github.com/openai/tunnel-client/releases/latest).
Configure its named profile using the official
[Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels),
run `tunnel-client doctor --profile <profile> --explain`, and keep
`tunnel-client run --profile <profile>` healthy during ChatGPT discovery and
calls. Keep the runtime key in the client's secret/configuration mechanism; do
not paste it into this repository, shell history, logs, or acceptance artifacts.
The tunnel ID is an identifier, not a substitute for the runtime key or the
workspace association.

OAuth has a related but distinct network path. The current Secure MCP Tunnel
guide says OAuth discovery can travel through the tunnel path, so protected-
resource metadata need not require a separate public MCP listener. The
authorization server itself is not automatically tunneled. Inspect the
Gateway's protected-resource and authorization-server metadata and verify that
the advertised issuer, authorization endpoint, token endpoint, and (when
advertised) revocation endpoint are reachable by their respective ChatGPT
authorization flow clients. If those endpoints are private, use an explicitly
supported reachable OAuth deployment or a public HTTPS route for the
authorization server; do not infer that the MCP tunnel exposes them. Mark OAuth
acceptance blocked until authorization-code + PKCE, token exchange, refresh,
and revocation have each been exercised through ChatGPT. See the current
[Secure MCP Tunnel OAuth guidance](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels#oauth).

The tunnel guide documents a 120-second absolute MCP request deadline and a
10 MiB serialized request/response limit. Keep the tunnel smoke small and
bounded; verify that every tool call completes within the deadline and the
result/artifact path fits the transfer limit. Treat this as ChatGPT connection
and short CPU-vertical evidence only. It does not establish a stable service,
continuous worker availability, seven-day operation, public plugin
distribution, or large-artifact delivery. Those still require the selected P3
host and public HTTPS route. Do not start the tunnel or expose a local server
until the required Platform/workspace access and local service state have been
confirmed.

### Container-hosted tunnel-client on macOS

The host may run the official client in Docker when native installation is
unavailable. The current OpenAI release is `v0.0.18`; its multi-architecture
image digest is
`sha256:486321616c197fed2d3fbe7d44f22433ce9a1e6c1ee434c0d6652868a5fda5c1`.
For this macOS ARM64 host, `gh attestation verify
oci://ghcr.io/openai/tunnel-client:v0.0.18 -R openai/tunnel-client` succeeded,
and the pinned image reported version `0.0.18+274a5588414819f063d27100a4fb1096aae3830f`.
The following no-network check prints the supported quickstart without
contacting Platform or needing credentials:

```sh
docker run --rm --network none --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --entrypoint /usr/bin/tunnel-client \
  ghcr.io/openai/tunnel-client@sha256:486321616c197fed2d3fbe7d44f22433ce9a1e6c1ee434c0d6652868a5fda5c1 \
  help quickstart
```

Keep the tunnel runtime key in a root/user-restricted file and pass the CLI a
`file:/run/secrets/...` reference from a read-only container mount; do not put
the key in an image, command argument, Compose file, repository environment
file, or terminal history. The client container must be able to reach the
Gateway on its private Docker network. This image/tool preflight does not prove
that a tunnel exists, the runtime key has Tunnels Read + Use, ChatGPT is
associated with the tunnel, or the local Gateway is ready.

## Required deployment state

### Latest observed preview state (2026-10-28)

Read-only Vercel inventory found the latest PR #51 deployment for head
`f054aebe96460fe033dde8d91d7e3bbab0255655`: READY build
`dpl_DFmSmWfMKE2Nbox5ufWDxKBa7Y9p`, target `null`, at
`https://gpu-control-65fenen47-unjunos-projects.vercel.app`. Direct authenticated
Vercel fetches returned `/healthz`=200 with `configured=false` and
`auth_configured=false`; `/readyz`=503 with database, migration, worker,
supervisor, registry, and authentication all false; and protected-resource
discovery=503 `configuration_required`. This confirms a preview build only.
The current preview is not configured or ready for ChatGPT connection or
experiment execution, and does not change the production alias.

### Existing Neon database candidate (read-only inventory, 2026-10-28)

A read-only Neon inventory found an existing `gpu-control-gateway` project with
a ready `production` branch and PostgreSQL 17. Its listed Gateway tables are
still unversioned legacy tables; `gateway_schema_version` was not present in
the table inventory. The inspected run table has the legacy `gateway_runs_v1`
shape, and the control row has `worker_seen_at` but no `supervisor_seen_at`.
This is a candidate database, not a migration acceptance result. No migration,
backup, service stop, or data query was performed. Before using it, identify all
connected services, take and validate the paired database/artifact backup,
verify restore, and run the reviewed migration through the manual migration
unit while application services are stopped. Keep ChatGPT disconnected until
the new schema and both worker heartbeats pass `/readyz`.

### Current production alias checks (2026-10-28)

Vercel reports the production alias is served by deployment
`dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`, target `production`, built from `main` SHA
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. Direct read-only requests observed:

- `/healthz` returns 200 with `configured=true`, `auth_configured=true`, and
  `auth_mode=local_oauth`.
- OAuth protected-resource and authorization-server discovery return 200 and
  advertise the production `/mcp` resource, authorization-code + refresh-token
  grants, PKCE S256, and the `offline_access` scope.
- Unauthenticated `GET /mcp` returns 401 with the advertised bearer metadata
  challenge. This verifies the unauthenticated boundary only; no OAuth grant or
  ChatGPT connection was exercised.
- `/readyz` returns 404 because this production revision predates the readiness
  route and the reviewed local CPU Gateway vertical.

The production alias has configured OAuth, but readiness, database migration,
worker/supervisor availability, CPU registry, and ChatGPT tool execution remain
unverified. Vercel environment-variable metadata was not inspected and no
credentials were read. Recheck `/readyz` on the reviewed deployment and require
200 before connecting ChatGPT.

Latest read-only endpoint recheck (2026-10-28 04:54 UTC): unauthenticated
requests still returned `/healthz`=200 (`configured=true`,
`auth_configured=true`, `auth_mode=local_oauth`), `/readyz`=404, and `/mcp`=401
(`Bearer access token is required`). This confirms the alias is responsive and
the unauthenticated MCP boundary rejects access; it does not identify the
deployed source revision, prove readiness, or establish a ChatGPT connection.

Fresh read-only endpoint recheck (2026-10-28 06:21 UTC): `/healthz`=200 with
configured local OAuth, `/readyz`=404, and
`/.well-known/oauth-protected-resource`=200 advertising read/run/cancel scopes.
The readiness route is still absent. No OAuth grant, authenticated MCP request,
or ChatGPT conversation was attempted; acceptance remains **NOT RUN**.

Before **release or continuous-operation acceptance**, provide all of the
following. A private tunnel may replace the public URL only for a bounded
development smoke; it does not waive the remaining service requirements:

- A stable, reachable HTTPS URL whose `/mcp` route points to this Gateway.
- A persistent PostgreSQL database migrated with `python -m gpu_gateway.worker --init-db`.
- An independent worker that can reach the database and the dedicated local Docker
  host. The API deployment must not receive Docker socket access. The existing
  `docker-compose.yml` is demo-provider-only; `Dockerfile.worker` has no Docker CLI
  or daemon connection. For local CPU execution, provision a dedicated trusted
  worker host, install a compatible Docker CLI, grant only that worker access to
  its daemon, verify `docker info` and the registered immutable image digest, and
  keep that daemon separate from public API and untrusted workloads. Docker socket
  access gives the worker effective host-root authority.
- A separate recovery supervisor must also run against the same database. It
  claims expired leases for already-active runs and can take over a submitting
  intent when the execution-worker heartbeat goes stale, so it can reconcile
  cancellation and pending cleanup without competing for new submissions.
  `/readyz` remains false until both worker heartbeats are fresh.
- Dedicated Linux worker/supervisor service definitions and an environment example
  are available under `gateway/deploy/`. They are templates only: adapt paths/socket group,
  install secrets with restrictive ownership, and verify service-level DB/Docker
  access on the target host before treating this as deployed.
- The systemd templates declare persistent service state directories under
  `/var/lib`; artifact bytes live on the separately mounted
  `/var/lib/gpu-control/artifacts` filesystem. The worker owns artifact writes,
  while the API reads blobs and writes only its sticky probe directory. Verify
  the selected host's service accounts, ownership, and mount before enabling a
  workload.
- A configured authentication path. With external OIDC, configure issuer, JWKS,
  audience/resource, allowed subject, scopes and the MCP client's registration
  method. With built-in single-owner OAuth, run
  `python -m gpu_gateway.worker --bootstrap-auth --bootstrap-auth-ttl 900` after
  schema initialization in the trusted environment, deliver its one-time setup URL
  privately, then verify discovery, client registration, PKCE, token refresh and
  revocation against the live client. Do not retain the setup URL in shell history,
  CI output or deployment logs; it is a credential until consumed or expired.
- Hosted DCR currently accepts only ChatGPT's canonical HTTPS redirect forms:
  `https://chatgpt.com/connector/oauth/{callback_id}` and
  `https://chatgpt.com/connector_platform_oauth_redirect`. The callback-ID form
  is restricted to one URL-safe segment, without a query string; subdomains,
  lookalike hosts, and other paths are rejected. ChatGPT advises copying the
  exact production redirect URI from the MCP server management page.
- Built-in OAuth must show an owner consent page naming the registered client,
  requested scopes, and redirect destination. Authorization-code issuance must
  require the owner's CSRF-protected POST; visiting `/oauth/authorize` by GET
  while signed in is not consent. The implementation has a local regression for
  this boundary, but a live ChatGPT flow has not yet verified its user experience.
- An OAuth authorization server that can keep ChatGPT connected. OpenAI's current
  guidance calls out refresh-token issuance; for OIDC, `offline_access` should be
  requested and advertised. See the refresh-token section in the Help Center guide.
- An operator-reviewed local CPU workload registry and an explicitly enabled,
  time-bounded local CPU admission policy. The shipped policy defaults disabled.

The Vercel alias and OAuth discovery are reachable, but the deployed revision
predates the local CPU vertical. A persistent worker, recovery supervisor,
PostgreSQL/artifact backup acceptance, and ChatGPT tool scan/execution have not
been verified. Do not infer them from `/healthz` or discovery. Do not enter a
local URL or a provider secret into ChatGPT to work around those missing
prerequisites. The local CPU lane additionally needs a reviewed, expiring
operator policy and a dedicated worker/daemon; the demo Compose stack is not
evidence that lane is deployable.

## Live acceptance sequence

1. Verify `/healthz` and `/readyz`. Readiness must report the current migration,
   fresh worker heartbeat, database access and valid workload registry.
2. Add the server to the authorized ChatGPT workspace and complete its OAuth flow.
3. Confirm ChatGPT discovers the expected read, run and cancel tools. Check the
   server's discovered schema against this repository's MCP tool contract.
4. In one conversation, request the registered local CPU smoke. Verify the exact
   run ID, source SHA, image digest, `simulation=false`, `gpu_used=false`, result,
   and cleanup evidence through ChatGPT tool outputs.
5. In a second conversation, list/find the run and retrieve its result. Verify
   owner isolation, idempotent submit, a distinct new-run request, and cancellation.
6. Record redacted request/response evidence, endpoint version, tool snapshot,
   OAuth behavior and the exact worker/database revisions in
   `docs/CHATGPT_ACCEPTANCE.md`. Never include tokens, cookies or database URLs.

The chat connector's confirmation prompts do not replace Gateway authorization,
local admission policy, or any later human spending approval. ChatGPT's write-action
confirmation is a client control; server-side checks remain authoritative.


### Authenticated preview endpoint recheck (2026-10-28 09:00 UTC)

Vercel's authenticated protected-URL fetch reached the PR #51 preview.
`/healthz`=200 reports `configured=false` and `auth_configured=false`;
`/readyz`=503 reports `ready=false` with database, migration, worker,
supervisor, registry, and authentication false;
`/.well-known/oauth-protected-resource/mcp`=503 `configuration_required`.
The preview therefore has a successful build and a reachable process, but is
not configured or ready for ChatGPT. The temporary Vercel share link was used
only for these read-only GETs; no application credentials were supplied.

### Public alias endpoint recheck (2026-10-28 11:13 UTC)

Unauthenticated GETs to `https://gpu-control.vercel.app` returned
`/healthz`=200 (`configured=true`, `auth_configured=true`,
`auth_mode=local_oauth`), `/readyz`=404, protected-resource metadata=200,
authorization-server metadata=200 (authorization code, refresh token, PKCE
S256 and revocation endpoints advertised), and `/mcp`=401 (`invalid_token`,
access token required). This verifies current liveness, OAuth discovery, and
the unauthenticated MCP boundary only. It does not identify the deployed SHA,
prove worker/database readiness, complete an OAuth grant, or establish ChatGPT
tool use. No token or authenticated request was used; acceptance remains
**NOT RUN**.
