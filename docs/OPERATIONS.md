# Gateway operations and PostgreSQL recovery

This runbook covers the Gateway's database state. It does not make a deployment,
worker host, external OAuth issuer, or local Docker resources recoverable by
itself. Keep the local CPU policy disabled during a restore drill.

## Dedicated Linux host service layout

`gateway/deploy/` contains systemd units for the API, execution worker and
recovery-only supervisor. Install the application and locked Python
dependencies under `/opt/gpu-control`, create the `gpu-control` service account,
and install the shared environment file as `/etc/gpu-control/worker.env`
owned by root with mode `0600`. Configure one durable PostgreSQL URL, the exact
public HTTPS origin, and the same persistent `GATEWAY_ARTIFACT_DIR` in that
file. Keep the local CPU policy disabled until its independent acceptance gates
pass.

Place the API behind a TLS-terminating reverse proxy. The API unit binds only to
`127.0.0.1:8000` and has no Docker group membership; only the dedicated worker
and recovery supervisor receive access to the Docker daemon. Verify the proxy
forwards the original HTTPS scheme/host safely and that the OAuth issuer,
resource metadata, and public MCP origin all match. Do not expose port 8000
directly to the network.

Copy the database-migration, API, worker, supervisor, capacity-check service,
and capacity timer unit files from `gateway/deploy/` to
`/etc/systemd/system/`, then review their paths and environment file before
enabling them. On the target Linux host, run
`systemd-analyze verify /etc/systemd/system/gpu-control-db-migrate.service /etc/systemd/system/gpu-control-api.service /etc/systemd/system/gpu-control-worker.service /etc/systemd/system/gpu-control-supervisor.service /etc/systemd/system/gpu-control-artifact-capacity.service /etc/systemd/system/gpu-control-artifact-capacity.timer`
before starting any unit. Start the API only after TLS proxy and PostgreSQL are ready. Start
worker and supervisor only after confirming their dedicated host's Docker
trust boundary and persistent artifact path. Enable the capacity timer only
after the artifact filesystem is mounted and checked. `systemd-analyze verify`
accepted all six service/timer units in an ephemeral Debian 12/systemd 252
container with placeholder installation paths, executable files, service
accounts, groups, and environment file. This verifies unit syntax and
references only. These templates are not yet validated on a target Linux host;
successful unit startup alone is not deployment acceptance.

`gpu-control-db-migrate.service` is a manual, oneshot unit and has no install
target; it must not be enabled at boot. Before the first deployment or a schema
upgrade, stop ingress and every old/new API, worker, and supervisor that uses
the database. Drain or cancel work and require zero nonterminal runs and
`active_count=0`; resolve unknown provider outcomes before proceeding. Create
and validate a recoverable database backup, plus a paired artifact-volume
backup when artifacts exist. Only after the migration has been reviewed against
the exact release, run:

```sh
sudo systemctl start gpu-control-db-migrate.service
sudo systemctl --no-pager --full status gpu-control-db-migrate.service
sudo journalctl --no-pager -u gpu-control-db-migrate.service
```

The unit runs `python -m gpu_gateway.worker --init-db` as `gpu-control` with
the protected deployment `EnvironmentFile`. It applies the explicit
v1-to-current migration and idempotently creates missing Gateway/OAuth tables;
it does not start the API or queue workers. A nonzero start or migration error
means do not start the application services. PostgreSQL migrations are
forward-only; there is no automatic downgrade. After investigating, either
apply a reviewed forward fix or restore the database and paired artifact volume
from the same verified generation while all services remain stopped. Never
restore only one half of a paired generation. A successful migration command
is not readiness or deployment acceptance.

The capacity-check service declares
`RequiresMountsFor=/var/lib/gpu-control/artifacts`, matching the example
environment file. Configure the dedicated filesystem at that exact path (or
change the unit and its test together before installation). API, worker, and
recovery supervisor deliberately have no hard mount dependency: they must stay
available to report storage failure and recover/cancel tracked work if the
artifact mount is missing. The capacity monitor fails unless the path is a
distinct filesystem with the required headroom; API capabilities/prepare and
the worker immediately before local CPU start enforce that probe. A missing
artifact volume therefore blocks new artifact-producing CPU starts without
preventing recovery processing.

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

