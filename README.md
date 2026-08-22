# gpu-control

`gpu-control` is a reusable control plane for validating and, later, launching containerized workloads on external GPU providers.

The project is public by design. Provider credentials are never stored in the repository.

> Current status: **validation and dry-run only**. No GPU provider API is called and no paid GPU resource is created yet.

## Quick start

Requirements:

- Python 3.11+
- `uv`

Clone the repository and install the locked development environment:

```bash
git clone https://github.com/Unjuno/gpu-control.git
cd gpu-control
uv sync --locked --extra dev
```

Run the standalone self-test:

```bash
uv run gpu-control self-test
```

The self-test requires no network access, no GitHub token, and no GPU. It verifies the installed CLI, bundled default policy, and request validation.

You can also invoke the package directly:

```bash
uv run python -m gpu_control self-test
```

Run the full test suite:

```bash
uv run pytest
```

## Validate a GPU request locally

`validate` checks the public workload contract and policy limits without launching anything:

```bash
uv run gpu-control validate \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

The command returns machine-readable JSON. A successful request has `status: valid` and `dry_run: true`.

### Request fields

- `target_repo`: public GitHub repository in `owner/repository` form
- `target_sha`: immutable 40-character Git commit SHA
- `dockerfile_path`: relative POSIX path, default `Dockerfile`
- `gpu_profile`: policy-defined profile
- `max_runtime_minutes`: requested runtime ceiling
- `max_cost_usd`: requested provider-cost ceiling

No arbitrary shell command is accepted as an input.

## Policy

The CLI ships with a default policy, so installed usage does not depend on the current working directory.

The repository copy is available at:

```text
policies/gpu-policy.yaml
```

The packaged copy is:

```text
src/gpu_control/default_policy.yaml
```

Tests require both copies to remain identical.

To validate against another policy file:

```bash
uv run gpu-control validate \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20 \
  --policy ./my-policy.yaml
```

The MVP policy allows exactly one GPU and constrains runtime, cost, and minimum VRAM by profile.

## GitHub Actions

Two workflows are currently included:

- `CI`: runs the unit and standalone tests on pushes and pull requests.
- `GPU request dry-run`: manually validates a request through `workflow_dispatch` without creating GPU resources.

The GitHub workflows use minimal `contents: read` permissions and pin third-party Actions to immutable commit SHAs.

## Intended workload contract

A future GPU workload is expected to live in a separate public repository. `gpu-control` will identify it by repository plus immutable commit SHA.

The initial workload contract is intentionally small:

```text
public repository
+ immutable commit SHA
+ Dockerfile
```

The target container should be a finite batch job rather than an interactive session:

```text
container starts
  -> workload runs
  -> outputs are written
  -> process exits with a meaningful exit code
```

The next integration milestone is to verify that the repository, commit, and Dockerfile exist and that the image can be built before any provider integration is enabled.

## Planned architecture

```text
Public workload repository
        |
        | repo + commit SHA
        v
    gpu-control
        |
        +-- input validation
        +-- policy validation
        +-- source verification
        +-- container validation
        +-- submit job
        |
        v
 External GPU provider
        |
        | asynchronous execution
        v
 containerized workload
        |
        v
 results / status collection
```

Long-running GPU work should not keep a GitHub-hosted runner waiting. Provider integration will use a submit/collect model rather than polling for hours inside one Actions job.

## Security model

Assume every workflow, policy, source file, and Actions log in this public repository is visible to an attacker.

- Never commit API keys, tokens, `.env` files, private datasets, or private checkpoints.
- Provider credentials will be read from GitHub Actions Secrets only.
- Paid-compute launch workflows will begin with `workflow_dispatch` only.
- Pull requests, forks, issues, comments, and `pull_request_target` must not launch paid compute.
- Arbitrary shell commands are not workflow inputs.
- GPU count, runtime, and cost are constrained by policy.
- Third-party Actions in trusted workflows are pinned to immutable commit SHAs.
- Provider jobs must be terminated on success, failure, timeout, and cancellation.

See [SECURITY.md](SECURITY.md) for the detailed threat model.

## Current repository layout

```text
.github/workflows/       GitHub Actions validation workflows
policies/                Human-editable policy copy
src/gpu_control/         CLI, validation, policy logic, bundled policy
tests/                   Unit and standalone behavior tests
pyproject.toml            Python package metadata
uv.lock                   Locked Python dependency graph
```

## Roadmap

1. Standalone CLI, bundled policy, lockfile, and zero-GPU CI.
2. Verify public repository, commit SHA, and Dockerfile existence.
3. Build the target container and run a CPU-side smoke check where possible.
4. Add the first provider adapter, initially RunPod, with fail-closed pricing and cleanup.
5. Submit GPU jobs asynchronously so Actions runners are released during GPU execution.
6. Collect status, logs, metrics, and outputs.
7. Add other providers behind the same public policy interface.

## License

MIT
