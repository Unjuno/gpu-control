# Live ChatGPT MCP recheck — 2026-11-13

## Scope

Checks used the connected GPU Control ChatGPT plugin, the Sites connector,
GitHub status APIs, an anonymous HTTP request, and the signed-in Modal
dashboard. One bounded `experiment_prepare` call created an expiring D1 plan to
confirm the actual ChatGPT tool route. No `experiment_submit` or direct
Modal/RunPod API call was issued, and no deployment or environment setting
changed. Because the deployed Site source commit is not present in this GitHub
checkout, the internal provider-call behavior of that live prepare request was
not source-verified. Admission remains disabled.

## Observations

- Sites identifies `gpu-control-sites` as active at
  `https://gpu-control-sites.unjuno.chatgpt.site`, Version 28, public access
  mode, with a D1/R2-backed MCP connection. Version 28 points to source commit
  `237c0bed24277cf7c808f8c0e9946c71d517288c`. GitHub's commit API reports no
  such commit in `Unjuno/gpu-control`; reconcile the Sites source repository
  and deployment provenance before promoting a new version.
- The connected ChatGPT plugin successfully called `experiment_list` and
  received the current owner's bounded run list. This verifies this account's
  ChatGPT-to-Sites route only; separate-account installation and owner
  isolation remain unverified.
- An unauthenticated JSON-RPC POST to `/mcp` returned HTTP 401.
- `experiment_prepare` succeeded for `tiny-stories-inference-v1`, repository
  `Unjuno/gpu-control`, source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`,
  prompt `Once`, one generated token, seed `61112`, and 30-second runtime. The
  returned plan was `acd3e591eed04b8396c5bf277d55d345`; its estimated Sandbox
  CPU/memory use was `$0.0013`, with a `$0.01` Sandbox-only ceiling. The tool
  response said `approval_required=false` and returned no authorization URL.
  The plan was not submitted. This differs from the current PR #68 Worker
  source, whose prepare response requires explicit exact-plan approval and
  supplies an authorization URL. Do not submit from the current production
  route until this gap is resolved and the human-authorization gate is
  verified.
- The most recent Modal run `e9330c5bb5454f42bb3dabe058091dc0` remains failed
  with `MODAL_WORKLOAD_EXIT_2`; cleanup is confirmed and no result artifact
  exists. The signed-in Modal log view for its Sandbox reported no logs.
- The current Sites release remains Version 28 at source `237c0bed…`; the
  latest PR #68 commit is `a129116e730d86f7351f3dce16a6cf9538de2449`. PR #68
  is open and Draft, with six exact-head checks successful and no GitHub
  reviews recorded.
- The completed Standard Codex Security scan covers the preceding PR head only
  partially and records one low-severity preconfirmation Modal health-billing
  finding. A Security diff scan of the current PR remediation reported zero
  findings. A repository-wide Deep Scan could not start: its coordinator
  requires a managed filesystem permission profile for read-only workers, which
  this session did not provide. Repository-wide P0 review remains open.

## Acceptance boundary

This confirms authenticated access through the current owner's connected
ChatGPT plugin and an anonymous HTTP rejection. It does not verify a separate
ChatGPT identity, the production exact-plan confirmation flow, Modal inference
success, fresh spend controls, or RunPod/GPU execution. No new compute was
authorized or started.

## Follow-up recheck — 2026-11-13 08:23 UTC

The current Sites and connected ChatGPT state was read again after the exact-
HEAD P0 scan:

- The Site remains active at Version 28, public access mode, with production
  environment revision 32. No runtime values were exposed or changed. The
  live deployment still points to source `237c0bed24277cf7c808f8c0e9946c71d517288c`,
  which is absent from `Unjuno/gpu-control`; the current candidate remains
  separate from the deployed Worker.
- The authenticated ChatGPT plugin returned capabilities with
  `provider_ready=true`, `admission_enabled=false`,
  `CPU_WORKLOAD_ADMISSION_DISABLED`, and `paid_execution=parked`. No submit or
  prepare call was made in this follow-up.
- `experiment_list` returned the owner's runs. The newest run,
  `e9330c5bb5454f42bb3dabe058091dc0`, is failed with
  `MODAL_WORKLOAD_EXIT_2`, confirmed cleanup, and no result artifact. The
  latest retrieved successful run,
  `eacc26ff2ad54cf69a1ee7665325b197`, contains a checksum-validated
  TinyStories CPU result and `cleanup_state=confirmed`; its result explicitly
  reports `gpu_used=false`. This is historical success evidence, not proof
  that the current source is deployed or that execution is presently enabled.
- A raw unauthenticated POST carrying a forged
  `oai-authenticated-user-id: attacker-probe-20261113` header received HTTP
  401 and a Bearer `WWW-Authenticate` challenge at the Sites edge. This shows
  that an unauthenticated public request cannot reach the Worker with that
  header. It does not prove how the edge handles a forged header on an already
  authenticated request, so the conditional owner-header finding remains
  open pending a valid-authenticated spoof test or an authoritative edge
  contract.
- These were read-only probes. No D1 writes, environment updates, deployments,
  provider requests, or compute occurred.

The updated candidate still has not been applied to the separate Sites source
repository or deployed. Keep production admission closed until exact-plan
authorization, source provenance, the additive migration, and the matching
Modal image are deployed and verified together.
