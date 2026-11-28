# Google Colab provider integration

Status: in progress. The selected product path is the official hosted Colab API
MCP behind the existing GPU Control MCP. ChatGPT chat/Work and compatible
authenticated MCP clients use the same owner-bound plan, run, budget, result,
and cleanup lifecycle. The
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
   The exact plan must disclose that Google has not supplied a balance or
   per-run price. It must also disclose that Colab-managed runtime egress is
   unrestricted by GPU Control; never place provider/GitHub credentials or
   private user data in that runtime. Internal registration/run IDs stay
   agent-managed.
3. Submit uses the current exact saved plan and a stable UUID requestId. Google
   documents `requestId` idempotency for `create_runtime`; retry an ambiguous
   request only with the same ID. Store the returned operation/runtime identity
   before progressing.
4. Execution uses one run-owned session and one unique `executionId` per code
   call. After `DEADLINE_EXCEEDED` or `UNAVAILABLE`, repeat the same call with
   the same session/executionId to reattach; never rerun training as a retry.
5. Cancellation closes the session created for that run. A plan must explicitly
   state that its run-owned runtime will be deleted after output retrieval; the
   exact write confirmation authorizes that destructive cleanup. Never delete a
   pre-existing or unrelated notebook runtime/session. Retrieve allowlisted
   outputs before runtime deletion, independently compute checksums, then
   verify the owned runtime is absent. If the exact plan did not disclose
   runtime deletion, leave it intact and report cleanup as incomplete.
6. Persist status transitions, provider operation IDs, runtime/session IDs,
   bounded logs, artifacts, and cleanup receipt in the owner-scoped Sites
   ledger. Treat Google errors, workload output, logs, and artifacts as
   untrusted data.

## Long-call and recovery boundary

Google's `execute_code` API cuts off a tool call after 600 seconds with
`DEADLINE_EXCEEDED`, but the kernel code keeps running and the session remains
busy. A retry with the same session and `executionId` reattaches to that exact
execution; it does not start another one while the result is pending. After a
result has been returned, reusing that ID runs the code again. Persist the
exact session and execution ID before calling Google, persist the result before
advancing the run, and never infer that a lost HTTP response means the job
failed or that a completed execution is safe to replay. See Google's
[`execute_code` contract](https://developers.google.com/colab/api/reference/mcp/tools_list/execute_code).

`create_runtime` has a separate stable UUID `requestId` for idempotent runtime
creation; persist it before submitting and reuse it after an ambiguous
response. Runtime creation, code execution, result retrieval, and deletion
must be distinct persisted state transitions. Do not reuse one generic HTTP
timeout or automatic retry policy for all four operations.

The Sites Worker client currently applies a 30-second timeout to every Google
MCP call. Keep that limit for short capability reads. The execution adapter
needs a recoverable call protocol that survives the connected MCP client's
own request deadline. Cloudflare documents no hard wall-clock duration for an
HTTP-triggered Worker while the client remains connected, but work may be
cancelled when that connection ends; `waitUntil()` extends work for only 30
seconds after response or disconnect. Therefore a long Colab execution cannot
depend on one open `training_submit` request or an in-memory promise. Persist
the request identity and make `training_status` resume only the same pending
operation, or use a separately justified durable Cloudflare coordinator. See
[Workers platform limits](https://developers.cloudflare.com/workers/platform/limits/).

Before enabling Colab admission, prove that a disconnected or timed-out chat
request leaves enough durable state to recover the run and delete its owned
runtime without asking the user to resubmit training. A second call with a new
execution ID is a new execution and must never be used as transport recovery.

## Quota and cost semantics

The Colab API MCP's `get_subscription` returns only `FREE`, `PRO`, or `PRO_PLUS`;
`list_runtime_specs` reports current runtime eligibility. Neither returns a
documented compute-unit balance or per-run monetary quote. Google's usage
policy says managed runtimes in the free tier or without a positive Colab
compute-unit balance may not be used for remote control, bypassing the notebook
UI, or distributed-computing workers, and may be terminated without warning.
Therefore, do not submit a GPU Control run when the requested GPU spec is not
currently eligible or the user has not explicitly confirmed in the exact-plan
write action that their Colab account has a positive compute-unit balance.
Recheck tier and eligibility immediately before runtime creation. A prior
attestation is not reusable for a later run. A `FREE` tier without positive
units is not an allowed automated execution route.

Google's FAQ says that paid-account execution reverts to free-tier restrictions
after compute units are exhausted. Google does not document an API that lets
GPU Control read or reserve those units. The exact plan must say `cost_unknown`
and show the maximum run duration and accelerator; it must never describe a
Sites reservation as a Google billing stop. GPU Control cannot purchase
Pay-As-You-Go units, and must not attempt top-up or paid-provider fallback.
If the user requires an exact USD ceiling or cannot confirm positive units,
block Colab submit while leaving other eligible providers available. The
official CLI's `colab usage` uses an undocumented endpoint; do not treat it as
a billing authority. See Google's [Colab usage limits FAQ](https://research.google.com/colaboratory/faq.html)
and [Colab API MCP subscription contract](https://developers.google.com/colab/api/reference/mcp/tools_list/get_subscription).

Colab runtime code has external network access that Sites cannot constrain
through this API. The plan must state `network_egress: unrestricted`; only run
an owner-selected, immutable source that the owner is willing to trust with
that access. Never mount Google Drive, forward secrets, or include private data
in the source/runtime. This is a provider-specific execution boundary and must
not inherit Modal's network-isolation claims.

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
   inputs and response identity. Internal runtime/session reads, creation,
   execution, and deletion must bind to the expected run-owned runtime,
   session, and execution IDs. In particular, `list_sessions` and
   `delete_session` require the exact expected runtime/session, while
   `get_runtime`, `execute_code`, and `delete_runtime` require their persisted
   identity. This prevents generic calls from inspecting or deleting unrelated
   notebook sessions. These operations have no public Sites caller yet; Colab
   remains a read-only public capability surface. The current request timeout
   is not suitable for runtime creation or long training.
3. Add Colab capabilities and prepare logic with immutable source, eligible
   runtime spec, hard runtime/output bounds, and an explicit `cost_unknown`
   semantics until quota evidence is trustworthy.
4. Add idempotent D1 submit and a persisted Colab operation state machine to
   the existing training run. Store stable `requestId`, `sessionId`, and
   `executionId` values before remote calls; `training_status` resumes only
   the exact unfinished call after ambiguity. Do not create a second queue or
   run ledger, and do not automatically replay a completed execution ID.
   Implement cancellation, bounded result/artifact retrieval, and confirmed
   session/runtime cleanup. The exact plan and native execution confirmation
   must explicitly authorize deletion of the run-owned runtime after outputs
   are verified; never delete a runtime that pre-dates the run.
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
