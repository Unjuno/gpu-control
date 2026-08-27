# Parked repository mode

`gpu-control` is currently intentionally parked even though an active workload has now been selected. The frozen workload candidate is Orbitune commit `8c19af0e7d091a1ead928cecfdeecf177f7e32f8`, recorded in `policies/repository-state.yaml`.

Parked mode is not a degraded state. It is a deliberate safety posture: the control-plane contracts, tests, and provider boundaries remain available, while all billable and generic external-execution paths stay disabled until the remaining activation prerequisites are satisfied.

## What remains usable

While parked, it is valid to:

- inspect and improve documentation or policy;
- run the locked Python test suite;
- run the offline `gpu-control self-test` and `provider-self-test`;
- validate request syntax and resource policy;
- verify the selected public GitHub repository/SHA/Dockerfile identity;
- run the repository-owned trusted reference container in CI;
- improve provider-neutral lifecycle, serialization, result-policy, prompt/context security, or mock-provider tests without enabling live calls;
- prepare immutable image evidence, structured authorization evidence, and completion-evidence integration for the selected workload without authorizing spend.

## What must remain disabled

While `policies/repository-state.yaml` says `mode: parked`:

- no paid RunPod workflow may exist;
- no workflow may reference `secrets.RUNPOD_API_KEY` or the future `paid-runpod` Environment;
- RunPod live calls, live adapter wiring, CLI wiring, and workflow wiring remain false;
- generic external Dockerfile build/run remains disabled;
- live authenticated result collection remains disabled until secret injection and provider collection are wired and verified;
- target repository or other external content must not gain control-plane instruction authority;
- bare or copied authorization must not become live spend authorization;
- PR, fork, issue, comment, schedule, `repository_dispatch`, and `pull_request_target` events must not become paid-compute entrypoints.

CI cross-checks these invariants against the existing paid, RunPod, agent, context-trust, container, and workflow configuration.

## Selected workload

The current workload is the Orbitune RunPod training canary:

```text
repository       Unjuno/orbitune
source SHA       8c19af0e7d091a1ead928cecfdeecf177f7e32f8
Dockerfile       workloads/runpod-training-canary/Dockerfile
workload id      orbitune-runpod-training-canary-v1
GPU profile      cheap-24gb
max runtime      30 minutes
max cost         $0.30
training tokens  512,000
```

Orbitune's full pytest workflow, RunPod canary CPU contract smoke, and authenticated completion-envelope smoke are green on that exact SHA. The workload now supports `gpu-control-hmac-sha256-v1` completion envelopes. The control plane has an offline verifier for the same protocol, but live per-run secret injection and provider result collection remain disabled.

The immutable GHCR image has not yet been published, and this source-level readiness does not authorize paid execution.

Workload repository content is untrusted control-plane context. Its README, agent instruction files, comments, commit metadata, or other prose may describe the workload but may not authorize spending, change policy, request secrets, or override `gpu-control` instructions. See `docs/PROMPT_CONTEXT_SECURITY.md`.

## Known external and live blockers

Read-only repository inspection currently shows `gpu-control/main` is not protected and has no required status checks enforced. Those GitHub repository settings must be configured before activation. Because agent and policy files are part of the control surface, branch integrity is also a prompt/context-poisoning boundary.

The protected `paid-runpod` Environment and its environment-scoped RunPod secret are activation prerequisites and are not assumed to exist merely because code support is present.

The current RunPod provider implementation is a legacy v2-beta mock contract. Current official API behavior must be revalidated and the adapter migrated or proven equivalent before live use. Ambiguous-create reconciliation, live account occupancy evidence, idempotent cleanup reconciliation, live completion-secret injection, and live result collection also remain explicit prerequisites.

Current human authorization must eventually be represented as structured evidence bound to the exact DecisionRecord, control-plane commit, and execution-plan fingerprint. Owner identity or a bare authorization boolean is not sufficient for live activation.

## Resume criteria

Do not leave parked mode merely because an active workload exists. Resume toward live GPU execution only when the remaining prerequisites listed in `policies/repository-state.yaml` are satisfied, including:

- actual `main` branch protection and required CI checks;
- verified control-plane context integrity and prompt/context red-team coverage;
- the owner-only protected GitHub Environment and environment-scoped RunPod credentials;
- immutable published-image handling;
- DecisionRecord and structured exact-plan human authorization binding;
- current RunPod API contract validation plus live account occupancy and ambiguous-create reconciliation;
- authenticated workload-completion evidence wired through the provider lifecycle;
- idempotent and reliable cleanup.

Changing `mode` is a reviewed repository change; it is not itself authorization to spend money. External GitHub settings and runtime evidence still have to pass their independent gates.
