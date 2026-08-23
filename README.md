# gpu-control

`gpu-control` is a public, local-first control plane for reproducible containerized GPU experiments.

It is designed to make escalation deliberate rather than sending every experiment directly to paid GPU infrastructure:

```text
inspect
  -> decision gate
  -> local container
  -> smallest useful experiment
  -> workload repository + immutable commit
  -> policy + source verification
  -> isolated container verification
  -> approved execution plan
  -> RunPod only when GPU compute is actually required
```

> **Current status:** the repository is intentionally **parked** because there is no active GPU workload. Local validation, public GitHub source verification, trusted-container isolation, structured container/pricing evidence, immutable approved plans, durable async lifecycle state, bounded result contracts, and a RunPod API v2 adapter are implemented and tested offline/mock-only. Generic external Dockerfile execution, authenticated live result collection, provider workflow wiring, provider credentials, and all billable RunPod calls remain disabled.

## Operating rule

Use the cheapest, smallest, most local execution environment that can answer the current question. Paid compute is an escalation stage, not the default development loop.

Repository access is not authorization to spend money. Agents operating in this repository must follow [ACTION_CONSTITUTION.md](ACTION_CONSTITUTION.md), [AGENTS.md](AGENTS.md), [policies/decision-policy.yaml](policies/decision-policy.yaml), and [policies/agent-policy.yaml](policies/agent-policy.yaml).

Defensive controls are expected to preserve the user's objective whenever a safe path remains. Rejecting a specific high-impact action does not automatically mean abandoning the goal.

## Action constitution

`ACTION_CONSTITUTION.md` is the repository's highest-level behavioral norm. Its machine-readable counterpart is `policies/action-constitution.yaml`.

The constitution does **not** grant authority or weaken hard security boundaries. It defines how an authorized objective should be pursued when safety, cost, uncertainty, reversibility, and progress pull in different directions.

Its conflict-resolution order is:

1. preserve human control;
2. prevent unacceptable irreversible harm or unauthorized action;
3. preserve the active objective;
4. prefer smaller, reversible, evidence-producing progress;
5. maximize useful information or outcome relative to cost and risk;
6. stop only when no acceptable path remains.

Lower-level policies may become more restrictive for concrete security, authorization, or repository-state reasons. They may not silently turn denial of one high-impact action into abandonment of an otherwise achievable objective.

## Parked state

`policies/repository-state.yaml` is the machine-readable current operating state. While it says `mode: parked`, the repository is deliberately held without an active workload.

Parked mode keeps offline validation, tests, documentation, policy work, mock-provider work, and the repository-owned trusted container available, while CI enforces that paid workflow wiring, RunPod secrets, live provider flags, generic external container execution, and public/scheduled paid entrypoints stay disabled.

See [docs/PARKED_MODE.md](docs/PARKED_MODE.md) for the resume criteria. Leaving parked mode requires an explicit human request and a reviewed repository change; changing the mode is not itself authorization to spend money.

## Decision governance

`policies/decision-policy.yaml` defines a goal-preserving decision layer before escalation and must conform to the action constitution.

When a proposed action is unjustified, too broad, too costly, insufficiently evidenced, or outside current authority, the preferred response is:

```text
continue
  -> reduce scope
  -> safer alternative
  -> human checkpoint
  -> deny the specific action
```

The mission remains active unless the objective has been achieved, explicitly cancelled, become invalid, or no safe and authorized path remains.

Before increasing experiment scope, consider purpose, evidence, cheaper alternatives, decision value, economic value, reversibility, blast radius, authority, stop conditions, failure learning value, and opportunity cost.

A remaining budget is not a reason to spend it. Cost limits are loss ceilings, not spending targets. Success at one stage does not authorize the next stage, and failure does not justify more spending. Expansion requires new information and a current rationale tied to the active goal.

See [docs/DECISION_GOVERNANCE.md](docs/DECISION_GOVERNANCE.md).

The intended execution sequence remains:

