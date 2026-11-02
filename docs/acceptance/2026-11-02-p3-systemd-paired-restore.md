# P3 systemd paired backup and restore rehearsal

Date: 2026-11-02 UTC

## Scope and environment

This rehearsal exercised the current candidate's installed Linux systemd units,
quiesced backup-generation gate, independent PostgreSQL restore, artifact
archive restore, and authenticated MCP result retrieval. It used synthetic
data only and left local CPU admission, external providers, GPU, and paid
execution disabled.

- Dedicated OrbStack machine `gpu-control-p3-restore-20261102`, Ubuntu 24.04.5
  arm64, created with host/file integration disabled, network isolation,
  no SSH-agent forwarding, 2 CPUs, 6 GiB memory, and a configured 16 GiB disk
  limit. The guest ran systemd as PID 1; `systemd-detect-virt` identified its
  container guest context as LXC, so this is isolated guest evidence rather
  than a production VM/host certification.
- Candidate application code was checked out clean at PR #66 candidate HEAD
  `ee136730dc8b9dd8a6abf1669f386619c0f4c0c1`. For the service-permission
  experiment, the five systemd unit files from the current working-tree patch
  were copied into the guest and installed; the guest was not a pristine
  execution of the earlier commit's service templates.
- PostgreSQL 16.15 source cluster on port 5432 and a separately initialized
  empty PostgreSQL 16 target cluster on port 5433.

## Procedure and results

- Installed the candidate systemd units and real API, worker, and supervisor
  processes. The first service start exposed `/etc/gpu-control` traversal
  failure for their service identities. A dedicated read-only
  `gpu-control-config` supplementary group was applied to the affected units;
  the directory was root-owned `0750`, nonsecret registry/policy files were
  root-owned `0640`, and EnvironmentFiles remained root-owned `0600`.
- Seeded one synthetic terminal result and owner-scoped artifact in schema v10.
  With the services active, `backup_generation.py` exited 2 with
  `all Gateway systemd services must be loaded and inactive`.
- Stopped API, worker, supervisor, migration, capacity-monitor, timer, and
  capacity-bridge units. All seven reported `LoadState=loaded` and
  `ActiveState=inactive`. The actual `backup_generation.py` implementation
  then created and verified a paired PostgreSQL/artifact generation. The
  manifest recorded schema 10, one run, one artifact-bearing run, and the
  complete seven-unit inactive attestation.
- Restored the no-owner/no-ACL database dump to the independent empty target
  cluster. Provisioned fresh cluster-global runtime roles, transferred
  ownership to `gpu_control_migrate`, and reapplied the runtime ACL script as
  that login. The restored SECURITY DEFINER function owner was
  `gpu_control_migrate`; `PUBLIC EXECUTE=false` and worker `EXECUTE=true`.
- Extracted the artifact archive to a separate restored artifact directory.
  Pointed actual API, worker, and supervisor systemd units to the restored
  database and artifact directory. All three became active and `/readyz`
  returned HTTP 200 with `ready=true`.
- Used the original synthetic owner's OAuth access token against the restored
  API's `/mcp` endpoint. `experiment_result` returned HTTP 200 and state
  `succeeded`. `experiment_artifact` returned all 46 bytes; SHA-256
  `44ef8040e7293a0e9539ffd033a01215e8774aec1e59db008079710207e5a078` matched
  both the restored manifest and backup-generation record. A second synthetic
  owner received a tool-level `not_found` with no result body from the restored
  API.

## Verification

- `gateway/tests/test_deploy_units.py`: 16 passed.
- Gateway CI-equivalent suite with the digest-addressed local CPU image and a
  dedicated PostgreSQL 16 test container: 380 passed, 1 skipped. The first
  attempt used the default test source SHA instead of the image's embedded
  candidate SHA and failed the image provenance assertions; rerunning with the
  workflow's explicit repository/SHA environment passed.
- `systemd-analyze verify` passed for the installed units in the guest.
- The independent read-only Security Review reported no actionable findings
  in the uncommitted service/config-permission patch.

## Limits

This proves the local systemd path and synthetic paired restore in this
isolated OrbStack guest. It does not prove the selected target host, durable
production backup storage/retention, deployed OAuth issuer, ChatGPT account
integration, operator reproduction, measured RPO/RTO, or provider execution.
The machine used a guest/container systemd environment, and its guest context
was reported as LXC. No GPU or paid provider was enabled or contacted.
