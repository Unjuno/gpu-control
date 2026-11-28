# ADR 0010: Integrate Colab CLI through an owner-controlled runner

- Status: accepted for implementation
- Date: 2026-11-28
- Scope: Google Colab CLI integration with the existing GPU Control Sites MCP

## Context

The product's primary experience is an ordinary ChatGPT conversation: the
owner asks to run an experiment, the agent selects an eligible provider, and
GPU Control prepares, submits, monitors, and returns the run with artifacts
and cleanup evidence. Colab must join that same lifecycle; a standalone Colab
MCP connection or an ad hoc CI workflow would fragment run history and
authorization.

Google's official `googlecolab/google-colab-cli` provides a usable execution
primitive: fresh CPU/GPU/TPU runtime allocation, non-interactive script
execution, file transfer, status/usage inspection, and a `colab run` command
that attempts teardown. It supports OAuth2 or ADC and stores OAuth credentials
in the local OS keyring. The documented timeout is an idle-output timeout, so
it is not a wall-clock safety boundary. A Cloudflare Sites Worker cannot run a
local CLI process or read the owner's keyring.

## Decision

Keep ChatGPT Sites MCP and its D1 owner, plan, run, budget, event, artifact,
and cleanup records as the sole user-facing control plane. Add a separately
installed, owner-controlled Colab runner that connects outbound to Sites and
executes only exact, server-issued Colab plans through the official CLI pinned
to a reviewed immutable upstream commit. The upstream repository currently
publishes no GitHub releases.

The runner holds the Google credential locally. It never sends that credential
to Sites, ChatGPT, CI logs, or the experiment workload. Sites authenticates and
authorizes each run as it does for other providers; a short-lived runner
credential binds one runner to one owner and is revocable independently of the
Google account credential.

This same protocol should support a local coding agent and a user-controlled CI
runner. CI is an optional execution host for the runner, not a new GPU provider
or a separate source of truth. Live CI must not be enabled by default.

## Required protocol boundaries

1. Pairing is explicit, owner-scoped, one-time, short-lived, and revocable.
   Store only a verifier/hash server-side. Never accept a runner identity from
   user-controlled job payloads.
2. Sites issues immutable jobs containing the owner, run ID, plan fingerprint,
   repository and commit, manifest digest, accelerator request, absolute
   deadline, output limits, and cleanup requirement. The runner accepts no
   arbitrary shell command and cannot widen the plan.
3. Job claim and lease renewal are idempotent and fenced. A lost submit
   response resumes the same run/runtime identity; it never creates a second
   runtime automatically.
4. Provide source as a pinned, bounded snapshot over a short-lived
   owner-bound transfer URL. Workload code receives no Google, GitHub, Sites,
   or provider credentials. Treat source instructions, logs, and artifacts as
   untrusted data.
5. Enforce an absolute deadline outside `colab run` because its CLI timeout
   only bounds silence. Cancellation stops the exact run-owned Colab session.
   The runner reports provider state and verifies session absence before the
   Sites run is considered cleaned up.
6. Bound artifact count/bytes, calculate digests independently on the runner
   and Sites, and retrieve artifacts before runtime deletion.
7. Read GPU availability and CU data before plan acceptance. Since `colab
   usage` reads an undocumented endpoint and does not represent a provider
   billing stop, missing/stale/contradictory usage data blocks exact spend
   claims. A D1 reservation is a product guard, not a Colab charge cap.

## Alternatives considered

- **Run the CLI inside the Sites Worker:** rejected because Workers cannot
  spawn the process or access the owner's local OAuth/keyring state.
- **Call Colab's hosted API MCP directly from ChatGPT:** useful for a separate
  manual integration, but it bypasses GPU Control's owner-bound run ledger
  unless reimplemented as a provider connector. It does not provide the
  requested single experiment workflow by itself.
- **Put the Google credential in a hosted service or repository secret:**
  deferred. It expands credential blast radius, creates a new credential
  lifecycle, and makes account-level Colab entitlement and CU semantics
  harder to attribute safely.
- **Use GitHub Actions as the product control plane:** rejected. It would
  require a second authorization/run history and would not make Colab a
  selectable provider in the current ChatGPT Sites workflow.

## Delivery sequence

1. Define the versioned runner protocol and its threat model.
2. Implement D1 job claims, leases, runner pairing/revocation, and bounded
   source/artifact transfer. Keep provider admission closed.
3. Implement the macOS/Linux runner wrapper with CLI pinning, isolated config
   directory, credential redaction, absolute deadlines, cancellation, and
   cleanup verification. Add mocked protocol/CLI tests and CLI version checks.
4. Verify capability/usage discovery without allocating compute. Resolve how
   CU evidence maps to the account's current limits; fail closed when unknown.
5. Exercise synthetic non-sensitive code end to end, then independently
   review the security boundary and exact-head CI.
6. Only then enable a single bounded real-GPU acceptance run under current
   quota/cost conditions and record actual GPU, outputs, digests, and teardown.

## Consequences

- ChatGPT remains the one conversational front door and internal IDs stay
  agent-managed.
- Colab Google authentication occurs once on the owner-controlled runner; the
  runner must be online for the ChatGPT route to use Colab.
- A local Mac runner is easy to start with but is unavailable while that Mac
  is offline. A dedicated or CI runner can improve availability while keeping
  the same protocol and owner control.
- Colab usage limits, GPU availability, and account billing remain controlled
  by Google. GPU Control must never describe its own reservation as a provider
  billing cap.

## References

- [Official `googlecolab/google-colab-cli`](https://github.com/googlecolab/google-colab-cli)
- [CLI ephemeral job lifecycle](https://github.com/googlecolab/google-colab-cli/blob/main/docs/05_run_command.md)
- [CLI auth and compute-unit usage notes](https://github.com/googlecolab/google-colab-cli/blob/main/docs/04_automation_and_utility.md)
- [GPU Control Colab integration specification](../google-colab-provider.md)
