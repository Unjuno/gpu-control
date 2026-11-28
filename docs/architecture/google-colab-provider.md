# Google Colab integration

Status: integration is not implemented. The chosen product direction is to make
Colab another backend of the existing GPU Control experiment lifecycle, with
Google Colab CLI as the first execution mechanism. ChatGPT/Sites remains the
conversation-facing control plane; a user may also operate the same bounded
Colab execution path from a local coding agent or CI client.

## What the official CLI enables

`googlecolab/google-colab-cli` is an official Google Colab project, Apache-2.0
licensed, supporting macOS and Linux. `colab run --gpu … <script>` provisions a
fresh runtime, executes a script, and attempts to release the runtime in a
`finally` path. It has non-interactive pipeline modes. `colab --auth` supports
OAuth2 and Application Default Credentials (ADC); the documented ADC setup
requires the Colab, user-info, cloud-platform, and openid scopes. The CLI stores
OAuth credentials in the local OS keyring and session metadata locally.

This means Colab can be driven from CI or an agent runner. It does **not** mean
that a Cloudflare Sites Worker can execute the CLI: the Worker has no local
process, keyring, or user Google session. CI is an execution host, not a
replacement for the GPU Control MCP or its owner/run/budget ledger.

The CLI's `--timeout` is an idle-output timeout, not a maximum wall-clock
duration. The job wrapper must enforce an absolute deadline independently and
the adapter must call `colab stop`, then verify that the run-owned session is
gone, even after timeout, cancellation, or an ambiguous response. Do not use
`--keep` for managed experiment jobs.

`colab usage` reports compute-unit balance, aggregate CU/hour, and active
assignments according to the CLI documentation. It uses an undocumented
Colab backend endpoint; this observation is not yet a provider-backed hard
spending guarantee. Treat missing, stale, zero, or contradictory CU evidence as
unknown. Until a fresh, validated estimate and a conservative run limit are
available, do not advertise a dollar ceiling or imply that a Sites-side budget
stops Google billing.

## Integration shape

Use one provider-neutral execution contract with two ways to reach the Colab
CLI:

1. **Conversation route:** ChatGPT calls the existing GPU Control Sites MCP.
   Sites authenticates the owner, pins the selected repository commit, validates
   its `.gpu-control/experiment.json`, resolves the requested accelerator and
   a bounded run plan, and records the run. A paired, owner-controlled Colab
   runner claims that exact run and invokes the CLI pinned to an immutable
   upstream commit. The runner connects
   outbound to Sites; Sites never needs a Google token or inbound access to the
   user's machine. This is the route that makes the ordinary ChatGPT request
   work.
2. **Local-agent/CI route:** a developer or pipeline invokes the same versioned
   plan/execution contract through the Colab CLI runner. CI may run contract and
   adapter tests without allocating a Colab runtime. Live CI execution is
   opt-in, isolated to an owner-controlled runner, and must use the same source,
   runtime, duration, quota, artifact, and cleanup rules as the Sites route.

The companion runner is the only component holding Google's credential. It
must be paired to one Sites owner and one Colab account, use an owner-scoped
short-lived runner credential, and accept only server-issued run IDs and signed
plan fingerprints. It must not accept arbitrary shell commands from chat or
forward Google credentials to the workload. The workload gets a pinned source
snapshot and declared inputs only; source/artifact transfer uses a bounded,
short-lived, owner-bound channel. It must preserve run idempotency across lost
responses and never allocate a second runtime to recover an uncertain submit.

Keep the existing GPU Control D1 plan, run, budget, event, artifact, and cleanup
records authoritative. Runner pairing, job claims, heartbeats, cancellation,
provider terminal evidence, and cleanup receipts must be owner-bound and
recoverable. A direct ChatGPT-to-Colab MCP connection can remain a manual
standalone option, but it is not evidence that the GPU Control route works.

## Runtime contract and readiness gates

## Runtime behavior and safety

- Discover eligible runtime shapes and current account usage before allocation;
  availability is dynamic and no accelerator is guaranteed.
- Use one stable idempotency key per plan/run and persist the assigned runtime
  identifier before execution. Resume an ambiguous call using that same key.
- Enforce an absolute run deadline outside the CLI; the CLI's idle timeout does
  not bound total execution time.
- Retrieve bounded output files and compute their checksums before teardown.
  Stop only the run-owned runtime and verify it is absent.
- Validate `colab usage` against actual account behavior and independently
  establish how CU balance/rate relates to current allocations before using it
  as an admission or budget rule. Keep the route disabled if this evidence is
  missing or internally inconsistent.
- Workload code may have network egress. Do not place GitHub tokens, Google
  credentials, GPU Control keys, or provider secrets in the runtime. Treat
  logs, results, and artifacts as untrusted data.

## Delivery sequence

1. Pin a reviewed upstream CLI commit (the repository currently publishes no
   GitHub releases) and define a machine-readable runner protocol:
   pair/revoke, claim/heartbeat, exact plan delivery, cancel, result upload, and
   cleanup receipt.
2. Implement Sites-side owner/run/job-lease records and a short-lived,
   owner-scoped runner credential. Do not add Google OAuth tokens to Sites.
3. Implement the macOS/Linux companion runner around `colab` with an absolute
   deadline, idempotent run identity, bounded source/artifact transfer, strict
   command construction, cancellation, and verified teardown.
4. Add read-only discovery for GPU shapes and CU observations. Prove the
   account-usage signal experimentally without allocating a runtime; classify
   missing or contradictory data as unknown.
5. Wire owner-selected repository preparation and ChatGPT Sites submission to
   Colab only after the runner is online, then test the complete D1-to-runner-to-
   Colab lifecycle with synthetic non-sensitive code.
6. Do not enable general user workload execution until exact-head CI,
   independent security review, owner isolation, idempotent recovery, actual
   GPU evidence, independently checked artifact checksums, and confirmed
   cleanup pass. A first live GPU acceptance run must be separately bounded by
   a current account quota and the user's current cost tolerance.

## References

- [Google announcement for the local Colab MCP server](https://developers.googleblog.com/announcing-the-colab-mcp-server-connect-any-ai-agent-to-google-colab/)
- [Official `googlecolab/colab-mcp` README](https://github.com/googlecolab/colab-mcp#readme)
- [Colab API MCP reference](https://developers.google.com/colab/api/reference/mcp)
- [Google MCP authentication](https://docs.cloud.google.com/mcp/authenticate-mcp)
- [Colab runtime API](https://developers.google.com/colab/api/reference/rest/v1beta/runtimes)
- [Official `googlecolab/google-colab-cli` repository](https://github.com/googlecolab/google-colab-cli)
- [Official CLI ephemeral job design](https://github.com/googlecolab/google-colab-cli/blob/main/docs/05_run_command.md)
- [Official CLI automation and CU usage notes](https://github.com/googlecolab/google-colab-cli/blob/main/docs/04_automation_and_utility.md)
- [Colab usage limits and availability](https://research.google.com/colaboratory/faq.html)
