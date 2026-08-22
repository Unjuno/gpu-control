# gpu-control

`gpu-control` is a public, local-first control plane for reproducible containerized GPU experiments.

It is designed to make escalation deliberate rather than sending every experiment directly to paid GPU infrastructure:

```text
inspect
  -> local container
  -> smallest useful experiment
  -> workload repository + immutable commit
  -> policy + source verification
  -> isolated container verification
  -> approved execution plan
  -> RunPod only when GPU compute is actually required
```

> **Current status:** local validation, public GitHub source verification, a repository-owned trusted container smoke test, dry-run workflows, structured container-verification evidence, and the provider-agnostic paid-execution gate are implemented. Generic external Dockerfile execution and provider adapters remain disabled, so no paid GPU resource can be created.

## Operating rule

Use the cheapest, smallest, most local execution environment that can answer the current question. Paid compute is an escalation stage, not the default development loop.

Repository access is not authorization to spend money. Agents operating in this repository must follow [AGENTS.md](AGENTS.md), and paid compute is denied by default in [policies/agent-policy.yaml](policies/agent-policy.yaml).

The intended sequence is:

1. Test the workload locally in a container.
2. Reduce it to the smallest useful experiment.
3. Put the workload in a separate repository with reproducible dependencies.
4. Identify the workload by an immutable 40-character commit SHA.
5. Validate policy and verify the repository, exact commit, and Dockerfile.
6. Verify the container itself in an appropriate isolation boundary and produce structured evidence tied to the exact workload identity and image digest.
7. Produce an immutable `ApprovedExecutionPlan` only after source, container, dry-run, pricing, cleanup, policy, and explicit-human-authorization gates pass.
8. Allow a provider adapter to consume that approved plan; never pass it a raw workload request.
9. Escalate to RunPod only when GPU compute is actually required.

See [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) for the detailed rationale.

## Quick start

Requirements:

- Python 3.11+
- `uv`

```bash
git clone https://github.com/Unjuno/gpu-control.git
cd gpu-control
uv sync --locked --extra dev
uv run gpu-control self-test
uv run pytest
```

`self-test` is offline and requires no GPU, provider account, or GitHub token.

## Validate a request offline

`validate` checks syntax and resource policy only. It performs no network or provider calls.

```bash
uv run gpu-control validate \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --dockerfile-path Dockerfile \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

A successful result contains `status: valid` and `dry_run: true`.

`max_cost_usd` accepts at most two decimal places. Values requiring implicit rounding are rejected.

## Verify a public GitHub workload

`verify-source` runs the same request and policy validation, then verifies through the GitHub API that:

- the repository exists and is public;
- the requested full SHA resolves to that exact commit;
- `dockerfile_path` resolves to a file at that commit.

```bash
uv run gpu-control verify-source \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --dockerfile-path Dockerfile \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

The command can use `GITHUB_TOKEN` when present to improve GitHub API reliability and rate limits. The current MVP still rejects private repositories even if a token could access them.

A successful result contains `status: verified` and remains `dry_run: true`. Source verification is read-only and does not execute workload code.

## Trusted container smoke test

`examples/reference-workload/` is a repository-owned fixture used to exercise the container boundary without enabling arbitrary external Dockerfiles.

CI builds and runs that fixture with:

- no network;
- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- no GPU or provider credential;
- explicit CPU, memory, PID, and wall-clock limits;
- a bounded writable `/outputs` tmpfs.

The fixture writes `/outputs/result.json` during execution and emits the same machine-readable result on stdout; CI validates the stdout result because the tmpfs is intentionally ephemeral after container exit. The Docker base image is pinned by digest.

This is intentionally **not** generic workload execution. `policies/container-verification-policy.yaml` keeps external build/run denied until hostile workload, secret-isolation, and resource-limit tests are complete.

## Structured container evidence

`src/gpu_control/container.py` defines `ContainerVerificationResult`. Paid-compute code does not accept a bare `container_verified=True` flag.

Container evidence must be tied to:

- the exact repository;
- the exact commit SHA;
- the exact Dockerfile path;
- an immutable lowercase `sha256:` image digest;
- a non-empty verification/audit reference.

It also records whether build isolation, runtime isolation, smoke testing, output-contract checks, credential isolation, network policy, and resource limits all passed. The paid gate rejects partial evidence and rejects evidence whose repository/SHA/Dockerfile identity does not match the verified source.

## Paid execution gate

`src/gpu_control/execution.py` defines the boundary future provider adapters must use.

