# RunPod API v2 boundary

`gpu-control` targets the RunPod REST API v2 for the first live provider integration.

RunPod API v2 is currently beta. The fixed production origin is:

```text
https://api.runpod.io/v2
```

The implementation in `src/gpu_control/providers/runpod_v2.py` is **not wired to a CLI or GitHub Actions workflow**. Repository CI injects a fake HTTP opener and makes no request to RunPod.

Official references used for this boundary:

- https://docs.runpod.io/api-reference-v2/overview
- https://docs.runpod.io/api-reference-v2/pods/create-a-pod
- https://docs.runpod.io/api-reference-v2/pods/get-a-pod
- https://docs.runpod.io/api-reference-v2/pods/terminate-a-pod
- https://docs.runpod.io/api-reference-v2/pods/trigger-a-pod-state-transition
- https://docs.runpod.io/api-reference-v2/catalog/list-gpu-types

## Why published-image evidence is separate

An `ApprovedExecutionPlan` binds the verified container content using `image_digest`, but RunPod needs a pullable image reference such as:

```text
ghcr.io/example/workload@sha256:<64 lowercase hex characters>
```

A tag-only reference such as `ghcr.io/example/workload:latest` is mutable and is rejected.

`PublishedImageEvidence` therefore binds all three values:

```text
approved-plan fingerprint
+ immutable image digest
+ pullable registry/repository@sha256:digest reference
```

The image publication stage itself is not implemented yet. A future trusted build/publish stage must produce this evidence after pushing the exact verified image to a registry.

## Minimal Pod request

`build_create_pod_payload(...)` intentionally produces a small request:

```text
name
image                  digest-pinned registry reference
gpu.id                 verified RunPod GPU type id
gpu.count              1
disk                    fixed bounded controller value
cloud                   SECURE or COMMUNITY
globalNetworking        false
```

It does not forward arbitrary workload environment variables, ports, mounts, or shell arguments.

RunPod documents Pod creation as asynchronous. A successful create returns a Pod while it is normally still `PROVISIONING`; readiness must be observed separately.

## Post-create validation

The create response is not trusted merely because RunPod returned HTTP 201. Before its Pod id becomes lifecycle identity, the controller must revalidate:

- Pod id exists;
- returned image equals the published immutable image reference;
- returned GPU type and count match the approved plan;
- returned hourly cost does not exceed the verified approved hourly price;
- returned status is a known state.

A future live adapter must terminate the newly created Pod immediately if post-create validation fails after allocation.

## Status translation

The v2 Pod states are translated conservatively:

| RunPod v2 | gpu-control |
| --- | --- |
| `PROVISIONING` | `submitted` |
| `STARTING` | `submitted` |
| `RUNNING` | `running` |
| `ERROR` | `failed` |
| `TERMINATED` | `cancelled` |
| `EXITED` | rejected as ambiguous |
| unknown future state | rejected |

`EXITED` is intentionally not treated as success. RunPod Pod status shows that the container stopped, but the control plane still needs workload completion evidence to distinguish a successful experiment from an application failure or explicit stop.

This is the main remaining state-model blocker before implementing a full `ProviderAdapter` for RunPod.

## HTTP client constraints

`RunPodV2HttpClient`:

- uses only the fixed `https://api.runpod.io/v2` origin;
- puts the API key only in `Authorization: Bearer ...`;
- never puts credentials in a query string;
- uses a bounded request timeout;
- accepts only known Pod transition actions;
- validates response status and JSON shape;
- does not include the API key in raised error messages.

The current public policy in `policies/runpod-v2-policy.yaml` keeps live calls, CLI wiring, and workflow wiring disabled.

## Remaining work before a real paid Pod

The remaining prerequisites are deliberately explicit:

1. implement a trusted image build/publish stage that produces `PublishedImageEvidence`;
2. derive fresh `PricingVerificationResult` from the v2 GPU catalog and availability response;
3. define authenticated workload-completion evidence for the ambiguous `EXITED` state;
4. implement a live RunPod `ProviderAdapter` using the existing trusted provider controller;
5. add immediate compensating termination on any post-create validation failure;
6. wire the live adapter only to an explicit trusted paid-compute workflow with `RUNPOD_API_KEY` stored as a GitHub Actions secret.

Until those items are complete, no repository workflow can create a RunPod resource.
