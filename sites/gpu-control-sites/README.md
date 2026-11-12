# GPU Control Sites

Public ChatGPT MCP Site source for `Unjuno/gpu-control`.

## Current hosted state

- Live URL: <https://gpu-control-sites.unjuno.chatgpt.site>.
- Access mode: public Site, with authenticated owner-scoped MCP operations.
- State and artifacts: Sites D1 binding `DB` and R2 binding `BUCKET`.
- The current capability tool reports `available=false`,
  `provider_ready=false`, and `admission_enabled=false` for `modal_cpu` until
  the Modal endpoint, Workspace Proxy Token, image fingerprint, and admission
  flag are configured and health-checked.
- The former macOS Runner, its Worker routes, and its bearer secret are retired.
- Modal control service and the Sites adapter are now in source, but the
  endpoint and runtime credentials are not deployed; no Modal Sandbox has been
  started. RunPod is not connected and paid GPU execution remains parked.
- Vercel and Neon/PostgreSQL are not target runtime dependencies.

Every data-bearing or execution MCP tool must require the Sites-injected user
ID and enforce D1 ownership. This ChatGPT connection has called the capability
and experiment-list tools; access from another ChatGPT account/process is not
yet verified. Anonymous HTTP probes were blocked at the edge and do not verify
Worker-level authentication. Provider admission remains disabled.

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
