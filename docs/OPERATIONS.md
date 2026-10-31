# Gateway operations and PostgreSQL recovery

This runbook covers the Gateway's database state. It does not make a deployment,
worker host, external OAuth issuer, or local Docker resources recoverable by
itself. Keep the local CPU policy disabled during a restore drill.

## Reproducible source and runtime installation

Use this first-install procedure only for an exact 40-character commit that has
passed the required independent review and CI and is present on the approved
`main` branch. A READY Preview or a local worktree is not a release. This block
installs source and locked runtime dependencies but does not start services,
initialize/migrate PostgreSQL, enable CPU admission, or install credentials.

The `/opt/gpu-control` path must not already exist. The checkout and virtual
environment stay root-owned; service identities may read and execute files
there but cannot modify them. Use the uv release pinned by the Gateway CI
workflow, and preserve the repository's exact `gateway/uv.lock` through
`--locked`.

```sh
set -eu
release_sha=REPLACE_WITH_REVIEWED_MAIN_COMMIT
case "$release_sha" in
  *REPLACE*|*[!0-9a-f]*) echo 'set a lowercase hexadecimal release SHA' >&2; exit 2 ;;
esac
test "${#release_sha}" -eq 40
test ! -e /opt/gpu-control && test ! -L /opt/gpu-control
test "$(uv --version)" = 'uv 0.10.0'
sudo git clone --no-checkout --branch main --single-branch \
  https://github.com/Unjuno/gpu-control.git /opt/gpu-control
sudo git -C /opt/gpu-control checkout --detach "$release_sha"
test "$(sudo git -C /opt/gpu-control rev-parse HEAD)" = "$release_sha"
sudo chown -R root:root /opt/gpu-control
sudo chmod -R go-w /opt/gpu-control
sudo env UV_PROJECT_ENVIRONMENT=/opt/gpu-control/venv \
  uv sync --project /opt/gpu-control/gateway --locked --no-dev --python 3.12
sudo /opt/gpu-control/venv/bin/python - <<'PY'
from pathlib import Path
import gpu_control
import gpu_gateway

root = Path('/opt/gpu-control').resolve()
assert Path(gpu_control.__file__).resolve().is_relative_to(root / 'src')
assert Path(gpu_gateway.__file__).resolve().is_relative_to(root / 'gateway')
print('locked Gateway runtime imports from the pinned checkout')
PY
sha256sum /opt/gpu-control/gateway/uv.lock
test -z "$(sudo git -C /opt/gpu-control status --porcelain)"
```

The final Git status must be empty. Record the approved SHA, uv version, Python
version, lockfile digest, and import-check result in the private release record.
Do not continue if checkout, dependency resolution, or source-path assertions
fail. For upgrades, use the maintenance/drain/paired-backup procedure below;
do not replace a running checkout in place. Install and verify systemd templates
only after this source/runtime step has passed.

## Dedicated Linux host service layout

`gateway/deploy/` contains systemd units for the API, execution worker and
recovery-only supervisor. Install the application and locked Python
dependencies under `/opt/gpu-control`, create separate API, worker, migration,
capacity-monitor, and capacity-bridge service users plus artifact/probe groups,
and install `/etc/gpu-control/gateway.env` from `gateway.env.example` for the
common database, workload, policy, public-origin, and artifact settings.
Install `/etc/gpu-control/api.env` from `api.env.example` for API-only
cookie/OIDC credentials, and `/etc/gpu-control/capacity.env` from
`capacity.env.example` for the capacity monitor's artifact path/headroom only.
All files must be root-owned mode `0600`. API loads common plus API-only
settings; worker, supervisor, and manual migration load common settings only;
capacity monitoring receives filesystem settings only. Worker and supervisor
may also load the optional root-owned `worker-secrets.env`, which is not loaded
by API, migration, or capacity services. Do not add OAuth credentials to the
common file. Keep the local CPU policy disabled until its independent
acceptance gates pass.

