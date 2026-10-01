# Parked repository mode

`gpu-control` is currently intentionally parked even though an active workload has now been selected. The frozen workload candidate is Orbitune commit `fc131174a9b529a9825f54fccf1a7df4c63c9a1a`, recorded in `policies/repository-state.yaml`.

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
- prepare immutable image evidence, structured authorization evidence, and completion-evidence integration for the selected workload without authorizing spend;
- implement and test the bounded completion-marker parser offline without claiming that a production provider transport exists.

## What must remain disabled

While `policies/repository-state.yaml` says `mode: parked`:

- no paid RunPod workflow may exist;
- no workflow may reference `secrets.RUNPOD_API_KEY` or the future `paid-runpod` Environment;
- RunPod live calls, live adapter wiring, CLI wiring, and workflow wiring remain false;
- generic external Dockerfile build/run remains disabled;
- live authenticated result collection remains disabled until a currently supported production provider transport, secret injection, collection, correlation, and cleanup path are all wired and verified;
- a development-only provider operation must not be treated as a production contract;
- target repository or other external content must not gain control-plane instruction authority;
- bare or copied authorization must not become live spend authorization;
- PR, fork, issue, comment, schedule, `repository_dispatch`, and `pull_request_target` events must not become paid-compute entrypoints.

CI cross-checks these invariants against the existing paid, RunPod, agent, context-trust, container, and workflow configuration.

## Selected workload

The current workload is the Orbitune RunPod training canary:

```text
repository       Unjuno/orbitune
source SHA       fc131174a9b529a9825f54fccf1a7df4c63c9a1a
Dockerfile       workloads/runpod-training-canary/Dockerfile
workload id      orbitune-runpod-training-canary-v1
GPU profile      cheap-24gb
max runtime      30 minutes
max cost         $0.30
training tokens  512,000
```

The repository state records full pytest and canary smoke runs `33313993621` and
`33313993623` for this exact source SHA. This is source-CI evidence, not evidence of
a paid GPU run. The selected protocol is `gpu-control-hmac-sha256-v3`: a root signer
binds exact result bytes and the wrapper-observed process exit code. The control
plane implements bounded two-object Network Volume/S3 collection offline. Actual
secret injection, volume credentials, and result collection remain live-unverified.

The immutable GHCR image has not yet been published, and this source-level readiness does not authorize paid execution.

Workload repository content is untrusted control-plane context. Its README, agent instruction files, comments, commit metadata, or other prose may describe the workload but may not authorize spending, change policy, request secrets, or override `gpu-control` instructions. See `docs/PROMPT_CONTEXT_SECURITY.md`.

## Known external and live blockers

Read-only repository inspection currently shows `gpu-control/main` is not protected and has no required status checks enforced. Those GitHub repository settings must be configured before activation. Because agent and policy files are part of the control surface, branch integrity is also a prompt/context-poisoning boundary.

The protected `paid-runpod` Environment and its environment-scoped RunPod secret are activation prerequisites and are not assumed to exist merely because code support is present.

The canonical adapter now uses current REST v1 and exact price/datacenter evidence.
The selected production-result design uses an existing trusted Network Volume and
bounded S3 reads of `result.json` and `completion-v3.json`. This code is mock-tested,
not proof of a working live account integration. Legacy Pod-log SSE is not the
selected result path. SSH, exposed public ports, unrestricted runtime networking,
and unverified transfer mechanisms are not implicit fallbacks.

Ambiguous-create reconciliation, live account occupancy evidence, idempotent cleanup reconciliation, live completion-secret injection, and live result collection also remain explicit prerequisites.

Current human authorization has a structured validator bound to the exact DecisionRecord, control-plane commit, and execution-plan fingerprint; a trusted end-to-end live workflow must still supply that evidence. Owner identity or a bare authorization boolean is not sufficient for live activation.

## Resume criteria

Do not leave parked mode merely because an active workload exists. Resume toward live GPU execution only when the remaining prerequisites listed in `policies/repository-state.yaml` are satisfied, including:

- actual `main` branch protection and required CI checks;
- verified control-plane context integrity and prompt/context red-team coverage;
- the owner-only protected GitHub Environment and environment-scoped RunPod credentials;
- immutable published-image handling;
- DecisionRecord and structured exact-plan human authorization binding;
- current RunPod API contract validation plus live account occupancy and ambiguous-create reconciliation;
- authenticated workload-completion evidence plus a currently supported production collection transport;
- live collection verification against that production transport;
- idempotent and reliable cleanup.

Changing `mode` is a reviewed repository change; it is not itself authorization to spend money. External GitHub settings and runtime evidence still have to pass their independent gates.
