# RunPod API v2 boundary

`gpu-control` targets the RunPod REST API v2 for the first live provider integration.

RunPod API v2 is currently beta. The fixed production origin is:

```text
https://api.runpod.io/v2
```

The implementation in `src/gpu_control/providers/runpod_v2.py` is **not wired to a CLI or GitHub Actions workflow**. Repository CI injects a fake HTTP opener and makes no request to RunPod.

Official references used for this boundary include RunPod's public v2 documentation and the official `runpod/runpod-mcp` repository, whose v2 migration tests track differences between the development and production API surfaces.

## Current production-log limitation

The production v2 API and the Pod container-log operation must be treated as separate contracts.

As of the 2026-08-27 UTC audit, the exact upstream evidence is pinned to:

```text
repository  runpod/runpod-mcp
commit      465872464c4f157a2e87afcd855c60a607954c26
path        test.md
section     K — Dev-only tools, currently DISABLED (not registered)
URL         https://github.com/runpod/runpod-mcp/blob/465872464c4f157a2e87afcd855c60a607954c26/test.md
```

That pinned official RunPod validation records:

- production REST v2 is live at `https://api.runpod.io/v2`;
- the Pod log stream operation `GET /v2/pods/{id}/logs` is present on the development v2 surface;
- the same operation is intentionally disabled in the official MCP production tool surface because production currently returns HTTP 422 `path not found`;
- the official tool is to be re-enabled only when the production operation ships.

Therefore `gpu-control` may implement and test bounded marker parsing and completion authentication **offline**, but it must not treat Pod log SSE as a supported production result-collection transport. A future live path needs either:

1. fresh evidence that RunPod has shipped the production Pod-log operation and the exact contract has been revalidated; or
2. a different provider-supported authenticated result transport that preserves the same isolation, boundedness, correlation, and cleanup requirements.

Opening SSH, a public service port, unrestricted runtime networking, or an unverified volume-transfer path merely to bypass this limitation is not an acceptable implicit fallback.

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

`EXITED` is intentionally not treated as success. RunPod Pod status shows that the container stopped, but the control plane still needs authenticated workload completion evidence to distinguish a successful experiment from an application failure or explicit stop.

The workload-side completion protocol and offline verifier now exist. The remaining blocker is a currently supported production transport that can retrieve that evidence before destructive cleanup.

## HTTP client constraints

`RunPodV2HttpClient`:

- uses only the fixed `https://api.runpod.io/v2` origin;
- puts the API key only in `Authorization: Bearer ...`;
- never puts credentials in a query string;
- uses a bounded request timeout;
- accepts only known Pod transition actions;
- validates response status and JSON shape;
- does not include the API key in raised error messages.

The current public policy in `policies/runpod-v2-policy.yaml` keeps live calls, CLI wiring, workflow wiring, and live result collection disabled.

## Remaining work before a real paid Pod

The remaining prerequisites are deliberately explicit:

1. implement a trusted image build/publish stage that produces `PublishedImageEvidence`;
2. derive fresh provider pricing and availability evidence from the current v2 catalog;
3. retain authenticated completion verification while choosing a production-supported collection transport;
4. revalidate the current production RunPod API immediately before activation, including the chosen result transport;
5. implement/review ambiguous-create reconciliation and idempotent cleanup reconciliation;
6. wire a live adapter only after the provider transport and repository security prerequisites are independently satisfied;
7. require fresh structured human authorization for the exact approved execution plan before any billable create.

Until those items are complete, no repository workflow can create a RunPod resource.
