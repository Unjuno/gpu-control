# gpu-control

A reusable GitHub Actions control plane for validating and launching containerized workloads on external GPU providers.

## Status

`gpu-control` is in an early, safety-first bootstrap phase. The current milestone does **not** launch or bill GPU resources. It validates experiment requests and policy locally in GitHub Actions before any provider integration is enabled.

## Goals

- Keep GPU orchestration separate from model repositories.
- Accept a public GitHub repository and immutable commit SHA as the workload source.
- Validate inputs, runtime limits, cost limits, and GPU profiles before launch.
- Keep provider credentials in GitHub Actions Secrets only.
- Avoid holding a GitHub-hosted runner open while a long GPU job is running.
- Add RunPod as the first provider without coupling the public interface to one vendor.

## Planned flow

```text
Public workload repository
        |
        | repo + 40-char commit SHA
        v
    gpu-control
        |
        +-- input validation
        +-- policy validation
        +-- dry-run plan
        |
        v
 External GPU provider
        |
        v
 containerized workload
```

## Current dry-run interface

The initial workflow accepts:

- `target_repo`: `owner/repository`
- `target_sha`: exactly 40 hexadecimal characters
- `dockerfile_path`: relative path, default `Dockerfile`
- `gpu_profile`: policy-defined profile
- `max_runtime_minutes`: requested upper bound
- `max_cost_usd`: requested upper bound

The first implementation is intentionally dry-run only. No provider API key is required yet.

## CI smoke test

Pull requests run the validation test suite on a standard GitHub-hosted Ubuntu runner. This provides a zero-GPU, zero-provider-cost smoke test for the control plane before any paid compute integration is enabled.

## Security model

This repository is public by design. Assume every workflow, policy, source file, and Actions log is visible to an attacker.

- Never commit API keys, tokens, `.env` files, private datasets, or private checkpoints.
- Provider credentials will be read only from GitHub Actions Secrets.
- GPU launch workflows will start with `workflow_dispatch` only.
- Untrusted PRs, issues, comments, forks, and `pull_request_target` must not launch paid compute.
- Arbitrary shell commands are not accepted as workflow inputs.
- GPU count, runtime, and cost are constrained by policy.
- Third-party Actions used in trusted workflows are pinned to immutable commit SHAs.

See [SECURITY.md](SECURITY.md) for details.

## Development

Requires Python 3.11+.

```bash
python -m pip install -e '.[dev]'
pytest
```

Validate a request locally:

```bash
gpu-control validate \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

## Roadmap

1. Input and policy validation with dry-run Actions.
2. Public repository / commit checkout validation.
3. Container build and CPU smoke test.
4. RunPod provider adapter and strict lifecycle cleanup.
5. Asynchronous submit/collect flow so Actions runners are not held during GPU execution.
6. Additional providers behind the same policy interface.

## License

MIT