If `GATEWAY_ARTIFACT_DIR` is configured, make a paired database/artifact
generation only after quiescing the Gateway. First set `"enabled": false` in the
operator-owned local CPU policy and stop the API to prevent new submissions.
Keep the worker and recovery
supervisor running while accepted work drains or is cancelled and reconciled.
Do not proceed while any run is nonterminal, `active_count` is nonzero, or a
provider outcome is unknown. Once the database confirms zero nonterminal runs
and `active_count=0`, stop the worker and recovery supervisor. Keep all three
services stopped until both archives and checksums have been created. If the
run state cannot be brought to this boundary, do not label the result a
consistent paired generation; follow the incident recovery procedure instead.

`gateway/deploy/backup_generation.py` rechecks quiescence before dumping. It
requires zero nonterminal runs and `active_count=0`; when the schema has
`cleanup_state`/`slot_reserved`, it also requires cleanup proof for every run
and no reserved slots. It refuses a missing singleton, partial cleanup schema,
unknown cleanup, or artifact manifests without the artifact directory. These
database checks complement the required service shutdown; they do not prove
that ingress has been stopped, so stop the old and new API/worker/supervisor
processes first.

Create an existing mode-0700 output directory on an encrypted,
access-controlled backup filesystem. Keep PostgreSQL connection settings in
libpq environment configuration or a protected `PGPASSFILE`; never pass a
database URL or password as a command argument. Run the same command from one
shell after all Gateway processes have stopped:

```sh
set -eu
python /opt/gpu-control/gateway/deploy/backup_generation.py \
  --output-dir /secure/gateway-backups \
  --artifact-dir /var/lib/gpu-control/artifacts
```

Omit `--artifact-dir` only when there is no artifact volume and the database has
no artifact manifests. The program stages the dump, optional artifact tar, and
`manifest.json` in a private temporary directory under the output filesystem.
It runs `pg_restore --list` and `tar --list`, calculates sizes and SHA-256
digests, fsyncs files/directories, then atomically renames the complete
generation directory into its final name. On a normal error, staging is
removed; after abrupt termination, a hidden `.gpu-control-incomplete-*`
directory may remain but is never a valid restore generation. Restore only a
published `gpu-control-*` directory with a valid manifest. Never overwrite or
delete the only known-good generation.

```sh
generation_dir=/secure/gateway-backups/gpu-control-REPLACE_WITH_PRINTED_GENERATION_ID
python /opt/gpu-control/gateway/deploy/backup_generation.py \
  --verify-generation "$generation_dir"
```

The verification command checks generation identity, exact file set, archive
sizes, checksums, and archive readability before restore. It also checks every
artifact tar member against the opaque owner/run/blob layout without extracting
it, rejecting absolute or parent-traversal paths, links, special files, duplicate
paths, and objects outside per-run limits. On macOS, archive creation disables
AppleDouble metadata so platform resource-fork entries cannot enter the backup.
The manifest records
the source schema version, run count, active count, database checksum, and
optional artifact checksum/source device. A successful backup and verification
do not prove successful recovery; restore into isolated services and exercise
owner-scoped artifact retrieval as described below. A local Compose named
volume or host filesystem without a configured quota is not a production
backup or capacity policy.

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

