# gpu-control

`gpu-control` is a public, local-first control plane for reproducible containerized GPU experiments.

Its purpose is not to send every experiment to a cloud GPU. Its purpose is to make escalation deliberate:

```text
inspect
  -> local container
  -> smallest useful experiment
  -> workload repository + immutable commit
  -> validation / CI / dry-run
  -> RunPod only when GPU compute is actually required
```

> **Current status:** validation and dry-run only. No provider API is called and no paid GPU resource is created yet.

## Why this project exists

GPU experiments become expensive and difficult to debug when source control, containers, CI, provider APIs, and autonomous agents are mixed together without a clear boundary.

`gpu-control` separates those concerns. A workload lives in its own repository. This repository validates the workload identity and resource policy, then eventually submits a bounded GPU job only after cheaper checks have passed.

The repository is public by design. Provider credentials are not stored in source.

## Operating model

The expected workflow is:

1. **Experiment locally in a container.** Validate imports, configuration, entrypoint behavior, outputs, and exit codes before remote execution.
2. **Make the experiment small.** Use the smallest dataset, steps, timeout, process count, and resource footprint that can answer the current question.
3. **Create or select a workload repository.** Keep the workload separate from `gpu-control` and make the execution state reproducible.
4. **Grant repository access deliberately.** Repository creation, collaborator permissions, secrets, and write access remain explicit human-controlled boundaries.
5. **Validate through `gpu-control`.** Run self-tests, request/policy checks, source/container verification, and dry-run gates.
6. **Escalate to RunPod last.** Paid GPU compute is used only when the workload genuinely needs it and the paid run is explicitly authorized.

See [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) for the rationale and detailed gates.

## Agent behavior

This repository is intended to be useful as execution context for coding and automation agents, not merely as a collection of scripts.

Agents operating in this repository must follow [AGENTS.md](AGENTS.md). The central rule is:

> **Paid compute is denied by default. Repository access or a request to prepare an experiment does not authorize GPU spending.**

The repository also contains:

- `.github/copilot-instructions.md` for GitHub Copilot repository context;
- `policies/agent-policy.yaml` as a machine-readable escalation policy;
- `SECURITY.md` for trust and secret boundaries;
- `policies/gpu-policy.yaml` for GPU resource limits.

## Quick start

Requirements:

- Python 3.11+
- `uv`

Clone and install the locked development environment:

```bash
git clone https://github.com/Unjuno/gpu-control.git
cd gpu-control
uv sync --locked --extra dev
```

Run the standalone self-test:

```bash
uv run gpu-control self-test
```

The self-test requires no GPU, no provider account, and no GitHub token. It verifies the CLI, bundled policy, and validation path.

Run the full test suite:

```bash
uv run pytest
```

The package can also be invoked directly:

```bash
uv run python -m gpu_control self-test
```

## Validate a request locally

`validate` checks the workload request and resource policy without launching anything:

```bash
uv run gpu-control validate \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

A successful request returns machine-readable JSON with `status: valid` and `dry_run: true`.

### Request fields

- `target_repo`: GitHub repository in `owner/repository` form
- `target_sha`: immutable 40-character Git commit SHA
- `dockerfile_path`: relative POSIX path, default `Dockerfile`
- `gpu_profile`: policy-defined resource profile
- `max_runtime_minutes`: requested runtime ceiling
- `max_cost_usd`: requested provider-cost ceiling

The public interface does not accept arbitrary shell commands.

## Workload contract

A GPU workload should normally live in a separate repository and be addressable by an immutable commit.

The baseline contract is intentionally narrow:

```text
public or explicitly authorized repository
+ immutable commit SHA
+ Dockerfile
+ locked/reproducible dependencies where applicable
+ finite non-interactive container entrypoint
+ meaningful process exit code
```

The container should start, run a bounded experiment, write outputs, and exit. Interactive SSH sessions are not the default execution model.

## Policy

The CLI ships with a bundled default GPU policy, so installed usage is independent of the current working directory.

Human-editable copy:

```text
policies/gpu-policy.yaml
```

Packaged copy:

```text
src/gpu_control/default_policy.yaml
```

Tests require them to remain identical.

A custom policy can be supplied explicitly:

```bash
uv run gpu-control validate \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20 \
  --policy ./my-policy.yaml
```

The current MVP allows exactly one GPU and constrains runtime, cost, and minimum VRAM by profile.

## GitHub Actions

Two workflows are currently included:

- **CI** — runs locked-environment unit and standalone tests on pushes and pull requests.
- **GPU request dry-run** — manually validates a request through `workflow_dispatch` without creating GPU resources.

Workflows declare minimal permissions and pin third-party Actions to immutable commit SHAs.

Paid compute must never be triggered directly by untrusted pull requests, forks, issues, comments, or public webhooks.

## Planned architecture

```text
Workload repository
        |
        | repository + immutable commit SHA
        v
    gpu-control
        |
        +-- input validation
        +-- agent/resource policy
        +-- source verification
        +-- container verification
        +-- dry-run plan
        +-- bounded job submission
        |
        v
      RunPod
        |
        | asynchronous execution
        v
 containerized workload
        |
        v
 results / status collection
```

Long-running GPU work should not keep a GitHub-hosted runner waiting. Provider integration will use an asynchronous submit/collect lifecycle.

## Security model

Assume every source file, workflow, policy, and Actions log in this public repository is visible to an attacker.

- Never commit API keys, tokens, `.env` files, private datasets, or private checkpoints.
- Provider credentials belong in GitHub Actions Secrets or an equivalent secret store.
- Paid-compute authorization is separate from repository read/write access.
- Pull requests, forks, issues, comments, and `pull_request_target` must not launch paid compute.
- Arbitrary shell commands are not workflow inputs.
- GPU count, runtime, and cost are bounded by policy.
- Provider jobs must have cleanup behavior for success, failure, timeout, and cancellation.
- Unknown price, authorization, policy state, or cleanup capability must fail closed.

See [SECURITY.md](SECURITY.md).

## Repository layout

```text
.github/workflows/              GitHub Actions workflows
.github/copilot-instructions.md GitHub Copilot repository instructions
AGENTS.md                       Normative agent operating policy
docs/OPERATING_MODEL.md         Human-readable staged workflow
policies/agent-policy.yaml      Machine-readable agent escalation policy
policies/gpu-policy.yaml        GPU resource limits
src/gpu_control/                CLI, validation, policy logic, bundled GPU policy
tests/                          Unit, standalone, and repository-policy tests
pyproject.toml                   Python package metadata
uv.lock                          Locked Python dependency graph
```

## Roadmap

1. Standalone CLI, bundled policy, lockfile, and zero-GPU CI. **Done.**
2. Repository-level agent policy and public operating model. **Done.**
3. Verify target repository, commit SHA, and Dockerfile existence.
4. Build the target container and run a CPU-side smoke check where possible.
5. Add the RunPod adapter with fail-closed pricing, authorization, and lifecycle cleanup.
6. Submit GPU jobs asynchronously so Actions runners are released during execution.
7. Collect status, logs, metrics, and outputs.
8. Add additional providers behind the same resource-policy interface if useful.

## Contributing

Contributions should preserve the local-first escalation model and public-repository security assumptions. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
