# Trusted reference workload

This directory is a repository-owned CI fixture used to validate the container boundary without enabling arbitrary external Dockerfile execution.

It is intentionally small:

- no third-party Python dependencies;
- no GPU requirement;
- no network requirement;
- deterministic computation;
- finite non-interactive entrypoint;
- machine-readable result written to `/outputs/result.json` and stdout;
- Docker base image pinned by digest.

The CI job builds this image and runs it with a read-only root filesystem, no network, all Linux capabilities dropped, `no-new-privileges`, and explicit CPU, memory, PID, and wall-clock limits.

The workload also probes its own runtime boundary and fails unless all of these hold:

- `GITHUB_TOKEN`, `RUNPOD_API_KEY`, and a host-only secret sentinel are absent;
- `/var/run/docker.sock` is absent;
- common NVIDIA device nodes are absent;
- an outbound TCP connection attempt fails.

CI independently inspects Docker `HostConfig` and container environment values, so the runtime checks are not accepted solely on the workload's own report.

This fixture does **not** mean generic workload execution is enabled. `policies/container-verification-policy.yaml` keeps arbitrary external build/run denied until the isolation and hostile-workload tests required by that policy are implemented.
