# RunPod v2 cursor inventory hardening — 2026-11-12

## Scope

Moved the canonical RunPod price, inventory, and adapter path to REST v2. The
inventory collector must consume every cursor page before it can produce
account occupancy or reconciliation evidence. Live RunPod requests, API
credentials, Pod allocation, and billing were not used.

## Changes

- `GET /v2/pods` follows the documented `pods` plus `pagination` envelope and
  passes the opaque `nextCursor` on subsequent requests.
- Requests are bounded to at most 32 pages and 256 Pod records. Duplicate Pod
  IDs, repeated cursors, malformed pagination, oversized pages, and incomplete
  inventories fail closed.
- Current price/capacity and exact datacenter availability use the v2 GPU
  catalog. Secure price, one-GPU capacity, VRAM, and `HIGH` availability for
  the trusted Network Volume datacenter are bound into short-lived evidence.
- `RunPodV2CurrentAdapter` requires that evidence and revalidates it before
  submission. The v1 API and GraphQL pricing policy are marked legacy and
  forbidden for live calls.

## Verification

The full offline suite passed **565 tests**, with **1 skipped**. `git diff
--check` passed. A Security Review found an unbounded-page-count risk when
empty pages returned fresh cursors; the 32-page cap and a regression test were
added afterward. The review was not rerun after that focused fix.

No live provider behavior, account inventory, pricing, result transport,
cleanup, or paid GPU execution is verified by these offline checks. Live calls
remain disabled and `policies/repository-state.yaml` remains parked.
