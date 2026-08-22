# RunPod catalog pricing evidence

RunPod Pod pricing depends on the exact GPU type and the selected cloud (`SECURE` or `COMMUNITY`). The control plane therefore must not treat a bare hourly-price scalar or a GPU type id by itself as sufficient pricing identity.

`src/gpu_control/providers/runpod_pricing.py` normalizes one exact RunPod REST API v2 GPU catalog row into `RunPodCatalogPricingEvidence`.

The current implementation is mock-tested only. It does not call RunPod from CI, the public CLI, or a GitHub Actions paid workflow.

Official API reference:

- https://docs.runpod.io/api-reference-v2/catalog/list-gpu-types

The intended catalog request is equivalent to:

```text
GET /v2/catalog/gpus?include=AVAILABILITY&product=POD&count=1&cloud=SECURE
```

or the corresponding `COMMUNITY` request.

## Evidence identity

One normalized evidence record binds:

```text
control-plane GPU profile
+ exact RunPod GPU type id
+ SECURE or COMMUNITY cloud
+ GPU memory
+ hourly price for that cloud
+ HIGH availability
+ verification reference
+ verified-at timestamp
+ validity deadline
```

The verification reference is a deterministic SHA-256 identifier over those normalized values.

The provider-neutral `PricingVerificationResult` is still used by the paid execution gate. `RunPodCatalogPricingEvidence.to_pricing_result()` converts the provider-specific evidence into that existing type while retaining the RunPod evidence separately for later cloud binding.

## Conservative MVP availability rules

For the one-GPU MVP, catalog evidence is accepted only when all of the following hold:

- the requested GPU type appears exactly once in the response;
- its VRAM is at least the profile's `min_vram_gb`;
- it is offered in the selected cloud;
- that cloud has a positive hourly price;
- `maxCount` for that cloud is at least 1;
- top-level catalog availability is `HIGH`;
- at least one returned data center has `HIGH` availability.

Lower or unknown availability fails closed rather than being interpreted as an allocation promise.

## Short validity window

Catalog state and availability can change quickly. Evidence therefore expires quickly:

- default validity: 120 seconds;
- absolute current policy maximum: 300 seconds.

The existing paid-execution lifecycle already rechecks pricing expiry immediately before provider submission. Expired catalog evidence must be refreshed rather than extended locally.

## Cloud is part of price identity

The same GPU type can have different prices in `SECURE` and `COMMUNITY` clouds. A plan approved using a `SECURE` price must not later submit a `COMMUNITY` Pod, and vice versa.

`build_priced_create_pod_payload(...)` therefore validates that the catalog evidence matches all pricing fields carried by the approved plan, then passes **that evidence's cloud** to the RunPod create-pod codec.

The lower-level `build_create_pod_payload(...)` exists as a transport primitive, but a future live paid adapter must use the priced wrapper or an equivalent control-plane binding. Arbitrary caller-selected cloud values are not an acceptable paid submission path.

After Pod creation, `validate_created_pod_with_pricing(...)` revalidates the returned cloud before the existing image, GPU type/count, price, and status checks are applied.

## What this still does not do

This module does not yet:

- make a live GPU catalog request;
- read `RUNPOD_API_KEY`;
- automatically select the cheapest eligible GPU type;
- allocate a Pod;
- retry on changing availability;
- authorize paid compute.

A future trusted RunPod adapter will fetch fresh catalog data, build this evidence, pass its provider-neutral projection through the existing approval gate, retain the RunPod-specific evidence for cloud binding, and only then reach the create-pod HTTP boundary.