`docs/acceptance/2026-10-28-paired-artifact-restore.md` records a local
synthetic restore through separate PostgreSQL 16 containers and the
owner-scoped application read path. It is supporting local evidence only; the
production, second-operator, and timed RPO/RTO gates below remain open.
`docs/acceptance/2026-10-28-atomic-backup-generation.md` additionally records
an end-to-end run of the atomic backup tool, checksum verification, injected
archive failure, and retrieval after restore. This also remains local synthetic
evidence.

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
alerts. `experiment_capabilities` checks that the artifact directory for local
CPU workloads exists, is writable by the Gateway process, and reports nonzero
available space; it blocks submissions when that probe fails. When
`GATEWAY_ARTIFACT_MIN_FREE_BYTES` is set, both capabilities and prepare also
require the artifact path to be on a distinct filesystem and block below that
headroom floor, so a failed capacity timer is not the only admission control.
`statvfs` free
space does not prove an enforced quota or provide a low-space alert. Before
enabling artifact-producing workloads on a target host, mount the artifact
directory as a separate fixed-size filesystem/volume. Its filesystem size then
enforces a global hard ceiling across API, worker, and supervisor, while
`GATEWAY_ARTIFACT_MIN_FREE_BYTES` preserves operational headroom. The capacity
timer runs every five minutes and exits nonzero if the path is not a distinct
filesystem, the probe fails, or free space is below the configured threshold;
systemd records the structured status in the journal. Connect failed
`gpu-control-artifact-capacity.service` results to the host's alerting system
and test notification delivery. The timer and journal output alone are not a
human notification. Record the selected alert system and route name (never its
secret), the injected capacity failure and journal event timestamp, the
delivered notification timestamp and recipient/on-call acknowledgment, and the
recovery notification timestamp. Acceptance requires one below-threshold event
to reach the responsible operator within the host's documented alert SLO, a
recovery event after free space returns, and confirmation that a failed probe
does not stop the API, worker, or recovery supervisor. Run this exercise on the
selected host with a disposable test filesystem or an injected probe fixture;
do not fill the production volume to trigger an alert. Alert integration
requires a reviewed sink, authenticated delivery configuration, and tested
failure behavior for the chosen host; none is configured by these templates.
Test artifact-write behavior at the volume limit before enabling the workload.
After mounting, set the filesystem root to owner/group
`gpu-control:gpu-control` with mode `0700`, verify the mounted source and free
space, and only then start API/worker/supervisor. Capabilities, prepare, and
the worker immediately before local CPU backend start all fail closed if the
artifact path or configured headroom is unavailable. The 7-day CPU observation period, host alert routing,
database-provider backup configuration, and production recovery remain
outstanding.

## Built-in OAuth issuer change

The built-in issuer is the public origin, and the run owner is derived from
`issuer + NUL + subject`. A domain change therefore changes the owner key. Use
the offline migration command below only after stopping the API, worker, and
recovery supervisor, disabling admissions, and taking the paired database and
artifact backup described above. It refuses unsettled runs, destination
idempotency collisions, a nonzero global active-slot counter, missing or corrupt
blobs, and unsafe artifact paths.

Configure the command environment for the **new** deployment, including its
database URL and persistent artifact directory. The default invocation is a
read-only preflight:

```sh
python -m gpu_gateway.owner_migration \
  --old-issuer https://old.example \
  --new-issuer https://new.example \
  --subject owner
```

Review the owner hashes and run counts. After confirming the paired backup and
stopped services, apply the migration:

```sh
python -m gpu_gateway.owner_migration \
  --old-issuer https://old.example \
  --new-issuer https://new.example \
  --subject owner \
  --apply \
  --confirm-services-stopped-and-backup-complete
```

Artifact blobs are copied to a hidden rollback directory and a private staging
directory. Once the transaction locks and revalidates every source run field,
it installs each destination owner/run scope and verifies the blobs through the
artifact store against stored size and SHA-256 before changing run ownership.
Keep `.owner-migration-backup-*` until
new-owner retrieval and owner-isolation acceptance pass; remove those rollback
copies only through an operator-reviewed cleanup. All local OAuth tokens, browser sessions,
authorization codes, and dynamic client registrations are revoked or deleted
in that transaction, so users must sign in and register the client again. If
the process stops after installing destination blobs but before DB commit, the
old owner remains authoritative and a rerun reuses only byte-identical scopes.
When old-owner rows still exist, a rerun may rebuild incomplete hidden rollback
or staging directories from the verified old scope. Keep services stopped
until the command succeeds and post-migration API checks pass. A dry-run is not
a migration, and a migration is not a backup/restore drill.
