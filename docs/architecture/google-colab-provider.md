# Google Colab provider integration

Status: approved direction; no Colab runtime can currently be started from
ChatGPT Sites.

## Product boundary

The Google `colab-mcp` project is a local stdio MCP bridge to a Colab session
open in a browser. It requires a local MCP client with
`notifications/tools/list_changed`; a hosted ChatGPT Sites MCP worker cannot
spawn or reach that process. Installing the official MCP package in the Sites
worker would therefore not connect the owner's ChatGPT conversation to Colab.

The ChatGPT product path must instead implement a GPU Control provider adapter.
The local Colab MCP remains useful for local Codex/Gemini/Claude workflows, but
is a separate client integration and is not counted as Sites support. For
ChatGPT Chat/Work, the owner connects Google once through a standard OAuth
consent flow; ChatGPT and GPU Control never ask for or receive the Google
password. A server-side refresh token is reused for later jobs, and the owner
is asked to reconnect only after revocation, expiry, or a required scope change.

## Candidate execution path

```text
ChatGPT Chat / Work
  -> GPU Control Sites MCP (owner identity, repo binding, run plan, D1 budget)
  -> Colab adapter (owner-scoped Google OAuth; no workload credentials)
  -> one-shot Colab runtime (pinned source + declared entrypoint)
  -> bounded result bundle returned to owner-scoped run/artifact storage
```

The adapter should use Google's published `google-colab-cli` behavior where
possible, launched as a fixed `colab run` operation without `--keep`. It must
not accept arbitrary CLI arguments, arbitrary notebooks, user-supplied shell,
or a public callback URL. The plan binds the repository, immutable commit,
validated experiment manifest and lock hashes, selected accelerator, maximum
runtime, output paths, owner, provider lease, and idempotency key. Workload code
receives no Google OAuth refresh token, GitHub token, provider credential, or
GPU Control signing key.

## Account connection and quota

Colab's local CLI uses Google OAuth or ADC. Sites cannot reuse a browser's
Google login or the ChatGPT GitHub connector as Colab authorization. A future
`Connect Google Colab` flow needs its own Google OAuth client and owner-bound
connection record. Refresh tokens must be encrypted at rest, scoped to the
least permissions that support the official Colab API, refresh only in the
trusted adapter, and be revocable from GPU Control. Access tokens must never
enter an MCP response, experiment plan, runtime, log, or artifact.

Colab accelerator availability, GPU model, session duration, idle limits, and
compute-unit consumption are dynamic. Before allocating, the adapter must query
current account balance, aggregate usage rate, and active assignment count, then
apply a provider-specific lease expressed in compute units. Do not hardcode a
monthly unit grant or infer an account's balance from a subscription label.
Because the published usage rate is account-level and available hardware can
change, the estimate must include a conservative margin and the run must stop
when its configured CU ceiling is reached. If the account state or bounded CU
exposure cannot be established, keep the route unavailable. A Google AI/Colab
plan does not itself guarantee a particular GPU or session.

## Execution and cleanup requirements

- One run creates one fresh runtime; persistent `--keep`/session mode is not
  allowed for the ChatGPT job path.
- The adapter enforces one active job per owner initially, strict runtime,
  disk, output-size, and concurrency ceilings, and safe handling of an
  ambiguous create/submit response.
- Source is fetched at the exact authorized commit. Its declared manifest and
  lockfile are rehashed before execution. The workload receives only a
  read-only source tree and a bounded output directory.
- Colab has general runtime egress and dynamically managed runtime images;
  do not claim network isolation or immutable host images. Do not mount Google
  Drive or run `colab auth` in a job. The adapter must report the actual Python,
  framework, CUDA, and GPU identity from inside the allocated runtime.
- Cancel and timeout paths must request runtime stop and verify terminal
  release. A process exit is not a cleanup receipt.
- Outputs are untrusted data. Store only bounded artifacts and checksums in
  owner-scoped storage; never execute a returned checkpoint or log content.

## Delivery gates

1. Confirm official CLI license, OAuth scopes, supported automation interface,
   and exact quota output. Pin the CLI release and record its source digest.
2. Add an owner-scoped Google account connection and revoke flow; test token
   encryption, owner isolation, refresh failure, and revocation without
   allocating compute.
3. Implement and offline-test a Colab adapter for capability/quota inspection,
   one-shot submit, idempotent status recovery, cancel, result and cleanup.
4. Wire Colab into the common custom training plan only when the manifest,
   commit, provider lease, maximum compute-unit exposure, and current user run
   intent are all bound to the same plan fingerprint.
5. Run a smallest owner-requested GPU canary; verify an actual GPU, completion,
   output checksums, quota delta, stop/cleanup, and owner isolation. Keep Colab
   disabled if any of these cannot be observed.

The official local Colab MCP does not satisfy these gates and is not evidence
of ChatGPT Sites integration.
