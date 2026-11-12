# Runner environment inheritance finding — 2026-11-12

## Observation

A read-only inspection of the live macOS LaunchAgent showed the runner process
inherits `SSH_AUTH_SOCK` from the user's launchd session. The fixed workload
container receives a deliberately bounded environment, but the host-side Runner
process had not cleared unrelated inherited variables before loading its
Keychain credentials. An inherited proxy or Docker endpoint could also alter
how the Runner reaches Sites or Docker if one were present.

The active process, plist, and installed launcher were not changed or restarted.
The current active Site remained Version 15 during this review. The running
`run.py` and Keychain launcher are mode `0600` and byte-identical to the current
checkout; the plist is mode `0600` and passes `plutil -lint`. This confirms
source integrity and file permissions, not that the inherited agent socket was
unavailable to the Runner.

## Candidate mitigation

`runner/macos_keychain_launcher.py` now reduces the process environment to an
explicit allowlist before loading secrets. This drops `SSH_AUTH_SOCK`,
`SSH_AGENT_PID`, proxy variables, Docker endpoint overrides, Python path hooks,
and any environment-provided credentials. The allowlist retains only the fixed
Site and workload settings, `PATH`, and the pinned user home/locale from the
LaunchAgent plist. Keychain bearer values remain in process memory, never in the
environment.

Local regression coverage passes: 24 Runner tests, including poisoned
`SSH_AUTH_SOCK`, proxy, Docker-host, `PYTHONPATH`, and environment-token cases;
30 Sites Worker/D1 tests also pass. This is candidate code evidence only.

## Rollout gate

- [ ] Reconcile the local Site source checkout with the source branch behind the
  deployed Version 15 before publishing. The local source branch is behind its
  recorded `sites/main` reference and has unrelated uncommitted Site changes;
  do not push or publish this checkout as-is.
- [ ] Publish a reviewed source version, close free CPU admission during the
  Runner replacement, install the sanitized launcher and plist, restart through
  launchd, verify the live heartbeat and successful zero-cost inference, and
  confirm the running process has no SSH-agent/proxy/Docker endpoint variables.
- [ ] Reopen free CPU admission only after the checks above pass. Paid providers
  remain parked.
