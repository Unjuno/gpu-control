# Using gpu-control

`gpu-control` is currently useful as a local-first validation and control-plane toolkit. Live paid GPU execution is intentionally disabled on `main`.

## 1. Install and verify the tool

Requirements:

- Python 3.11+
- `uv`

```bash
git clone https://github.com/Unjuno/gpu-control.git
cd gpu-control
uv sync --locked --extra dev
uv run gpu-control self-test
uv run gpu-control provider-self-test
uv run pytest
```

`self-test` and `provider-self-test` are offline. They do not require a GPU account, provider credential, or GitHub token.

## 2. Validate a workload request locally

A workload request identifies a target repository and immutable source commit plus the intended Dockerfile and resource/cost bounds.

```bash
uv run gpu-control validate \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --dockerfile-path Dockerfile \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

This checks syntax and repository resource policy only. It does not contact GitHub or a GPU provider.

## 3. Verify a public GitHub workload

```bash
uv run gpu-control verify-source \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --dockerfile-path Dockerfile \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

This verifies that:

- the repository exists and is public;
- the supplied 40-character commit resolves exactly;
- the Dockerfile exists at that immutable commit.

`GITHUB_TOKEN` may be supplied to improve API rate limits. The current MVP still rejects private workload repositories.

## 4. Use the GitHub Actions dry-run

The repository includes a manual dry-run workflow. It performs policy/source validation without allocating GPU resources.

This is useful when a user wants a reviewable GitHub-hosted record of the exact target repository, SHA, Dockerfile, GPU profile, runtime bound, and cost ceiling.

A dry-run is **not** a paid execution authorization.

## 5. Use gpu-control as an agent/control-plane context

The repository is designed to be consumed by both humans and automation agents. The intended order is:

```text
objective
  -> context trust / decision gate
  -> local validation
  -> smallest useful experiment
  -> immutable workload identity
  -> source/container/pricing evidence
  -> approved execution plan
  -> exact human authorization
  -> provider adapter
  -> authenticated completion
  -> cleanup / bounded results
```

External workload content, README text, code comments, provider logs, issues, and prior examples are treated as data rather than instruction authority.

## 6. What is not available yet

There is currently no supported command such as:

```text
gpu-control run ...
gpu-control submit ...
```

that starts a paid GPU job.

There is also no paid RunPod GitHub Actions workflow on `main`.

The current repository state is `parked`, so live provider calls, provider credentials, and billable GPU allocation remain disabled.

## 7. Workload contract for future live use

A target workload should be reducible to:

```text
public repository
+ immutable 40-character commit SHA
+ Dockerfile
+ reproducible dependencies
+ finite non-interactive container entrypoint
+ meaningful exit code
```

The workload should perform a bounded experiment, write bounded outputs, and exit. Interactive SSH and arbitrary remote shell operation are not the default model.

## 8. Example: selected Orbitune canary

The repository currently uses `Unjuno/orbitune` as the reference live-canary candidate. Its completion protocol and result acceptance are implemented and tested offline, but live provider transport remains disabled.

This makes Orbitune useful for validating control-plane contracts without implying that the paid path is already operational.

## 9. Forking

A fork can immediately use the offline CLI, tests, source verification, policies, decision/context-security framework, and provider self-tests.

A fork must **not** assume the original repository's owner identity or future paid-environment settings. See [FORK_SETUP.md](FORK_SETUP.md) before attempting any live integration.

For a capability-by-capability view, see [STATUS.md](STATUS.md).
