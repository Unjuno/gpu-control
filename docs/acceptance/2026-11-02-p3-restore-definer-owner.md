# P3 restore ownership and SECURITY DEFINER validation

Date: 2026-11-02 UTC

## Finding

The paired-backup procedure creates PostgreSQL archives with `pg_dump
--no-owner --no-acl`. The restore procedure also used `pg_restore --no-owner
--no-acl`, but did not transfer ownership of the slot-release
`SECURITY DEFINER` function back to `gpu_control_migrate` before applying its
ACL. Such a restore leaves the function owned by the restore administrator;
granting the worker EXECUTE would then run the function with that
administrator's authority.

## Remediation

- `database-runtime-roles-ownership.sql` now transfers the slot-release
  function to `gpu_control_migrate` alongside the allowlisted Gateway tables.
- The isolated restore procedure provisions cluster-global roles, restores the
  archive, transfers table/function ownership as the restore DBA, and applies
  `database-runtime-roles.sql` as the migration login before application use.
- A PostgreSQL regression emulates the no-owner restore owner change, proves
  the ownership transfer, reapplies the ACL, and checks worker EXECUTE and
  absence of PUBLIC EXECUTE.

## Verification

- PostgreSQL 16 disposable role suite: **3 passed** on Python 3.12.13.
- Full Gateway suite after the change, with PostgreSQL role and outage tests,
  Docker CPU integrations and the digest-pinned CPU fixture: **365 passed,
  1 skipped**, one existing Starlette deprecation warning, 23.39 seconds.
- A separate manual paired-restore drill then used the pinned PostgreSQL 16
  image to generate and verify a real schema-v9 backup generation, restore its
  `--no-owner --no-acl` dump into a second empty database, apply the ownership
  transfer as the restore administrator, and reapply runtime ACLs as
  `gpu_control_migrate`.
- The restored slot-release function owner was `gpu_control_migrate`; Worker
  EXECUTE was present and PUBLIC EXECUTE absent. A synthetic OAuth refresh
  token retained `grant_id=restore-grant` and `revoked=false`. The restored
  terminal run retained its artifact manifest; extracting the paired archive
  and reading through `ArtifactStore.get` returned the exact payload with
  SHA-256 `eab3df963d3d8efe049db05ce08db97cc1d78162be1e7869ae1d695c5c0d121f`.
- `backup_generation.verify_generation` reported schema version 9 and verified
  both archive digests. Source and target were separate databases in the same
  disposable PostgreSQL cluster, so runtime role identities were cluster-wide.
- `git diff --check` and staged diff checks passed.
- The PostgreSQL test and restore containers, temporary backup generation, and
  artifact directories were removed after verification.

## Schema v10 independent-cluster paired backup and restore refresh

- Repeated the paired restore against two independent disposable PostgreSQL
  16.15 clusters using the repository-pinned image digest. Both clusters used
  ephemeral container storage; the only published ports were bound to
  `127.0.0.1`. No persistent Docker volumes or hosted database were used.
- Initialized the source at the current schema v10 with the three restricted
  runtime roles. Seeded synthetic v10 login-throttle bucket/budget rows, an
  OAuth client, live and revoked refresh-token grant state, one terminal CPU
  run, and its owner-scoped result artifact.
- Ran the actual `backup_generation.create_generation` and
  `verify_generation` implementation. PostgreSQL client commands were bridged
  into the source container because the macOS host has no `pg_dump`/`psql`/
  `pg_restore`; the backup helper's systemd stopped-state attestation was
  injected because the host has no Gateway systemd units.
- Restored the dump into the second, separately initialized cluster with
  `--no-owner --no-acl`, applied
  `database-runtime-roles-ownership.sql` as the restore administrator, then
  reapplied `database-runtime-roles.sql` through the `gpu_control_migrate`
  login. All 12 `gateway_*` table row counts matched and the restored schema
  version was 10.
- The v10 login source bucket retained `attempts=3`; the global login budget
  retained its synthetic remaining-token value; OAuth grants retained
  `restore-grant-v10:false` and `revoked-grant-v10:true`. No raw token was
  stored in the acceptance output.
- The restored slot-release function owner was `gpu_control_migrate`; Worker
  EXECUTE was present, PUBLIC EXECUTE absent, and the API/Worker table privilege
  probe returned `true|false|true` for API run insert, Worker OAuth-token read,
  and API OAuth-token read. No runtime role memberships existed.
- Extracting the artifact archive and reading the blob through `ArtifactStore`
  returned the exact synthetic payload. Its SHA-256 was
  `4f60415fed5cd1f0da0615744b971a689fcb2efa77ac92c1107da91d9367b389`.
  Backup generation took 0.563 seconds and restore plus local checks took
  0.154 seconds after both databases were already available. These are local
  procedure timings, not measured RPO/RTO.
- Temporary databases, containers, backup files, and artifact directories
  were removed. The prior schema-v9 drill remains historical evidence; this
  refresh extends local synthetic restore evidence to v10 and independent
  clusters.

## Limits

The manual drills' systemd stopped-state attestation was injected by the
disposable harness because the macOS host has no installed Gateway systemd
units; neither revalidates that live gate. Production/Preview restore,
secret-manager credentials, target-host database-owner configuration,
second-operator reproduction, and measured RPO/RTO remain unverified. The
synthetic local drill is not completion of P3 operational acceptance.
