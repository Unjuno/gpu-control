# Asynchronous Execution Contract

Long-running GPU work must not keep a GitHub-hosted Actions runner alive while the provider job runs.

The intended lifecycle is split into short control-plane stages connected by immutable identifiers and persisted state.

## Approved plan identity

`ApprovedExecutionPlan` provides:

- `to_dict()` for a JSON-compatible representation;
- `canonical_json()` for deterministic serialization;
- `fingerprint()` for a `sha256:` content identifier.

The fingerprint changes when any plan field changes, including workload identity, image digest, limits, price evidence, or authorization reference.

A fingerprint is **not a signature** and is **not authorization**. An attacker who can replace both a plan and its fingerprint can still produce a matching pair. The expected fingerprint therefore has to travel through a trusted state or metadata channel when it is used as an integrity check.

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
persist submission receipt
        |
        v
GitHub Actions job exits
```

A submission receipt should eventually contain at least:

- plan fingerprint;
- provider name;
- provider job/resource identifier;
- submission timestamp;
- requested runtime/cost ceilings;
- cleanup state or cleanup reference.

The submit stage must not wait for training or inference to finish.

## Provider execution stage

The provider owns the long-running lifetime of the containerized workload. GitHub Actions is not the job scheduler for the GPU workload.

Provider execution must remain bounded by the approved plan and provider-side lifecycle controls where available.

## Collection stage

A later authenticated event or scheduled recovery path starts a separate short-lived collection stage:

```text
submission receipt
        |
        | correlate plan fingerprint + provider job id
        v
read provider status/results
        |
        +-- collect bounded logs/metrics/artifacts
        +-- record terminal status
        +-- ensure cleanup/termination
        v
persist result state
```

The collector must not infer a different workload, image, GPU profile, runtime limit, or cost limit from provider state. The approved plan remains the control-plane source of truth.

## Failure and recovery

The design must account for failures between every transition:

- provider accepted the job but the submit workflow failed before persisting the receipt;
- provider API returned an ambiguous response;
- result callback was lost;
- collection failed after the GPU job completed;
- cleanup failed after success or failure;
- the provider job outlived the expected runtime ceiling.

Recovery logic should be idempotent where possible and should identify resources using provider job ids plus the plan fingerprint or another trusted correlation identifier.

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
