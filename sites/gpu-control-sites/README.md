# GPU Control Sites

Private ChatGPT MCP Site source for `Unjuno/gpu-control`.

## Current live state — 2026-11-12

- Site: `gpu-control-sites`, currently owner-only, deployed Version 16.
- Live URL: <https://gpu-control-sites.unjuno.chatgpt.site>.
- Hosting/control plane: ChatGPT Sites Worker.
- State and artifacts: Sites D1 binding `DB` and R2 binding `BUCKET`.
- ChatGPT capability response: `available=false`, `runner_ready=false`,
  `admission_enabled=false`; the former `local_cpu` path is unavailable.
- Paid execution: parked. Modal and Runpod are not yet connected to this Site.
- Vercel, Neon/PostgreSQL, macOS Keychain, and the personal-host Runner are not
  supported runtime dependencies.

The requested target is public discovery with authenticated use. Do not change
the Site audience until anonymous requests are proven unable to access user
data or invoke compute. Every data-bearing or execution MCP tool must require
the Sites-injected user ID and enforce D1 ownership. Add per-user and global
resource bounds before any public compute route is enabled.

## Target execution architecture

The Site remains the only ChatGPT-facing product and control plane. Modal is the
first bounded compute provider; Runpod is a later GPU provider that stays behind
separate authorization, pricing, availability, result-integrity, and cleanup
gates. D1/R2 lifecycle data must be preserved through the transition.

```text
ChatGPT -> private Sites MCP Worker -> D1/R2
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
legacy `/runner/*` Worker routes and their Site secret are scheduled for removal
in a reviewed saved-Site cutover. Historical run and artifact records remain
untouched.

## Source layout

- `worker/index.js`: ChatGPT MCP Worker and D1/R2 control-plane logic.
- `drizzle/`: append-only D1 schema migrations.
- `workloads/tiny_stories_inference/`: pinned workload and container recipe;
  it is not a current compute service. Provider-specific packaging must verify
  the source and model digests before use.
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
