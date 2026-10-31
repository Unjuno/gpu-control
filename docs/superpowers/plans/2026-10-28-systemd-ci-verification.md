# Continuous verification for Gateway systemd units

## Goal

Run `systemd-analyze verify` against all current Gateway service units and the
capacity timer in pull-request CI. Keep provider integrations parked and do not
start services or use credentials.

## Task 1: Add a CI-only systemd template verification step

### Changes

- Add a CI helper that checks for `systemd-analyze`, creates the service users,
  groups, environment-file placeholders, working directories, and executable
  placeholders required by `verify`, installs the six unit templates into the
  ephemeral runner, and runs `systemd-analyze verify` on all six.
- Call the helper from `.github/workflows/gateway-ci.yml`.
- Add a regression test that fails unless the CI workflow invokes the helper
  and the helper verifies every service and timer template.

### TDD and verification

1. Add the regression test and run it; expected result: failure because the CI
   workflow does not yet invoke the helper.
2. Add the helper and workflow step; expected result: regression passes.
3. Run the helper in the isolated Debian 12/systemd 252.39 container and run
   the full Gateway pytest suite; expected result: unit verification passes and
   all Gateway tests pass.
4. Run `git diff --check`.

The CI runner is ephemeral; the helper must not be documented as a production
installer and must not run a service, migration, network client, or provider.

## 2026-10-28 follow-up: manual capacity journal bridge unit

Added `gpu-control-capacity-bridge.service` to the CI helper's unit inventory.
The manual-only oneshot runs the explicit-bootstrap/poll-once CLI under a
dedicated UID, grants `systemd-journal` read access, uses a private
`StateDirectory`, and has no network or credential environment. No timer is
installed while delivery has no selected sink. CI inventory now verifies seven
unit files (six prior service/timer templates plus this bridge service). The
new template has static regression coverage and passed the helper in the
cached Debian 12/systemd 252.39 image with `--rm --network none` and a read-only
repository mount. GitHub Actions for the uncommitted diff and target-host
startup remain outstanding.
