# P1 v10 to P5 schema migration lineage repair — 2026-11-03

Status: **cross-branch SQLite upgrade reproduced and repaired locally; focused
migration tests pass; full-suite, PR integration, PostgreSQL upgrade, and hosted
database migration NOT RUN.**

## Finding

The latest published P1 candidate, PR #66 head
`1adc2417ef506bd0b9bac4dacafc8b0f5f8ea0f2`, uses schema v10. Its v8-v10
migrations cover OAuth consent and login-rate-limit tables. The P5 candidate
branch `codex/gpu-control-current-p5-on-pr58` at `14361c32091db9789e38ffe84d0150a0527185f8`
used overlapping version numbers for provider observations and account leases.
Applying P5 to the P1 v10 database therefore advanced the version while leaving
both P5 tables absent. Its v13 migration also risked resetting explicitly
consented P1 OAuth clients because it could not distinguish the two histories.

## Repair

- Bumped the P5 candidate schema version to 14.
- The new additive migration creates provider-observation and account-lease
  tables with `checkfirst=True`, so it repairs the cross-lineage schema and is
  safe to re-run.
- OAuth-consent repair now detects the old P5 lineage from its provider tables.
  It keeps the conservative reset for clients that may have received inferred
  consent on that lineage, while preserving explicit consent from P1 v9/v10.
- Added a focused regression case for P1 v10 login-budget data, explicitly
  consented OAuth clients, missing P5 tables, and repeat migration.

## Verification

An isolated temporary SQLite database was initialized by the exact PR #66
checkout, given an explicitly consented ChatGPT client, then upgraded by the
P5 candidate source. The observed before/after state was:

```text
P1: schema 10; login budget present; consented client true;
    provider observations absent; account leases absent
P5: schema 14; login budget preserved; consented client true;
    provider observations present; account leases present;
    paid authorizations present
```

A second migration was idempotent. The focused migration suite passed **12
tests** using the existing Python 3.12 test environment from the PR #66
worktree, with `PYTHONPATH=.:../src` so imports came from this P5 candidate.
Python `compileall` and `git diff --check` also passed. The exact cross-branch
upgrade reproduction above separately used the PR #66 source for initialization
and this P5 source for upgrade. PostgreSQL and hosted databases were not
touched.

If an environment was already upgraded with the earlier P5 v13 code from a
P1 v10 database, that migration may already have reset OAuth clients' persistent
consent flags. This repair does not reconstruct consent; those clients must
complete owner consent again. Do not restore the flags from token history.

## Integration limits

This change is on the existing P5 candidate based on PR #58, not on PR #66.
That P5 candidate lacks some later P1 security/operations changes, including
the P1 login throttling migration itself. Before integration or deployment,
rebase/merge P5 onto the current P1 candidate and re-run the migration suite on
the resulting exact head. Do not run this against production until the normal
paired backup, restore, and migration approval gates pass. Repository mode and
all provider spending gates remain unchanged.

A read-only `git merge-tree --write-tree` preflight between the existing P5
candidate and PR #66's exact head reports 40 conflicted files, including the
Gateway worker, API, configuration, migrations, OAuth flow, deployment units,
and their tests. No merge was attempted. Integration must preserve PR #66's
login throttling, database-role separation, and operational improvements while
applying the migration repair; the P5 candidate is not yet ready to deploy.

The source comparison also found a security incompatibility that a clean text
merge would miss: PR #66's worker role cannot update `gateway_runs_v1.slot_reserved`
or `gateway_control_v1.active_count`; it must call the narrowly scoped
`gpu_control_release_finished_slot` SECURITY DEFINER function. P5's
`finish_run_after_provider_cleanup` currently updates both fields directly.
PR #66's role script also has no grants for the new P5 authorization and
provider-lease tables. Resolve this with narrowly scoped database functions or
column/table grants that enforce the same exact-run and lease-token conditions,
then add PostgreSQL tests executed as the real runtime roles. Until that work
passes, do not apply the P5 code under PR #66's runtime roles or call the merged
stack secure.
