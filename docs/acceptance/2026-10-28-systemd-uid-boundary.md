# systemd unit and artifact UID boundary validation — 2026-10-28

## Environment

- Disposable Debian 12 container image: `sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`.
- `systemd-analyze` reports systemd **252.39**.
- Container ran with `--network none`; repository deployment files were mounted read-only for unit verification. The container was removed on exit.

## systemd template validation

Created placeholder service users/groups, environment files, working directories,
and executable paths, then ran `systemd-analyze verify` over the five service
units and capacity timer:

```sh
systemd-analyze verify \
  /units/gpu-control-db-migrate.service \
  /units/gpu-control-api.service \
  /units/gpu-control-worker.service \
  /units/gpu-control-supervisor.service \
  /units/gpu-control-artifact-capacity.service \
  /units/gpu-control-artifact-capacity.timer
```

Result: exit status 0, no diagnostics. This verifies systemd syntax and unit
relationships against systemd 252. It does not start a unit or validate actual
mount activation, network, restart behavior, or service environment contents.

## Linux filesystem permission behavior

Created the four service identities/groups in the same disposable Debian
environment and prepared the artifact root as worker-owned `02750`, a blob as
worker-owned `0640`, and `.gpu-control-probes` as worker-owned,
`gpu-control-artifact-probes` group, `03770`. Results:

- API read the blob and created/removed its own probe; API could not create a
  file in the artifact root or modify the blob.
- The capacity identity could read the blob but could not create a probe. This
  is the intended permission boundary: `check_artifact_capacity.py` only checks
  filesystem identity and free bytes with `statvfs`; API readiness calls
  `inspect_artifact_storage()` for the create/write/fsync/unlink probe.
- Worker created an artifact-scope file.
- Migration identity could not read the artifact.

### Superseded capacity probe-group change

An earlier source interpretation incorrectly attributed the API readiness
probe to `check_artifact_capacity.py`. On that basis the capacity unit was
temporarily given `gpu-control-artifact-probes`; a mode-bit test correctly
showed that this granted capacity write/unlink access in `.gpu-control-probes`,
blob reads, and artifact-root write denial. The test result was accurate for
that temporary group layout, but the permission was not required by the
capacity program and widened its access unnecessarily.

The supplementary group has now been removed from capacity, worker and
supervisor units. API alone joins the probe group; worker owns the directory and
can access it through its UID. Capacity retains only primary
`gpu-control-artifacts` read access. A fresh disposable Debian 12 UID/GID
matrix then confirmed the corrected layout using actual service UIDs and groups:
API blob read and probe create/remove; capacity blob read with probe creation
denied; worker probe access as directory owner; migration blob read denied;
and API artifact-root/blob writes denied. This validates ordinary Linux
mode-bit behavior for this layout.

Earlier command output remains historical evidence for the respective layouts;
it does not validate the corrected capacity group membership, systemd's mount
namespace/read-write path filters, the actual deployment filesystem, or the
live service processes.

The migration utility itself was then mounted read-only into a fresh disposable
container. A root-owned fixture started at root/scope mode 0700 and blob mode
0600. Dry-run reported one scope and one file without changing the root mode or
creating the probe directory. `--apply` changed ownership to the test worker
and the two configured groups, set root/scope to 02750, blob to 0640, created
the 03770 probe directory, and passed exact `stat` checks. The fixture and
container were removed on exit; no user artifact tree was involved.

## Acceptance status

Local template and permission-boundary checks pass. Target-host acceptance is
still required for the mounted artifact volume, installed service identities,
`ProtectSystem`/`ReadWritePaths` behavior, boot/mount ordering, restarts, and
capacity alert delivery. No provider was enabled, no paid workload was started,
and `policies/repository-state.yaml` remains parked.

A follow-up attempt to boot systemd as PID 1 in an unprivileged disposable
container exited with status 255 and emitted no useful log output. The
diagnostic container was removed. No additional container capabilities were
granted; actual service sandbox startup therefore remains unverified.

## Additional systemd sandbox review