A raw `WorkloadRequest` is not sufficient to allocate resources. `build_approved_execution_plan(...)` requires:

- exact source verification matching the request;
- a structured `ContainerVerificationResult` matching the same workload identity;
- an immutable container image digest and verification reference;
- all required container isolation checks to have passed;
- a successful dry-run;
- verified provider hourly pricing;
- policy-compliant runtime and cost limits;
- one GPU in the current MVP;
- a cleanup guarantee;
- explicit human authorization plus an audit reference.

Worst-case spend is calculated from the verified hourly price and requested runtime, then rounded **up** to the nearest cent before comparison with the requested cost ceiling.

The resulting `ApprovedExecutionPlan` is immutable and carries the verified image digest and container-verification reference forward to the provider boundary. This is a defense-in-depth gate, not an identity provider: the trusted workflow or caller must establish that the authorization and verification evidence actually came from trusted stages.

There is intentionally no public CLI command that manufactures an approved paid plan yet. A trusted authorization path must exist first.

## Workload contract

The baseline workload contract is intentionally narrow:

```text
public repository
+ immutable full commit SHA
+ Dockerfile
+ locked/reproducible dependencies where applicable
+ finite non-interactive container entrypoint
+ meaningful process exit code
```

The container should start, perform a bounded experiment, write outputs, and exit. Interactive SSH sessions and arbitrary remote shell commands are not the default execution model.

## GitHub Actions

Two workflows are included:

- **CI** — tests the locked Python environment on 3.11, 3.12, and 3.13 using `ubuntu-24.04`, and separately runs the trusted reference container under restricted settings.
- **GPU request dry-run** — manually validates policy and verifies the public workload repository, exact commit, and Dockerfile without creating GPU resources.

Checkout credentials are not persisted. Workflows use minimal permissions and pin third-party Actions to immutable commit SHAs.

Paid compute must never be triggered directly by untrusted pull requests, forks, issues, comments, or public webhooks.

## Repository context and policy

This repository is intended to be useful as execution context for both humans and automation agents:

- [AGENTS.md](AGENTS.md) — normative agent operating rules;
- [policies/agent-policy.yaml](policies/agent-policy.yaml) — machine-readable escalation policy;
- [policies/gpu-policy.yaml](policies/gpu-policy.yaml) — GPU, runtime, and cost limits;
- [policies/container-verification-policy.yaml](policies/container-verification-policy.yaml) — container trust and isolation policy;
- [SECURITY.md](SECURITY.md) — trust, authorization, and secret boundaries;
- [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) — staged experiment workflow;
- [docs/CONTAINER_VERIFICATION.md](docs/CONTAINER_VERIFICATION.md) — untrusted container boundary;
- `src/gpu_control/container.py` — structured container-verification evidence;
- `src/gpu_control/execution.py` — runtime paid-compute precondition gate;
- [.github/copilot-instructions.md](.github/copilot-instructions.md) — GitHub Copilot repository context;
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution requirements.

When policy, authorization, price, or cleanup guarantees are unknown, the intended behavior is fail-closed.

## Planned architecture

```text
Workload repository
        |
        | repository + immutable commit SHA
        v
    gpu-control
        |
        +-- request validation
        +-- resource / agent policy
        +-- source verification
        +-- isolated container verification
        +-- structured container evidence + image digest
        +-- dry-run
        +-- verified provider price
        +-- explicit authorization + cleanup gates
        +-- ApprovedExecutionPlan
        |
        v
 provider adapter (RunPod first)
        |
        | asynchronous submit / collect
        v
 containerized workload
        |
        v
 results / status collection
```

Long-running GPU work must not keep a GitHub-hosted runner polling for hours.

## Roadmap

1. Standalone CLI, bundled policy, lockfile, and zero-GPU CI. **Done.**
2. Repository-level agent policy and public operating model. **Done.**
3. Verify public target repository, exact commit SHA, and Dockerfile. **Done.**
4. Add provider-agnostic `ApprovedExecutionPlan` and fail-closed paid-compute preconditions. **Done.**
5. Run a repository-owned reference container under bounded, secret-free CI isolation. **Done.**
6. Replace bare container booleans with structured verification evidence tied to workload identity and image digest. **Done.**
7. Publish a separate minimal reference workload repository and add hostile build/runtime isolation tests.
8. Generalize container verification to explicitly authorized public workload repositories.
9. Add the RunPod adapter so it accepts only an approved execution plan.
10. Submit GPU jobs asynchronously and collect status, logs, metrics, and outputs.
11. Add other providers behind the same resource-policy interface if useful.

## License

MIT
