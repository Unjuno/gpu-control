# Existing Neon schema migration evidence — 2026-10-28

## Scope

PASS for a local isolated PostgreSQL rehearsal of the current Gateway
operator `--init-db` path against a synthetic copy of the live Neon Gateway
v1 table shape through schema v7. This is not a production migration, deployment, backup/restore
drill, independent review, or ChatGPT acceptance.

## Read-only production inventory

Neon MCP inspection used project `delicate-smoke-00521013` and production branch
`br-raspy-cell-b3l93n46`. No database settings or rows were changed. No
credential/hash/token/session values or row JSON were read.

- PostgreSQL 17, region `aws-ap-southeast-1`; branch state ready, branch
  protection disabled, history retention 21,600 seconds.
- `gateway_runs_v1`: 0 rows; `gateway_control_v1.id=1`: `active_count=0`.
- `gateway_schema_version` is absent.
- Gateway run columns match the unversioned v1 layout in the local migration
  source. `gateway_control_v1` has `id`, `active_count`, and `worker_seen_at`;
  v5 `supervisor_seen_at` is absent.
- OAuth tables include admin, bootstrap, clients, codes, login guard, sessions,
  and tokens. Aggregate counts were respectively 1, 0, 0, 0, 1, 1, and 0.
  In particular, live owner-auth configuration exists; counts do not establish
  its usability or any session/token value.

## Isolated rehearsal

- Local Docker server: 29.8.2; disposable PostgreSQL 16 container exposed only
  on loopback port 55433.
- Created the observed unversioned Gateway run/control schema and synthetic
  OAuth admin/login-guard/session/client/unrevoked-token rows. Inserted one
  synthetic terminal run representing a legacy record.
- Ran the current `Store.initialize()` implementation from this worktree.
- The first rehearsal reported schema version 6, which was current at that
  time. A v7 refresh is recorded below. The run owner, idempotency key, and terminal
  state were preserved; its legacy `cleanup_state` was conservatively
  `unknown`, `attempt` was 0, and `last_observed_at` remained NULL. The control
  singleton remained at `active_count=0` and gained `supervisor_seen_at=0`.
- OAuth table counts after migration were admin 1, bootstrap 0, clients 1,
  codes 0, login guard 1, sessions 1, and tokens 1. The synthetic token remained
  unrevoked. This verifies additive schema compatibility and preservation of
  representative synthetic auth records only.
- The first probe attempt used a container without an exposed host port and did
  not connect. A second attempt initially used an out-of-range synthetic expiry
  for PostgreSQL INTEGER and rolled back its seed transaction. Neither attempt
  touched production. The loopback-only rehearsal then completed as described.
- The disposable container was removed after the rehearsal.

## Operator migration entrypoint rehearsal

- Built the current `gateway/Dockerfile` as a disposable Linux image and ran
  the exact command used by `gpu-control-db-migrate.service` against an isolated
  PostgreSQL 16 container on a private Docker network.
- Ran `python -m gpu_gateway.worker --init-db` twice. Both exited successfully;
  the DB remained at schema v6 with zero runs and `active_count`, worker
  heartbeat, and supervisor heartbeat all zero. This confirms the command is
  idempotent and does not start queue-processing roles.
- Changed only the disposable database's schema version to 99, reran the same
  command, and observed exit code 1 with
  `UnsupportedSchemaVersion: Gateway database schema is unsupported`. A
  follow-up read showed version 99, run count 0, active count 0, and both
  heartbeats 0; the unsupported-schema failure did not modify state or start
  another service.
- The temporary app image, PostgreSQL container, and Docker network were
  removed. This ran the migration entrypoint in a Linux application container,
  not under systemd or the target `gpu-control` host account. `systemd-analyze
  verify` and unit policy tests separately cover template syntax and intended
  isolation; target-host service execution remains unverified.

## Current schema v7 operator-entrypoint refresh

- On 2026-10-28, started a disposable PostgreSQL 16 container exposed only on
  `127.0.0.1:55436`. Reconstructed the observed unversioned v1 column shape,
  removed `gateway_schema_version`, and seeded one synthetic terminal run plus
  synthetic OAuth admin, login-guard, session, client, and unrevoked refresh
  token rows.
