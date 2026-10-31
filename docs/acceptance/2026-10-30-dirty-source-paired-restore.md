# Dirty-source PostgreSQL and artifact paired restore — 2026-10-30

Status: **PASS for local synthetic schema-v8 generation, verification, restore, and artifact retrieval. Target-host/production recovery acceptance remains NOT RUN.**

## Source and environment

- Gateway source was the dirty primary worktree at HEAD
  `aa681f4062dac6b73bcf380a38a4258b96a47e1d`; its Gateway dirty-source
  fingerprint was
  `06dc2a2d9b48d146d0dc45a650feacaa7949ff7860eb4fba25c6bc1cfd605877`.
- PostgreSQL 16 source and restore databases used the pinned image
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
  The disposable DB was published on loopback only. A same-image client
  container on a task-specific Docker network supplied the real `psql`,
  `pg_dump`, `pg_restore`, `createdb`, and `dropdb` binaries because these are
  absent from the macOS host.
- Seeded one synthetic schema-v8 successful, cleanup-complete run and its
  persisted artifact manifest/blob. Payload was 33 bytes with SHA-256
  `616c8774486298901a5aada4fbb72c891852af1a156823a7ef9ffcdfdb791b92`.

## Procedure and result

- Called the current `backup_generation.create_generation()` against the
  source DB and artifact tree. The systemd unit-state probe was stubbed to the
  expected `inactive` values; no host services were observed or changed.
- The utility created a real PostgreSQL custom-format dump, validated it with
  real `pg_restore --list`, archived the artifact tree with host `tar`, checked
  every unexpired DB manifest against source and archive bytes, and passed
  `verify_generation()`.
- Restored the dump into a separate database in the same disposable PostgreSQL
  container and extracted the paired artifact archive into a separate tree.
  The restored schema version was 8, the same run owner/state and artifact
  digest were present, and `ArtifactStore.get()` returned the exact original
  33 bytes.
- Generation ID: `20261030T171106Z-fae400e2475244f29f5900b995810c22`.
  Database dump SHA-256:
  `2c554895b80fb2f2161221db7f285ca72cd6c687df7b79cb62e5a76214948064`.
  Artifact archive SHA-256:
  `8c8a2c09fb0f1b1fa0c37e3286f85aa588d75b78625a2e8c39a8886c4e095911`.
- Disposable source/restore DB, client container, network, and scratch files
  were removed by the task cleanup trap.

This is local synthetic evidence for the current dirty backup code. It does
not prove target-host systemd state, Neon behavior, encrypted off-host backup
retention, operator recovery, worker/container reconciliation, or measured
RPO/RTO. It does not change `policies/repository-state.yaml` from
`mode: parked`.

## Follow-up: current-source PostgreSQL artifact-manifest integration — 2026-10-31 03:37 JST

This is a focused integration rerun against the current dirty checkout, not a
second paired dump/restore drill.

- Gateway HEAD: `a794438f42bd7246f463eaaa40d963af0aae9d13`.
- Tested file SHA-256 values:
  - `gateway/deploy/backup_generation.py`:
    `bf2f343a286c29772b3d13c19ac1fb40f007391c6a1ba349e085974773f1f724`
  - `gateway/tests/test_postgresql_backup_integrity.py`:
    `133e21b9b62922723cfc6ad940924e118db12016ae06d0976c5d2fde50a5bebe`
  - `gateway/gpu_gateway/store.py`:
    `74de25e8e4fb350bbd9918d1e502fe0d8b56acaab7d7a3cdbf50697cc09b0b66`
- Ran `gateway/.venv/bin/python -m pytest -o addopts= -q
  tests/test_postgresql_backup_integrity.py` against an isolated loopback-only
  PostgreSQL 16 container using image digest
  `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`:
  **1 passed** (one existing Starlette deprecation warning).
- The test verified PostgreSQL artifact-manifest query shape, owner/run scoped
  blob naming, and current blob/archive bytes against manifest size and digest;
  it also rejected malformed JSON manifest shape and corrupted bytes. The
  disposable container was removed and port 55471 had no listener afterward.

This does not repeat `pg_dump`/`pg_restore`, prove production/Neon backup
behavior, target-host service quiescence, off-host retention, second-operator
restore, or measured RPO/RTO. No production data or service was touched.

## Current P3 backup-integrity review overlay replay — 2026-10-31

Rebuilt the three-file P3 code/test overlay from the current dirty checkout at
HEAD `a794438f42bd7246f463eaaa40d963af0aae9d13` and applied it to a detached
worktree at PR #51's pushed head
`aa681f4062dac6b73bcf380a38a4258b96a47e1`. The patch applies cleanly and all
three candidate files match the current dirty source byte-for-byte. The
code/test patch is `/tmp/gpu-control-p3-backup-integrity.patch`, SHA-256
`d36b3a575a7f9944bfcf7718cfe3d827d7619365f8897adbd940591967d3768a`.

In that candidate worktree, `test_backup_generation.py` and
`test_postgresql_backup_integrity.py` passed **25/25** against disposable
PostgreSQL 16 pinned to
`sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`,
bound to loopback port 55475. The container was removed and the port was
closed. This current replay supersedes the previously recorded P3 patch
fingerprint `e5c05d1f...`; do not apply that older fingerprint as the current
overlay. This remains local candidate evidence, not GitHub CI, a production
backup/restore drill, or target-host recovery acceptance.
