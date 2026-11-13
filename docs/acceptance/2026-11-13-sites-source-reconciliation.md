# Sites production source reconciliation — 2026-11-13

## Scope and method

Read the active `gpu-control-sites` Site metadata and Version 28 provenance,
then used the Sites source workflow to fetch the bound `main` source into a new
temporary checkout. The checkout was `/tmp/gpu-sites-audit.HFvtMn/.sites-checkout`
and its HEAD was `237c0bed24277cf7c808f8c0e9946c71d517288c`. No remote source
write, version save, deployment, D1 migration, or provider call was performed.
The temporary source credential was passed only through helper stdin.

A separate read of production runtime settings reported revision 32, last
updated `2026-11-12T13:45:33.497536Z`, and
`CPU_WORKLOAD_ADMISSION_ENABLED=false`. Modal proxy credential entries are
marked secret and their values were returned as `null`; this does not establish
whether the credentials are configured. No values were logged or changed.

## Findings

- The source commit exists in the Cloudflare artifact Git repository bound to
  this Site, but is not a commit in `Unjuno/gpu-control`. The public Site and
  GitHub PR therefore have independent source histories; PR CI does not
  validate the currently deployed Worker.
- Migrations `0000` through `0004` in the fetched live source are byte-identical
  to the GitHub candidate. The deployed D1 table overview showed the expected
  current tables plus no authorization tables, so candidate migration `0005`
  is the missing additive schema step; no production migration was run.
- Version 28 source `worker/index.js` returns `approval_required: false` from
  `experiment_prepare` and provides no exact-plan authorization URL. Its
  `experiment_submit` calls `providerHealth()` before checking admission and
  has no human-authorization check at all. The live ChatGPT prepare response
  observed earlier in the day has the same behavior. Do not use this production
  submit route until exact-plan approval and preflight billing behavior are fixed.
- Production admission is currently closed at environment revision 32. Modal
  secret values remain unverified because the environment reader returned them
  as `null`.
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
- Semgrep 1.161.0 `p/security-audit` on the fetched Version 28 source completed
  with 0 findings and no scan errors. A redacted Gitleaks working-tree scan
  found three `generic-api-key` matches; all three are 64-character hex values
  assigned to `TOKENIZER_SHA256` / `MODAL_TOKENIZER_SHA256` constants. These
  are fixed integrity checksums, not provider credentials. This narrow static
  scan is not a substitute for repository P0 review.
- Added [`tests/test_sites_d1_migrations.py`](../../tests/test_sites_d1_migrations.py)
  to replay all six migrations in an in-memory SQLite database. It starts with
  synthetic pre-migration plan, failed-run, and retired-runner heartbeat rows,
  confirms those rows survive migrations 0001–0004, creates the 0005 approval
  tables, inserts valid approval records, and checks foreign-key integrity.
  `uv run --locked pytest` passed 573 tests with 1 skipped. This verifies the
  checked-in SQLite-compatible sequence against representative rows; it does
  not mutate or prove the live D1 database.
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

