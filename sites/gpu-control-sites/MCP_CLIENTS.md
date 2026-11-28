# Connect another MCP client

GPU Control has one owner-scoped experiment control plane. ChatGPT remains the
primary client. A compatible remote MCP client can connect to the same MCP URL
using OAuth; it shares the same plans, provider policies, run history, results,
artifacts, and cleanup records. It does not receive provider credentials.

“Use it from another chat or agent” means connecting that client to this remote
MCP endpoint and signing in as the already linked owner. It does not mean an
anonymous public API or a separate provider-specific integration. Each client
has its own revocable OAuth grant, while the owner identity, authorization,
budget checks, and run ledger remain shared.

## Release status

The repository source implements this flow in PR #70. It is not available on a
deployed Site until migration `0036_mcp_oauth_clients.sql` is applied and the
OAuth endpoints are deployed. Check the current Site release record before
trying to connect. Source tests are not proof of a live handshake.

## Requirements

The client must support remote MCP over Streamable HTTP, OAuth authorization
code with PKCE S256, protected-resource and authorization-server metadata, and
Dynamic Client Registration (public clients without a client secret). A client
that cannot complete this flow is not compatible; do not work around that by
copying a bearer token into a prompt or using a provider key as a substitute.

The endpoint is:

`https://gpu-control-sites.unjuno.chatgpt.site/mcp`

On first connection the client registers itself and opens the GPU Control
authorization page. Sign in to GitHub with the same account already linked to
your GPU Control owner, review the requested scopes, and authorize the client.
If the GitHub account has not been linked, first complete the existing
`github_connection_start` flow in ChatGPT, then restart the external client's
connection.

This OAuth implementation is source-only in PR #70 at the current repository
snapshot. It becomes usable from another client only after the migration and
OAuth routes are deployed and a fresh no-compute handshake succeeds. The
release status above takes precedence over this setup procedure.

## Scopes

- `experiments:read` permits capabilities, run listing, status, result, and
  declared artifact reads.
- `experiments:execute` adds the existing plan and lifecycle tools. It is not
  a standing approval to spend money: exact plans, provider admission,
  per-provider budgets, one-use dispatch authorization, and cleanup rules
  still apply.

Do not paste access or refresh tokens into a chat, shell history, source file,
or provider configuration. Let the MCP client store and refresh them in its
credential store. Disconnect/revoke the client from its MCP account settings;
the OAuth revocation endpoint revokes that token family, and refresh-token
reuse also revokes the family.

## What remains a separate integration

Google's standalone Colab CLI and Colab MCP do not become GPU Control clients
by using their own Google login. They must connect to this GPU Control MCP to
share its run ledger; Colab's provider lifecycle remains independently
gated. Likewise, this OAuth flow authenticates an MCP client but does not
enable a provider, create an experiment, or deploy the Site.
