# Container Verification Security Boundary

Container verification is the next major execution boundary in `gpu-control`.

Reading a public repository is not equivalent to building or running it. A Dockerfile can execute arbitrary commands during `RUN` instructions, access the network, consume resources, and attempt to attack the build or runtime environment. Therefore generic container verification must be treated as untrusted code execution.

## Current status

A repository-owned fixture at `examples/reference-workload/` is built and run in CI under restricted settings. This validates the mechanics of a bounded container smoke test without trusting arbitrary external Dockerfiles.

Generic external container build/run remains **denied** until the isolation requirements in `policies/container-verification-policy.yaml` are implemented and tested against hostile workloads.

Source verification remains read-only. The manual dry-run workflow does not execute target workload code.

## Trusted reference fixture

The trusted fixture is deliberately narrower than the future generic verifier:

- its source is part of this repository and reviewed with the control plane;
- it has no third-party Python dependencies;
- its Docker base image is pinned by digest;
- it performs a deterministic finite calculation;
- it writes a machine-readable `/outputs/result.json`;
- it requires no GPU, network, token, provider account, or secret.

CI runs it with a read-only root filesystem, `--network none`, all Linux capabilities dropped, `no-new-privileges`, PID/CPU/memory limits, a hard external timeout, and bounded tmpfs mounts. CI also inspects the created container and asserts the key runtime restrictions rather than relying only on the workflow text.

Passing this fixture proves the isolation mechanism works for repository-owned code. It does **not** establish that arbitrary hostile Dockerfiles are safe.

## Trust model

A workload repository may be public and still be malicious. Repository visibility, a valid commit SHA, and a valid Dockerfile path prove identity and reproducibility; they do not establish trustworthiness.

Container verification must therefore assume:

- Dockerfile instructions are hostile;
- the image entrypoint is hostile;
- build dependencies may be hostile;
- network endpoints contacted by the build may be hostile;
- generated files and logs may contain hostile or oversized content.

## Required separation

Container verification must run in a separate execution boundary from control-plane jobs that can access provider credentials or other secrets.

The verification environment must not receive:

- `RUNPOD_API_KEY` or any provider credential;
- repository write tokens;
- private dataset credentials;
- cloud credentials;
- SSH agents or SSH keys;
- package registry credentials unless a future policy explicitly designs for them;
- reusable host credentials.

A GitHub token used earlier for read-only source verification must not be forwarded into the workload build or runtime environment. GitHub checkout credentials should not be persisted when they are unnecessary.

## Source requirements

Before generic container execution:

1. `target_repo` must pass the public source policy;
2. `target_sha` must be an immutable full commit SHA;
3. the exact commit must be verified in the repository;
4. the Dockerfile must be verified at that exact commit;
5. checkout must use that exact SHA, never a branch or tag;
6. submodules are disabled by default;
7. no additional unpinned repository checkout is allowed implicitly.

## Build isolation requirements

The build stage must be ephemeral and bounded.

Minimum requirements:

- a fresh disposable worker for the verification job;
- no provider secrets or reusable credentials;
- no host Docker socket shared from a persistent control-plane host;
- no privileged mode;
- no host filesystem mounts;
- no host network mode;
- no SSH forwarding;
- no BuildKit secret mounts unless a later explicit policy permits them;
- a hard workflow timeout;
- bounded disk usage where the execution environment supports it;
- no cache reuse across unrelated untrusted workload repositories unless the cache design is explicitly hardened.

Build-time network access is a separate policy decision because many legitimate Dockerfiles install dependencies during build. If build networking is allowed, it must still run without secrets and within a bounded disposable environment.

The current trusted fixture has no Dockerfile `RUN` step, so it does not yet exercise hostile build-time behavior. That is intentionally left for the hostile-build test milestone.

## Runtime isolation requirements

The default smoke-test runtime should be stricter than the build stage:

- no GPU;
- no provider credentials;
- no GitHub token;
- `--network none` by default;
- read-only root filesystem where practical;
- all Linux capabilities dropped;
- `no-new-privileges` enabled;
- no host PID/IPC/network namespaces;
- no Docker socket;
- no host device mounts;
- bounded CPU, memory, process count, and wall-clock time;
- only a dedicated bounded output location may be writable;
- no interactive TTY or SSH service.

A workload that requires broader privileges does not silently receive them. It requires a separate policy decision.

## Output handling

Container output is untrusted.

The control plane must bound and sanitize what it retains:

- cap log size;
- cap artifact/output size;
- do not interpret generated shell code;
- do not automatically execute generated files;
- do not publish secrets detected in output;
- keep machine-readable exit status separate from free-form logs.

The trusted fixture currently validates a small JSON result. Generic artifact ingestion is not enabled.

## Authorization

A request to verify source does not authorize executing the container.

Generic container execution should require an explicit trusted action from a repository writer or another authenticated control path. Public users, forks, issues, comments, and pull-request content must not be able to trigger generic workload execution.

The repository-owned reference fixture is part of ordinary CI and is not a general target-repository execution interface.

Container verification is still non-billable provider work, but it is a code-execution boundary and therefore needs explicit authorization before it is generalized.

## Relationship to paid compute

A successful isolated container verification result becomes one input to `ApprovedExecutionPlan` generation. It is not itself authorization to allocate a GPU.

The paid-compute gate still requires:

- successful source verification;
- successful isolated container verification;
- successful dry-run;
- verified provider price;
- runtime and cost bounds;
- cleanup guarantee;
- explicit human authorization for paid compute.

## Implementation sequence

The intended implementation sequence is:

1. keep generic external container execution denied — **done**;
2. add a repository-owned trusted reference workload — **done**;
3. run that reference workload in bounded, secret-free CI isolation — **done**;
4. publish the reference workload as a separate public repository;
5. add hostile build, hostile runtime, secret-isolation, and resource-limit tests;
6. only then generalize to explicitly authorized public workload repositories;
7. keep paid provider credentials in a later, separate job/stage.

Do not collapse container verification and paid provider submission into one credential-bearing workflow job.
