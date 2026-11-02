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

## Limits

The manual drill's systemd stopped-state attestation was injected by the
disposable harness because the macOS host has no installed Gateway systemd
units; it does not revalidate that live gate. Production/Preview restore,
secret-manager credentials, target-host database-owner configuration,
second-operator reproduction, and measured RPO/RTO remain unverified. The
synthetic local drill is not completion of P3 operational acceptance.
