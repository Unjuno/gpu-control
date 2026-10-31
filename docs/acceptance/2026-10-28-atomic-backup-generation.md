# Atomic paired backup generation — 2026-10-28

Status: **PASS for local synthetic PostgreSQL 16 schema v6 and v7 backup,
verification, restore, and failure-injection checks; production acceptance NOT RUN**.

## Environment and output

- Disposable PostgreSQL 16 container on an isolated Docker network.
- Gateway schema version: 6; one synthetic succeeded run with cleanup complete.
- Run ID: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
- Artifact fixture: `result.bin`, 25 bytes, SHA-256
  `1993d519d243af437e7c265d809c18a1061beabdead8520754b66d9c1e080716`.
- Published generation:
  `gpu-control-20261027T222922Z-200fa888523044939615fba871183a5f`.
- Database dump SHA-256:
  `99cfb878b18ef40526332e8a8e2354850d6894668d2635c1cd100b004f821579`.
- Artifact archive SHA-256:
  `e4da56d95b2fa8f33ab82b113a4ab504755f288c44a14fe2c5fb49238b4c03ab`.

## Checks performed

- Created a paired generation with `gateway/deploy/backup_generation.py`.
  The manifest reported schema v6, one run, zero active slots, one run with
  artifact manifests, and `consistency=quiesced`.
- Ran `--verify-generation`; it validated generation identity, exact file set,
  sizes, checksums, and both archive listings.
- Injected exit 42 from `tar`. The command failed and the output contained no
  published generation and no staging directory. The previously completed
  generation remained intact.
- Restored the database dump into a separate database on the disposable
  PostgreSQL server, extracted the artifact archive to a new directory, and
  fetched the object through `ArtifactStore.get` using the restored database.
  The run state was `succeeded`; returned bytes and SHA-256 matched the fixture.
- Focused tests:
  `./gateway/.venv/bin/python -m pytest -o addopts= gateway/tests/test_backup_generation.py -q` —
  6 passed, 1 Starlette deprecation warning.

All disposable Docker resources and files are removed after this record is
written.

## Limits

This is local synthetic evidence. It does not establish production secret
handling, encrypted off-host retention, target-host permissions, a scheduled
backup, second-operator reproducibility, timed RPO/RTO, OAuth-state parity, or
worker/container reconciliation. It does not complete P3 recovery acceptance.

## Schema v7 refresh

A follow-up paired backup/restore is recorded in
`2026-10-28-paired-artifact-restore.md`. The backup tool generated and verified
a schema v7 generation, which restored into a separate disposable PostgreSQL 16
database together with the artifact archive. The run, exact artifact bytes,
OAuth grant IDs, and token revoked states were preserved. These synthetic local
checks extend this result through the v7 schema but do not establish production
backup/restore or timed RPO/RTO.

## Follow-up archive validation

After the initial drill, source review found that archive checksum/listing did
not reject unsafe member paths or link/special-file entries before restore.
`backup_generation.py` now validates the opaque artifact layout without
extracting the archive and enforces per-object/per-run limits. Tests reject
absolute paths, `..`, nested paths, symlinks, hard links, and FIFOs. A real
macOS `tar` fixture exposed AppleDouble metadata entries; creation now disables
those entries with `COPYFILE_DISABLE=1`, and a real OS tar archive passed the
layout validator. Gateway suite after this follow-up: 258 passed, 8 skipped,
1 Starlette deprecation warning. Production restore acceptance remains open.

## Required stopped-service attestation — 2026-10-28

Source review found that database row checks can pass while API/worker services
are idle but still running; a new admission or OAuth write could race the
backup. The operator runbook already requires ingress and all API, worker, and
supervisor instances to be stopped. The backup tool now requires the explicit
`--confirm-services-stopped` CLI flag, locally checks all seven installed
Gateway systemd units report `LoadState=loaded` and `ActiveState=inactive`, and
records both `services_stopped_confirmed: true` and the per-unit states in new
manifests. Verification rejects explicit false or incomplete systemd states.
It continues to accept legacy format-1 generations with neither field so
existing backups remain verifiable.

The systemd query covers only this local manager. It cannot prove that every
replica on other hosts or manually started processes is stopped; operators must
complete the runbook's ingress and all-host shutdown procedure before
confirming. Database quiescence and cleanup checks remain additional guards.

- Focused `test_backup_generation.py`: **20 passed**, one existing Starlette
  deprecation warning.
