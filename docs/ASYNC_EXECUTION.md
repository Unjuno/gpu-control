# Asynchronous Execution Contract

Long-running GPU work must not keep a GitHub-hosted Actions runner alive while the provider job runs.

The intended lifecycle is split into short control-plane stages connected by immutable identifiers and persisted state.

## Approved plan identity

`ApprovedExecutionPlan` provides:

- `to_dict()` for a JSON-compatible representation;
- `canonical_json()` for deterministic serialization;
- `fingerprint()` for a `sha256:` content identifier.

The fingerprint changes when any plan field changes, including workload identity, image digest, limits, pricing evidence, provider resource identity, or authorization reference.

A fingerprint is **not a signature** and is **not authorization**. An attacker who can replace both a plan and its fingerprint can still produce a matching pair. The expected fingerprint therefore has to travel through a trusted state or metadata channel when it is used as an integrity check.

## Implemented lifecycle model

`src/gpu_control/lifecycle.py` now provides provider-neutral types for the submit/collect handoff:

- `SubmissionReceipt` — persisted after a provider accepts a job;
- `JobObservation` — one correlated provider-state observation;
- `JobState` — submitted, running, succeeded, failed, cancelled, or timed out;
- `CleanupState` — not started, pending, completed, or failed;
- transition validation for job and cleanup state.

These types make the asynchronous contract executable without adding a provider adapter.

## Submit stage

A future trusted submit stage should be short-lived:

```text
ApprovedExecutionPlan
        |
        | verify trusted plan fingerprint
        v
provider adapter
        |
        | submit once
        v
provider job id
        |
        v
build + persist SubmissionReceipt
        |
        v
GitHub Actions job exits
```

`build_submission_receipt(...)` binds the provider response to:

- provider name;
- concrete provider resource id;
- provider job id;
- approved-plan fingerprint;
- immutable image digest;
- submission time;
- requested runtime ceiling;
- requested cost ceiling.

The receipt has its own deterministic JSON representation and `sha256:` fingerprint for persistence/correlation. Like the plan fingerprint, the receipt fingerprint is not a signature.

The submit stage must not wait for training or inference to finish.

## Provider execution stage

The provider owns the long-running lifetime of the containerized workload. GitHub Actions is not the job scheduler for the GPU workload.

Provider execution must remain bounded by the approved plan and provider-side lifecycle controls where available.

## Collection stage

A later authenticated event or scheduled recovery path starts a separate short-lived collection stage:

```text
SubmissionReceipt
        |
        | correlate plan fingerprint + provider job id
        v
read provider status/results
        |
        v
JobObservation
        |
        +-- validate identity and monotonic state transition
        +-- collect bounded logs/metrics/artifacts
        +-- record terminal status
        +-- ensure cleanup/termination
        v
persist observation/result state
```

`validate_observation(...)` rejects an observation whose provider, provider job id, or plan fingerprint does not match the persisted submission receipt. It also rejects observations that predate submission.

`validate_observation_transition(...)` enforces monotonic state. A terminal job cannot move back to running or change to a different terminal outcome. Cleanup cannot start while a job is non-terminal; failed cleanup may be retried; completed cleanup cannot regress.

A `JobObservation` is considered finalized only when the provider job is terminal and cleanup is recorded as completed.

The collector must not infer a different workload, image, GPU profile, runtime limit, cost limit, or provider resource from provider state. The approved plan remains the control-plane source of truth.

## Failure and recovery

The design must account for failures between every transition:

- provider accepted the job but the submit workflow failed before persisting the receipt;
- provider API returned an ambiguous response;
- result callback was lost;
- collection failed after the GPU job completed;
- cleanup failed after success or failure;
- the provider job outlived the expected runtime ceiling.

Recovery logic should be idempotent where possible and should identify resources using the provider job id plus the plan fingerprint or another trusted correlation identifier.

Cleanup failure remains visible as lifecycle state. A failed cleanup may transition back to pending for a retry and then to completed; it is not silently treated as success.

## Forbidden pattern

Do not implement long-lived polling such as:

```text
submit provider job
while running:
    sleep
    poll provider
```

inside a GitHub-hosted runner for the duration of a GPU experiment.

Short bounded polling during submission/consistency windows may be acceptable when required by a provider API, but the GPU workload lifetime itself belongs outside the Actions runner.

## Still not implemented

The lifecycle model does not itself:

- call RunPod or another provider;
- persist receipts to GitHub artifacts, object storage, or a database;
- authenticate callbacks;
- schedule recovery checks;
- collect real provider logs or metrics;
- perform provider cleanup.

Those operations belong to future provider and workflow layers that consume these provider-neutral types.
