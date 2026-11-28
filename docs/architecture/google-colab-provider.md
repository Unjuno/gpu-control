# Google Colab provider integration

Status: source-integrated; release and live-provider acceptance pending. The
selected product path is the official hosted Colab API MCP behind the existing
GPU Control MCP. ChatGPT chat/Work and compatible authenticated MCP clients use
the same owner-bound plan, run, artifact, and cleanup lifecycle. Source now
includes prepare/submit/status/cancel/artifact/reconcile and D1/R2 persistence.
Local tests do not prove production secrets, migrations, Google OAuth setup, or
live Colab GPU behavior. The official Colab CLI is a separate local/CI entry
point; direct CLI executions do not create GPU Control ledger records and are
not evidence for this provider route. A client that needs shared history
should call the shared GPU Control MCP rather than maintain a second ledger.

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
   request only with the same ID. The operation journal is written before the
   provider call and binds its state to owner/run/fingerprint.
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
6. Persist status transitions, provider operation IDs, encrypted
   runtime/session IDs, bounded results, R2 artifact metadata and cleanup
   receipt in the owner-scoped Sites ledger. Treat Google errors, workload
   output, logs, and artifacts as untrusted data.

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

The Sites Worker client uses short timeouts for capability and lifecycle reads,
and the documented 600-second ceiling for `create_runtime` and `execute_code`.
This bounds the provider call but does not make it durable. Cloudflare
documents no hard wall-clock duration for an HTTP-triggered Worker while the
client remains connected, but work may be cancelled when that connection ends;
`waitUntil()` extends work for only 30 seconds after response or disconnect.
Therefore a long Colab execution cannot depend on one open `training_submit`
request or an in-memory promise. Persist the request identity and make
`training_status` resume only the same pending operation, or use a separately
justified durable Cloudflare coordinator. See [Workers platform
limits](https://developers.cloudflare.com/workers/platform/limits/).

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

1. **Implemented in source:** Google OAuth callback, owner binding, encrypted
   token storage, refresh, disconnect/revocation, and account-isolation tests.
2. **Implemented in source:** the hosted-MCP client enforces endpoint
   allowlisting, bounded request/response sizes, OAuth refresh, fixed tools,
   short/long call deadlines and runtime/session/execution identity checks.
3. **Implemented in source:** capability and prepare resolve an immutable
   public source, eligible runtime spec, hard runtime/output bounds and
   `cost_unknown` semantics. Private repositories are rejected.
4. **Implemented in source:** shared MCP submit/status/cancel/artifact and
   scheduled reconciliation use the D1 operation journal and shared owner-
   bound run ledger. Stable runtime/session/execution IDs recover the same
   operation. Verified output files are stored in private R2 before the
   run-owned runtime is deleted.
5. **Remaining:** independent security review, production OAuth/configuration
   and migration, and one small owner-authorized live GPU
   acceptance with digest and cleanup verification. The submit contract now
   requires an exact-call positive-CU attestation. Routine CI stays offline
   and must not allocate a Colab runtime.
6. Keep admission closed until all remaining release evidence passes.

## Security implementation notes

The runtime proxy URL is a credential-bearing egress target: the proxy token
is sent in a request header, so accepting a provider-returned arbitrary URL
would create an SSRF and credential-forwarding primitive. Validate the URL
against the exact Google Colab runtime proxy origin before any request, reject
redirects, and never expose or log either URL or token. The current contract
allows only `https://colab.googleusercontent.com` with no port, userinfo,
query, or fragment. Reconfirm that origin against Google's live API contract
before implementing runtime file transfer. A mismatch must fail closed rather
than widen the allowlist from observed untrusted response data.

The existing `training_preview` and `training_submit` use cases still apply
Modal-only pricing, admission and runtime assumptions. Do not route Colab into
them by adding provider conditionals. Extract a provider-neutral owner-bound
plan/authorization/ledger contract first, then keep Modal and Colab policy
adapters separate. Colab's `cost_unknown` cannot be represented by a zero-cost
USD reservation; its plan discloses that Google does not expose a balance or
hard spend cap. The source path is wired, and submit enforces the positive-CU
attestation on the exact call. It must not be advertised as released until the
independent review and live acceptance gates pass.

Google's current tool contracts also constrain allocation and cleanup:
`list_sessions` includes user-notebook sessions, and `create_session` with a
matching ID returns an already-open session. Only a session created by this
run may be closed. `delete_runtime` removes every file and every session and
is irreversible, so it is allowed only for a runtime whose creation request
and returned identity are durably bound to the exact run and whose cleanup was
included in that run's plan. A runtime found by listing is never considered
owned or reusable by GPU Control. Keep one run-owned runtime/session per run
until an explicit, reviewed reuse contract exists.

`create_runtime` must persist its UUID `requestId` before the provider call;
after a timeout, retry the identical request and never mint a replacement ID.
Each execution must persist a UUID `executionId` before dispatch. After
`DEADLINE_EXCEEDED` or `UNAVAILABLE`, reattach with the exact same session,
code and execution ID. Because replaying a completed ID starts the code again,
the journal must distinguish pending from completed before retrying. Provider
execution can take 600 seconds, so a caller's request timeout is not the run
state. The owner-scoped operation journal and status-triggered exact-operation
recovery are implemented in source; live response-loss recovery remains an
acceptance item.

`google_colab_run_operations` is linked by a composite owner/run/fingerprint
foreign key to the shared delegated plan ledger. The owner-checked storage
module creates the `runtime_create_pending` row before allocation, reuses the
same persisted `requestId` on retries, scopes transitions by owner and plan
fingerprint, and encrypts runtime connection data with AES-GCM additional
authenticated data bound to owner, run ID and plan fingerprint. Runtime and
session identities are immutable after first persistence. The public MCP
dispatcher now uses these operations for submit and status recovery.

The adapter treats runtime deletion as complete only when the hosted MCP
returns Google's empty protobuf success response. A non-empty or malformed
response leaves the operation in `cleanup_pending`; the next status call
retries cleanup on the same run and does not replay execution. This matches the
[Colab `delete_runtime` MCP output contract](https://developers.google.com/colab/api/reference/mcp/tools_list/delete_runtime).

`google_colab_execution_code.js` now generates a deterministic credential-free
Python runner for an immutable public source and reviewed manifest. It enforces
hash-locked dependency installation, a 360-second execution ceiling, a
run-specific durable receipt, declared-output path/size/checksum capture, and
an actual `nvidia-smi` plus PyTorch CUDA/GPU-name check before invoking the
entrypoint. It rejects private source visibility and mismatched GPU profiles.
The generator is used by the owner-selected Colab submit lifecycle in source;
it does not by itself establish live Colab availability.

`google_colab_runtime_files.js` implements the first artifact transport slice:
GET one declared relative path from the exact run-owned runtime, reject
redirects, enforce the API's 50 MiB per-file limit, and independently verify
the receipt's exact size and SHA-256. Verified files are persisted to private
R2 and returned by the shared owner-scoped chunked `experiment_artifact` tool.

`colab/lifecycle/google_colab_result.js` parses exactly one bounded
`GPU_CONTROL_RECEIPT` record and binds it to the prepared run, public
repository, immutable commit, selected T4/L4 profile, declared output paths,
artifact sizes and checksums.
Ordinary stdout is not control data. A successful result requires explicit
CUDA/GPU evidence, exit code zero, and a metrics artifact; malformed or
duplicate receipts fail closed. The parser is used by the public Colab
lifecycle. The integrated source is locally contract-tested, but requires
exact-head review, production setup and live GPU acceptance before release.

## References

- [Official Colab API MCP tools and schemas](https://developers.google.com/colab/api/reference/mcp)
- [Colab `execute_code` idempotency and cancellation behavior](https://developers.google.com/colab/api/reference/mcp/tools_list/execute_code)
- [Colab API runtime creation and quota semantics](https://developers.google.com/colab/api/reference/rest/v1beta/runtimes/create)
- [Google MCP authentication and no-DCR limitation](https://docs.cloud.google.com/mcp/authenticate-mcp)
- [Official `googlecolab/google-colab-cli`](https://github.com/googlecolab/google-colab-cli)
- [CLI auth and CU usage notes](https://github.com/googlecolab/google-colab-cli/blob/main/docs/04_automation_and_utility.md)
- [Colab usage limits and availability](https://research.google.com/colaboratory/faq.html)
