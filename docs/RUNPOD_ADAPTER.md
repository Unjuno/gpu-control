# RunPod v2 adapter safety contract

`src/gpu_control/providers/runpod_adapter.py` connects the existing provider-neutral controller contract to the RunPod REST API v2 codecs.

The adapter is **mock-tested only**. `policies/runpod-v2-policy.yaml` keeps live adapter construction, public CLI wiring, GitHub Actions workflow wiring, and live result collection disabled.

## Trusted construction inputs

A `RunPodV2Adapter` is constructed from already-established control-plane inputs:

```text
RunPodV2HttpClient
ApprovedExecutionPlan
PublishedImageEvidence
RunPodCatalogPricingEvidence
account occupancy probe
optional Pod inventory probe
optional RunPodCompletionLaunch
```

The adapter constructor revalidates the plan, immutable published image, exact plan fingerprint, RunPod GPU type, cloud-specific catalog price, pricing validity metadata, and—when present—the per-execution completion launch. The adapter does not accept a raw `WorkloadRequest`.

The existing `submit_approved_plan(...)` controller remains the outer paid-compute boundary. It still validates the trusted expected plan fingerprint and pricing freshness before invoking `adapter.submit(...)`.

## Exactly one create request

`RunPodV2Adapter.submit(...)` deliberately issues one `POST /pods` request and has no automatic create retry loop.

A transport failure is ambiguous: the server may have accepted the Pod even if the client did not receive the response. Blindly retrying the POST could therefore allocate a second billable Pod.

The adapter can now reconcile that ambiguity, but only when both of these are configured:

1. a `RunPodCompletionLaunch` carrying the unique pre-create `CompletionChallenge.execution_name`;
2. a fresh bounded full-account Pod inventory.

The reconciliation contract follows the pinned official RunPod v2 List Pods behavior: `GET /v2/pods` returns a `{pods: [...]}` envelope and v2 does not provide server-side name filtering. The control plane therefore validates the full bounded inventory locally and requires exactly one Pod whose name equals the execution identity.

```text
POST /pods
   |
   +-- response received ------------------------> validate normally
   |
   +-- transport/API error
          -> fresh full-account inventory
          -> exact execution-name match
             +-- zero matches -------------------> fail closed
             +-- multiple matches ---------------> fail closed
             +-- TERMINATED-only match ----------> fail closed
             +-- exactly one live candidate
                    -> GET /pods/{id}
                    -> revalidate name/image/GPU/cloud/price/status
                    -> re-check account exclusivity
                    -> persist provider job id
```

The create request itself is never retried. A plan-level deterministic name is not sufficient for recovery because separate executions of the same plan need independent identities; ambiguous-create reconciliation therefore requires the per-execution completion challenge.

## Compensating termination after known bad creation

A 201 response is not sufficient to trust the allocation. The adapter revalidates the returned:

- Pod id;
- per-execution name when completion launch is configured;
- digest-pinned image reference;
- GPU type and count;
- cloud;
- hourly cost;
- known provider status.

If this validation fails **and the response contains a usable Pod id**, the adapter immediately calls the irreversible terminate endpoint before returning an error.

A failure of the compensating termination is itself surfaced as a stronger error. It is never hidden as ordinary validation failure because an invalid billable resource may still exist.

## Observation

`observe(...)` requires the persisted receipt to remain bound to the same approved plan, GPU resource identity, and image digest.

Each `GET /pods/{id}` response is revalidated against the same image and catalog pricing evidence before status translation. When a completion launch is configured, the Pod name must also remain the exact pre-create execution identity. Unknown states fail closed. `EXITED` remains ambiguous and is not translated to success.

## Cleanup and idempotency reconciliation

For a trusted terminal observation, `cleanup(...)` performs one terminate request. A successful terminate response records cleanup as completed.

If the terminate request itself errors, the adapter does **not** blindly report success and does not need to issue a second terminate immediately. When a fresh bounded inventory probe is configured, it rechecks the exact provider Pod id:

```text
terminate error
   -> fresh full-account inventory
      +-- exact Pod id absent ----------> cleanup completed (reconciled)
      +-- exact Pod status TERMINATED --> cleanup completed (reconciled)
      +-- exact Pod still active -------> cleanup failure remains visible
      +-- invalid/ambiguous inventory --> cleanup failure remains visible
```

This supports retries after an ambiguous delete without turning an active Pod into false cleanup success. Result capture failure never authorizes leaving a billable Pod running.

## Inventory evidence bounds

`runpod_reconciliation.py` normalizes one List Pods response into short-lived `RunPodPodInventoryEvidence`:

- at most 256 Pod entries;
- unique Pod ids;
- bounded, trimmed id/name/status fields;
- canonical uppercase status;
- deterministic SHA-256 content reference;
- exact approved-plan fingerprint binding;
- at most 60 seconds validity.

Reconstructed evidence recomputes the content digest and revalidates every entry before use.

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