- Full offline Gateway suite: **351 passed / 9 skipped**, one existing
  Starlette deprecation warning.
- Source SHA-256:
  `8326f29ba084bad13a9be9c838238dcbdca6ead5770e768ab1b00e654b78c860`.
- Test SHA-256:
  `23255bc9b3f2f8cf759cd070a6044c6247adf4d3114c43ba6defb4639022efdc`.
- systemctl outputs were stubbed in unit tests; no target Linux manager or
  backup/restore was exercised for this follow-up. `git diff --check` passed.

## Database-stage failure cleanup follow-up — 2026-10-28

Added regressions that inject failure at `pg_dump` and at the subsequent
`pg_restore --list` validation. Both failures leave the output directory
without a published generation or a `.gpu-control-incomplete-*` staging
directory. Focused `test_backup_generation.py` now passes **22 tests**, with
one existing Starlette deprecation warning. This is fault-injected local
filesystem/tool-boundary evidence; no database dump or restore was run in this
follow-up, and production recovery acceptance remains open.

## Database-to-artifact integrity gate — 2026-10-30

Source review found that a backup generation could be published with a valid
database dump and a valid artifact tar even when a live artifact referenced by
the database was missing or corrupt. Generation now reads the database's
artifact metadata while the services are quiesced and checks each unexpired
reference against both the source blob and the bytes in the generated tar,
using the same owner/run scope and artifact-ID hashing as `ArtifactStore`.
Expired artifacts are excluded because the API no longer serves them after
their recorded expiry. Missing files, unsafe file types, size mismatches, and
digest mismatches fail the generation before publication.

Focused tests cover matching files, expiry handling, source size mismatch, and
archive digest mismatch: `gateway/.venv/bin/python -m pytest -o addopts=
gateway/tests/test_backup_generation.py -q` — **24 passed**, one existing
Starlette deprecation warning. `git diff --check` passed. No PostgreSQL dump,
target-host operation, or restore was run for this code change; synthetic
production recovery and measured RPO/RTO remain unaccepted.

## PostgreSQL manifest query and platform tar revalidation — 2026-10-30

- Used one uniquely named disposable PostgreSQL 16 container pinned to
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
  The schema and succeeded run were synthetic. No host port was published.
- Exercised the new `_artifact_records()` query against PostgreSQL, then ran
  generation through the real local `tar` and `verify_generation()` paths. The
  `pg_dump` and `pg_restore --list` commands were deliberately stubbed, so this
  is DB-query and paired-artifact integration evidence, not a real database
  backup or restore.
- Replaced the source blob with different bytes of the same length. Generation
  rejected its SHA-256 mismatch before publishing another generation. The
  valid generation and negative case both passed; the disposable container and
  temporary files were removed.
- The first run exposed a macOS tar naming detail: entries start with `./`.
  Archive member lookup now normalizes that prefix, and the unit fixture uses
  the same form. Focused backup-generation tests remain **24 passed**. No
  target Linux host, full PostgreSQL dump/restore, second operator, or timed
  RPO/RTO drill was performed.

## Real dump and paired restore through the new integrity gate — 2026-10-30

- Repeated the path using the same pinned PostgreSQL 16 image and a synthetic
  run/artifact in a minimal unversioned test schema. The source and restore
  database were in one disposable container with no published host port.
- `backup_generation.py` executed real `pg_dump --format=custom`, validated it
  with real `pg_restore --list`, created the artifact tar with host `tar`, and
  passed `verify_generation()`. The database archive was then restored into a
  separately created database in the same container. The restored run identity
  and terminal state matched the source.
- Extracted the verified paired artifact into a separate temporary tree and
  retrieved it with `ArtifactStore.get`. Returned bytes matched the seeded
  payload and its manifest SHA-256 exactly. Container and temporary files were
  removed.
- The systemd stopped-unit check was stubbed to the expected inactive state,
  and the schema was intentionally minimal/unversioned. This is local synthetic
  backup/restore and API-store artifact retrieval evidence; it does not accept
  Linux target-host service state, the production schema/provider, second-
  operator recovery, or timed RPO/RTO.

## Current Gateway schema v8 dump and paired restore — 2026-10-30

- Repeated the recovery path with `Store.initialize()` on a disposable
  PostgreSQL 16 instance pinned to the image digest above. The database port
  was dynamically published on loopback only. This created the current Gateway
  schema v8, including OAuth tables and current migrations; one synthetic
  terminal run and its artifact manifest/blob were added.
