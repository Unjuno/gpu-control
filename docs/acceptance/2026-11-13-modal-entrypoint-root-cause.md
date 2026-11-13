# Modal Sandbox command override root cause — 2026-11-13

## Finding

The observed Modal failure (`MODAL_WORKLOAD_EXIT_2`, cleanup confirmed, no
diagnostic marker) is explained by the current container command configuration.
`modal.Sandbox.create(*SANDBOX_ENTRYPOINT, ...)` supplies the Sandbox command,
which Modal documents as overriding the image's `CMD`. It does not replace an
image `ENTRYPOINT`. The workload Dockerfile used an `ENTRYPOINT` that invoked
`/work/inference.py` directly, so the bootstrap command that drops privileges
and records preflight diagnostics was not guaranteed to run. Modal documents
that it runs containers as UID 0 and ignores Dockerfile `USER`; the inference
guard therefore returns exit 2 at `os.getuid() != 10001` when started directly.

Evidence:

- [Modal Python Sandbox SDK](https://modal.com/docs/sdk/py/latest/Sandbox):
  positional command arguments set Sandbox `CMD`, overriding image `CMD`.
- [Modal existing-image guide](https://modal.com/docs/guide/existing-images):
  Modal ignores Dockerfile `USER` and launches containers as root.
- Local source: `modal/app.py` passes `*SANDBOX_ENTRYPOINT`; the workload's
  non-root guard rejects any UID other than 10001; the old Dockerfile declared
  the inference script as `ENTRYPOINT`.
- The Modal dashboard returned “No logs found” for Sandbox
  `sb-01M77ZZRFC1090CXA2W3MHDH7V`, matching the missing bootstrap diagnostic.

This is a high-confidence source-to-runtime explanation, not yet a live
confirmation from a fixed Sandbox run.

## Source correction

The workload Dockerfile now declares the direct inference invocation as
`CMD`, leaving the Modal Sandbox command free to override it with the fixed
bootstrap wrapper. The image fingerprint names both the default image command
and the effective Sandbox command. That wrapper drops groups and UID/GID to
10001, runs the pinned inference file, and maps known guard returns to bounded
diagnostics.

## Validation and remaining acceptance

- Focused Modal bootstrap tests and Sites Worker tests passed locally.
- This correction has not been deployed to Modal or ChatGPT Sites. No Sandbox
  was launched, and production admission remains disabled.
- The workload OCI digest and Modal image fingerprint must be rebuilt and
  compared with the health response before the Sites registry/environment can
  accept the new image. The refreshed values must then be bound to the D1 plan
  and ChatGPT `experiment_prepare` contract.
- A fresh exact-run authorization is required before a live test. Verify the
  returned diagnostic if it fails, inference result and artifact digest if it
  succeeds, and Modal cleanup in either case.

The change does not establish repository-wide P0 security, ChatGPT browser
confirmation, Sites identity-header spoof resistance, RunPod GPU execution,
paid execution safety, or long-term recovery acceptance.
