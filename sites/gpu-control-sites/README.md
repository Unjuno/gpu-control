# GPU Control Sites

Public ChatGPT MCP Site source for `Unjuno/gpu-control`.

## Current hosted state

- Live URL: <https://gpu-control-sites.unjuno.chatgpt.site>.
- Deployed Site version: 28, source commit
  `237c0bed24277cf7c808f8c0e9946c71d517288c`; current environment revision 32.
- Access mode: public Site, with authenticated owner-scoped MCP operations.
- State and artifacts: Sites D1 binding `DB` and R2 binding `BUCKET`.
- Current ChatGPT capability evidence (2026-11-12 13:46 UTC):
  `provider_ready=true`, every provider health check passed,
  `admission_enabled=false`, and `available=false` for
  `modal_cpu`. The latest bounded ChatGPT-initiated run failed with workload
  exit code 2; cleanup was confirmed. The v28 Worker labels the provider as
  billable and estimates Sandbox CPU/memory only. The estimate excludes
  separately billed Modal control functions and is not a total-cost guarantee.
- MCP access is restricted to the owner IDs listed in the secret runtime
  variable `GPU_CONTROL_ALLOWED_USER_IDS`; missing or non-listed identities
  are rejected before D1 or Modal access.
- The former macOS Runner, its Worker routes, and its bearer secret are retired.
- Modal control service is deployed at `unjuno--gpu-control-sites-control-api`
  in `main`; the current health response matches all eight Site checks,
  including source, image digest, fingerprint, and runtime. The deploy used a
  temporary one-hour Workspace token which was deleted immediately afterward.
  The Modal Usage page showed a `$1` Workspace usage limit, `$0.04` in credits
  used, and `$0` in charges at 2026-11-12 12:20 UTC, up from `$0.03` before the
  run. This total includes control/deploy activity and cannot be attributed to
  the Sandbox alone. The displayed limit is an account-level ceiling, not a
  per-run cost guarantee. Official Sandbox list rates imply about `$0.0013` for
  the maximum 30-second, 1-core, 512-MiB request; credits may offset this usage.
  The fix that drops Sandbox privileges to UID/GID 10001 and binds that
  effective command into the image fingerprint is deployed. The four-token run
  `eacc26ff2ad54cf69a1ee7665325b197` was executed by the retired local Runner.
  The latest one-token Modal run `e9330c5bb5454f42bb3dabe058091dc0` failed
  with `MODAL_WORKLOAD_EXIT_2`; Modal dashboard showed Sandbox
  `sb-01M77ZZRFC1090CXA2W3MHDH7V` failed with code 2 after 247 ms and no logs.
  Sites recorded cleanup confirmed and no artifact was produced. The bounded
  preflight line marker was absent, leaving the failed check unknown. The
  one-run authorization is consumed; do not retry without new authorization
  and a useful diagnostic change. RunPod remains absent from the Sites Worker
  route and GPU/paid execution remains parked.
- A fresh read-only history check found another failed status,
  `0f2a3ddaa7da40648600bae21ccd9ed1`, created earlier at 11:25 UTC with
  `MODAL_WORKLOAD_EXIT_2`, confirmed cleanup, and no artifact. Its deployment
  and authorization provenance remain unknown; it is retained as a separate
  failed event.
- Diagnostic follow-up commit `d1dd4fe2bbaf220e24fe1c1f97f958491a3d5674`
  adds a non-sensitive inference preflight line marker and strict Worker
  persistence; it is deployed to Modal `unjuno/main`. The marker was absent in
  the latest run. The temporary Workspace deploy token was revoked and the
  API-token page showed zero tokens.
- The deployed ChatGPT tool schema accepts
  `experiment_prepare.max_cost_usd=0.01`, matching this Worker's usage-billed
  Sandbox CPU/memory ceiling.
- The Worker uses a 15-second bounded Modal request timeout to accommodate a
  measured 6.3-second cold start; this change is deployed in Site Version 28.
- Vercel and Neon/PostgreSQL are not target runtime dependencies.

Every data-bearing or execution MCP tool must require the Sites-injected user
ID and enforce D1 ownership. This ChatGPT connection has called the capability
and experiment-list tools; access from another ChatGPT account/process is not
yet verified. Anonymous HTTP probes were blocked at the edge and do not verify
Worker-level authentication. Execution is currently disabled after the one
explicitly authorized bounded Modal attempt. The `$0.01` ceiling applies to
Sandbox CPU/memory only.
Control-function charges are separate and remain governed by the account-level
Workspace usage limit.

## Target execution architecture

The Site remains the only ChatGPT-facing product and control plane. Modal is the
first bounded compute provider; Runpod is a later GPU provider that stays behind
separate authorization, pricing, availability, result-integrity, and cleanup
gates. D1/R2 lifecycle data must be preserved through the transition.

```text
ChatGPT -> public Sites MCP Worker (authenticated stateful tools) -> D1/R2
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
