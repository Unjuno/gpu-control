# ADR 0012: Authenticate multiple MCP clients through owner-bound OAuth

- Status: source implemented; release acceptance pending
- Date: 2026-11-28
- Scope: authenticated access to the GPU Control Sites MCP from ChatGPT and
  other MCP-capable clients

## Context

The Sites Worker currently derives the owner only from ChatGPT's trusted
`oai-authenticated-user-id` request header and a fixed owner allowlist. That
works for the ChatGPT-hosted connector, but a local agent, Codex, or another
MCP client does not receive that platform header. The Colab CLI and local
Colab MCP are separate execution surfaces and do not write to GPU Control's
owner-scoped plans, budget reservations, run ledger, artifacts, or cleanup
records.

The product requirement is one experiment control plane with more than one
client. Client-specific credentials must identify the same owner and preserve
the existing exact-plan, admission, provider-budget, and cleanup controls.

## Decision

Implement standard OAuth authorization for non-ChatGPT MCP clients. The Sites
MCP is the OAuth-protected resource server; token issuance is a logically
separate authorization-server module, even if it shares the same Worker and
D1 deployment. Use authorization code with PKCE, protected-resource and
authorization-server discovery, strict audience binding to the GPU Control
MCP, and scoped short-lived access tokens. Support refresh-token rotation and
per-client revocation. Token family replay is tested; concurrent Cloudflare D1
execution and a real external-client handshake remain release checks.

Use the existing GitHub App OAuth identity proof to link an external OAuth
login to the same Sites owner. Persist the verified immutable GitHub user ID
beside the owner-bound installation record; never use an account login name,
email address, user-supplied owner ID, GitHub installation ID, or callback
query as identity. A client must complete the browser OAuth flow as that
already-linked GitHub user. If the owner has no verified link, fail with an
explicit connection-required response.

The existing ChatGPT header path remains a separate trusted transport adapter
and resolves to the same owner principal. Both transports call the same
owner-scoped domain operations. Neither transport can bypass exact-plan
authorization, provider policy, one-use dispatch, or cleanup verification.

## Security and compatibility requirements

1. Follow the current MCP authorization specification: publish protected
   resource metadata, validate bearer tokens at the HTTP boundary, reject
   wrong audience/issuer/expiry/scope, and return the required `401` challenge.
2. Do not mint a persistent API key through a ChatGPT tool or put bearer
   credentials in a conversation, tool result, URL, log, or workload.
3. OAuth client registration must validate public-client metadata and exact
   redirect URI matches. Do not allow open redirects, arbitrary token
   audiences, wildcard redirect hosts, or implicit grants.
4. Keep access tokens short-lived and refresh tokens rotated, hashed at rest,
   owner-bound, client-bound, single-use, and revocable. Reuse after rotation
   revokes that client's token family.
5. Split read and execution scopes. Execution scope permits calling the
   existing exact-plan MCP operation but does not itself approve a plan or
   enable a provider.
6. Keep secrets out of MCP schemas and tool output. Store any signing or
   client-authentication material as Cloudflare secrets, never D1 plaintext.
7. Preserve ChatGPT tool names and input/output schemas. Do not turn this
   authentication migration into a second experiment API or run ledger.

## Alternatives rejected

- **Keep only the ChatGPT identity header:** cannot authenticate another MCP
  client and does not satisfy the multi-client product requirement.
- **Long-lived personal API keys:** nonstandard client setup, broad bearer
  lifetime, difficult rotation and accidental transcript leakage.
- **Let each client call Google's Colab CLI/MCP directly:** creates a separate
  authorization and run history and bypasses GPU Control's provider policy,
  owner-scoped records, and cleanup evidence.
- **Use the GitHub App installation ID or username as a bearer identity:**
  neither proves the caller controls the linked GitHub user account.

## Delivery sequence

1. Add immutable GitHub subject ID to the owner-link flow with a forward
   migration and tests for account-switch, relink, and concurrent callbacks.
2. Implement OAuth metadata, client registration, PKCE authorization/code
   exchange, access-token verification, owner principal resolution, scope
   checks, refresh rotation, and client revocation as isolated modules.
3. Adapt the MCP HTTP boundary to accept either the trusted ChatGPT identity
   or a validated OAuth principal; keep anonymous status pages public and
   every tool owner-authenticated.
4. Source tests cover owner resolution, wrong audience, token expiry through
   the verifier, revocation, refresh replay, redirect attacks, and scope gates.
   Add an architecture rule that identity parsing is confined to the
   transport/authentication boundary.
5. Connect a non-ChatGPT MCP client to a non-production endpoint and verify
   capabilities, prepare/read, and a no-compute lifecycle before considering
   any provider execution. Keep repository mode parked.

## Consequences

- ChatGPT and other compatible MCP clients use the same GPU Control plans and
  run records after owner-bound authentication. ChatGPT's trusted identity
  header remains one transport adapter; it does not define a separate product
  contract or ledger.
- The official Colab CLI remains a standalone developer tool. It is not
  described as a GPU Control client until it authenticates to this MCP instead
  of using a separate Colab credential and execution path.
- Account-linking and token migrations are release gates. The checked-in
  source now implements the protocol, but external clients are not supported
  until migration `0036`, GitHub OAuth callback settings, deployed metadata,
  and a fresh no-compute client handshake are verified.