1. Define the current objective and question.
2. Choose the smallest justified action that can change the next decision.
3. Test the workload locally in a container when practical.
4. Reduce it to the smallest useful experiment.
5. Put the workload in a separate repository with reproducible dependencies.
6. Identify the workload by an immutable 40-character commit SHA.
7. Validate policy and verify the repository, exact commit, and Dockerfile.
8. Verify the container itself in an appropriate isolation boundary and produce structured evidence tied to the exact workload identity and image digest.
9. Produce an immutable `ApprovedExecutionPlan` only after decision, source, container, dry-run, pricing, cleanup, policy, and explicit-human-authorization gates pass.
10. Allow a provider adapter to consume that approved plan; never pass it a raw workload request.
11. Escalate to RunPod only when GPU compute is actually required.

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
uv run gpu-control provider-self-test
uv run pytest
```

Both self-tests are offline and require no GPU, provider account, or GitHub token. `provider-self-test` exercises the approved-plan, submit/observe/cleanup, and bounded-result contracts through a synthetic provider without network access or billable resources.

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

The fixture also probes from inside the container that credentials, the Docker socket, GPU devices, and outbound network access are absent. CI independently inspects the resulting Docker host configuration.

This is intentionally **not** generic workload execution. `policies/container-verification-policy.yaml` keeps external build/run denied until hostile workload, secret-isolation, and resource-limit tests are complete.

## Structured container evidence

`src/gpu_control/container.py` defines `ContainerVerificationResult`. Paid-compute code does not accept a bare `container_verified=True` flag.

Container evidence is tied to the exact repository, commit SHA, Dockerfile path, immutable lowercase `sha256:` image digest, and a non-empty verification/audit reference. It records build/runtime isolation, smoke-test, output-contract, credential-isolation, network-policy, and resource-limit results. The paid gate rejects partial or mismatched evidence.

## Paid execution gate

`src/gpu_control/execution.py` defines the boundary provider adapters must use.

A raw `WorkloadRequest` is not sufficient to allocate resources. `build_approved_execution_plan(...)` requires exact source verification, structured container evidence, an immutable image digest, a successful dry-run, fresh structured pricing/availability evidence, policy-compliant runtime/cost limits, a cleanup guarantee, and explicit human authorization.

The repository policy additionally requires a current paid-compute decision rationale: an active goal, current question, cheapest viable alternative, expected decision impact, maximum justified cost, success condition, stop condition, failure learning value, and worst-case downside. The current runtime `ApprovedExecutionPlan` schema does not yet encode this qualitative record; live compute remains disabled, so that integration can be done only when a concrete workload requires it.

Worst-case spend is calculated from verified hourly price and requested runtime, then rounded **up** to the nearest cent before comparison with the requested cost ceiling.

The resulting `ApprovedExecutionPlan` is immutable, has canonical JSON/fingerprinting support, and is revalidated when restored across asynchronous stages. The fingerprint is an integrity/correlation identity, not a cryptographic signature.

There is intentionally no public CLI command that manufactures a live approved paid plan.

## Provider and asynchronous lifecycle

A provider-neutral controller and a RunPod API v2 adapter are implemented. The RunPod adapter is currently mock-tested only and live wiring is disabled by policy.

The adapter requires approved-plan identity, digest-pinned published-image evidence, short-lived catalog pricing/availability evidence, and account-occupancy evidence. It does not automatically retry an ambiguous create request. A known invalid newly created Pod is compensating-terminated, and account exclusivity is checked before and immediately after create.

Long-running jobs follow a submit/collect model rather than keeping GitHub-hosted runners polling for hours. Submission receipts, job observations, cleanup state, approved plans, and bounded result manifests use strict durable JSON contracts and fingerprint correlation.

RunPod `EXITED` alone is deliberately not treated as successful workload completion. Authenticated workload-completion evidence is still required before live result collection can be enabled.

## Owner-exclusive future paid path

Paid execution is designed to be exclusive to the repository owner and is still disabled.

Future live authorization requires the expected repository, `main`, dedicated manual workflow identity, matching `github.actor` and `github.triggering_actor`, actual protected-main evidence with required CI checks, a protected owner-reviewed `paid-runpod` GitHub Environment, an environment-scoped `RUNPOD_API_KEY`, global single-flight concurrency, and an empty RunPod account before submission.

The actual `main` branch protection and protected Environment are external GitHub settings; they are prerequisites rather than assumptions. Current runtime gates fail closed without trusted evidence that they are configured.

Fail-closed behavior applies to the risky provider action. When possible, the active objective should remain available for local, read-only, mock, CPU, or otherwise lower-risk progress.

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

- **CI** — tests the locked Python environment on 3.11, 3.12, and 3.13 using `ubuntu-24.04`, runs offline self-tests, and separately runs the trusted reference container under restricted settings.
- **GPU request dry-run** — manually validates policy and verifies the public workload repository, exact commit, and Dockerfile without creating GPU resources.

Checkout credentials are not persisted. Workflows use minimal permissions. Third-party Actions are pinned to full immutable commit SHAs, and CI rejects non-SHA `uses:` references. `uv` bootstrap also uses a full-SHA-pinned official setup action while installing the repository-selected uv version.

Paid compute must never be triggered directly by untrusted pull requests, forks, issues, comments, schedules, repository dispatches, or public webhooks.

## Repository context and policy

This repository is intended to be useful as execution context for both humans and automation agents:

- [ACTION_CONSTITUTION.md](ACTION_CONSTITUTION.md) — highest-level provider-neutral behavioral constitution;
- [policies/action-constitution.yaml](policies/action-constitution.yaml) — machine-readable constitutional invariants and conflict order;
- [policies/repository-state.yaml](policies/repository-state.yaml) — current parked/active repository mode;
- [docs/PARKED_MODE.md](docs/PARKED_MODE.md) — parked-state invariants and resume criteria;
- [policies/decision-policy.yaml](policies/decision-policy.yaml) — goal-preserving action and escalation policy;
- [docs/DECISION_GOVERNANCE.md](docs/DECISION_GOVERNANCE.md) — decision rationale, progressive experimentation, and stop semantics;
- [AGENTS.md](AGENTS.md) — normative agent operating rules;
- [policies/agent-policy.yaml](policies/agent-policy.yaml) — machine-readable escalation policy;
- [policies/gpu-policy.yaml](policies/gpu-policy.yaml) — GPU, runtime, and cost limits;
- [policies/container-verification-policy.yaml](policies/container-verification-policy.yaml) — container trust and isolation policy;
- [policies/paid-execution-policy.yaml](policies/paid-execution-policy.yaml) — owner-only paid path and repository-security prerequisites;
- [policies/runpod-v2-policy.yaml](policies/runpod-v2-policy.yaml) — disabled-by-default RunPod v2 contract;
- [SECURITY.md](SECURITY.md) — trust, authorization, and secret boundaries;
- [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) — staged experiment workflow;
- [docs/CONTAINER_VERIFICATION.md](docs/CONTAINER_VERIFICATION.md) — untrusted container boundary;
- [docs/ASYNC_EXECUTION.md](docs/ASYNC_EXECUTION.md) — durable asynchronous lifecycle;
- `src/gpu_control/container.py` — structured container-verification evidence;
- `src/gpu_control/execution.py` — runtime paid-compute precondition gate;
- [.github/copilot-instructions.md](.github/copilot-instructions.md) — GitHub Copilot repository context;
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution requirements.

When a high-impact action lacks policy, authorization, price, repository security, or cleanup guarantees, that action is fail-closed. When a safe lower-impact path remains, continue progress toward the active objective rather than treating the entire mission as failed.

## Planned architecture

```text
Workload repository
        |
        | repository + immutable commit SHA
        v
    gpu-control
        |
        +-- action constitution
        +-- active goal + decision governance
        +-- request validation
        +-- resource / agent policy
        +-- source verification
        +-- isolated container verification
        +-- structured container evidence + image digest
        +-- dry-run
        +-- verified provider price / availability
        +-- repository + owner authorization gates
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
 authenticated completion evidence
        |
        v
 bounded results / status collection
