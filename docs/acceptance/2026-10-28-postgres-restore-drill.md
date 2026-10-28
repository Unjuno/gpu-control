# PostgreSQL restore drill evidence — 2026-10-28

## Scope

PASS for an isolated synthetic-data PostgreSQL dump and restore, with exact row
parity across all Gateway metadata tables. This does not prove a production
restore, a real OAuth issuer or worker, second-operator reproducibility, Docker
resource recovery, or the roadmap RPO/RTO targets.

## Environment and artifact

- Local Docker/OrbStack server: 29.8.2.
- PostgreSQL image: `postgres:16` at `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
- Gateway database schema: v4.
- Synthetic custom-format dump SHA-256: `5afb42f72515bac33700da0e2b9862079d29cbe0c6610f2148c1d2b3a64b7fc7`.
- The dump and isolated database container were removed after verification.

## Seeded state and checks

The source database contained two synthetic runs: one queued run with an
`approval_id` and expiry, and one succeeded run with cleanup complete and a
structured result. It also contained one synthetic registered OAuth client and
one unrevoked refresh-token hash. No real owner, credential, token, or customer
data was used.

The custom-format archive passed `pg_restore --list`, restored into a separately
created empty database with `pg_restore --exit-on-error`, and reported schema
version 4. The verification compared every row from each Gateway metadata table
between source and restored databases; all were identical:

| Table | Source / restored rows | Result |
| --- | ---: | --- |
| `gateway_control_v1` | 1 / 1 | identical |
| `gateway_runs_v1` | 2 / 2 | identical |
| `gateway_schema_version` | 1 / 1 (version 4) | identical |
| `gateway_oauth_admin_v1` | 0 / 0 | identical |
| `gateway_oauth_bootstrap_v1` | 0 / 0 | identical |
| `gateway_oauth_clients_v1` | 1 / 1 | identical |
| `gateway_oauth_codes_v1` | 0 / 0 | identical |
| `gateway_oauth_login_guard_v1` | 0 / 0 | identical |
| `gateway_oauth_sessions_v1` | 0 / 0 | identical |
| `gateway_oauth_tokens_v1` | 1 / 1 | identical |

The restored run approval ID/expiry, succeeded state and result metrics were
queried directly and matched the seeded values. The isolated container and dump
were removed after the drill; no project or production database was involved.

## Gateway application read check

A second isolated PostgreSQL 16 source/restore pair was created from synthetic
records. The Gateway `create_app` and MCP request path were exercised with the
restored database as the store. `/readyz` returned HTTP 200 with schema v4, DB
connectivity, a valid registry and configured test auth. `experiment_list`
returned both seeded run IDs; `experiment_result` returned the succeeded run's
`checks: 3` metric and `cleanup_state: complete`.

The check used a generated signing key and test JWKS key lookup, with a manually
refreshed synthetic worker heartbeat. It proves application read-path
compatibility with restored records; it does not prove a live issuer, worker or
ChatGPT client. The second isolated container was also removed.

## Still required for P3

- Repeat against the selected production PostgreSQL service and verify its
  encryption, retention and access controls.
- Exercise a timed restore with representative database size and measure RPO/RTO.
- Reconcile nonterminal run records with the dedicated worker's actual Docker
  resources before resuming submissions.
- Have a second operator reproduce the procedure and record discrepancies.
- See `2026-10-28-paired-artifact-restore.md` for a separate synthetic paired
  database/artifact restore; repeat it with the selected production backup and
  artifact-volume configuration before claiming P3 acceptance.
