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

Small run results and artifact manifests remain in PostgreSQL. Artifact bytes
are separate private files under the configured `GATEWAY_ARTIFACT_DIR`; API and
worker must use the same persistent filesystem. A database dump alone cannot
restore artifact bytes. Pair the database dump and artifact-volume archive as
one recovery generation.

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
sha256sum "$final" > "$final.sha256"
```

The temporary file is created with mode 0600 by the `umask`; the containing
directory must be private as well. A successful dump and archive listing prove
backup creation, not successful recovery. Never overwrite the only known-good
backup while testing.

When `GATEWAY_ARTIFACT_DIR` is configured, create a paired archive while the
API, execution worker and recovery supervisor are stopped and admissions are
disabled. Continue in the same shell as the database dump so `backup_dir` and
`stamp` identify one generation. This keeps manifests and blob files from
changing during the snapshot.

```sh
artifact_root=/var/lib/gpu-control/artifacts
artifact_tmp="$backup_dir/gateway-artifacts-$stamp.tar.tmp"
artifact_final="$backup_dir/gateway-artifacts-$stamp.tar"
tar --create --file="$artifact_tmp" --directory="$artifact_root" .
test -s "$artifact_tmp"
tar --list --file="$artifact_tmp" >/dev/null
mv "$artifact_tmp" "$artifact_final"
sha256sum "$artifact_final" > "$artifact_final.sha256"
```

Record both checksums, sizes, the source schema version and the artifact root's
filesystem. If artifacts are not configured, record that the generation has no
artifact volume. A local Compose named volume or a host filesystem without a
configured quota is not a production backup or capacity policy.

## Isolated restore drill

Restore into a new, empty database and a new, empty artifact directory on a
separate PostgreSQL instance or isolated cluster. Keep the live API and worker
connected to the original database and artifact volume. Use separately
provisioned credentials from a secret manager.

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
sha256sum -c "$ARTIFACT_ARCHIVE.sha256"
tar --extract --file="$ARTIFACT_ARCHIVE" --directory="$RESTORE_ARTIFACT_DIR"
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

For every non-expired artifact manifest in the restored database, fetch the
artifact through the owner-scoped result API in bounded chunks and verify the
reported full-object SHA-256 and size. Missing or mismatched blobs fail the
drill. Restore as the dedicated service user, then verify the artifact root is
not a symlink and has the expected owner and restrictive modes before starting
the API. Do not run workers or enable local admission during this check.

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
drill by a second operator and a documented recovery of run, approval, OAuth and
matching artifact-volume state. The repository enforces per-run artifact count
and size bounds but does not impose a global volume quota or emit capacity
alerts. Before enabling artifact-producing workloads on a target host, set a
filesystem/provider quota, alert before exhaustion, and test behavior at the
quota boundary. The 7-day CPU observation period, database-provider backup
configuration, and production recovery remain outstanding.