```

## Roadmap

1. Standalone CLI, bundled policy, lockfile, and zero-GPU CI. **Done.**
2. Repository-level agent policy and public operating model. **Done.**
3. Verify public target repository, exact commit SHA, and Dockerfile. **Done.**
4. Add provider-agnostic `ApprovedExecutionPlan`, strict persistence, pricing evidence, and fail-closed paid-compute preconditions. **Done.**
5. Run a repository-owned reference container under bounded, secret-free CI isolation and probe isolation from inside the container. **Done.**
6. Add provider-neutral asynchronous lifecycle, durable receipts/observations, cleanup state, and bounded result manifests. **Done.**
7. Add RunPod API v2 transport, catalog-pricing evidence, account-exclusivity checks, and a mock-tested adapter behind the control plane. **Done; live disabled.**
8. Add owner-exclusive paid authorization and protected-main evidence requirements. **Done; external GitHub protection still must be configured before activation.**
9. Add goal-preserving decision governance so defensive controls reduce or redirect unjustified actions without needlessly abandoning the objective. **Done at policy/prompt level; runtime paid-plan integration deferred until a concrete workload exists.**
10. Add a provider-neutral action constitution above decision and agent policy, with machine-readable invariants and CI consistency checks. **Done at policy/prompt level.**
11. Publish/select a separate minimal workload repository and add hostile build/runtime isolation tests.
12. Generalize isolated container verification to explicitly authorized public workload repositories and establish immutable image publication.
13. Add authenticated workload-completion evidence and live result collection.
14. Only then configure the protected owner-only paid Environment and consider enabling the live RunPod path for a concrete workload.
15. Add other providers behind the same resource-policy interface only if useful.

## License

MIT
