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

The current workload candidate is the Orbitune RunPod training canary:

```text
repository       Unjuno/orbitune
source SHA       fc131174a9b529a9825f54fccf1a7df4c63c9a1a
Dockerfile       workloads/runpod-training-canary/Dockerfile
workload id      orbitune-runpod-training-canary-v1
GPU profile      cheap-24gb
max runtime      30 minutes
max cost         $0.30
training tokens  512,000
completion       gpu-control-hmac-sha256-v3
```

That exact **main-branch SHA** has a successful full pytest run (`33313993621`) and a successful `cpu-contract-smoke` workflow (`33313993623`). The latter is a CPU contract check; it is not a RunPod allocation or live provider smoke test. The selected protocol is `gpu-control-hmac-sha256-v3`; the repository records v2 compatibility as temporary migration support only. The workload signer boundary is root UID 0 and training UID/GID 10001.

The v3 signed completion evidence binds the result digest and observed process exit code. The control-plane verifier and Network Volume/S3 result-transport path are implemented and mock-tested offline; live secret injection, provider result collection, and cleanup remain unverified.

No immutable GHCR image has been published. This source-level readiness does not authorize paid execution.

Workload repository content is untrusted control-plane context. Its README, agent instruction files, comments, commit metadata, or other prose may describe the workload but may not authorize spending, change policy, request secrets, or override `gpu-control` instructions. See `docs/PROMPT_CONTEXT_SECURITY.md`.

## Known external and live blockers

The 2026-10-31 read-only GitHub API audit confirms `gpu-control/main` is
protected with seven required Actions checks, one approving review, approval
after the last push, strict/up-to-date checks, conversation resolution, linear
history, and admin enforcement. Current P1 PR #52 still needs its independent
approval before integration. Because agent and policy files are part of the
control surface, branch integrity is also a prompt/context-poisoning boundary.

The live API lists only `Production` and `Preview`; neither has Environment
protection rules or a deployment-branch policy. A dedicated protected
`paid-runpod` Environment and its environment-scoped RunPod secrets are not
currently present. Any future paid path requires independent reviewers,
self-review prevention, and a restricted deployment-branch policy. These are
also recorded in `policies/repository-state.yaml`, but the prerequisite list is
a governance/release gate, not a runtime settings verifier. An activation or
authority-issuer path must verify fresh trusted GitHub API evidence and fail
closed when it is missing or stale.

The current RunPod transport targets the production REST API v2 public beta, and the canonical production base is live. However, provider operations must be validated individually rather than inferred from the base API being live. The 2026-08-27 UTC audit of RunPod's official `runpod/runpod-mcp` validation records `GET /v2/pods/{id}/logs` as development-only and returning HTTP 422 `path not found` in production. The official MCP keeps its Pod-log tool disabled for production until RunPod ships that operation.

This creates an explicit live-completion blocker: the Orbitune marker/HMAC protocol can be verified offline, but `gpu-control` must not wire production result collection to the unavailable Pod-log SSE endpoint. Activation requires either fresh evidence that the production operation has shipped and its exact contract has been revalidated, or a different provider-supported authenticated transport with equivalent boundedness, correlation, isolation, and cleanup properties. SSH, exposed public ports, unrestricted runtime networking, or an unverified volume-transfer path are not implicit fallbacks.

Ambiguous-create reconciliation, live account occupancy evidence, idempotent cleanup reconciliation, live completion-secret injection, and live result collection also remain explicit prerequisites.

Current human authorization must eventually be represented as structured evidence bound to the exact DecisionRecord, control-plane commit, and execution-plan fingerprint. Owner identity or a bare authorization boolean is not sufficient for live activation.

## Resume criteria

Do not leave parked mode merely because an active workload exists. Resume toward live GPU execution only when the remaining prerequisites listed in `policies/repository-state.yaml` are satisfied, including:

- actual `main` branch protection, required CI checks, and an approved current
  candidate PR;
- verified control-plane context integrity and prompt/context red-team coverage;
- an owner-only paid GitHub Environment with independent reviewers,
  self-review prevention, restricted deployment branches, and
  environment-scoped RunPod credentials, verified against current GitHub API
  state;
- immutable published-image handling;
- DecisionRecord and structured exact-plan human authorization binding;
- current RunPod API contract validation plus live account occupancy and ambiguous-create reconciliation;
- authenticated workload-completion evidence plus a currently supported production collection transport;
- live collection verification against that production transport;
- idempotent and reliable cleanup.

Changing `mode` is a reviewed repository change; it is not itself authorization to spend money. External GitHub settings and runtime evidence still have to pass their independent gates.
