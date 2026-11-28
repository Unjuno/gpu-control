# Google Colab CLI and GPU Control

This guide separates three ways an agent can use Colab. They have different
authentication and run-history behavior; only the shared GPU Control route
counts as a GPU Control experiment.

## What the official CLI can do

Google's [`google-colab-cli`](https://github.com/googlecolab/google-colab-cli)
can run a Python file on a fresh Colab accelerator and release the VM when the
command finishes:

```bash
uv tool install google-colab-cli
colab run --gpu T4 train.py
```

It also supports explicit session creation, script execution, artifact
download, and stop:

```bash
colab new -s gpu-control-check --gpu T4
colab exec -s gpu-control-check -f train.py
colab download -s gpu-control-check checkpoints/model.bin ./model.bin
colab stop -s gpu-control-check
```

Check `colab --help` for the installed release's exact flags. The CLI's
noninteractive execution commands can run in a CI script once the runner has
an authenticated Colab identity. The current CLI stores OAuth credentials in
the operating system's native keyring; local session metadata and history are
under `~/.config/colab-cli/`. Its documented ADC mode can use credentials
provided through `GOOGLE_APPLICATION_CREDENTIALS` or the normal `gcloud` ADC
chain, subject to Colab account entitlement and API support. A hosted CI
runner does not inherit the user's Mac keyring, and a headless OAuth login may
still require the owner to complete Google's authorization flow. Do not put a
personal refresh token or copied local session file into an ordinary CI secret
just to make a GPU job start. Colab quota, accelerator allocation, and any
compute-unit use remain governed by the Google account.

## Which route to use

| Goal | Route | GPU Control run history |
| --- | --- | --- |
| Check a script in a developer-owned environment | Official `google-colab-cli` | No |
| Let a local MCP agent operate a browser-open Colab session | Google's `googlecolab/colab-mcp` | No |
| Ask ChatGPT or another remote MCP client to run an experiment | GPU Control MCP, with Colab implemented as a provider adapter | Yes, when that provider lifecycle is released and enabled |

The standalone CLI is useful for local development and a separately managed
CI job. It does not call GPU Control's prepare/authorization/submit/status
contract, so its runs, budget reservations, result digests, and cleanup are not
written to the shared owner ledger. Adding a second CLI dispatch route to
GPU Control would split run recovery and authorization. The chat route should
therefore call Google's hosted Colab API MCP from the Sites provider adapter;
the official CLI is not the Sites Worker runtime.

## Chat and other MCP clients

The intended user flow is to connect the Google account once, then ask in
ordinary ChatGPT conversation for a registered repository experiment. The
agent should select a currently eligible provider, keep registration and run
IDs internal, and use the same GPU Control lifecycle for plan, submit, status,
artifact verification, and cleanup. A compatible external MCP client should
authenticate to the same GPU Control MCP and share the same owner ledger; it
should not use its own Colab CLI identity as a bypass.

In the current source candidate, Colab connection and read-only capability
discovery exist, but Colab training prepare/submit/status/result/cleanup are
not connected. `colab_capabilities` must not be interpreted as an executable
route. The official Colab CLI can run independently, but that is not evidence
that a ChatGPT request reached Colab through GPU Control. See the
[Colab provider implementation gates](architecture/google-colab-provider.md)
and [release status](STATUS.md) before relying on a deployed capability.

## CI policy for this repository

Routine pull-request CI remains offline and must not allocate a Colab runtime.
It can validate the pinned source manifest, provider request/response
contracts, recovery logic, and cleanup behavior with fixtures. A live Colab
acceptance workflow would need a separately secured owner identity, explicit
manual dispatch, strict runtime/quota bounds, cleanup verification, and an
artifact digest check. It must not run on ordinary pull requests or create a
second experiment ledger. Until those controls and the shared provider
lifecycle exist, do not add a workflow that submits GPU work directly through
the CLI and calls it a GPU Control acceptance test.

## References

- [Official CLI README and commands](https://github.com/googlecolab/google-colab-cli)
- [CLI automation and authentication design](https://github.com/googlecolab/google-colab-cli/blob/main/docs/04_automation_and_utility.md)
- [CLI ephemeral run lifecycle](https://github.com/googlecolab/google-colab-cli/blob/main/docs/05_run_command.md)
- [Hosted Colab MCP reference](https://developers.google.com/colab/api/reference/mcp)
- [GPU Control Colab provider specification](architecture/google-colab-provider.md)
