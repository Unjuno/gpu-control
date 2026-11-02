# P3 runtime installation on isolated Linux

Date: 2026-11-02 UTC

## Scope

This rehearsal checks the locked runtime installation path used before a
deployment. It does not start the Gateway, migrate a production database, enable
CPU admission, or establish ChatGPT or target-host acceptance.

## Environment

- OrbStack machine `gpu-control-p3-restore-20261102`, Ubuntu 24.04.5 arm64.
- Created as an isolated machine with host/file integration disabled, network
  isolation enabled, no SSH-agent forwarding, 2 CPU, 6 GiB memory, and a 16 GiB
  configured disk limit. The machine's `systemd` is PID 1.
- The candidate source was cloned from the public PR branch at exact HEAD
  `ee136730dc8b9dd8a6abf1669f386619c0f4c0c1` and installed root-owned under
  `/opt/gpu-control`; the checkout was clean.
- Python 3.12.3, uv 0.10.0, and the repository's pinned root `uv.lock` were used.

## Finding and correction

The first installation rehearsal followed the runbook command without
`--all-packages`:

```sh
UV_PROJECT_ENVIRONMENT=/opt/gpu-control/venv \
  uv sync --project /opt/gpu-control/gateway --locked --no-dev --python 3.12
```

That installed `gpu-control-gateway` but not the workspace root package
`gpu-control`. The runbook's required import check then failed with
`ModuleNotFoundError: No module named 'gpu_control'`. The Gateway runtime imports
`gpu_control.selection` and `gpu_control.workloads`, so the initial command
would not produce a runnable installation.

The corrected command adds `--all-packages`, matching the already passing
Gateway CI installation check:

```sh
UV_PROJECT_ENVIRONMENT=/opt/gpu-control/venv \
  uv sync --project /opt/gpu-control/gateway --all-packages --locked \
  --no-dev --python 3.12
```

The rerun installed both workspace packages. Imports resolved to
`/opt/gpu-control/src/gpu_control/__init__.py` and
`/opt/gpu-control/gateway/gpu_gateway/__init__.py`. The lockfile SHA-256 was
`4ae724ba2e1cf72e9c98d121d0fe5aaf372153523b7d5d6f35efdd72b840e4c6`; `git
status --porcelain` was empty.

The runbook now syncs all workspace packages and hashes the root
`/opt/gpu-control/uv.lock`. `gateway/README.md` was corrected to identify that
same lockfile.

## Limits

No Gateway systemd service, database migration, artifact mount, backup gate,
restore, or API result retrieval was exercised in this installation check. The
source was an unreviewed PR candidate in a disposable isolated machine, not an
approved release. It does not complete P3 operational acceptance.
