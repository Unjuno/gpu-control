# Google Colab provider integration

Status: in progress. The selected product path is the official hosted Colab API
MCP behind the existing GPU Control MCP. ChatGPT chat/Work is the primary
client; compatible authenticated MCP clients should share its owner-bound
plan, run, budget, result, and cleanup lifecycle. The
current code includes owner-bound OAuth storage, a bounded Google MCP client,
and read-only capability discovery. Provider execution, unified run records,
and live availability are not yet implemented. `colab_capabilities` reports
this blocker explicitly. The official Colab CLI is a separate local/CI entry
point; its executions do not create GPU Control ledger records or substitute
for this lifecycle. A later CLI client should call the shared GPU Control MCP
instead of keeping a second run ledger or bypassing its authorization.

## Product and client paths

Google publishes two relevant interfaces:

- `https://colaboratory.googleapis.com/mcp` is Google's hosted Colab API MCP.
  It exposes runtime eligibility and listing, runtime/session creation,
  execution, deletion, and subscription lookup. Use this for the Sites
  provider adapter so ChatGPT's run continues to be recorded in GPU Control.
- [`googlecolab/google-colab-cli`](https://github.com/googlecolab/google-colab-cli)
  is an official Apache-2.0 CLI for macOS/Linux. It can provision a Colab
  runtime and run a script non-interactively in CI or a local agent. It is a
  useful standalone route for non-ChatGPT clients, but it does not connect a
  run to Sites D1 and must not recreate the retired macOS Runner, Keychain
  bearer, or `/runner/*` routes. CI use is not a substitute for the ChatGPT
  provider integration.
- `googlecolab/colab-mcp` is a local stdio MCP server for a browser-open Colab
  session. It is also a standalone client integration; it does not give Sites
  the user's Google identity or place those runs in the GPU Control ledger.

Google's hosted MCP uses OAuth 2.0 or ADC; Google does not support dynamic
client registration for its remote MCP servers. The Sites route therefore
needs a configured Google OAuth web client and a one-time owner-scoped Google
account connection. The Google account is authorized directly by Google; never
ask for its password or pass tokens through ChatGPT. Keep access/refresh tokens
out of tool outputs, logs, source bundles, and Colab workloads. Store any
refresh credential encrypted at rest under an owner-keyed D1 record, using a
Cloudflare secret-managed encryption key, and provide an explicit disconnect
that revokes/erases the connection. The connection must be independent from the
existing ChatGPT Sites sign-in and GitHub App installation.

The Google OAuth consent screen, OAuth client, callback URI, Colab API/MCP
enablement, and any verification requirements are external prerequisites.
Implementation must report the exact missing prerequisite instead of
pretending that Sites authentication automatically grants Google access.

## Shared lifecycle contract

1. Capabilities use the authenticated owner's current Google connection to
   list eligible Colab runtime specs and report the connected account in
   redacted form. Do not allocate a runtime during capability discovery.
2. Prepare pins the selected GitHub repository and immutable commit, validates
   the existing experiment manifest and dependency lock, resolves one eligible
   runtime spec, and records a Colab-specific duration/compute-unit policy.
   Internal registration/run IDs stay agent-managed.
3. Submit uses the current exact saved plan and a stable UUID requestId. Google
   documents `requestId` idempotency for `create_runtime`; retry an ambiguous
   request only with the same ID. Store the returned operation/runtime identity
   before progressing.
4. Execution uses one run-owned session and one unique `executionId` per code
   call. After `DEADLINE_EXCEEDED` or `UNAVAILABLE`, repeat the same call with
   the same session/executionId to reattach; never rerun training as a retry.
5. Cancellation closes only the session and runtime created for that run. Do
   not delete a user's unrelated notebook runtime or session. Retrieve
   allowlisted outputs before deletion, independently compute checksums, then
   verify the owned runtime is absent.
6. Persist status transitions, provider operation IDs, runtime/session IDs,
   bounded logs, artifacts, and cleanup receipt in the owner-scoped Sites
   ledger. Treat Google errors, workload output, logs, and artifacts as
   untrusted data.

## Quota and cost semantics

The Colab API MCP can report the user's subscription tier and eligible runtime
specs, but it does not expose a documented per-run monetary quote or compute
unit balance. Google's FAQ says a paid user's Colab execution falls back to
free-tier policies and restrictions after their compute-unit balance is
exhausted. This makes remaining units an availability limit, not a per-run
price quote or a provider-side dollar cap. The CLI's `colab usage` command
reports a balance and aggregate CU/hour through an undocumented Colab endpoint;
do not use that private endpoint as a billing authority. A Sites-side budget
reservation therefore cannot be described as a Google billing stop. Until a
trusted and fresh account limit can be enforced, show the account's current
quota limitations, set strict run duration/GPU/session bounds, and do not
promise a dollar ceiling. If the user requires an exact spend cap, block Colab
submission while allowing other eligible providers. See Google's [Colab usage
limits FAQ](https://research.google.com/colaboratory/faq.html).

Runtime creation can be slow and quota-limited. Google documents
`FAILED_PRECONDITION` when eligibility, capacity, or usage limits prevent
allocation and `RESOURCE_EXHAUSTED` for API rate limits. Do not silently fall
back to a paid provider or claim GPU availability from subscription tier alone.

## Implementation sequence

1. **In progress:** Google OAuth connection, callback, owner binding, encrypted
   token storage, refresh, disconnect/revocation, and account-isolation tests.
   The current implementation is local to Sites and is not deployed.
2. **In progress:** the hosted-MCP client enforces endpoint allowlisting,
   bounded request/response sizes, OAuth refresh, and a fixed tool allowlist.
   `google_colab_mcp_contract.js` validates exact runtime/session/execution
   inputs and response identity. These operations have no public Sites caller
   yet; Colab remains a read-only public capability surface. The current
   request timeout is not suitable for runtime creation or long training.
3. Add Colab capabilities and prepare logic with immutable source, eligible
   runtime spec, hard runtime/output bounds, and an explicit `cost_unknown`
   semantics until quota evidence is trustworthy.
4. Add an owner-scoped durable job mechanism supported by the Sites host, then
   idempotent D1 submit, asynchronous operation/status reconciliation, session
   execution recovery, cancellation, result retrieval, and confirmed session
   cleanup. Do not delete a runtime unless the owner explicitly asks.
5. Keep CI offline by default. Use mocks/contracts for routine CI; a separate
   owner-controlled live Colab acceptance workflow may be added only when its
   credential, quota, cost, and cleanup bounds are verified and the workflow
   cannot allocate on ordinary pull requests.
6. Keep Colab admission closed until exact-head CI, independent security
   review, Google-account owner isolation, one bounded live GPU run, digest
   verification, and cleanup verification pass.

## References

- [Official Colab API MCP tools and schemas](https://developers.google.com/colab/api/reference/mcp)
- [Colab `execute_code` idempotency and cancellation behavior](https://developers.google.com/colab/api/reference/mcp/tools_list/execute_code)
- [Colab API runtime creation and quota semantics](https://developers.google.com/colab/api/reference/rest/v1beta/runtimes/create)
- [Google MCP authentication and no-DCR limitation](https://docs.cloud.google.com/mcp/authenticate-mcp)
- [Official `googlecolab/google-colab-cli`](https://github.com/googlecolab/google-colab-cli)
- [CLI auth and CU usage notes](https://github.com/googlecolab/google-colab-cli/blob/main/docs/04_automation_and_utility.md)
- [Colab usage limits and availability](https://research.google.com/colaboratory/faq.html)
