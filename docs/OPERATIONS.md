# Gateway operations and PostgreSQL recovery

This runbook covers the Gateway's database state. It does not make a deployment,
worker host, external OAuth issuer, or local Docker resources recoverable by
itself. Keep the local CPU policy disabled during a restore drill.

## State included in the database

The PostgreSQL database contains run plans/results and lifecycle state, the
control/admission row, schema version, and (when built-in OAuth is enabled) owner,
login guard, browser sessions, registered OAuth clients, authorization codes and
hashed tokens. A full database dump captures these tables consistently. OAuth
tokens are stored as hashes; restore the same configured public HTTPS origin and
cookie key when returning service, or intentionally invalidate browser sessions
and reauthorize clients.

Run results currently remain in PostgreSQL; there is no separate artifact object
store or artifact generation to restore. If external artifact storage is added,
its backup generation must be coordinated with the database backup before this
runbook can claim artifact recovery.

## Backup

Use a PostgreSQL client version at least as new as the server. Configure libpq
connection variables (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and a protected
`PGPASSFILE`) through the deployment secret manager. Do not put credentials in a
command argument, terminal transcript, or backup filename. Store backups in an
encrypted, access-controlled location with retention appropriate to the data.

```sh
set -eu
umask 077
backup_dir=/secure/gateway-backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
tmp="$backup_dir/gateway-$stamp.dump.tmp"
final="$backup_dir/gateway-$stamp.dump"
pg_dump --format=custom --no-owner --no-acl --file="$tmp"
test -s "$tmp"
pg_restore --list "$tmp" >/dev/null
mv "$tmp" "$final"
shasum -a 256 "$final" > "$final.sha256"
```

The temporary file is created with mode 0600 by the `umask`; the containing
directory must be private as well. A successful dump and archive listing prove
backup creation, not successful recovery. Never overwrite the only known-good
backup while testing.

## Isolated restore drill

Restore into a new, empty database on a separate PostgreSQL instance or isolated
cluster. Keep the live API and worker connected to the original database. Use
separately provisioned credentials from a secret manager.

```sh
set -eu
sha256sum -c "$DUMP_FILE.sha256"
createdb --host "$RESTORE_HOST" --username "$RESTORE_ADMIN" "$RESTORE_DB"
pg_restore --exit-on-error --no-owner --no-acl \
  --host "$RESTORE_HOST" --username "$RESTORE_ADMIN" \
  --dbname "$RESTORE_DB" "$DUMP_FILE"
psql --host "$RESTORE_HOST" --username "$RESTORE_ADMIN" \
  --dbname "$RESTORE_DB" --set=ON_ERROR_STOP=1 --command \
  'SELECT version FROM gateway_schema_version WHERE id=1;'
```

Compare row counts for `gateway_runs_v1`, `gateway_control_v1`,
`gateway_schema_version`, and all present `gateway_oauth_*` tables between the
source snapshot and restored database. Check representative run IDs, terminal
results, approval IDs/expiry, `active_count`, and OAuth client/token revocation
state. Do not print token hashes, session hashes, owner credentials, or row JSON
into shared logs. Run a read-only Gateway smoke check against the restored DB;
do not point a live worker at the drill database. Record dump checksum, server
versions, schema version, table counts, elapsed time and any discrepancy in the
private operations record.

## Production recovery constraints

A database restore cannot reconstruct a lost Docker daemon or prove what happened
to a container on a destroyed worker host. Before planned database recovery,
stop new submissions, worker and recovery supervisor; preserve the worker
host/container inventory; restore the database; then let an operator reconcile
every nonterminal run before restarting either process or admissions. Unknown
provider outcomes remain unknown; never resubmit them automatically. Verify that
restored `active_count` agrees with the
operator-reviewed run/resource inventory before enabling submissions.

The initial operational target in the roadmap is RPO 24 hours and RTO 2 hours.
Those targets are **not yet measured**. A release claim requires a timed restore
drill by a second operator and a documented recovery of run, approval and OAuth
state. The 7-day CPU observation period, database-provider backup configuration,
and production recovery remain outstanding.
