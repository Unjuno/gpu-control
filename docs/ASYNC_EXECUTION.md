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

`src/gpu_control/lifecycle.py` provides provider-neutral types for the submit/collect handoff:

- `SubmissionReceipt` — persisted after a provider accepts a job;
- `JobObservation` — one correlated provider-state observation;
- `JobState` — submitted, running, succeeded, failed, cancelled, or timed out;
- `CleanupState` — not started, pending, completed, or failed;
- transition validation for job and cleanup state;
- strict JSON serialization/deserialization for cross-process persistence;
- submission-time revalidation of time-sensitive pricing evidence.

These types make the asynchronous contract executable without adding a provider adapter.

## Submit stage

A future trusted submit stage should be short-lived:

```text
ApprovedExecutionPlan
        |
        | validate_plan_for_submission(now)
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

The approval decision and the provider submission are separate time boundaries. Pricing may expire between them. `validate_plan_for_submission(...)` therefore re-checks immediately before submission that:

- pricing verification has not expired;
- submission does not predate pricing verification;
- the approved plan still records verified pricing;
- explicit human authorization is still represented in the immutable plan;
- the cleanup guarantee is still represented in the immutable plan.

A future provider adapter should call this validation immediately before the billable provider request. `build_submission_receipt(...)` repeats the same check defensively.

`SubmissionReceipt` binds the provider response to:

- provider name;
- concrete provider resource id;
- provider job id;
- approved-plan fingerprint;
- immutable image digest;
- submission time;
- requested runtime ceiling;
- requested cost ceiling.

The receipt has its own deterministic JSON representation and `sha256:` fingerprint for persistence/correlation. Like the plan fingerprint, the receipt fingerprint is not a signature.

## Durable state format

Submission and collection normally run in different processes or workflow jobs, so in-memory dataclasses are not enough.

`SubmissionReceipt.from_json(...)` and `JobObservation.from_json(...)` provide strict restoration of persisted lifecycle state. The parser fails closed on:

- invalid JSON;
- non-object JSON;
- duplicate JSON keys;
- missing fields;
- unknown fields;
- unsupported schema versions;
- malformed enum values;
- malformed fingerprints/digests;
- invalid timestamps;
- invalid limits;
- JSON numeric money values instead of decimal strings.

Money is serialized as a decimal string such as `"0.10"`, not as a JSON floating-point number. This avoids precision ambiguity between workflow stages and languages.

After restoring a receipt, `validate_receipt_against_plan(...)` must verify that provider, provider resource id, plan fingerprint, image digest, runtime ceiling, and cost ceiling still match the trusted `ApprovedExecutionPlan`.

Persisted state is not trusted merely because it parses successfully.

## Provider execution stage

The provider owns the long-running lifetime of the containerized workload. GitHub Actions is not the job scheduler for the GPU workload.

Provider execution must remain bounded by the approved plan and provider-side lifecycle controls where available.

## Collection stage

A later authenticated event or scheduled recovery path starts a separate short-lived collection stage:

```text
trusted ApprovedExecutionPlan
        +
restored SubmissionReceipt
        |
        | validate receipt against plan
        v
read provider status/results
        |
        v
restored/new JobObservation
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
- persisted lifecycle state was corrupted or tampered with;
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
