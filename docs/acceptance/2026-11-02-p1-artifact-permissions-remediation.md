# P1 artifact permission remediation

Status: **LOCAL CANDIDATE VERIFIED; HOSTED ACCEPTANCE NOT RUN**.

Target: draft PR #66, source HEAD `2098ab25056ca33f74577b301fa4692af0a1bca7`.
The remediation is an uncommitted worktree diff based on that HEAD.

## Finding and change

An independent provider-independent recovery review found that the documented
separate service identities could not use artifact storage: API readiness
required root write permission, while the worker reset the root and run scopes
to `0700` and created blobs as `0600`. This prevented the API UID from reading
worker results and could mask the capacity-probe ACL.

The candidate now checks API read/search permission on the root and performs an
exclusive create/delete probe only in `.gpu-control-probes`. Worker readiness
continues to require root write access. ArtifactStore creates newly provisioned
roots and scopes as `02750`, creates blobs as `0640` despite `UMask=0077`, and
does not chmod an existing root. It also fails closed when the configured root
or its parent has not been provisioned, rather than creating worker-private
ancestor directories.

## Validation

- Focused artifact, deploy-unit, owner-migration, backup, experiment API, and
  HTTP auth tests: **124 passed**, one Starlette deprecation warning.
- Full Gateway suite: **365 passed, 15 skipped**, one Starlette deprecation
  warning.
- `git diff --check`: passed.
- Linux container check against the patched source, with worker UID `10001`,
  API UID `10002`, shared artifact GID `20000`, probe GID `20001`, and worker
  `umask(0077)`: worker wrote a result with scope mode `02750` and blob mode
  `0640`; API readiness and byte-for-byte `ArtifactStore.get` succeeded; API
  root write access was false; API probe create/delete succeeded. The temporary
  Docker volume was removed after the check.
- A read-only review of this candidate identified implicit creation of missing
  parent directories as a remaining access failure. The code now requires the
  artifact root's parent to be provisioned and has a regression test for that
  behavior. No second review of this final small adjustment was run.

## Limits

This is not target-host systemd, filesystem ACL, mount-loss, ChatGPT, or hosted
deployment acceptance. The recovery review's operational findings remain open.
The candidate has not been committed or pushed, and GitHub checks have not run
against this diff. Keep provider and paid-execution modes parked.
