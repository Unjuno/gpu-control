# Parked repository mode

`gpu-control` is currently intentionally parked even though an active workload has now been selected. The frozen workload candidate is Orbitune commit `dfb878b91f258e8ca496fac5e457dfbc4216ba89`, recorded in `policies/repository-state.yaml`.

Parked mode is not a degraded state. It is a deliberate safety posture: the control-plane contracts, tests, and provider boundaries remain available, while all billable and generic external-execution paths stay disabled until the remaining activation prerequisites are satisfied.

## What remains usable

While parked, it is valid to:

- inspect and improve documentation or policy;
- run the locked Python test suite;
- run the offline `gpu-control self-test` and `provider-self-test`;
- validate request syntax and resource policy;
- verify the selected public GitHub repository/SHA/Dockerfile identity;
- run the repository-owned trusted reference container in CI;
- improve provider-neutral lifecycle, serialization, result-policy, or mock-provider tests without enabling live calls;
- prepare immutable image evidence and completion-evidence design for the selected workload without authorizing spend.

## What must remain disabled

While `policies/repository-state.yaml` says `mode: parked`:

- no paid RunPod workflow may exist;
- no workflow may reference `secrets.RUNPOD_API_KEY` or the future `paid-runpod` Environment;
- RunPod live calls, live adapter wiring, CLI wiring, and workflow wiring remain false;
- generic external Dockerfile build/run remains disabled;
- authenticated result collection remains disabled until its evidence path exists;
- PR, fork, issue, comment, schedule, `repository_dispatch`, and `pull_request_target` events must not become paid-compute entrypoints.

CI cross-checks these invariants against the existing paid, RunPod, agent, container, and workflow configuration.

## Selected workload

The current workload is the Orbitune RunPod training canary:

```text
repository       Unjuno/orbitune
source SHA       dfb878b91f258e8ca496fac5e457dfbc4216ba89
Dockerfile       workloads/runpod-training-canary/Dockerfile
workload id      orbitune-runpod-training-canary-v1
GPU profile      cheap-24gb
max runtime      30 minutes
max cost         $0.30
training tokens  512,000
```

Orbitune's full pytest workflow and RunPod canary CPU contract smoke are green on that exact SHA. The immutable GHCR image has not yet been published, and this source-level readiness does not authorize paid execution.

## Resume criteria

Do not leave parked mode merely because an active workload exists. Resume toward live GPU execution only when the remaining prerequisites listed in `policies/repository-state.yaml` are satisfied, including actual `main` branch protection, required CI checks, the owner-only protected GitHub Environment, environment-scoped RunPod credentials, immutable published-image handling, authenticated workload-completion evidence, and reliable cleanup.

Changing `mode` is a reviewed repository change; it is not itself authorization to spend money. External GitHub settings and runtime evidence still have to pass their independent gates.
