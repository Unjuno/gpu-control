# Google Colab in the ChatGPT experiment workflow

Status: the official hosted MCP endpoint is confirmed, but no Colab provider is
configured in GPU Control yet.

## Available integration

Google now exposes two distinct Colab MCP surfaces; they must not be treated as
interchangeable:

- `https://github.com/googlecolab/colab-mcp` is a local stdio bridge to a
  browser-open Colab session. Google's README says the MCP client must run on
  the user's device and support `notifications/tools/list_changed`; it lists
  Gemini CLI, Claude Code and Windsurf as compatible examples. It is not
  callable from the hosted Sites Worker. The README does not establish that
  ChatGPT's hosted Chat/Work client can launch or connect to this local server.
- `https://colaboratory.googleapis.com/mcp` is Google's hosted Colab API MCP.
  Its live `tools/list` response was read on 2026-11-27 and returned
  `list_runtime_specs`, `create_runtime`, `create_session`, `execute_code`,
  `delete_session`, `delete_runtime`, runtime listing/inspection, and
  subscription lookup.

The local stdio server can be useful for a local coding-agent workflow, but it
does not by itself add Colab to ordinary ChatGPT web conversations or to GPU
Control. Do not install or ask the user to authenticate to that local server as
if it would grant the Sites Worker access. First verify the exact target
client's local MCP support. For the ChatGPT Sites product path, investigate the
hosted API MCP and its OAuth/delegation contract behind the GPU Control
provider adapter.

The hosted endpoint is the integration surface to investigate for Colab. A
direct ChatGPT-to-Colab app can be used as a separate, manually connected tool
when the user's ChatGPT client and plan permit remote MCP write tools. That
connection does not grant the GPU Control Sites Worker access to the user's
Google OAuth token, and its runs are separate from GPU Control's D1 run history
and provider budget leases. It is therefore not the product acceptance path.

The target product path is to select Colab from the same GPU Control
conversation, after the owner connects Google once through an explicit
owner-scoped OAuth flow. Do not ask for a password or copy access/refresh
tokens into chat. Google's third-party MCP authentication requires an OAuth
client ID/secret and does not support dynamic client registration, so first
connection may need Google Cloud project setup and Colab API/MCP enablement.
Check the project's billing requirements before changing project settings.
The ChatGPT app's OAuth session cannot be assumed to be reusable by Sites; the
GPU Control connection needs its own documented delegation and revocation
contract.

## Runtime behavior and safety

- Call `list_runtime_specs` before requesting an accelerator. It reports the
  runtime types the authenticated account is eligible to allocate. Availability
  and quotas are dynamic; account tier does not guarantee a particular GPU.
- `create_runtime` accepts a request ID for idempotency. Save and reuse the
  same request ID after an ambiguous response; never create a second runtime
  merely because the first response timed out.
- Use a run-owned runtime and session. For each execution, provide a fresh
  `executionId`; after a `DEADLINE_EXCEEDED` or `UNAVAILABLE`, repeat the exact
  same call with that ID to resume instead of rerunning training.
- Recover result files before deleting the runtime. Delete only the runtime
  created for that run, then verify it is absent. Colab MCP's `delete_runtime`
  removes the runtime, sessions, files, and state.
- The Colab MCP returns subscription tier, but its published tool list does not
  expose the compute-unit balance or a run-specific price quote. GPU Control
  cannot enforce a precise CU/dollar budget from that information alone. Until
  a trustworthy balance/rate check is available, enforce a strict runtime and
  resource ceiling, never promise a dollar cap, and keep the route unavailable
  for requests that require an exact spend ceiling.
- Code in the runtime is the user's repository code and may have network
  egress. Do not place GitHub tokens, Google credentials, GPU Control keys, or
  provider secrets in the runtime. Upload a pinned source snapshot and bounded
  outputs; treat all logs and artifacts as untrusted data.

## Delivery sequence

1. Define and implement a one-time, owner-scoped Google account connection and
   revocation flow for GPU Control. Do not assume a separate ChatGPT MCP app's
   OAuth token is available to Sites.
2. Discover eligible runtime specs and subscription tier read-only; do not
   allocate a runtime during setup. Record that the current API does not expose
   a balance or per-run quote, so an exact dollar/CU ceiling cannot yet be
   enforced.
3. Implement the Colab adapter as one option in the common GPU Control
   lifecycle. Bind the owner, GitHub installation, immutable commit, manifest,
   exact plan, runtime/resource ceiling, idempotency, cancellation, result
   retrieval, and cleanup receipt. Keep Google credentials in a trusted
   control adapter, never in the workload.
4. Keep direct ChatGPT-to-Colab use documented as a separate escape hatch, and
   never count its out-of-ledger calls as GPU Control acceptance evidence.
5. Do not enable provider execution until independent security review,
   exact-head CI, owner isolation, idempotent recovery, real GPU evidence,
   artifact checksums, and confirmed cleanup all pass.

## References

- [Google announcement for the local Colab MCP server](https://developers.googleblog.com/announcing-the-colab-mcp-server-connect-any-ai-agent-to-google-colab/)
- [Official `googlecolab/colab-mcp` README](https://github.com/googlecolab/colab-mcp#readme)
- [Colab API MCP reference](https://developers.google.com/colab/api/reference/mcp)
- [Google MCP authentication](https://docs.cloud.google.com/mcp/authenticate-mcp)
- [Colab runtime API](https://developers.google.com/colab/api/reference/rest/v1beta/runtimes)
- [Colab usage limits and availability](https://research.google.com/colaboratory/faq.html)
