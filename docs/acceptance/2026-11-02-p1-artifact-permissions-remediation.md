# P1 artifact permission remediation

Status: **PR CI PASSED; TARGET-HOST AND CHATGPT ACCEPTANCE NOT RUN**.

Target: draft PR #66, source HEAD `2098ab25056ca33f74577b301fa4692af0a1bca7`.
The permission remediation is in `dbef0d4`; its test-fixture follow-up is
`0bdcd969889d35fdd8bc767181a6784e8e12efea`.

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
- Full Gateway suite without its optional Docker/PostgreSQL integration
  environment: **365 passed, 15 skipped**, one Starlette deprecation warning.
- CI-equivalent full Gateway suite with a disposable PostgreSQL 16 container
  and digest-pinned CPU smoke image: **379 passed, 1 skipped**, one Starlette
  deprecation warning. The authenticated MCP CPU execution and cross-client
  artifact retrieval test passed **1/1**.
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
- The first GitHub CI run for commit `dbef0d4` caught a missing probe directory
  in the real MCP integration test fixture (`probe_not_directory`). The fixture
  now provisions that directory. The same test and the configured full suite
  pass locally; all GitHub checks pass on follow-up commit `0bdcd96`, including
  the real Docker/PostgreSQL Gateway workflow.

## Limits

This is not target-host systemd, filesystem ACL, mount-loss, ChatGPT, or hosted
deployment acceptance. The recovery review's operational findings remain open.
PR #66 remains draft with no GitHub review decision. Keep provider and
paid-execution modes parked.
