# Trusted reference workload

This directory is a repository-owned CI fixture used to validate the container boundary without enabling arbitrary external Dockerfile execution.

It is intentionally small:

- no third-party Python dependencies;
- no GPU requirement;
- no network requirement;
- deterministic computation;
- finite non-interactive entrypoint;
- machine-readable result written to `/outputs/result.json`;
- Docker base image pinned by digest.

The CI job builds this image and runs it with a read-only root filesystem, no network, all Linux capabilities dropped, `no-new-privileges`, and explicit CPU, memory, PID, and wall-clock limits.

This fixture does **not** mean generic workload execution is enabled. `policies/container-verification-policy.yaml` keeps arbitrary external build/run denied until the isolation and hostile-workload tests required by that policy are implemented.
