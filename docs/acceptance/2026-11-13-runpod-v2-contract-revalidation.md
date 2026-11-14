# RunPod REST v2 contract revalidation — 2026-11-13

## Scope

Revalidated the repository's bounded RunPod REST v2 adapter against RunPod's
current official API reference and OpenAPI document. This was a documentation
and schema read only. No RunPod credential, account endpoint, Pod allocation,
Network Volume, or billing operation was used.

## Current contract

- The official production server remains `https://api.runpod.io`; v2 operations
  are under `/v2`. The OpenAPI document identifies itself as Runpod REST API
  version `2.0.0`.
- The v2 migration guide still says REST v1 is deprecated and retires on
  **2026-11-15**. Authentication remains a Bearer API key in the
  `Authorization` header.
- `GET /v2/pods` returns `pods` with cursor metadata (`nextCursor`,
  `hasNextPage`). `limit` is documented from 1 to 1000. The local client uses
  the stricter 256-record, 32-page bound and rejects malformed or partial
  inventories.
- `GET /v2/catalog/gpus` supports `include=AVAILABILITY`, `product=POD`,
  `count=1`, and a `cloud` selector. Its response includes prices, capacity,
  GPU memory and per-datacenter availability used by the current evidence
  builder.
- `POST /v2/pods` returns **201** when it creates a Pod immediately. The API
  also documents **202** for a queued request when the request includes
  `queue` and capacity is unavailable or `queue.startsAt` is in the future;
  that response represents a queued resource, with a `Location` for
  `GET /v2/queued-pods/{id}` and a separate cancellation operation. The
  current adapter does not send `queue` and expects 201, so it deliberately
  rejects 202 instead of accepting an unimplemented queued lifecycle.
- Pod create requests use `mounts.network` entries with `volumeId` and `path`;
  preferred placement uses top-level `dataCenterIds`. `DELETE /v2/pods/{id}`
  remains the documented termination operation.

## Engineering consequence

No API migration was needed for the current non-queued path. The policy now
records the 201/202 distinction and that queueing is disabled. A regression
test proves that a 202 response is rejected when the request omitted `queue`.
Any future queue support must add queued-resource polling, identity binding,
expiry and cancellation reconciliation before it is enabled.

## Acceptance boundary

The official reference confirms contract shape only. It does not verify a live
RunPod account, current resource availability or price, image pull, completion
secret injection, result collection, account-wide occupancy, cleanup, or GPU
execution. RunPod remains disabled and parked pending those separate gates.

## Completion signer security blocker — 2026-11-13

The original workload ran the training process with the completion key, which
allowed that process to forge completion-v3 evidence. The configured Orbitune
workload at `fc131174a9b529a9825f54fccf1a7df4c63c9a1a` now has a root-owned
wrapper that captures and removes the key before starting training as fixed
UID/GID 10001 without supplementary groups. The control-plane candidate sends
the per-run key to that digest-pinned wrapper and refuses provider submission
unless authenticated Network Volume result collection is configured. This
protects against unprivileged training-code forgery; it does not attest the
RunPod host or an account administrator. RunPod live allocation and collection
remain disabled pending live acceptance.

The current official [REST v2 OpenAPI document](https://api.runpod.io/v2/openapi.json)
defines `GET /pods/{podId}` as returning a `Pod` schema, but contains no
`exitCode` or `exit_code` property. Do not replace the removed key with
controller-side signing that repeats a workload-supplied exit-code claim. A
replacement must keep signing material outside the Pod, bind the exact
provider job and result bytes, and state clearly which terminal facts are
observed from RunPod versus reported by the workload. Independently review
that boundary before enabling RunPod.

## Official references

- [RunPod API v2 create a Pod](https://docs.runpod.io/api-reference-v2/pods/create-a-pod)
- [RunPod API v2 list Pods](https://docs.runpod.io/api-reference-v2/pods/list-pods)
- [RunPod API v2 list GPU types](https://docs.runpod.io/api-reference-v2/catalog/list-gpu-types)
- [RunPod API v2 migration from v1](https://docs.runpod.io/api-reference-v2/migrate-from-v1)
- [RunPod API v2 OpenAPI](https://api.runpod.io/v2/openapi.json)

## Fresh official OpenAPI check — 2026-11-14 17:01 UTC

A fresh unauthenticated read of the current official OpenAPI document reports
REST API version `2.0.0` at `https://api.runpod.io` and includes
`GET /v2/pods/{id}/logs`, with a `200 text/event-stream` response. The current
official documentation also lists the Stream pod logs operation and its
bounded `tail` parameter. This corrects the earlier inference from the
`runpod/runpod-mcp` repository's disabled MCP tool: that project-specific note
does not establish that RunPod's production REST endpoint is unavailable.

This is only an official contract/documentation observation. No RunPod API key,
authenticated request, Pod, GPU, Network Volume, or billing operation was used.
The endpoint remains unverified against this account, and SSE has not been
enabled as a result transport. The independent completion-integrity and
cleanup gates still block live execution.
