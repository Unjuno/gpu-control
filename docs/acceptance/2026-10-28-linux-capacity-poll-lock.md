# Linux capacity poll lock verification — 2026-10-28

Status: **PASS for Linux cross-process `flock` behavior only**.

## Environment

- Runtime image: `python@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f`.
- The container ran with `--network none`; `gateway/deploy` was mounted
  read-only at `/work`.
- State-machine source SHA-256:
  `906e9f2c92edef8674055e45c96104031aaff4ebb1ee4152fc76b562ec2d5a58`.
- Test source SHA-256:
  `1cc3773d6e06517fdf6a29990ada7f3b5e02ddb5d271e4d7653e63050b8d318f`.

## Probe and result

The Linux container created a private temporary directory and acquired the
same poll lock used by `CapacityEventState._poll_lock()`. A child Python process
attempted a nonblocking exclusive lock on that lock file and confirmed it was
held, then waited through the production `_poll_lock()` context manager. The
parent confirmed the child had not acquired the lock, released it, and observed
the child acquire it and exit successfully. Result: `linux_process_poll_lock=PASS`.

The container used `--rm`; temporary state stayed inside the container. This
does not exercise systemd, a live journald cursor, installed service identity,
or a selected Linux host. The repository regression tests separately verify
that `JournalPoller` holds this lock across its complete read/query/apply path.

## Follow-up — lock error boundary

After the Linux probe, the context manager was tightened so only `fstat` and
`flock` acquisition errors are translated into lock-specific errors. An
`OSError` raised by the operation protected by the lock now propagates unchanged
while the descriptor is still released in `finally`. On macOS, the focused
capacity-state module passed 32 tests and the full offline Gateway suite passed
340 tests with 9 skips. The added regression injects a write `OSError`, checks
that its original error reaches the caller, and verifies a subsequent writer
can acquire the released lock.

- Follow-up state-machine source SHA-256:
  `9904841f4f95a947499803b4ef5fde363d47273d96e2b692f92c65c1f25332f7`.
- Follow-up test source SHA-256:
  `1915f103ac85ca1bf301b1093a00b78ecd7fca0772fffcede8036b57e23b7ae5`.

The Linux cross-process probe above predates this exception-boundary-only
follow-up; it verifies the unchanged lock-file and `flock` path. The follow-up
test ran on macOS and does not claim Linux execution of the new exception path.