An offline `systemd-analyze security` pass on systemd 252 initially reported
7.6/10 `EXPOSED` for all five services. This is a heuristic over systemd
sandbox directives, not a vulnerability finding; systemd documents that a high
exposure score does not mean a service is vulnerable
([systemd-analyze security](https://www.freedesktop.org/software/systemd/man/251/systemd-analyze.html)).
Reviewed missing controls against each service's needs and added private
devices, invisible cross-UID proc visibility, PID-only proc subset, empty
capability bounding set, native syscall ABI, realtime/clock/hostname/kernel-log
protection, and address-family allowlists. The capacity monitor additionally
uses a private network namespace and AF_UNIX-only socket access; API, worker,
supervisor, and migration retain AF_UNIX/IPv4/IPv6 for proxy, PostgreSQL, and
Docker-socket communication.

After the changes, offline scores were API 3.8, worker 3.8, supervisor 3.8,
migration 3.8, and capacity 3.0 (all `OK`). These values compare the unit
directives only; they do not model Docker socket's effective host-root authority
or prove that the application continues to work under the restrictions. Full
service startup, database connectivity, HTTP proxy behavior, worker Docker
operations, and the capacity timer must pass on the target host before release.

The Gateway offline CI workflow now calls
`gateway/deploy/verify_systemd_units_ci.sh`, which is guarded to run only on a
Linux GitHub Actions runner and uses inert placeholder accounts/files to verify
all six units without starting them. The helper itself passed in the disposable
Debian 12/systemd 252.39 container. The GitHub Actions run for this unpushed
worktree change has not occurred yet.

## Current worktree verification refresh — 2026-10-28

The then-current uncommitted unit templates were rechecked in an
`--rm --network none` container based on local image
`sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`
(Debian 12, systemd 252.39). The repository was mounted read-only and
`gateway/deploy/verify_systemd_units_ci.sh` passed for all six service/timer
templates with inert account, path, executable, and empty environment-file
placeholders. No unit was started. The named disposable container was removed
automatically, and a follow-up inventory found no container with that name.

This refresh closed the template-syntax gap at that point in the worktree. A
later source audit found and removed the unnecessary capacity/worker/supervisor
probe-group membership. The current templates were revalidated below. No
service startup or systemd mount namespace permissions, the selected
host/filesystem, alert delivery, or production readiness is established. The
earlier UID/GID mode-bit probe remains a separate Linux permission-layer
result.

## Manual capacity bridge unit follow-up — 2026-10-28

After adding `gpu-control-capacity-bridge.service`, reran the repository's CI
verification helper in the already-cached Debian 12 image
`sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`
(systemd 252.39). The invocation used `--rm --network none`, mounted
`gateway/` read-only, explicitly overrode the image entrypoint to `/bin/bash`,
and set the helper's documented ephemeral Linux CI guard variables. The helper
returned exit code 0 with no diagnostics and verified all seven current unit
templates, including the new bridge service. The named containers were absent
after exit. No service started and no host journal, credential, network, or
provider was accessed. This is template syntax/reference evidence only; actual
bridge identity/journal access and target-host runtime remain unverified.

## Revalidation — 2026-10-28 05:34 UTC

Re-ran the same helper against the same locally cached Debian 12/systemd 252.39
image (`sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`)
with `--rm --network none`, a read-only `gateway/` mount, inert guard variables,
and `/bin/bash` as the entrypoint. Exit status was 0 with no diagnostics. A
post-run container inventory for that image showed no remaining containers.
The exact helper SHA-256 was
`9aec725b96eb4e1608110cc5637b76d414e313d5c403dfa6e47ab996f90beada`; the
capacity bridge unit SHA-256 was
`b4b3f2a3eb957bca84535e2f3c82a54fc3d2adcada726dec2991e6e3d0fdd3c0`.
This revalidates syntax/reference resolution for seven templates only; no
service or host state was changed.

## Current CI helper rerun — 2026-10-28

Re-ran the current helper in the cached Debian 12/systemd 252.39 image
`sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`,
with `--network none`, the repository's `gateway/` mounted read-only, inert
guard variables, and automatic container removal. Exit status was 0 with no
diagnostics. The current helper SHA-256
`9aec725b96eb4e1608110cc5637b76d414e313d5c403dfa6e47ab996f90beada` and
capacity bridge unit SHA-256
`b4b3f2a3eb957bca84535e2f3c82a54fc3d2adcada726dec2991e6e3d0fdd3c0` match the
previous recorded snapshot; this rerun confirms the current seven-unit set.
No service started. This remains template syntax/reference evidence and does
not validate the target host, sandbox mount behavior, journal permissions, or
alert delivery.

## Current-worktree continuation — 2026-10-28

Re-ran the current P3 artifact/capacity/systemd focused regression set:
`test_artifact_storage.py`, `test_backup_generation.py`,
`test_capacity_event_state.py`, `test_artifact_permission_migration.py`, and
`test_deploy_units.py` — **91 passed**, one existing Starlette deprecation
warning. Re-ran `verify_systemd_units_ci.sh` in the cached Debian 12/systemd
252.39 image (`sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`),
with `--network none`, read-only `gateway/` mount, inert CI guard variables, and
`/bin/bash` entrypoint. It exited 0 with no diagnostics for all seven units.
An initial invocation used a plain Debian base image without systemd and stopped
at the helper's required-binary preflight; no service ran and the container was
removed. The corrected run is the relevant syntax/reference result. This still
does not test target-host mounts, systemd sandbox runtime, journal access, alert
delivery, backup retention, or production recovery.

## Manual database check unit addition — 2026-10-28

Added `gpu-control-db-check.service` as a separate manual oneshot using the
restricted migration UID, the common Gateway environment file, and the same
systemd sandbox as the migration unit. It runs only the read-only `--check-db`
command. The migration unit retains a second preflight as `ExecStartPre`.

Ran `systemd-analyze verify` for all eight service/timer templates in a
disposable Debian 12 container based on image
`sha256:854dd8ab51d62866dbd8f5431d15ce77b12983a2a4a1e1fe43a2395dc7ef9f61`.
Installed systemd 252.39 only inside the container, provided inert service
account/path/environment placeholders, and mounted the repository's deploy
directory read-only. Verification exited 0 with no diagnostics. No service
was started; the container was removed. The GitHub-only helper now includes the
new unit, but this dirty worktree still has no GitHub Actions result. Host
startup, mount filtering, database reachability, and migration remain untested.

## Current P3 regression and template revalidation — 2026-10-28

- Focused local Gateway tests for artifact storage, paired backup generation,
  capacity-event state, artifact permission migration, and deploy units:
  **92 passed**, one existing Starlette deprecation warning.
- Ran `deploy/verify_systemd_units_ci.sh` inside the cached Debian 12 /
  systemd 252.39 image
  `mixed-formal-2992-debian@sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`.
  The container had `--network none`, the Gateway tree mounted read-only, and
  only the helper's inert Linux CI guard variables. Exit status was 0 with no
  diagnostics for all eight current service/timer templates. The container was
  `--rm`; a follow-up inventory found none remaining for that image.
- Two initial harness attempts stopped before `systemd-analyze verify`: one
  addressed the cached image by the wrong repository name, and one invoked the
  helper from `deploy/` even though it expects the Gateway root as its working
  directory. The corrected invocation above is the passing result; no service
  ran and no host state was changed.
- This remains local test and systemd syntax/reference evidence. It does not
  verify target-host mount filtering, installed identities, journal access,
  alert delivery, quota behavior, or production recovery.

## Current template verification — 2026-10-30

At control-plane commit `aa681f4062dac6b73bcf380a38a4258b96a47e1`, manually
reproduced the CI helper's inert placeholder setup inside the cached
`mixed-formal-2992-debian:20260920` container (Debian 12, systemd 252.39).
The container used `--network none`; only `gateway/` was mounted and it was
read-only. Placeholder service users/groups, empty environment files, and
executable paths were created in the disposable container. `systemd-analyze
verify` accepted all eight service/timer templates with exit code 0 and no
diagnostics. No unit started; the container was removed. The GitHub-Actions-
only helper was not invoked or bypassed. This is template syntax/reference
validation, not target-host startup, sandbox mount behavior, or runtime
acceptance.

## Current-worktree CI helper rerun — 2026-10-31

Re-ran `deploy/verify_systemd_units_ci.sh` against the current Gateway tree in
the cached `mixed-formal-2992-debian:20260920` image, whose image digest is
`sha256:766abfd10382ab8b59ed793094a685481190f840d338b7bc4664ca162a2da619`
(Debian 12/systemd 252.39). The container used `--network none`, mounted
`gateway/` read-only, supplied only the helper's inert Linux CI guard values,
and was automatically removed. The helper exited 0 with no diagnostics for
all eight current service/timer templates. Its SHA-256 was
`569261ffcd54de9d921d2d1361fa6deec044598e9ae4bbe3f312ed5bcf683d34`.
Post-run container inventory found no matching container. No unit started;
this is syntax/reference evidence only, not target-host runtime, mount,
permissions, journal, alert-delivery, or production recovery acceptance.
