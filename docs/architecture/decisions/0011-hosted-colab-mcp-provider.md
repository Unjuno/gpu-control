# ADR 0011: Integrate hosted Colab MCP as a Sites provider

- Status: accepted for implementation
- Date: 2026-11-28
- Supersedes: ADR 0010

## Context

GPU Control's product requirement is a single ChatGPT Sites conversation and
one owner-scoped run ledger across providers. Google publishes a hosted Colab
API MCP at `https://colaboratory.googleapis.com/mcp` with runtime discovery,
creation, code execution, session/runtime deletion, and subscription lookup.
It uses Google OAuth/ADC; Google's remote MCP does not support dynamic client
registration.

The official Colab CLI supports headless Linux/macOS automation, including an
ephemeral `colab run` job that retrieves outputs and tears down its runtime. It
also exposes account CU usage/balance. Its OAuth/session state lives locally
under `~/.config/colab-cli/`, separate from Sites D1. Embedding the CLI in a
Sites Worker is impossible because a Worker cannot launch a local process.
The repository explicitly retired its former macOS Runner, Keychain bearer,
and `/runner/*` routes; that retired Runner must not return.

## Decision

Implement the hosted Colab API MCP as a Sites provider adapter. Sites remains
the user-facing MCP and the sole authority for owner identity, source and
plan, run lifecycle, internal budgets, result metadata, and cleanup receipt.
Each Sites owner connects their Google account once using a Google OAuth web
client owned by this product. No local Runner or Keychain credential is used.

The OAuth callback must bind the Google account connection to the authenticated
Sites owner with a one-time state/PKCE flow. Refresh credentials are encrypted
at rest using a Cloudflare secret-managed data-encryption key; they are never
returned to tools, passed into the Colab runtime, or included in logs. An owner
can disconnect the Google account, which revokes the grant where supported and
removes the encrypted credential. The credential contract, encryption, and
revocation path require independent security review before enabling runs.

The Sites adapter calls Google's hosted MCP endpoint using the linked owner's
Google OAuth token. Its own tool contract maps the provider lifecycle to the
existing GPU Control plan/run records; it does not expose generic raw MCP calls
to the agent. The direct standalone Colab MCP/CLI integrations remain available
to the owner in other clients, but their runs are not counted as GPU Control
acceptance evidence. A CI job that invokes the CLI directly is likewise outside
the Sites run ledger. Do not expose CLI and hosted-MCP dispatch as two Colab
provider routes; that would fork authorization, retries, history, and cleanup.

## Required controls

1. OAuth uses minimum required scopes, exact callback allowlisting, one-time
   state, PKCE, authenticated Sites-owner binding, verified Google identity,
   CSRF protections, encrypted token storage, bounded refresh, and disconnect.
2. Google account connection is a separate principal from ChatGPT Sites and
   GitHub. A connected account does not by itself authorize experiment submit.
3. Runtime discovery is read-only. Prepare resolves one eligible runtime and
   exact immutable repository source before any runtime allocation.
4. Runtime creation uses a stable UUID requestId, persisted provider operation
   identity, and D1 state recovery. Ambiguous calls resume with the same request
   identity; no blind retry allocates another runtime.
5. Each run uses an isolated session and unique executionId. A timeout resumes
   the same execution ID. Cancellation closes only the session/runtime owned by
   that run; unrelated user notebooks/runtimes remain untouched.
6. Source and outputs are size-bounded and artifact checksums are calculated
   independently. Provider responses, code output, and artifacts remain
   untrusted.
7. Do not claim a precise dollar cap: the hosted MCP reports subscription tier
   and runtime eligibility, not documented per-run CU or monetary cost. A Sites
   reservation is an internal guard only. Require fresh quota/runtime
   eligibility and strict duration limits; fail closed when cost constraints
   require an exact quote.
8. CI is offline by default. Any future live Colab workflow is separately
   credentialed, manual/owner-controlled, quota-bounded, prohibited on ordinary
   pull requests, and not a replacement control plane.

## Implementation sequence

1. Add owner-bound Google OAuth connection lifecycle and encrypted credential
   storage with cross-owner, replay, refresh, and revocation tests.
2. Add a bounded hosted-MCP client with endpoint allowlisting, schema checking,
   request/response size limits, deadlines, and safe OAuth refresh.
3. Add read-only capability projection, then exact-plan preparation with
   immutable source and explicit unknown-cost semantics.
4. Implement D1-backed asynchronous runtime operation tracking, execution
   idempotency, cancellation, artifact transfer, and cleanup verification.
5. Run offline CI and independent security review. Keep admission closed.
6. After the owner connects the Google account, verify one small bounded GPU
   execution under current Colab account quota, independently validate its
   artifact digest and actual GPU, and verify runtime deletion before enabling
   ongoing chat use.

## Consequences

- ChatGPT Agents can choose Colab through the same Sites MCP and run ledger.
- Sites must protect long-lived Google refresh credentials; compromise impact
  is constrained by minimal OAuth scopes and owner-specific records.
- Google OAuth client configuration and user consent are required once. Google's
  DCR restriction means these cannot be silently inferred from Sites or ChatGPT
  sign-in.
- Provider-side dollar spend cannot be stated as hard-bounded without a
  documented quote/quota mechanism. Product copy must disclose this clearly.
- The Google Colab CLI remains usable from a user's local agent or CI for
  independent workloads. Its sessions do not appear in GPU Control's run
  ledger. A future CI execution host must implement the same owner-bound job
  protocol rather than act as a second control plane.

## Current implementation status (2026-11-28)

The Sites source now includes the first slice: owner-scoped OAuth state and
encrypted refresh-token storage, one-time Google identity binding, refresh and
disconnect, and a fixed-endpoint/fixed-tool Google MCP HTTP client. The
read-only `colab_capabilities` tool reports Google account eligibility and
explicitly reports the missing execution lifecycle. This does not yet create a
Colab run, advertise an enabled execution route, or write Colab provider state
into the shared run ledger. Keep admission closed.

## References

- [Official Colab API MCP tools and schemas](https://developers.google.com/colab/api/reference/mcp)
- [Google MCP OAuth and DCR limitations](https://docs.cloud.google.com/mcp/authenticate-mcp)
- [Colab runtime creation idempotency and quota](https://developers.google.com/colab/api/reference/rest/v1beta/runtimes/create)
- [Colab execution resumption and cancellation](https://developers.google.com/colab/api/reference/mcp/tools_list/execute_code)
- [Colab CLI for local agents and CI](https://github.com/googlecolab/google-colab-cli)
- [Sites architecture pivot and Runner retirement](../../decisions/2026-11-11-sites-d1-architecture-pivot.md)
