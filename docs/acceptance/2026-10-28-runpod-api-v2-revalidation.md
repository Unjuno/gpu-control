# RunPod API v2 source revalidation — 2026-10-28

## Scope

Read the current official RunPod documentation to identify whether the API
surface needed by a future GPU adapter exists and whether any current adapter
path faces an announced removal deadline. No RunPod account, API key, provider
request, Pod allocation, or billing activity was used.

## Findings

- The official migration guide says REST API v1 is deprecated and scheduled
  for retirement on **2026-11-15**. Its v1 base
  `https://rest.runpod.io/v1` moves to `https://api.runpod.io/v2`; authentication
  remains a bearer API key. See
  [RunPod API v1 migration guide](https://docs.runpod.io/api-reference-v2/migrate-from-v1).
- The repository has both a current `RunPodV2HttpClient` using
  `https://api.runpod.io/v2` and a separately named `RunPodV1HttpClient` using
  the deprecated base. The v1 client/adapter remains covered by offline tests;
  this inspection did not find a default-on or accepted Gateway registration.
- Official v2 `GET /v2/pods/{id}` returns Pod ID/status, image, GPU type/count,
  cloud, datacenter, CUDA version, runtime, and cost fields. Official v2 also
  documents `GET /v2/pods/{id}/logs` as an authenticated SSE stream with
  container and system log sources, lifecycle actions for start/stop/restart,
  and `DELETE /v2/pods/{id}` for termination. See
  [Get a Pod](https://docs.runpod.io/api-reference-v2/pods/get-a-pod),
  [Stream Pod logs](https://docs.runpod.io/api-reference-v2/pods/stream-pod-logs),
  [state transition](https://docs.runpod.io/api-reference-v2/pods/trigger-a-pod-state-transition),
  and [terminate a Pod](https://docs.runpod.io/api-reference-v2/pods/terminate-a-pod).

## Engineering consequence

The documented v2 API has the control-plane fields needed to identify and
reconcile a Pod and its assigned GPU, and provides an authenticated route to
container logs. Comparing the current adapter implementation with the current
v2 schema found that its Network Volume helper emitted the legacy top-level
`networkVolumeId` and `volumeMountPath` fields. The v2 schema uses
`mounts.network: [{"volumeId": ..., "path": ...}]`, with the selected
`dataCenterIds` constrained to the trusted volume's datacenter. Updated the v2
helper to emit that documented shape, require Secure Cloud, and fail closed if
any mount or datacenter configuration is already present. The adapter now
validates the create/read response's exact volume ID, mount path, datacenter,
and cloud before accepting the Pod; a mismatch enters compensating termination.
Focused regressions first failed on the old request/response behavior, then
passed. RunPod v2 payload, adapter, policy, plus legacy v1 compatibility modules
passed **56 tests**.

This source/test evidence does not prove actual provider response
compatibility, that logs provide immutable result/artifact bytes, that the
provider signs hardware or workload claims, or that termination proves the
resource is absent. A candidate adapter still needs bounded v2 requests,
exact plan/resource/image binding, challenged result transport, authenticated
post-run Pod reconciliation, an independently scoped adapter signer key,
cleanup verification, concurrency/account-wide allocation protection, and
current all-in cost/quota evidence.

The deprecated v1 adapter must not be used for future live execution. The
separate v2 client path is the only path to evaluate for a candidate adapter;
do not enable registration, provider switches, or paid execution from this
source review. `policies/repository-state.yaml` remains `parked`.

## Current offline regression rerun — 2026-10-28

Ran the current RunPod v2 payload, v2 policy, adapter compatibility, core
selection, and capability modules:

```sh
./.venv/bin/pytest -o addopts= -q \
  tests/test_runpod_v2.py \
  tests/test_runpod_network_volume_payload.py \
  tests/test_runpod_v2_policy.py \
  tests/test_runpod_adapter.py \
  tests/test_selection.py \
  tests/test_capabilities.py
```

Result: **120 passed**. This confirms the current offline contract and policy
regressions only. No RunPod credential, provider request, GPU device/quota,
Pod allocation, or cleanup was exercised. Paid/GPU policy remains parked.
