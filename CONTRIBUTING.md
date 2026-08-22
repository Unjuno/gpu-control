# Contributing

Contributions are welcome when they preserve the repository's local-first, policy-gated operating model.

## Before changing behavior

Read:

- `AGENTS.md`
- `SECURITY.md`
- `docs/OPERATING_MODEL.md`
- `docs/CONTAINER_VERIFICATION.md` when changing build/runtime behavior
- `policies/agent-policy.yaml`
- `policies/gpu-policy.yaml`
- `policies/container-verification-policy.yaml` when changing container execution

Changes that can execute untrusted workload code or create paid resources require substantially more review than read-only validation changes.

## Development

```bash
uv sync --locked --extra dev
uv run gpu-control self-test
uv run pytest
```

Keep `uv.lock` synchronized with `pyproject.toml`.

## Design expectations

Prefer changes that are:

- reproducible;
- small and testable;
- provider-agnostic at the public interface;
- explicit about cost and runtime;
- fail-closed around paid compute;
- explicit about trust boundaries;
- safe to publish and safe to run from a public repository.

Do not add arbitrary shell execution as a workflow input or provider API escape hatch.

Provider adapters must consume an `ApprovedExecutionPlan`; they must not allocate resources directly from a raw workload request.

## Workload assumptions

The initial workload contract is a finite container job identified by repository plus immutable commit SHA. Interactive remote sessions and long-lived services are outside the default MVP contract.

A public workload repository is still untrusted code. Source verification is read-only; Docker build/run requires the separate isolation rules in `docs/CONTAINER_VERIFICATION.md`.

## Container execution changes

Generic container execution is currently denied by `policies/container-verification-policy.yaml`.

A pull request that enables or broadens container execution must demonstrate, with automated tests where practical:

- disposable isolated workers;
- no provider credentials or repository write credentials in the workload environment;
- no privileged mode, host mounts, host networking, Docker socket, or SSH forwarding;
- bounded wall-clock time, CPU, memory, process count, logs, and artifacts;
- offline restricted runtime defaults;
- explicit authenticated authorization for workload code execution;
- hostile Dockerfile/runtime cases;
- separation from later provider-credential jobs.

Do not enable generic execution first and promise isolation later.

## Pull requests

A pull request should explain:

- what layer is changing: validation, policy, source verification, container execution, execution-plan gating, or provider integration;
- whether the change executes untrusted workload code;
- whether the change can create or prolong billable resources;
- what credentials are present in each execution stage;
- what tests cover the new behavior;
- how failure and cleanup behave.

For provider integrations, include tests for allocation failure, execution failure, timeout, cancellation, and cleanup. Unknown price, missing approved execution plan, or unknown policy state must fail closed.
