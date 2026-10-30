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
