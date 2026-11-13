# Sites production source reconciliation — 2026-11-13

## Scope and method

Read the active `gpu-control-sites` Site metadata and Version 28 provenance,
then used the Sites source workflow to fetch the bound `main` source into a new
temporary checkout. The checkout was `/tmp/gpu-sites-audit.HFvtMn/.sites-checkout`
and its HEAD was `237c0bed24277cf7c808f8c0e9946c71d517288c`. No remote source
write, version save, deployment, D1 migration, or provider call was performed.
The temporary source credential was passed only through helper stdin.

## Findings

- The source commit exists in the Cloudflare artifact Git repository bound to
  this Site, but is not a commit in `Unjuno/gpu-control`. The public Site and
  GitHub PR therefore have independent source histories; PR CI does not
  validate the currently deployed Worker.
- Version 28 source `worker/index.js` returns `approval_required: false` from
  `experiment_prepare` and provides no exact-plan authorization URL. Its
  `experiment_submit` calls `providerHealth()` before checking admission and
  has no human-authorization check at all. The live ChatGPT prepare response
  observed earlier in the day has the same behavior. Do not use this production
  submit route until exact-plan approval and preflight billing behavior are fixed.
- Version 28's source tree does not contain
  `drizzle/0005_human_plan_authorization.sql`,
  `modal/gpu_control_modal_bootstrap.py`, or
  `modal/requirements.in`; its TinyStories Dockerfile still uses the older
  entrypoint contract. The read-only D1 overview returned only `plans`,
  `runner_heartbeats`, and `runs`; the migration's `authorization_challenges`
  and `human_authorizations` tables are absent. No rows were read or changed.
  Preserve all existing tables and records during migration.
- Running `npm test` in the isolated Version 28 source checkout completed with
  22 passed, 0 failed, 0 skipped. These tests describe the older source and do
  not establish the new approval invariant or prove live runtime acceptance.
- The current GitHub candidate includes the human-authorization migration and
  approval checks, a Modal bootstrap module and dependency input, and the
  Dockerfile startup fix. Its Worker tests specifically require the exact-plan
  confirmation response and check provider health only after authorization.
  It is still an unmerged Draft PR and is not deployed.

## Required reconciliation

1. Keep admission closed and keep the live `experiment_submit` route unused.
2. Complete independent P0/security review and obtain PR review for the exact
   current head.
3. After review, synchronize the reviewed source to the Site's bound source
   repository, apply and verify the additive D1 migration, and save/deploy the
   matching source version through Sites.
4. Re-check the deployed prepare/confirmation flow and provider-health ordering
   through the connected ChatGPT tool before authorizing another Modal run.
5. Keep RunPod/GPU and paid execution gated until their independent provider,
   result, recovery, and cleanup acceptance passes.

