# RunPod v2 adapter safety contract

`src/gpu_control/providers/runpod_adapter.py` connects the existing provider-neutral controller contract to the RunPod REST API v2 codecs.

The adapter is **mock-tested only**. `policies/runpod-v2-policy.yaml` keeps live adapter construction, public CLI wiring, GitHub Actions workflow wiring, and live result collection disabled.

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

Cleanup failures remain visible through the existing lifecycle/recovery model. Result capture failure does not authorize leaving a billable Pod running.

## Results remain disabled because the production transport is missing

`collect_results(...)` currently rejects every request. This is no longer because the workload-completion protocol is undefined: the Orbitune workload emits the v2 HMAC completion envelope, the control plane authenticates it offline, and the workload-specific paid-canary acceptance layer is separately implemented.

The remaining RunPod blocker is transport. The pinned official RunPod audit records the Pod-log SSE operation used by the earlier prototype as unavailable on the production surface. No alternative production-supported authenticated collection transport has yet been verified.

The provider-neutral finalization contract supports both:

```text
terminal -> cleanup -> post-cleanup collection
```

for transports that survive resource deletion, and:

```text
terminal -> durable ProviderResultCapture -> cleanup -> finalized ResultManifest
```

for ephemeral transports that must be read before cleanup. Neither path changes the RunPod blocker: `RunPodV2Adapter.collect_results(...)` remains fail-closed until a production-supported authenticated transport is verified and wired.

When that transport exists, it must preserve the existing completion/result identity bindings, including approved plan, exact execution identity, source/image identity, authenticated result digest, provider-job correlation, bounded result policy, and cleanup lifecycle correlation.

## No live resource path yet

This adapter class existing in the package does not enable paid compute by itself. There is still no repository path that:

- reads `RUNPOD_API_KEY`;
- constructs `RunPodV2HttpClient` with the real network opener;
- constructs `RunPodV2Adapter` for a public CLI request;
- invokes it from a GitHub Actions paid workflow;
- collects live authenticated results through a verified production transport.

Those remain separately gated future changes.
