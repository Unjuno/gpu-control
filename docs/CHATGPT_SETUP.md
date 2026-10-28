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
are satisfied.

For a permitted workspace, the current UI flow is **Plugins → + → Add custom MCP
server**, then enter a public HTTPS MCP endpoint (or select an already configured
Secure MCP Tunnel), choose authentication, acknowledge the risk prompt, create the
plugin and inspect discovered tools. Install it before starting a conversation;
use `@` to select the plugin. Tool-list changes are not automatically applied to a
published connection: an admin must refresh/review the tool snapshot. See OpenAI's
[custom MCP server guide](https://developers.openai.com/api/docs/guides/custom-mcp-server)
and [Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

## Required deployment state

### Observed Vercel deployment (2026-10-28)

The `gpu-control.vercel.app` alias currently reaches a configured Gateway
deployment. Read-only checks observed `/healthz` returning `configured=true` and
`auth_configured=true` in built-in OAuth mode; protected-resource and
authorization-server discovery advertise `https://gpu-control.vercel.app/mcp`,
PKCE S256, refresh tokens, and `offline_access`. An unauthenticated MCP request
returns 401, as expected before authorization.

This is not the reviewed CPU vertical deployment. Vercel reports the production
deployment is built from `main` SHA
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`; that revision has no `/readyz`
route, and a direct request returned 404. The unique deployment URL redirects
to Vercel SSO. The Vercel integration denied access to environment-variable
metadata (403), so database, OAuth bootstrap and other environment settings
were not inspected. No credentials were read, and no ChatGPT OAuth flow or tool
scan was performed.

Before connecting ChatGPT, provide all of the following:

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
- Both systemd templates declare the persistent `gpu-control` state directory
  with mode 0700. Artifact bytes live below `/var/lib/gpu-control/artifacts`, so
  this path remains writable under `ProtectSystem=strict`; verify ownership and
  the mounted filesystem on the chosen host.
- A configured authentication path. With external OIDC, configure issuer, JWKS,
  audience/resource, allowed subject, scopes and the MCP client's registration
  method. With built-in single-owner OAuth, run
  `python -m gpu_gateway.worker --bootstrap-auth --bootstrap-auth-ttl 900` after
  schema initialization in the trusted environment, deliver its one-time setup URL
  privately, then verify discovery, client registration, PKCE, token refresh and
  revocation against the live client. Do not retain the setup URL in shell history,
  CI output or deployment logs; it is a credential until consumed or expired.
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