- Ran the exact `python -m gpu_gateway.worker --init-db` entrypoint twice from
  the current Gateway virtual environment. Both invocations exited 0 and
  schema reached v7. The run owner, idempotency key, and succeeded state were
  preserved; migration conservatively set cleanup to `unknown`, attempt to 0,
  and `last_observed_at` to NULL. `active_count`, worker heartbeat, and
  supervisor heartbeat were all 0.
- OAuth row counts remained 1 each for admin, login guard, session, client, and
  token. The synthetic legacy refresh-token hash and unrevoked state remained
  unchanged; the new `grant_id` is NULL, avoiding invented grant ownership.
- Set only the disposable schema version to 99 and reran the same entrypoint.
  It exited 1 with `UnsupportedSchemaVersion`; a follow-up read confirmed the
  version remained 99 and `active_count` remained 0.
- The disposable PostgreSQL container was stopped and auto-removed. This is
  isolated synthetic PostgreSQL 16 evidence. It does not establish PostgreSQL
  17 provider behavior, production backup/recovery, systemd execution,
  target-host account permissions, or authorize a production migration.

## Operational boundary

The production database has not been migrated. The earlier v1-to-v6 rehearsal
is superseded for release preparation by the current v1-to-v7 operator-entrypoint
rehearsal above. Before any production change,
review and execute a quiesced, paired database/artifact backup; validate restore
and current owner/OAuth behavior; review migration SQL and rollback/recovery;
apply through a controlled operator procedure; verify `/readyz`, OAuth login,
MCP tool scan, and owner-scoped CPU result retrieval. Existing Vercel production
still points to a pre-vertical revision. The owner migration command is not
needed for this observed schema upgrade and must not be substituted for the
versioned schema migration.

## Read-only Neon state refresh — 2026-10-28 10:28 UTC

Rechecked the current project and default branch through the Neon connector,
then issued only `SELECT` statements against project
`delicate-smoke-00521013`, production branch `br-raspy-cell-b3l93n46`, database
`gpu_control`. Project metadata reports PostgreSQL 17; `current_setting` on the
database returned server version `170011`. The branch was ready at read time.

- `gateway_schema_version` remains absent. Tables still include
  `gateway_runs_v1`, `gateway_control_v1`, and the OAuth admin/bootstrap/client/
  code/login-guard/session/token tables.
- The live `gateway_runs_v1`, `gateway_control_v1`, and
  `gateway_oauth_tokens_v1` columns match the unversioned v1 assumptions used
  by the local fixture. `supervisor_seen_at` and token `grant_id` are absent.
- Aggregate counts are: runs 0, admin 1, bootstrap 0, clients 0, codes 0,
  login guard 1, sessions 1, and tokens 0. Row contents, hashes, session values,
  credentials, and connection strings were not selected.
- No migration, write, branch change, endpoint operation, or configuration
  change was made. Existing OAuth admin/login-guard/session rows still require
  preservation and usable-login verification before any production migration.

Local PostgreSQL 16 and 17.11 full-suite compatibility evidence improves
confidence in the SQL migration path, but this live inventory is not a backup,
restore, migration rehearsal on a Neon branch, or production migration approval.

## Read-only schema preflight — 2026-10-28

Added `python -m gpu_gateway.worker --check-db`, backed by
`migration_status(engine)`. It reports supported/current/target schema versions
and pending version steps without creating the version table or changing rows.
For a nonexistent SQLite file, it also avoids SQLite's normal connection-time
file creation. Unsupported versions and malformed version-table layouts fail
closed. A separate manual `gpu-control-db-check.service` lets the operator
review the JSON before starting migration; the migration unit repeats this
check as `ExecStartPre` before `--init-db`.

- Migration and deployment-unit regression modules: **24 passed**, one
  existing Starlette deprecation warning.
- CLI smoke on a nonexistent SQLite database reported version 0 to target 8
  with steps `[1,2,3,4,5,6,7,8]`; a post-command filesystem check confirmed the
  database file was not created.
- The preflight was also added to the PostgreSQL v1 migration integration test
  to prove it leaves the live test schema-version table absent and the existing
  OAuth fixture row unchanged before migration. Full Gateway CI/integration is
  rerun separately and recorded in `2026-10-28-local-integration-revalidation.md`.
