# RunPod v2 adapter safety contract

`src/gpu_control/providers/runpod_adapter.py` connects the existing provider-neutral controller contract to the RunPod REST API v2 codecs.

The adapter is **mock-tested only**. `policies/runpod-v2-policy.yaml` keeps live adapter construction, public CLI wiring, and GitHub Actions workflow wiring disabled.

## Trusted construction inputs

A `RunPodV2Adapter` is constructed from four already-established inputs:

```text
RunPodV2HttpClient
ApprovedExecutionPlan
PublishedImageEvidence
RunPodCatalogPricingEvidence
```

The adapter constructor revalidates the plan, immutable published image, exact plan fingerprint, RunPod GPU type, cloud-specific catalog price, and pricing validity metadata. The adapter does not accept a raw `WorkloadRequest`.

The existing `submit_approved_plan(...)` controller remains the outer paid-compute boundary. It still validates the trusted expected plan fingerprint and pricing freshness before invoking `adapter.submit(...)`.

## Exactly one create request

`RunPodV2Adapter.submit(...)` deliberately issues one `POST /pods` request and has no automatic create retry loop.

A transport failure is ambiguous: the server may have accepted the Pod even if the client did not receive the response. Blindly retrying the POST could therefore allocate a second billable Pod.

Until an explicit reconciliation mechanism exists, an ambiguous create failure is surfaced for operator/recovery handling rather than retried automatically.

The deterministic Pod name derived from the approved-plan fingerprint is useful correlation metadata, but it is not assumed to be an API-level idempotency key.

## Compensating termination after known bad creation

A 201 response is not sufficient to trust the allocation. The adapter revalidates the returned:

- Pod id;
- digest-pinned image reference;
- GPU type and count;
- cloud;
- hourly cost;
- known provider status.

If this validation fails **and the response contains a usable Pod id**, the adapter immediately calls the irreversible terminate endpoint before returning an error.

```text
POST /pods
   |
   +-- response valid -----------------> persist provider job id
   |
   +-- response invalid + known id ----> DELETE /pods/{id} -> error
   |
   +-- response invalid + no id -------> error / reconciliation required
```

A failure of the compensating termination is itself surfaced as a stronger error. It is never hidden as ordinary validation failure because an invalid billable resource may still exist.

## Observation

`observe(...)` requires the persisted receipt to remain bound to the same approved plan, GPU resource identity, and image digest.

Each `GET /pods/{id}` response is revalidated against the same image and catalog pricing evidence before status translation. Unknown states fail closed. `EXITED` remains ambiguous and is not translated to success.

## Cleanup

For a trusted terminal observation, `cleanup(...)` calls the RunPod terminate endpoint and returns `CleanupState.COMPLETED` only after the HTTP operation succeeds.

Cleanup failures remain visible through the existing lifecycle/recovery model.

## Results remain disabled

`collect_results(...)` currently rejects every request. A stopped RunPod container is not sufficient evidence that the workload completed successfully or that arbitrary result references are trustworthy.

Before result collection can be enabled, the project still needs authenticated workload-completion evidence bound to:

```text
plan fingerprint
+ provider Pod id
+ workload exit outcome
+ output/result manifest identity
```

The existing bounded `ResultManifest` policy will still apply after that evidence layer is implemented.

## No live resource path yet

This adapter class existing in the package does not enable paid compute by itself. There is still no repository path that:

- reads `RUNPOD_API_KEY`;
- constructs `RunPodV2HttpClient` with the real network opener;
- constructs `RunPodV2Adapter` for a public CLI request;
- invokes it from a GitHub Actions paid workflow.

Those remain separately gated future changes.
