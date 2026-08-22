# Provider Adapter Contract

Provider-specific API code is a transport layer, not an authorization layer.

`gpu-control` therefore separates a narrow provider adapter from the control-plane controller that validates approval, lifecycle identity, cleanup, and result policy.

## Current status

No live RunPod or other billable provider implementation is enabled yet.

`src/gpu_control/providers/base.py` defines the provider protocol and small response types. `src/gpu_control/providers/controller.py` implements the trusted wrapper that a future live adapter must cross.

The repository test suite uses a no-network fake backend to exercise this boundary. That fake backend does not allocate resources and is not a production provider implementation.

## Submit boundary

A provider adapter receives only an `ApprovedExecutionPlan`.

Before `adapter.submit(...)` is invoked, the controller:

1. validates the full approved-plan shape;
2. compares the plan to a trusted expected plan fingerprint;
3. re-checks pricing freshness at the actual submission time;
4. verifies the adapter provider name exactly matches the plan provider.

If any of those checks fails, the provider submit method is not called.

After a provider returns a job id, the controller validates that id and creates the trusted `SubmissionReceipt` and initial `submitted` lifecycle observation.

A future live provider implementation must not expose another code path that accepts raw workflow inputs, a raw `WorkloadRequest`, or a caller-supplied arbitrary provider payload for allocation.

## Provider responses are untrusted

Provider status, cleanup, and result responses are not trusted merely because they came from the provider API.

The controller rebinds each response to the persisted lifecycle identity:

- provider name must remain unchanged;
- provider job id must match the submission receipt;
- plan fingerprint remains the control-plane correlation id;
- job-state transitions must be monotonic;
- cleanup cannot start before a terminal job state;
- result collection cannot start until cleanup is completed.

A provider response that attempts to change identity or regress state is rejected.

## Cleanup boundary

`cleanup_provider_job(...)` only calls the provider cleanup operation for a terminal lifecycle observation.

The provider may report cleanup as pending, completed, or failed. Failed cleanup remains visible and may be retried according to the lifecycle policy. Completed cleanup cannot regress.

## Result boundary

`collect_provider_results(...)` only calls the provider result translator after the lifecycle is finalized: the job is terminal and cleanup is completed.

Provider-translated artifacts still pass through `policies/result-policy.yaml` and the `ResultManifest` contract. This means:

- retained logs remain bounded;
- directly collected files remain bounded;
- large checkpoints remain reference-only by default;
- artifact SHA-256 digests are required;
- unsafe artifact paths are rejected;
- external artifact references are not automatically fetched.

## Async requirement

The adapter contract is deliberately one-operation-at-a-time. The submit controller returns after provider acceptance and receipt creation. It does not wait for the GPU workload to finish.

A future RunPod integration should therefore map roughly to:

```text
submit workflow
  -> restore + verify ApprovedExecutionPlan
  -> controller.submit_approved_plan(...)
  -> one RunPod submission request
  -> persist receipt
  -> exit

later collection/recovery workflow
  -> restore receipt
  -> one status observation
  -> terminal cleanup when needed
  -> bounded result manifest
  -> exit
```

Long-running provider polling inside a GitHub-hosted runner remains forbidden.

## Security note

The controller is defense in depth. It does not make provider credentials safe to expose to untrusted workload code. Provider credentials must still live only in a trusted credential-bearing job that never executes arbitrary target repository code.
