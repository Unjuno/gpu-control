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
