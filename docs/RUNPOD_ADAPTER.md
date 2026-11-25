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
Pod inventory probe
RunPodCompletionLaunch
trusted pre-existing Network Volume evidence
fixed-origin Network Volume S3 result client
trusted workload id
```

The adapter constructor revalidates the plan, immutable published image, exact plan fingerprint, RunPod GPU type, cloud-specific catalog price, pricing validity metadata, and the configured per-execution completion launch. Immediately before submission it also refuses allocation unless the inventory, signer, volume, result client, and workload identity are all present. The adapter does not accept a raw `WorkloadRequest`.

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

## Authenticated durable results

The selected Orbitune workload writes bounded `result.json` and
`completion-v3.json` objects to the trusted pre-existing Network Volume. The
control plane reads those objects through the fixed RunPod S3 origin and
authenticates the `gpu-control-hmac-sha256-v3` envelope. The evidence binds the
plan, execution name, source and image, exact result digest, workload id, and
effective process exit code. A `pass` result with a nonzero signed exit code,
or a `fail` result with a zero exit code, is rejected.

The transport and root-owned signer are implemented and mock-tested offline,
but have not been verified in this RunPod account. The per-run signer key is
sent only as system environment to the digest-pinned root wrapper; that wrapper
must remove it before launching training as UID/GID 10001. This boundary does
not attest the RunPod host or account administrator. Secret-bearing create
errors suppress arbitrary provider detail to prevent reflected environment
values from reaching exception logs.

The provider-neutral finalization contract supports both:

```text
terminal -> cleanup -> post-cleanup collection
```

for this Network Volume transport, which survives Pod deletion, and:

```text
terminal -> durable ProviderResultCapture -> cleanup -> finalized ResultManifest
```

for any future ephemeral transport that must be read before cleanup. The
current blocker is live provider/account acceptance and Sites orchestration,
not the absence of an offline result verifier.

Live acceptance must prove that the provider mount, root-wrapper secret
scrubbing, durable objects, S3 retrieval, provider-job correlation, bounded
result policy, and cleanup lifecycle all preserve those bindings.

## No live resource path yet

This adapter class existing in the package does not enable paid compute by itself. There is still no repository path that:

- reads `RUNPOD_API_KEY`;
- constructs `RunPodV2HttpClient` with the real network opener;
- constructs `RunPodV2Adapter` from a Sites owner-bound one-use authorization;
- reserves and transitions the D1 account lease atomically with RunPod intent;
- reconciles provider creation, cancellation, result capture, and cleanup from
  the Sites lifecycle;
- collects live authenticated results through the Network Volume transport.

Those remain separately gated future changes.
