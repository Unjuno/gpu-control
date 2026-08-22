# Parked repository mode

`gpu-control` is currently intentionally parked because there is no active workload that needs GPU execution.

Parked mode is not a degraded state. It is a deliberate safety posture: the control-plane contracts, tests, and provider boundaries remain available, while all billable and generic external-execution paths stay disabled.

## What remains usable

While parked, it is valid to:

- inspect and improve documentation or policy;
- run the locked Python test suite;
- run the offline `gpu-control self-test` and `provider-self-test`;
- validate request syntax and resource policy;
- verify public GitHub repository/SHA/Dockerfile identity;
- run the repository-owned trusted reference container in CI;
- improve provider-neutral lifecycle, serialization, result-policy, or mock-provider tests without enabling live calls.

## What must remain disabled

While `policies/repository-state.yaml` says `mode: parked`:

- no paid RunPod workflow may exist;
- no workflow may reference `secrets.RUNPOD_API_KEY` or the future `paid-runpod` Environment;
- RunPod live calls, live adapter wiring, CLI wiring, and workflow wiring remain false;
- generic external Dockerfile build/run remains disabled;
- authenticated result collection remains disabled until its evidence path exists;
- PR, fork, issue, comment, schedule, `repository_dispatch`, and `pull_request_target` events must not become paid-compute entrypoints.

CI cross-checks these invariants against the existing paid, RunPod, agent, container, and workflow configuration.

## Resume criteria

Do not leave parked mode merely because implementation work is possible. Resume toward live GPU execution only when there is a concrete workload and an explicit human request to activate the path.

Before any paid path can be enabled, the repository must have all prerequisites listed in `policies/repository-state.yaml`, including actual `main` branch protection, required CI checks, the owner-only protected GitHub Environment, environment-scoped RunPod credentials, immutable published-image handling, authenticated workload-completion evidence, and reliable cleanup.

Changing `mode` is a reviewed repository change; it is not itself authorization to spend money. External GitHub settings and runtime evidence still have to pass their independent gates.
