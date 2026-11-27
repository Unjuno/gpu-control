# ADR 0008: RunPod owner-selected execution contract

- **Status:** proposed; implementation and release gates remain open.
- **Date:** 2026-11-28
- **Scope:** run the owner's pinned GitHub experiment on RunPod Serverless from
  the same ChatGPT/Sites lifecycle used by other providers.

## Context

The existing RunPod Sites route is an endpoint-scoped, fixed-workload GPU
canary. The user's product goal requires running the selected repository's
declared experiment code on an actual RunPod GPU. The fixed canary is not
evidence that arbitrary owner-selected source is executable or safe there.

RunPod's current Serverless documentation describes workers as custom Docker
containers deployed to an endpoint. Queue-based endpoints process handler jobs
and document automatic retries on failure; the per-request job policy exposes
`executionTimeout` and `ttl`. The current Sites integration verifies a fixed
endpoint image and sends bounded per-job timeout and TTL, but it has no
owner-selected execution adapter or evidence for the isolation properties of
such a runtime. RunPod queue result retention is also finite, so GPU Control
must persist results and artifacts in its own store before that window expires.

The current RunPod fixed-canary plan also estimates billable time as 300 seconds
of job TTL plus 5 seconds of idle time (`RUNPOD_BILLABLE_CEILING_SECONDS = 305`).
RunPod documents that workers are billed during initialization and that the
default initialization timeout is 420 seconds. Current offer validation does
not bind or validate `workers.initTimeout`, and the estimate omits that phase.
This undercounts even before retry behavior is considered. Adding one maximum
initialization window would make the modeled duration at least 725 seconds, but
that alone is not a hard bound: retry attempts and worker starts also need a
documented, enforced maximum before the plan can claim a per-run maximum charge.

## Proposed contract

1. Keep ChatGPT Sites as the sole product-facing lifecycle and owner ledger.
   The agent selects an authorized repository, pins the commit, and carries
   registration/run IDs internally. Provider-specific payloads remain inside
   the adapter.
2. Use a GPU Control-owned, immutable RunPod worker image. Never accept an
   owner-provided Dockerfile, image, shell command, credential, network policy,
   or resource limit. The worker accepts only a strict versioned execution
   envelope bound to the Sites owner, exact commit, plan fingerprint, GPU,
   runtime and cost ceiling.
3. Before enabling owner code, prove a per-job execution boundary that prevents
   repository code from reading provider/control-plane credentials or another
   job's source, state, result, and artifacts. Prove bounded CPU, memory,
   GPU, runtime, output and network behavior. If the endpoint reuses a worker,
   demonstrate that prior job processes and writable state cannot affect the
   next job; otherwise require a verified one-job worker lifecycle.
4. Treat a lost submit response and provider retry separately. The same
   owner-bound run must not create duplicate GPU allocations or produce
   unaccounted billed attempts. Establish RunPod's exact retry behavior and
   include initialization, execution, idle time and the maximum billable
   attempts in the signed plan's cost bound. Until enforced, the fixed canary's
   current quote is an estimate, not a hard maximum provider charge.
   Never blindly resubmit an ambiguous request.
5. Persist terminal status, bounded metrics, checkpoint/artifact bytes and
   immutable digests into GPU Control's durable owner-scoped ledger before
   provider result retention expires. Reconcile cancellation and cleanup from
   provider evidence; TTL alone does not prove artifact persistence.
6. Advertise RunPod owner-selected capability only when current endpoint
   configuration, image digest, authorization, provider-specific budget,
   idempotency/recovery behavior, isolation, result durability and cleanup
   have passed exact-head review and acceptance. A configured key or fixed
   canary does not satisfy this contract.

## Consequences

- The next RunPod work is an offline adapter and threat-model contract, not a
  toggle on the existing fixed canary.
- Any endpoint behavior that cannot enforce the required isolation or bounded
  billing is a capability blocker. Preserve the conversational journey and
  route only to a provider whose complete capability is currently supported;
  never disguise CPU or Modal execution as RunPod GPU execution.
- This ADR does not authorize credentials, admission changes, endpoint
  mutation, deployments, provider calls, or GPU allocation. Repository parked
  policy remains authoritative.

## Evidence

- [RunPod Serverless endpoint types](https://docs.runpod.io/serverless/endpoints/overview)
  documents queue-based execution and automatic retries on failure.
- [RunPod endpoint settings](https://docs.runpod.io/serverless/endpoints/endpoint-configurations)
  documents execution timeout, job TTL, worker scaling, initialization timeout
  and billing during worker initialization.
- [RunPod request handling](https://docs.runpod.io/serverless/endpoints/send-requests)
  documents request policy, result retention, `/retry`, and duplicate-job risk
  when resubmitting after a timeout or server error.
- Repository evidence: `sites/gpu-control-sites/worker/runpod_provider.js`,
  `worker/runpod_plan.js` (currently models 305 seconds and omits initialization),
  `worker/runpod_lifecycle.js`, and
  `policies/repository-state.yaml`.

## Revisit when

- RunPod provides a documented configuration or runtime primitive that proves
  job isolation and retry/billing limits for this use case;
- a trusted disposable per-run worker can meet the same lifecycle without
  broadening credential scope; or
- the user explicitly changes the product requirement to permit a weaker,
  separately reviewed execution boundary.
