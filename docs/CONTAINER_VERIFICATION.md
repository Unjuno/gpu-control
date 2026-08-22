# Container Verification Security Boundary

Container verification is the next major execution boundary in `gpu-control`.

Reading a public repository is not equivalent to building or running it. A Dockerfile can execute arbitrary commands during `RUN` instructions, access the network, consume resources, and attempt to attack the build or runtime environment. Therefore generic container verification must be treated as untrusted code execution.

## Current status

Generic remote container build/run is **denied** until the isolation requirements in `policies/container-verification-policy.yaml` are implemented and tested.

Source verification remains read-only. No workload code is executed by the existing dry-run workflow.

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

A GitHub token used earlier for read-only source verification must not be forwarded into the workload build or runtime environment.

## Source requirements

Before container execution:

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

## Authorization

A request to verify source does not authorize executing the container.

Container execution should require an explicit trusted action from a repository writer or another authenticated control path. Public users, forks, issues, comments, and pull-request content must not be able to trigger generic workload execution.

Container verification is still non-billable provider work, but it is a code-execution boundary and therefore needs explicit authorization.

## Relationship to paid compute

A successful container verification result becomes one input to `ApprovedExecutionPlan` generation. It is not itself authorization to allocate a GPU.

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

1. keep generic container execution denied;
2. publish a minimal reference workload repository;
3. implement an isolated, secret-free build path for that reference workload;
4. add bounded offline runtime smoke testing;
5. test hostile Dockerfile and runtime cases;
6. only then generalize to authorized public workload repositories;
7. keep paid provider credentials in a later, separate job/stage.

Do not collapse container verification and paid provider submission into one credential-bearing workflow job.
