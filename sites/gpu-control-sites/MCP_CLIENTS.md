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

## Connect and verify

1. Add the remote MCP endpoint shown below to the client's MCP settings. Choose
   OAuth or "sign in" when prompted; do not configure a provider API key.
2. Complete the GPU Control authorization page. Sign in with the GitHub account
   already linked to the GPU Control owner and grant the scopes the client
   needs. Use `experiments:read` to inspect providers and existing runs. Add
   `experiments:execute` only when the client is meant to prepare and submit
   experiments.
3. In a new client conversation, ask it to list current provider capabilities
   and existing runs without starting an experiment. The agent should call
   `experiment_capabilities` and `experiment_list`; this confirms OAuth, tool
   discovery, and owner scoping without allocating compute.
4. For an execution request, tell the agent the repository or workload and the
   intended provider/cost constraint in ordinary language. The agent resolves
   current capabilities, prepares the exact plan, and uses the shared ledger;
   provider IDs and retry keys are server-managed. Client-side write
   confirmations and exact-plan authorization still apply.

## Use it from a conversation

After the client is connected and the current release exposes the requested
route, use ordinary language. Do not look up registration IDs, run IDs, commit
SHAs, or retry keys yourself. For example:

> https://github.com/owner/repository の実験をGPU Controlで実行してください。まず現在の
> capabilitiesを読み、このリポジトリを実行できるproviderと必要条件を
> 確認してください。無料経路を優先し、有料providerへは切り替えないで
> ください。実行できるなら、最新の正確なplanを作ってから実行し、同じrunの
> 結果、artifactのchecksum、cleanupまで確認してください。必要な内部IDは
> 自分で取得して保持してください。実行に必要なアカウント接続や、私が
> まだ示していない費用・quotaの判断があれば、そこで止めて具体的に教えて
> ください。

The agent should use the currently advertised tools and route capabilities. A
repository connection or registration is not itself proof that the source can
run. If no admitted provider supports that repository, the agent must report
the blocker rather than substitute a fixed demo or a paid provider. A current
request to run covers one exact prepared plan; a client may still show its
native write-action confirmation. The agent should not ask the owner to repeat
the same request after preparation.

For a read-only check, say: “GPU Controlで現在使えるprovider、workload、費用・
quota上の制約を確認してください。実験は開始しないでください。”

These prompts describe the intended client-neutral workflow, not proof that
every route is deployed. The release status above and live capability response
take precedence. Google Colab plans can expose quota usage that the provider API
does not report; the agent must show that limitation and obtain the required
owner attestation instead of treating a subscription tier as free compute.

ChatGPT's existing GPU Control Sites connection uses ChatGPT's authenticated
Sites identity. It does not need the separate OAuth registration described
here. Codex or another compatible MCP client uses the external OAuth flow and
the same owner-scoped tools and records. Whether an agent can invoke a write
tool also depends on that client's account, workspace, and tool-permission
settings; connecting successfully does not guarantee write access. OpenAI's
[current custom-MCP guidance](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
limits personal Pro connections to read/fetch, while full MCP write support is
available on Business, Enterprise, and Edu. Verify the permissions offered by
the actual ChatGPT connection rather than assuming an external-client grant
changes them. [Codex's MCP setup guide](https://developers.openai.com/learn/docs-mcp)
documents adding a remote HTTP MCP endpoint and reuses the same MCP config
between Codex CLI and the IDE extension; authentication is completed by the
selected MCP server/client flow.

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
