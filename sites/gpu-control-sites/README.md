# GPU Control Sites

Public ChatGPT MCP Site source for `Unjuno/gpu-control`.

## Current hosted state

- Live URL: <https://gpu-control-sites.unjuno.chatgpt.site>.
- Site Version 33 is live from source commit
  `c85fdf7da994ab59b8a19bbb42b2998bc9814e69`; deployment succeeded with
  environment revision 34. Platform access is public, with an owner account ID
  allowlist enforced for MCP operations. Cross-account denial and trusted
  provenance of the platform-injected identity are not independently verified.
- State and artifacts use Sites D1/R2 bindings `DB` and `BUCKET`. ChatGPT
  capability and experiment-list calls succeeded from the connected owner
  account on 2026-11-13. Capabilities report Modal configured, authorization
  storage ready, and CPU admission enabled. Provider readiness is deferred
  until an exactly authorized submit.
- Only `tiny-stories-inference-v1` is exposed: maximum 30 seconds, one
  in-flight run, estimated Sandbox cost `$0.0013`, and a `$0.01` Sandbox
  CPU/memory ceiling. Modal control-function charges are separate and are not
  covered by that per-run ceiling. A one-use confirmation is required for each
  exact plan.
- The five most recent Modal-origin runs failed with `MODAL_WORKLOAD_EXIT_2`
  or `MODAL_WORKLOAD_FAILED`; each reports cleanup confirmed and has no result
  artifact. They predate the Modal API deployment containing the fixed
  privilege-dropping bootstrap. A successful inference on the corrected Modal
  image is not yet accepted. Earlier successful records used the retired local
  Runner and are not Modal acceptance.
- The Modal API deployment is recorded from PR #68 head `496e28c`. The current
  local workload image ID is
  `sha256:60ea9d29f70def1ad4577021ac51e2b186b8f8d2c6dee7a2d2d848b441fcbda1`,
  while the Site advertises
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  These identities have not been reconciled, and authenticated provider
  readiness is unverified. Keep the provider gate open until a fresh exact-plan
  run proves output provenance and cleanup.
- The last recorded Modal dashboard snapshot showed a `$1` Workspace usage
  limit and `$0` charges. The current net spend limit has not been verified.
  Modal's billing documentation distinguishes a gross usage budget from the
  net spend limit; the Sandbox ceiling does not cap separately billed control
  calls.
- The former macOS Runner, its Worker routes, and its bearer secret are retired.
  RunPod is not connected to the Site Worker; GPU and paid execution remain
  parked. Vercel and Neon/PostgreSQL are not target runtime dependencies.
- See [current Site acceptance](../../docs/acceptance/2026-11-13-sites-v33-live-refresh.md)
  and [Modal deployment acceptance](../../docs/acceptance/2026-11-13-modal-main-deploy.md).

## Target execution architecture

The Site remains the only ChatGPT-facing product and control plane. Modal is the
first bounded compute provider; Runpod is a later GPU provider that stays behind
separate authorization, pricing, availability, result-integrity, and cleanup
gates. D1/R2 lifecycle data must be preserved through the transition.

```text
ChatGPT -> Sites MCP Worker -> owner-scoped D1/R2
                    -> exact-plan Sites confirmation page -> one-use D1 authorization
                                    -> authenticated Modal function
                                    -> Runpod only after live gates pass
```

No caller may choose arbitrary code, an image, a command, a provider URL, a
secret, or an owner ID. Provider call IDs and results must be bound to the
persisted run, plan fingerprint, and registered workload before they can change
run state or become retrievable artifacts.

## Retired local Runner

The former macOS LaunchAgent was unloaded, its local runtime was removed, and
its two Keychain credentials were deleted. Do not restore or use that path, ask
for a macOS password, or enable `RUNNER_BEARER_TOKEN` for a local poller. The
legacy `/runner/*` Worker routes and the obsolete Site secret are removed from
the current Site source/runtime. Historical run and artifact records remain
untouched.

## Source layout

- `worker/index.js`: ChatGPT MCP Worker and D1/R2 control-plane logic.
- `drizzle/`: append-only D1 schema migrations.
- `modal/`: authenticated, fixed-purpose Modal control API. Its Sandbox can
  start only the pinned CPU workload and has outbound networking blocked.
- `workloads/tiny_stories_inference/`: pinned workload and container recipe.
  Provider-specific packaging must verify the source and model digests before
  use.
- `workloads/third_party/llama2.c/`: the pinned upstream C inference source
  and its license.
- `scripts/`: deterministic Worker build and artifact validation.

## Verification and acceptance

Past end-to-end CPU runs through the local Runner are historical evidence only.
Their exact inputs, outputs, checksums, and cleanup observations are retained
under `docs/acceptance/`. Current provider readiness must be established through
the ChatGPT Site itself. The staged plan and acceptance criteria are in
[`../../docs/SITES_MODAL_RUNPOD_DELIVERY.md`](../../docs/SITES_MODAL_RUNPOD_DELIVERY.md).

The migration directory is append-only after publication. Do not erase D1/R2
records or rewrite historical acceptance evidence during provider migration.
