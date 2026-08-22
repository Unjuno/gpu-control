# Contributing

Contributions are welcome when they preserve the repository's local-first, policy-gated operating model.

## Before changing behavior

Read:

- `AGENTS.md`
- `SECURITY.md`
- `docs/OPERATING_MODEL.md`
- `policies/agent-policy.yaml`
- `policies/gpu-policy.yaml`

Changes that can create paid resources require substantially more review than validation-only changes.

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
- safe to run from a public repository.

Do not add arbitrary shell execution as a workflow input or provider API escape hatch.

## Workload assumptions

The initial workload contract is a finite container job identified by repository plus immutable commit SHA. Interactive remote sessions and long-lived services are outside the default MVP contract.

## Pull requests

A pull request should explain:

- what layer is changing: validation, policy, source verification, container execution, or provider integration;
- whether the change can create or prolong billable resources;
- what tests cover the new behavior;
- how failure and cleanup behave.

For provider integrations, include tests for allocation failure, execution failure, timeout, cancellation, and cleanup. Unknown price or policy state must fail closed.
