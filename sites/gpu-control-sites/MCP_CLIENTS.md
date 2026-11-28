# Connect another MCP client

GPU Control has one owner-scoped experiment control plane. ChatGPT and any
compatible remote MCP client can connect to the same MCP URL using their
supported authentication flow. They share the same plans, provider policies,
run history, results, artifacts, and cleanup records. No client receives
provider credentials.

“Use it from another chat, agent, or compatible automation client” means
connecting that client to this remote MCP endpoint and authenticating as the
already linked owner. It does not mean an anonymous public API or a separate
provider-specific integration. Each OAuth client has its own revocable grant,
while owner identity, authorization, budget checks, and the run ledger remain
shared. The MCP contract is the product interface; ChatGPT-specific Sites
identity is one transport adapter to that same owner-scoped contract.
The client and its account/workspace policy must also allow the relevant MCP
tools. A server-side OAuth grant cannot override a client-side restriction or
the native confirmation policy for write-capable tools.

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

Google's official `google-colab-cli` can run an ephemeral Colab job with
`colab run`, including from automation, and tears down the runtime when the job
finishes. CI still needs a Colab identity already available to that runner;
the CLI's OAuth setup is separate from this GPU Control OAuth grant. A direct
CLI or standalone Colab MCP run does not create a GPU Control plan, owner-bound
run record, budget reservation, artifact entry, or cleanup receipt.

For a conversation in ChatGPT or another compatible remote MCP client, use the
GPU Control MCP. Its Colab provider adapter maps the run into the shared plan
and ledger. Do not add a second direct-CLI run path to the conversation: that
would split ownership, recovery, budget checks, and history. If CI-hosted CLI
execution is later needed *inside* GPU Control, the CI runner must implement
the same owner-bound job/lease and exact-plan protocol before it is exposed as
a provider executor. Routine repository CI remains offline and must never
allocate Colab compute.

Likewise, this OAuth flow authenticates an MCP client but does not enable a
provider, create an experiment, or deploy the Site.
