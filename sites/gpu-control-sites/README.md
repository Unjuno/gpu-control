# GPU Control Sites

Public ChatGPT MCP Site source for `Unjuno/gpu-control`.

## Current hosted state

- Live URL: <https://gpu-control-sites.unjuno.chatgpt.site>.
- Site Version 34 is live from source commit
  `18339d5106ff148d0ec4b3acf8da64791b69d54f`; its published environment
  revision is 39 and deployment `appgdep_6af8a25b69b08191a7d67795a7b571ac`
  succeeded. Platform access is public, with an owner account ID allowlist
  enforced for MCP operations. Cross-account denial and trusted provenance of
  the platform-injected identity are not independently verified.
- State and artifacts use Sites D1/R2 bindings `DB` and `BUCKET`. ChatGPT
  capability and experiment-list calls succeeded from the connected owner
  account. Modal is configured and authorization storage is ready.
  `CPU_WORKLOAD_ADMISSION_ENABLED=true` in environment revision 39. The
  corrected Modal endpoint is deployed, but provider health and post-correction
  inference have not yet been verified.
- Only `tiny-stories-inference-v1` is exposed: maximum 30 seconds, one
  in-flight run, estimated Sandbox cost `$0.0013`, and a declared `$0.01`
  per-run Sandbox CPU/memory ceiling. The currently deployed Sandbox had CPU
  and memory limits displayed as `None`; its `cpu=1` and `memory=512` values
  were requests, so bursting could exceed that declared dollar ceiling. Current
  candidate source now sets request=limit to 1 physical CPU core and 512 MiB,
  fingerprints both limits, and documents CPU throttling and memory OOM failure.
  Current Site environment revision 39 registers fingerprint
  `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5` and image
  digest `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  Modal control-function charges remain outside the per-run Sandbox ceiling. A
  one-use confirmation is required for each exact plan.
- The five most recent Modal-origin runs failed with `MODAL_WORKLOAD_EXIT_2`
  or `MODAL_WORKLOAD_FAILED`; each reports cleanup confirmed and has no result
  artifact. The newest inspected sandbox failed after 247 ms on November 12,
  before the November 14 Modal API deployment, and had no logs. A local
  OrbStack reference-container smoke passed with the fixed bootstrap, but a
  successful inference on the current Modal deployment is not yet accepted.
  Earlier successful records used the retired local Runner and are not Modal
  acceptance.
- The Modal `main` app was redeployed from PR #68 candidate
  `3eb2ab5d218b06c2559fd22088e1a4763fc78521`; the deployment completed
  successfully without starting a Sandbox. The control function currently has
  zero live containers and zero running calls. Its displayed limits are 1 CPU
  request with default CPU limit, 512 MiB memory request with no memory limit,
  and a 60-second timeout. These control-function settings and charges are
  separate from the hard-limited Sandbox workload.
- The Modal Workspace usage limit is `$1`. Account-specific usage and balance
  details are intentionally omitted from this public repository. The
  Workspace API-token list shows zero active tokens after the temporary deploy
  token was revoked. The user's `$1`
  testing authorization is aggregate, not per run. Control-function charges
  count toward the Workspace limit but are not included in the Sandbox
  estimate. Keep the Workspace hard limit in place.
- The current owner prepared a fresh exact CPU plan, but its confirmation page
  required a ChatGPT sign-in in the browser. No health call or Sandbox request
  was issued from that plan; the five-minute plan expired before owner
  confirmation. CPU admission is enabled under the Workspace `$1` cap and
  exact-plan, one-use confirmation. Sign into the Site, then prepare and confirm
  a fresh plan before any provider call.
- The former macOS Runner, its Worker routes, and its bearer secret are retired.
  RunPod is not connected to the Site Worker; GPU and paid execution remain
  parked. Vercel and Neon/PostgreSQL are not target runtime dependencies.
- See [current Site acceptance](../../docs/acceptance/2026-11-13-sites-v33-live-refresh.md),
  [Modal deployment acceptance](../../docs/acceptance/2026-11-13-modal-main-deploy.md),
  and [latest Modal local smoke and live gate](../../docs/acceptance/2026-11-14-modal-local-smoke-and-live-gate.md).

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