The API, database migration, and capacity monitor must not share a Unix UID
with the worker. The worker and recovery supervisor intentionally share the
`gpu-control-worker` UID because both receive the same reviewed cleanup/provider
credentials. Environment-file separation alone is not process isolation:
`/proc/<pid>/environ` access is governed by ptrace permissions, and services
running as the same UID may be able to inspect each other's environment on a
host without additional procfs restrictions ([Linux proc environment access]
(https://man7.org/linux/man-pages/man5/proc_pid_environ.5.html), [systemd
environment security notes](https://www.freedesktop.org/software/systemd/man/258/systemd.exec.html)).
Create the dedicated identities before installing/starting units:

```sh
sudo groupadd --system gpu-control-artifacts
sudo groupadd --system gpu-control-artifact-probes
sudo groupadd --system gpu-control-migrate
sudo groupadd --system gpu-control-capacity-bridge
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid gpu-control-artifacts gpu-control-api
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid gpu-control-artifacts gpu-control-worker
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid gpu-control-migrate gpu-control-migrate
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid gpu-control-artifacts gpu-control-capacity
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid gpu-control-capacity-bridge gpu-control-capacity-bridge
sudo usermod --append --groups systemd-journal gpu-control-capacity-bridge
```

The API unit joins the artifact-probe group so its readiness endpoint can
create and remove a temporary probe; worker and recovery supervisor join only
the Docker group because the worker UID owns the probe directory and artifact
tree. The capacity user receives only its primary artifact-read group, allowing
`statvfs` and blob reads without probe-directory write permission, database/auth
settings, or Docker access. The migration user receives database settings only.

The optional capacity journal bridge uses a distinct
`gpu-control-capacity-bridge` identity, joins only the host's
`systemd-journal` read group, and writes only its private systemd
`StateDirectory`. Its service has no environment file, network, database,
artifact, Docker, or provider access. The unit is manual-only: do not schedule
it repeatedly until a reviewed sender is connected, because undelivered
transitions occupy the bounded outbox. `systemd-journal` membership grants
underlying read access to the host journal; bridge code restricts its fixed
no-shell query to the capacity unit and selected fields. Do not install this
identity if that host-journal trust boundary is unacceptable.

After mounting the dedicated artifact filesystem and before starting any unit,
prepare its root and probe directory. For a new empty mount:

```sh
sudo install -d -o gpu-control-worker -g gpu-control-artifacts -m 2750 /var/lib/gpu-control/artifacts
sudo install -d -o gpu-control-worker -g gpu-control-artifact-probes -m 3770 /var/lib/gpu-control/artifacts/.gpu-control-probes
```

Do not use these commands as a recursive migration for an existing artifact
tree. For an existing tree, follow the quiesced migration procedure below and
verify all stored digests before restarting services.

From the repository root, install the three required environment-file examples
first, edit their settings, then install all eight unit files (seven services
and one timer). The sample
database URL must be replaced with a value from the approved configuration
source. Set `GATEWAY_COOKIE_KEY` only for external OIDC browser login; generate
it with `Fernet.generate_key()` as described in the Gateway README. Built-in
local OAuth does not use this cookie key. Use `sudoedit` for the
credential-bearing files; do not put credentials in shell arguments or
terminal history.

```sh
sudo install -d -o root -g root -m 0750 /etc/gpu-control
sudo install -o root -g root -m 0600 gateway/deploy/gateway.env.example /etc/gpu-control/gateway.env
sudo install -o root -g root -m 0600 gateway/deploy/api.env.example /etc/gpu-control/api.env
sudo install -o root -g root -m 0600 gateway/deploy/capacity.env.example /etc/gpu-control/capacity.env
sudoedit /etc/gpu-control/gateway.env
sudoedit /etc/gpu-control/api.env
sudoedit /etc/gpu-control/capacity.env

sudo install -o root -g root -m 0644 gateway/deploy/gpu-control-api.service /etc/systemd/system/
sudo install -o root -g root -m 0644 gateway/deploy/gpu-control-worker.service /etc/systemd/system/
sudo install -o root -g root -m 0644 gateway/deploy/gpu-control-supervisor.service /etc/systemd/system/
sudo install -o root -g root -m 0644 gateway/deploy/gpu-control-db-check.service /etc/systemd/system/
sudo install -o root -g root -m 0644 gateway/deploy/gpu-control-db-migrate.service /etc/systemd/system/
sudo install -o root -g root -m 0644 gateway/deploy/gpu-control-artifact-capacity.service /etc/systemd/system/
sudo install -o root -g root -m 0644 gateway/deploy/gpu-control-artifact-capacity.timer /etc/systemd/system/
sudo install -o root -g root -m 0644 gateway/deploy/gpu-control-capacity-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemd-analyze verify \
  /etc/systemd/system/gpu-control-db-check.service \
  /etc/systemd/system/gpu-control-db-migrate.service \
  /etc/systemd/system/gpu-control-api.service \
  /etc/systemd/system/gpu-control-worker.service \
  /etc/systemd/system/gpu-control-supervisor.service \
  /etc/systemd/system/gpu-control-artifact-capacity.service \
  /etc/systemd/system/gpu-control-artifact-capacity.timer \
  /etc/systemd/system/gpu-control-capacity-bridge.service
```

Keep `worker-secrets.env` absent while provider integrations are parked. If a
later reviewed activation needs it, install that example separately with mode
`0600`, enter only the authorized worker/supervisor credentials using the
approved secret process, and continue to keep the integration disabled until
its independent acceptance gates pass. The migration service has no boot
install target; never enable it as a startup service. Keep the capacity timer
disabled until the fixed-size artifact filesystem is mounted and verified.

| Unit | Unix identity | Environment files | Runtime secret boundary |
| --- | --- | --- | --- |
| `gpu-control-api.service` | `gpu-control-api:gpu-control-artifacts` | `gateway.env`, `api.env` | DB/API auth; artifact read and probe-only write; no provider token |
| `gpu-control-worker.service` | `gpu-control-worker:gpu-control-artifacts` | `gateway.env`, optional `worker-secrets.env` | DB and approved execution-provider credentials; artifact read/write |
| `gpu-control-supervisor.service` | `gpu-control-worker:gpu-control-artifacts` | `gateway.env`, optional `worker-secrets.env` | Same worker identity for exact tracked-resource recovery/cleanup |
| `gpu-control-db-migrate.service` | `gpu-control-migrate:gpu-control-migrate` | `gateway.env` | DB credential only; no API auth/provider token |
| `gpu-control-artifact-capacity.service` | `gpu-control-capacity:gpu-control-artifacts` | `capacity.env` | Artifact mount identity and free-space headroom via `statvfs`; no artifact or probe writes |
| `gpu-control-capacity-bridge.service` | `gpu-control-capacity-bridge:gpu-control-capacity-bridge` plus `systemd-journal` | none | Read-only journal polling and private outbox state; no network or workload authority |

Before enabling a provider or local CPU admission on the selected host, verify
both the installed unit files and each running service's environment scope.
Inspect environment **variable names only**; never display, save, or log values,
and do not use `systemctl show -p Environment` or dump `/proc/*/environ` into a
log. For running API/worker/supervisor processes, `MainPID` and a names-only
inspection can be obtained as follows:

```sh
unit=gpu-control-api.service
pid=$(sudo systemctl show --property=MainPID --value "$unit")
test "$pid" -gt 1
sudo python3 - "$pid" <<'PY'
from pathlib import Path
import sys

items = Path(f"/proc/{sys.argv[1]}/environ").read_bytes().split(b"\0")
for name in sorted({item.partition(b"=")[0].decode("ascii", "replace")
                    for item in items if b"=" in item}):
    print(name)
PY
```

Repeat with the worker and supervisor units. For the capacity and migration
oneshot units, which may exit before their process environment can be inspected,
compare the configured environment-file paths in the installed units and list
the assignment names only (for example, `awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ {print $1}' /etc/gpu-control/capacity.env`). Confirm that API has no
`MODAL_TOKEN_*`, RunPod, or other provider secret; capacity monitoring has no
database or auth variable; migration has no API auth or provider credential; and
worker/supervisor have only the credentials needed for their reviewed backend
and cleanup responsibilities. Record pass/fail and unit revision in the private
acceptance record without recording values. Keep provider integrations disabled
if any service receives an unexpected variable.

When updating an installation made from the earlier single-file
`worker.env.example`, do not point the new units at the old file or copy it
wholesale into `gateway.env`: that file may contain API authentication values.
During a planned, quiesced deployment, prepare three required root-owned `0600`
files:
move only database, hosted-mode, public-origin, workload, policy, artifact,
provider-disable, and concurrency settings into `gateway.env`; put only cookie
and configured OIDC settings into `api.env`; and put only artifact path and
headroom settings into `capacity.env`. Preserve the existing cookie key and
database URL exactly unless their rotation is separately planned. Validate
variable names and file ownership without printing values, copy the new unit
files, run `systemd-analyze verify`, and only then perform the reviewed service
restart. Keep the old file root-only and mode `0600` until the new services are
healthy and the rollback window closes; then handle it under the host's secret
retention policy. Do not use `source` or execute a systemd environment file as
a shell script. If the old file contains Modal, RunPod, or other provider
credentials, do not copy them into `gateway.env`; keep those integrations
disabled until a separately reviewed worker-only secret path is configured.
When that path is approved, put provider credentials only in
`/etc/gpu-control/worker-secrets.env`, readable by worker and recovery
supervisor, and keep that integration's admission switch disabled until its
credential, quote, quota, cancellation, and cleanup gates pass. This file is
optional and remains absent while integrations are parked.

Place the API behind a TLS-terminating reverse proxy. The API unit binds only to
`127.0.0.1:8000` and has no Docker group membership; only the dedicated worker
and recovery supervisor receive access to the Docker daemon. Verify the proxy
forwards the original HTTPS scheme/host safely and that the OAuth issuer,
resource metadata, and public MCP origin all match. Do not expose port 8000
directly to the network.

Copy the read-only database-check, database-migration, API, worker, supervisor,
capacity-check service, capacity timer, and manual capacity-bridge service unit files from
`gateway/deploy/` to
`/etc/systemd/system/`, then review their paths and environment file before
enabling them. On the target Linux host, verify all eight files before starting
any unit:

```sh
sudo systemd-analyze verify \
  /etc/systemd/system/gpu-control-db-check.service \
  /etc/systemd/system/gpu-control-db-migrate.service \
  /etc/systemd/system/gpu-control-api.service \
  /etc/systemd/system/gpu-control-worker.service \
  /etc/systemd/system/gpu-control-supervisor.service \
  /etc/systemd/system/gpu-control-artifact-capacity.service \
  /etc/systemd/system/gpu-control-artifact-capacity.timer \
  /etc/systemd/system/gpu-control-capacity-bridge.service
```

Start the API only after TLS proxy and PostgreSQL are ready. Start
worker and supervisor only after confirming their dedicated host's Docker
trust boundary and persistent artifact path. Enable the capacity timer only
after the artifact filesystem is mounted and checked. At the earlier
verification point, `systemd-analyze verify` accepted all six then-existing
service/timer units in an ephemeral Debian 12/systemd 252
container with placeholder installation paths, executable files, service
accounts, groups, and environment file. This verifies unit syntax and
references only. These templates are not yet validated on a target Linux host;
successful unit startup alone is not deployment acceptance. After adding the
optional `worker-secrets.env` inputs, `systemd-analyze verify` again accepted
the six then-current templates in the same ephemeral Debian 12/systemd 252
environment, with placeholder users/groups, environment files, and executable
paths. This remains static verification only; no service was started or
validated on a target Linux host.

The manual capacity-bridge unit is installed and included above. The guarded
helper passed `systemd-analyze verify` for all seven templates in the cached Debian
12/systemd 252.39 image (`--rm --network none`, repository mounted read-only).
See [`systemd UID boundary acceptance`](acceptance/2026-10-28-systemd-uid-boundary.md).

The capacity bridge has no timer and is not for continuous service yet. Its
initial checkpoint must be explicit. For an authorized target-host read test,
create `/var/lib/gpu-control-capacity-bridge` as
`gpu-control-capacity-bridge:gpu-control-capacity-bridge` mode `0700`, then run
`capacity_event_bridge.py --bootstrap-latest` once as that identity with the
fixed state path. Review only the safe status output; it must not print the
cursor or event body. Subsequent manual unit invocations use `--poll-once` and
refuse to run without that checkpoint. A retention gap reports unknown state
and blocks ordinary polling. After reviewing the gap, an operator may explicitly
reconcile to the latest retained capacity event under the bridge identity and
`systemd-journal` supplementary group:

```sh
sudo -u gpu-control-capacity-bridge -g gpu-control-capacity-bridge \
  /opt/gpu-control/venv/bin/python \
  /opt/gpu-control/gateway/deploy/capacity_event_bridge.py \
  --reconcile-latest \
  --state-path /var/lib/gpu-control-capacity-bridge/state.json
```

The operation is allowed only while the
saved cursor is actually absent, reads one latest trusted event, rechecks the
gap, preserves every pending outbox item, and enqueues the latest status even
when it matches the last known state. This reannouncement makes the current
condition visible; it cannot recover transitions removed by journal retention.
This assumes the bridge identity was added to the `systemd-journal` group as
described in the setup steps above; sudo initializes its supplementary groups
from that identity. Record the command output and operator decision in the
incident record. The poller only records transitions locally and does not
notify an operator. Keep it unscheduled until a reviewed delivery sender and
route are configured and accepted.

To inspect local bridge counters without querying journald, use
`--show-health` with the same identity and state path:

```sh
sudo -u gpu-control-capacity-bridge -g gpu-control-capacity-bridge \
  /opt/gpu-control/venv/bin/python \
  /opt/gpu-control/gateway/deploy/capacity_event_bridge.py \
  --show-health \
  --state-path /var/lib/gpu-control-capacity-bridge/state.json
```

This returns only initialized/current status and bounded delivery counters; it
does not print cursors, event bodies, error strings, or notification responses.
It reports local outbox state, not journal-reader health or operator receipt.

The API, worker, and supervisor use `ProtectSystem=strict`. API receives a
`ReadWritePaths` exception only for
`/var/lib/gpu-control/artifacts/.gpu-control-probes`; worker and supervisor
receive the full artifact path for payload writes, pruning, and recovery. The
`-` prefix lets these services start when the mountpoint is absent. Host mount
changes propagate into these service namespaces; without the allowlist,
artifact writes and the readiness probe would fail under the strict read-only
filesystem view. The capacity unit alone has
`RequiresMountsFor=/var/lib/gpu-control/artifacts` because it must report a
missing mount as a failed check.

`gpu-control-db-migrate.service` is a manual, oneshot unit and has no install
target; it must not be enabled at boot. Before the first deployment or a schema
upgrade, stop ingress and every old/new API, worker, and supervisor that uses
the database. Drain or cancel work and require zero nonterminal runs and
`active_count=0`; resolve unknown provider outcomes before proceeding. Create
and validate a recoverable database backup, plus a paired artifact-volume
backup when artifacts exist. Only after the migration has been reviewed against
the exact release, run:

```sh
sudo systemctl start gpu-control-db-check.service
sudo systemctl --no-pager --full status gpu-control-db-check.service
sudo journalctl --no-pager -u gpu-control-db-check.service
```

Review the check unit's JSON output (`current_version`, `target_version`, and
`planned_versions`) against the exact release and migration record. Stop if the
observed version or plan is unexpected. The check unit is read-only and manual;
it does not automatically start migration. After review and the backup/drain
gates above, start the separate migration unit:

```sh
sudo systemctl start gpu-control-db-migrate.service
sudo systemctl --no-pager --full status gpu-control-db-migrate.service
sudo journalctl --no-pager -u gpu-control-db-migrate.service
```

The migration unit also runs the read-only `--check-db` as `ExecStartPre`, so an
unsupported version or malformed schema-version table prevents
`--init-db` from running if state changed after the manual review. The unit then
runs `python -m gpu_gateway.worker --init-db` as the same restricted identity.
It applies the explicit v1-to-current migration and idempotently creates missing Gateway/OAuth tables;
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
processes first. The CLI also requires all seven Gateway units to be loaded and
inactive. Before running it, stop the capacity timer and any active capacity
check or manual capacity bridge, and ensure the manual migration unit is not
running. For example, after recording whether the capacity timer was active:

```sh
sudo systemctl stop gpu-control-artifact-capacity.timer \
  gpu-control-artifact-capacity.service gpu-control-capacity-bridge.service
```

The API, worker, and supervisor must already be stopped after accepted work is
drained and reconciled. Do not start them automatically after backup; follow
the maintenance/change procedure. If the capacity timer was active before the
backup, restart it only after the backup command completes and the artifact
mount has been verified. The manual bridge remains manual-only.

Create an existing mode-0700 output directory on an encrypted,
access-controlled backup filesystem. Keep PostgreSQL connection settings in
libpq environment configuration or a protected `PGPASSFILE`; never pass a
database URL or password as a command argument. Run the same command from one
shell after all Gateway processes have stopped:

```sh
set -eu
python /opt/gpu-control/gateway/deploy/backup_generation.py \
  --output-dir /secure/gateway-backups \
  --artifact-dir /var/lib/gpu-control/artifacts \
  --confirm-services-stopped
```

`--confirm-services-stopped` is a required operator attestation for creating a
generation and is copied into `manifest.json`. The tool also requires all seven
installed Gateway systemd units to report `LoadState=loaded` and
`ActiveState=inactive`, and records those observations in the manifest. This
checks only the local systemd manager: stop ingress and every API/worker/
supervisor instance across all hosts, and check for manually started processes
outside these units before confirming. Database quiescence remains an
additional fail-closed guard.

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
provisioned credentials from a secret manager. Before starting, provision the
restore host, port, database name, artifact path, and an administrative
`PGPASSFILE` entry through the secret manager. The passfile must be mode `0600`
and match the restore host, port, database wildcard, and administrative user;
do not put its contents in shell history or the operations record. Prepare a
private mode-`0700` drill-record directory before running the commands. The
block captures exact row counts for `gateway_runs_v1`, `gateway_control_v1`, an
optional legacy `gateway_schema_version`, and every present
`gateway_oauth_*` table from the quiesced source before restore, then compares
them with the restored database. Missing required tables or count differences
stop the drill; counts remain in mode-`0600` private files.

```sh
set -eu
generation_dir=/secure/gateway-backups/gpu-control-REPLACE_WITH_GENERATION_ID
source_host=REPLACE_WITH_QUIESCED_SOURCE_HOST
source_port=5432
source_admin=REPLACE_WITH_SOURCE_READER_ROLE
source_db=REPLACE_WITH_SOURCE_DATABASE
source_passfile=/run/secrets/gpu-control-source.pgpass
restore_host=REPLACE_WITH_ISOLATED_RESTORE_HOST
restore_port=5432
restore_admin=REPLACE_WITH_RESTORE_ADMIN_ROLE
restore_db=REPLACE_WITH_NEW_EMPTY_DATABASE
restore_artifact_dir=/var/lib/gpu-control-restore/REPLACE_WITH_NEW_EMPTY_DIRECTORY
drill_record_dir=/secure/gateway-drill/REPLACE_WITH_PRIVATE_RECORD_DIRECTORY
export PGHOST="$restore_host" PGPORT="$restore_port" PGUSER="$restore_admin"
export PGPASSFILE=/run/secrets/gpu-control-restore.pgpass
: "${generation_dir:?set the verified backup generation directory}"
: "${source_host:?set the quiesced source host}"
: "${source_admin:?set the source reader role}"
: "${source_db:?set the source database}"
: "${source_passfile:?set the source passfile path}"
: "${restore_host:?set the isolated restore host}"
: "${restore_admin:?set the restore administrator role}"
: "${restore_db:?set a new database name}"
: "${restore_artifact_dir:?set a new artifact directory}"
case "$generation_dir $source_host $source_admin $source_db $source_passfile $restore_host $restore_admin $restore_db $restore_artifact_dir $drill_record_dir" in
  *REPLACE*) echo 'replace every REPLACE_... value before continuing' >&2; exit 2 ;;
esac
test -d "$drill_record_dir" && test ! -L "$drill_record_dir"
test "$(stat -c '%a' "$drill_record_dir")" = 700
test -r "$source_passfile"
test "$(stat -c '%a' "$source_passfile")" = 600
test -r "$PGPASSFILE"
test "$(stat -c '%a' "$PGPASSFILE")" = 600
test ! -e "$restore_artifact_dir" && test ! -L "$restore_artifact_dir"
umask 077
source_counts="$drill_record_dir/source-table-counts.txt"
restored_counts="$drill_record_dir/restored-table-counts.txt"
test ! -e "$source_counts" && test ! -e "$restored_counts"
count_gateway_tables() {
  PGPASSFILE="$5" psql --no-psqlrc --quiet --tuples-only --no-align \
    --set=ON_ERROR_STOP=1 --host="$1" --port="$2" --username="$4" \
    --dbname="$3" <<'SQL'
DO $$
DECLARE missing_tables text;
BEGIN
  SELECT string_agg(name, ', ' ORDER BY name) INTO missing_tables
  FROM unnest(ARRAY['gateway_runs_v1', 'gateway_control_v1']) AS required(name)
  WHERE to_regclass(format('public.%I', name)) IS NULL;
  IF missing_tables IS NOT NULL THEN
    RAISE EXCEPTION 'required Gateway tables are missing: %', missing_tables;
  END IF;
END
$$;
WITH table_names AS (
  SELECT 'gateway_runs_v1'::text AS table_name
  UNION ALL SELECT 'gateway_control_v1'
  UNION ALL SELECT 'gateway_schema_version'
    WHERE to_regclass('public.gateway_schema_version') IS NOT NULL
  UNION
  SELECT table_name FROM information_schema.tables
  WHERE table_schema='public' AND table_type='BASE TABLE'
    AND table_name LIKE 'gateway_oauth_%'
)
SELECT format(
  'SELECT %L || ''|'' || count(*)::text FROM %I.%I',
  table_name, 'public', table_name
)
FROM table_names
ORDER BY table_name
\gexec
SELECT 'SELECT ''gateway_schema_version|ABSENT'''
WHERE to_regclass('public.gateway_schema_version') IS NULL
\gexec
SQL
}
read_gateway_schema_version() {
  PGPASSFILE="$5" psql --no-psqlrc --quiet --tuples-only --no-align \
    --set=ON_ERROR_STOP=1 --host="$1" --port="$2" --username="$4" \
    --dbname="$3" <<'SQL'
SELECT CASE
  WHEN to_regclass('public.gateway_schema_version') IS NULL
    THEN 'SELECT ''unversioned'''
  ELSE 'SELECT COALESCE((SELECT version::text FROM gateway_schema_version WHERE id=1), ''missing'')'
END
\gexec
SQL
}
count_gateway_tables "$source_host" "$source_port" "$source_db" \
  "$source_admin" "$source_passfile" > "$source_counts"
source_schema_version=$(read_gateway_schema_version "$source_host" \
  "$source_port" "$source_db" "$source_admin" "$source_passfile")
python /opt/gpu-control/gateway/deploy/backup_generation.py \
  --verify-generation "$generation_dir"
createdb --host "$restore_host" --port "$restore_port" \
  --username "$restore_admin" "$restore_db"
pg_restore --exit-on-error --no-owner --no-acl \
  --host "$restore_host" --port "$restore_port" \
  --username "$restore_admin" --dbname "$restore_db" \
  "$generation_dir/database.dump"
expected_schema_version=$(python3 - "$generation_dir/manifest.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding='utf-8') as source:
    value = json.load(source).get('schema_version')
if not isinstance(value, str) or not value:
    raise SystemExit('backup manifest has no valid schema version')
print(value)
PY
)
restored_schema_version=$(read_gateway_schema_version "$restore_host" \
  "$restore_port" "$restore_db" "$restore_admin" "$PGPASSFILE")
test "$restored_schema_version" = "$expected_schema_version"
test "$source_schema_version" = "$expected_schema_version"
sudo install -d -o gpu-control-worker -g gpu-control-artifacts -m 2750 \
  "$restore_artifact_dir"
if [ -f "$generation_dir/artifacts.tar" ]; then
  sudo -u gpu-control-worker tar --extract --no-same-owner --no-same-permissions \
    --file="$generation_dir/artifacts.tar" --directory="$restore_artifact_dir"
fi
count_gateway_tables "$restore_host" "$restore_port" "$restore_db" \
  "$restore_admin" "$PGPASSFILE" > "$restored_counts"
diff -u -- "$source_counts" "$restored_counts"
```

The mode check uses GNU `stat`, as the target systemd host is Linux. Replace
every `REPLACE_...` value before running. The artifact path check deliberately
requires a path that does not exist yet, so extraction cannot silently overlay
stale files. The database creation likewise must fail if the chosen name
already exists. Keep
`PGHOST`, `PGPORT`, `PGUSER`, and `PGPASSFILE` pointed only at the isolated
restore service for all commands in this block.

The backup tool does not create detached `.sha256` sidecar files. Its
`--verify-generation` action checks the database and artifact archive against
their sizes and SHA-256 digests in `manifest.json`, and validates artifact
archive members before extraction. Restore from that verified generation using
the exact archive names above; `artifacts.tar` is absent only when there are no
artifact manifests and no artifact directory was included in the generation.

Compare the captured row counts for `gateway_runs_v1`, `gateway_control_v1`,
and every present `gateway_oauth_*` table between the source snapshot and
restored database. `gateway_schema_version` may be absent only when both source
and restore match the backup manifest's `unversioned` value; otherwise its
version and row count must match. Check representative run IDs, terminal
results, approval IDs/expiry, `active_count`, and OAuth client/token revocation
state. Do not print token hashes, session hashes, owner credentials, or row JSON
into shared logs. Run a read-only Gateway smoke check against the restored DB;
do not point a live worker at the drill database. Record dump checksum, server
versions, source/manifest/restore schema versions, table-count file references,
elapsed time and any discrepancy in the private operations record.

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
stop new submissions, worker and recovery supervisor. On every surviving worker
host, record the host identity, UTC capture time, Docker daemon endpoint/context,
and the complete container inventory in a private recovery record before
restarting Docker or changing containers. For example, run these read-only
commands as the service operator and store their output outside shared logs:

```bash
umask 077
date -u +%FT%TZ
hostname -f
docker context show
docker context inspect "$(docker context show)" --format '{{json .Endpoints.docker}}'
docker info --format '{{.ID}} {{.Name}} {{.ServerVersion}}'
docker ps -a --no-trunc \
  --format '{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Labels}}'
```

The full inventory may include unrelated workload metadata; restrict access to
the recovery record. Preserve daemon and worker journals for the incident
window. Restore the database only after the inventory is captured. Then export
the restored nonterminal run IDs and `active_count` using the reviewed
read-only database procedure for the deployed schema. For each nonterminal
`local_cpu` run, query the surviving daemon by the exact
`io.unjuno.gpu-control.run-id=<run-id>` label and record every matching
container ID and its state. For each run, the read-only lookup is:

```bash
run_id='REPLACE_WITH_32_CHARACTER_RUN_ID'
docker ps -a --no-trunc \
  --filter "label=io.unjuno.gpu-control.run-id=$run_id" \
  --format '{{.ID}}\t{{.Names}}\t{{.Status}}'
```

For every returned container ID, capture only its state and identity labels
with `docker inspect --format`; do not dump the full inspect JSON into shared
logs, since it includes environment and mount details. For each returned ID:

```bash
container_id='REPLACE_WITH_RETURNED_CONTAINER_ID'
docker inspect --format '{{.Id}}\t{{.State.Status}}\t{{index .Config.Labels "io.unjuno.gpu-control.run-id"}}\t{{index .Config.Labels "io.unjuno.gpu-control.owner-sha256"}}\t{{index .Config.Labels "io.unjuno.gpu-control.plan-sha256"}}\t{{index .Config.Labels "io.unjuno.gpu-control.image-digest"}}\t{{index .Config.Labels "io.unjuno.gpu-control.source-sha"}}' "$container_id"
```

Compare its full identity labels
(`run-id`, owner SHA-256, plan SHA-256, image digest, and source SHA) with that
run's persisted plan and intent; do not use a name match alone. One exact
identity match can be handed to the normal recovery supervisor for reconcile.
Zero matches, multiple matches, mismatched labels, an unavailable daemon, or a
missing host inventory leaves the run unresolved and requires operator
investigation; keep it nonterminal/unknown and keep admissions disabled. Do not
create a replacement container, blindly resubmit, or remove a container as a
manual shortcut. For remote providers, use the provider's read-only lookup and
the same no-resubmission rule; an unobservable outcome remains unknown.

After reconciliation, compare the database's nonterminal runs and `active_count`
to the operator-reviewed run/resource inventory. Restart workers and the
recovery supervisor only under the documented recovery sequence; enable
submissions only after every run is accounted for and the restored
`active_count` agrees with that inventory.

The initial operational target in the roadmap is RPO 24 hours and RTO 2 hours.
Those targets are **not yet measured**. A release claim requires a timed restore
drill by a second operator and a documented recovery of run, approval, OAuth and
matching artifact-volume state. The repository enforces per-run artifact count
and size bounds but does not impose a global volume quota or deliver capacity
notifications. `experiment_capabilities` checks that the artifact directory for local
CPU workloads exists, is writable by the Gateway process, and reports nonzero
available space; it blocks submissions when that probe fails. When
`GATEWAY_ARTIFACT_MIN_FREE_BYTES` is set, both capabilities and prepare also
require the artifact path to be on a distinct filesystem and block below that
headroom floor, so a failed capacity timer is not the only admission control.
`statvfs` free space does not prove an enforced quota or deliver a human
low-space alert. Before enabling artifact-producing workloads on a target
host, mount the artifact directory as a separate fixed-size filesystem/volume.
Its filesystem size then
enforces a global hard ceiling across API, worker, and supervisor, while
`GATEWAY_ARTIFACT_MIN_FREE_BYTES` preserves operational headroom. The capacity
timer runs every five minutes and exits nonzero if the path is not a distinct
filesystem, the probe fails, or free space is below the configured threshold;
systemd records the structured status in the journal. Every run now emits a
stable `status` field (`alert` or `ok`) alongside the capacity values, so a
journal/metrics bridge can raise and clear the same alert when the filesystem
recovers. The event is defined by
[`capacity-event.schema.json`](../gateway/deploy/capacity-event.schema.json);
bridges should reject unknown fields, require a nonempty reason for alerts,
and use `check` plus `status` as the deduplication key/state. Do not forward environment variables, filesystem
paths, or arbitrary exception text. The status event is not itself a
notification. Connect failed
`gpu-control-artifact-capacity.service` results to the host's alerting system
and test notification delivery. The unit writes to journald with identifier
`gpu-control-capacity`; a host bridge can consume its `MESSAGE` JSON and
trusted `_SYSTEMD_UNIT` metadata. Do not treat user-supplied `SYSTEMD_UNIT` as
unit identity. The timer and journal output alone are not a human
notification. Record the selected alert system and route name (never its
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
On a systemd host, a journal consumer can select only these records with
`journalctl --follow --output=json SYSLOG_IDENTIFIER=gpu-control-capacity`.
Parse each record's `MESSAGE` as JSON, validate it against the schema above,
and treat `status=ok` as a clear/update of the same alert key after previously
observed `status=alert`. Do not alert on unrelated capacity-service stderr or
forward the full journal record; retain timestamps and unit identity as
delivery evidence.
Test artifact-write behavior at the volume limit before enabling the workload.
After mounting, set the artifact filesystem root to owner/group
`gpu-control-worker:gpu-control-artifacts` with mode `02750`. Create
`/var/lib/gpu-control/artifacts/.gpu-control-probes` as
`gpu-control-worker:gpu-control-artifact-probes` mode `03770`. The root and
run-scope directories are worker-owned, group-readable/searchable, and
non-world-accessible; artifact blobs are mode `0640`. The probe directory is
sticky and group-writable so the API can create and unlink its short-lived
readiness probe without write access to artifact blobs. The capacity timer runs
`check_artifact_capacity.py`, which checks the mounted filesystem identity and
free-space headroom with `statvfs`; it does not perform the API's write probe.
Capacity therefore has no supplementary probe-group membership. Verify the
mounted source, group ownership, modes, and free space before starting
API/worker/supervisor.
For an existing artifact tree created with the former private modes, stop API,
worker, supervisor, and capacity services first. Confirm the mounted source and
inspect every entry without following links. Abort if the tree contains a
symlink, hard link, or special file; resolve it manually before migration. The
repository utility `gateway/deploy/migrate_artifact_permissions.py` first
audits the tree without changing it. It rejects links, hard-linked files,
special/nested entries, unexpected root entries or run-scope filenames, and
nonempty probe directories.
Review its output, ensure a current paired backup exists, then apply it as root
while all services remain stopped:

```sh
sudo /opt/gpu-control/venv/bin/python /opt/gpu-control/gateway/deploy/migrate_artifact_permissions.py /var/lib/gpu-control/artifacts
sudo /opt/gpu-control/venv/bin/python /opt/gpu-control/gateway/deploy/migrate_artifact_permissions.py /var/lib/gpu-control/artifacts --apply
```

The utility changes directory ownership/modes to
`gpu-control-worker:gpu-control-artifacts`/`02750`, blob ownership/modes to the
same owner/group/`0640`, and creates the probe directory as
`gpu-control-worker:gpu-control-artifact-probes`/`03770`. It verifies these
results and does not delete payload files. If it rejects an entry, stop and
resolve that entry manually; do not use blanket recursive `chown` or `chmod`.
Verify every manifest digest and resulting ownership/modes before restarting.
Capabilities, prepare, and
the worker immediately before local CPU backend start all fail closed if the
artifact path or configured headroom is unavailable. The 7-day CPU observation period, host alert routing,
database-provider backup configuration, and production recovery remain
outstanding.

Use [`docs/acceptance/2026-10-28-recovery-drill-record-template.md`](acceptance/2026-10-28-recovery-drill-record-template.md)
for every timed drill. It defines RPO as the interval from disruption start
back to the latest fully recovered acknowledged write at or before disruption,
and records missing acknowledged writes separately. RTO runs from the first
observed outage/recovery start through verified ingress restoration. Include
investigation and verification time; a successful restore command does not stop
either clock. Fill the template only with a real observed drill and have an
independent observer review it. An isolated synthetic run records procedure
evidence, not production RPO/RTO acceptance.

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