- Generated a real custom-format `pg_dump`, validated it with real
  `pg_restore --list`, and passed `verify_generation()`. Restored the dump into
  a separate database and confirmed schema version 8, the same run owner/state,
  and the artifact digest in its result manifest.
- Restored the paired tar to a separate temporary tree and fetched the payload
  through `ArtifactStore.get`; bytes matched exactly. The isolated systemd
  stopped-unit probe was stubbed as inactive, so no host service was observed
  or changed. The database container, both temporary databases, dump, archive,
  and artifact trees were removed.
- This verifies local synthetic v8 paired restore and artifact retrieval. It
  does not establish production/Neon behavior, target-host systemd state,
  second-operator recovery, alert delivery, or measured RPO/RTO.

## PostgreSQL-backed regression test — 2026-10-30

Added `gateway/tests/test_postgresql_backup_integrity.py` to the ordinary
Gateway CI suite. Against the dedicated PostgreSQL test database it initializes
the current Gateway schema, inserts a uniquely owned synthetic terminal run,
executes the real artifact-manifest SQL query, and verifies matching source and
tar bytes. Same-size source corruption must fail the digest check. The focused
test passed **1/1** against a fresh pinned PostgreSQL 16 container; it cleans up
its unique row and leaves the shared database usable. This test covers the
database-query/integrity helpers; it does not run `pg_dump`, restore, systemd,
or production recovery. GitHub CI has not yet run on this uncommitted test.

## Full Gateway regression after integrity change — 2026-10-30

The complete Gateway test suite passed **426 tests, 2 optional skips**, against
pinned PostgreSQL 16 and the cached digest-pinned CPU smoke image. This includes
the new PostgreSQL-backed manifest/integrity regression and the real CPU/MCP,
OAuth PostgreSQL, and PostgreSQL outage-recovery paths. The suite ran with the
named PostgreSQL container retained across stop/restart; it was removed after
the run. The initial `--rm` harness attempt is not counted because the outage
test needs to restart that same container. This remains local macOS/OrbStack
evidence, not GitHub CI or target-host acceptance.

## Dirty-source paired restore follow-up — 2026-10-30

The exact current dirty Gateway source fingerprint also passed an end-to-end
synthetic schema-v8 check using real PostgreSQL `pg_dump`, `pg_restore --list`,
separate-database restore, artifact archive extraction, and byte-exact
`ArtifactStore.get()`. The isolated systemd inactive-unit response was stubbed;
this does not constitute target-host/systemd, Neon, second-operator, or measured
RPO/RTO acceptance. See
`docs/acceptance/2026-10-30-dirty-source-paired-restore.md` for full image and
artifact hashes.

## Current schema v9 paired restore — 2026-10-31 07:50 JST

- Ran `backup_generation.create_generation()` from the exact-source local
  candidate based on PR #58 head `561a6c7`. The Gateway source in that
  candidate matches the current 340-file checkout. PostgreSQL 16 used pinned
  image `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
  bound only to `127.0.0.1:55484` in a disposable container and task-specific
  Docker network.
- Initialized current schema v9 and seeded one synthetic terminal run
  (`succeeded`, `cleanup_state=complete`, `active_count=0`), one persistent
  OAuth DCR client, and one 36-byte artifact with its exact manifest. The
  backup utility created a real PostgreSQL custom-format dump and artifact
  tar, validated both, verified their manifest digests, and published
  generation `20261030T225044Z-b7a601fdb7874c2a9731a9d1008992b6`.
- Restored the database into a separate database in the same disposable
  PostgreSQL container and extracted artifacts into a separate directory.
  The restored schema version was 9; the run state and cleanup state matched;
  the persistent OAuth client remained persistent; `ArtifactStore.get()`
  returned the exact 36 fixture bytes.
- Database dump SHA-256:
  `def8dae2d2fbc971a6ecf3ae91807b0d17e7a278d6fd4573e7d3088d8a106c3c`.
  Artifact archive SHA-256:
  `6aa69141df9f29b20e3a26ad07b78d2bebdeb91c6520bf4b5e97e947303b9d1c`.
- On macOS, `_assert_gateway_systemd_units_stopped()` was stubbed to the
  required inactive-unit map. This confirms only local schema-v9 database and
  paired artifact generation/restore; it does not establish target Linux
  systemd quiescence, Neon behavior, off-host retention, second-operator
  recovery, alerts, or measured RPO/RTO. The disposable database container,
  network, scratch files, and port were removed/closed after verification.
