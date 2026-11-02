# Paired PostgreSQL and artifact restore — 2026-10-28

Status: **PASS for local synthetic paired restore on schema v6 and v7; production acceptance NOT RUN**.

## Environment

- Source and restore were separate disposable PostgreSQL 16 containers using
  image digest `sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`.
- Restored Gateway database schema version: 6.
- Synthetic run ID: `b5064fba7096462e88b72b81b0148a17`.
- Database dump SHA-256: `fd45d698de49b492f1de8d4cbcb59c7c5f823a4d818c10b45a94fbcdf253f21a`.
- Artifact archive SHA-256: `deda7cc36f7bb90a6d3d3ee67acd8b78cfbd4e82953d5a357a7a4472c0ab708a`.

## Checks performed

- Seeded one synthetic, terminal, cleanup-complete run and its 50-byte artifact
  in the source database and artifact directory.
- Created and listed a PostgreSQL custom-format dump, restored it into the
  separate target container, and archived/extracted the artifact directory to
  a separate restore path.
- Confirmed the restored run and schema version, then fetched the artifact
  through `experiment_artifact` using the restored database and restored file
  tree. Returned bytes matched the fixture and its SHA-256 manifest.
- Confirmed an unrelated owner receives `not_found` for that run/artifact.
- Removed both disposable PostgreSQL containers and the temporary dump,
  archive, and artifact directories after the check.

## Limits

This is local synthetic evidence for paired DB/file restoration and the
owner-scoped application read path. It does not verify a production backup
service, configured filesystem quota, live OAuth/ChatGPT, worker/container
reconciliation, all-table row parity, second-operator reproducibility, or
measured RPO/RTO. It does not complete the P3 restore gate.

## Schema v7 paired backup and restore refresh

- On 2026-10-28, created two disposable PostgreSQL 16 containers on a
  task-specific Docker network. PostgreSQL client commands ran in a separate
  client container; the host connected only to the source and restore DBs on
  loopback ports 55437 and 55438.
- Seeded the source with one synthetic terminal run (`cccc...`), one 35-byte
  artifact, and two synthetic OAuth token records sharing separate grant IDs:
  one unrevoked refresh token and one revoked access token.
- Ran `gateway/deploy/backup_generation.py` against the source and artifact
  directory, then ran `--verify-generation`. The manifest reported schema v7
  and `verified=true`.
- Restored the custom-format dump to the separate PostgreSQL 16 target and the
  artifact tar to a new directory. The target reported schema v7 and preserved
  the succeeded run. `ArtifactStore.get` returned the exact 35 fixture bytes;
  SHA-256 was
  `5693568a2ef76fe9f146214f4546b3b8ca755191c2e4792d32827c122173d268`.
- Both OAuth rows retained their grant IDs and revoked states. Database dump
  SHA-256:
  `806c12e560bd81063b77c7c3e2ead121d6df4ead9c5dd4ca425bab66aaa85be3`.
  Artifact archive SHA-256:
  `c31626ba6bb604140549c2b3e7047612a610e64590f9bcc761f94bb56eaa7d83`.
- Both containers, the task-specific network, and temporary files were
  removed.

This extends local synthetic PostgreSQL 16 evidence through schema v7 and OAuth
grant/revocation preservation. The separate PostgreSQL 17 probe below adds
cross-major restore coverage. Neon behavior, production credentials or
retention, target-host permissions, a second operator,
worker/container reconciliation, and measured RPO/RTO remain unverified.
Production backup and restore acceptance remains open.

## PostgreSQL 16 to 17 restore compatibility probe

- Repeated the synthetic schema v7 backup using a disposable PostgreSQL 16
  source and restored its dump into a separate PostgreSQL 17.11 target
  (`postgres:17.11-bookworm`, image digest
  `sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27`).
- The v7 generation passed `--verify-generation`. The PostgreSQL 17 target
  reported schema v7 and preserved the succeeded run, OAuth grant ID
  `grant-pg17` with `revoked=false`, and the paired artifact. `ArtifactStore.get`
  returned byte-exact fixture data.
- Database dump SHA-256:
  `d388364560d174f6a53f02924cddd913d657c0234eace998e93f641c63f932d4`.
  Artifact archive SHA-256:
  `6444d3d5766958f9c207f12e7972d54a6f47cf04a982bbc144bdd21df7105761`.
- Both database containers, the task-specific Docker network, and temporary
  files were removed.

This is local PostgreSQL major-version restore compatibility evidence only. It
does not establish Neon-specific behavior, production backup credentials or
retention, target-host permissions, second-operator reproducibility, worker
reconciliation, or measured RPO/RTO.

## Schema v8 atomic generation through isolated systemd and restore — 2026-10-28

- Built an ephemeral Ubuntu 24.04 container with a live systemd manager and
  installed the seven Gateway unit templates into that manager. Before backup,
  `systemctl show` reported every required unit `LoadState=loaded` and
  `ActiveState=inactive`; the backup CLI observed those states directly.
- Initialized the current worktree's Gateway schema in a disposable PostgreSQL
  16 source container and inserted one synthetic terminal run with
  `cleanup_state=not_required`, `slot_reserved=false`, and a zero active count.
  No OAuth credentials, real owners, provider handles, or artifact manifests
  were seeded. The paired artifact directory was empty.
- Ran the current `gateway/deploy/backup_generation.py` with the stopped-service
  confirmation, generated a database dump plus empty artifact archive, and
  passed `--verify-generation`; the manifest reported `schema_version=8` and
  `verified=true`.
- Restored `database.dump` into a separate disposable PostgreSQL 16 target and
  extracted the paired empty artifact archive. The target reported schema 8,
  one preserved run, `active_count=0`, state `succeeded`, and cleanup state
  `not_required`.
- Removed the disposable source and target databases, privileged systemd
  container, network, built image, and temporary generation after recording the
  result.

This is current-schema local backup-generation and database-restore evidence,
including the CLI's real systemd state gate. The artifact archive was empty, so
this run does not add artifact-byte retrieval evidence. It used synthetic data
and a disposable Linux container; it does not establish target-host or Neon
behavior, encrypted off-host retention, second-operator reproducibility,
worker/container reconciliation, OAuth preservation for this v8 generation,
or measured RPO/RTO. Production recovery acceptance remains open.
