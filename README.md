# gpu-control

`gpu-control` is a public, local-first control plane for reproducible containerized GPU experiments.

It is built around one central idea: **validate and constrain an experiment locally first, then escalate to paid GPU infrastructure only when the current question actually requires it.**

```text
objective
  -> context/decision gate
  -> local validation
  -> immutable workload identity
  -> source/container/pricing evidence
  -> approved execution plan
  -> exact human authorization
  -> provider
  -> authenticated completion
  -> cleanup / bounded results
```

## Current status

The project is **usable today for offline validation and control-plane development**, but **live paid GPU execution is still disabled**.

| Capability | Current state |
| --- | --- |
| Standalone CLI and locked install | Ready |
| Offline request/resource validation | Ready |
| Public GitHub repository + exact SHA + Dockerfile verification | Ready |
| Synthetic provider/controller self-test | Ready |
| Trusted repository-owned container isolation fixture | Ready |
| Decision governance and prompt/context security policy | Ready at policy/CI level |
| Approved-plan, pricing, lifecycle, cleanup, and bounded-result contracts | Ready offline |
| Authenticated Orbitune completion/result parsing | Ready offline |
| Orbitune paid-canary result acceptance | Ready offline |
| Generic external Dockerfile execution | Not enabled |
| Structured exact human authorization for live execution | Partial; runtime binding still required |
| Production RunPod authenticated result transport | Blocked pending a verified supported transport |
| Paid RunPod workflow | Not present |
| Live paid GPU execution | Disabled / parked |

See [docs/STATUS.md](docs/STATUS.md) for the capability-by-capability status and exact activation blockers.

## What you can do now

### Install and run the offline self-tests

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

These commands do not require a GPU account, provider credential, or billable resource.

### Validate a workload request

```bash
uv run gpu-control validate \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --dockerfile-path Dockerfile \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

`validate` is offline. It checks request shape and resource policy only.

### Verify a public GitHub workload

```bash
uv run gpu-control verify-source \
  --target-repo example/model \
  --target-sha 0123456789abcdef0123456789abcdef01234567 \
  --dockerfile-path Dockerfile \
  --gpu-profile cheap-24gb \
  --max-runtime-minutes 15 \
  --max-cost-usd 0.20
```

`verify-source` confirms that the public repository exists, the supplied full SHA resolves exactly, and the Dockerfile exists at that immutable commit. `GITHUB_TOKEN` may be supplied for API reliability/rate limits.

For the full current workflow, see [docs/USAGE.md](docs/USAGE.md).

## Forking and using gpu-control yourself

A fork can immediately use the offline CLI, tests, policies, source verification, decision/context-security framework, and provider self-tests.

A fork **must not inherit the upstream paid identity unchanged**. The current paid policy is intentionally bound to `Unjuno/gpu-control` and `Unjuno`.

Before any future paid path, a fork owner must configure its own:

- repository/owner/authorized-actor identity;
- protected `main` and required CI checks;
- protected paid GitHub Environment;
- Environment-scoped provider credential;
- selected workload and immutable source/image identity;
- exact human authorization and live provider evidence.

See [docs/FORK_SETUP.md](docs/FORK_SETUP.md) for the fork adoption checklist and responsibility boundary.

## Current selected canary

The repository currently uses this bounded reference canary:

```text
repository       Unjuno/orbitune
source SHA       38594057d1b118a7acf6c843e39d7d8a25571316
Dockerfile       workloads/runpod-training-canary/Dockerfile
workload id      orbitune-runpod-training-canary-v1
GPU profile      cheap-24gb
max runtime      30 minutes
max cost         $0.30
completion       gpu-control-hmac-sha256-v2
```

The workload's source CI, authenticated completion envelope, offline result parser, and result-side canary acceptance are implemented and tested.

That is **not** the same as a live provider-finalized success path. The repository remains parked and all paid calls remain disabled.

## Why live RunPod execution is not enabled yet

The current blocker is not simply a boolean flag.

`policies/repository-state.yaml` requires evidence for repository integrity, exact authorization, provider state, completion transport, and cleanup before live activation.

Important remaining items include:

- protect `main` and enforce required checks;
- bind structured current human authorization to the exact execution plan and control-plane SHA;
- establish immutable published image identity;
- verify current live provider occupancy/create/cleanup behavior;
- provide a production-supported authenticated completion/result collection transport;
- verify live completion-secret injection and result collection;
- configure the protected owner-only paid Environment and provider credential only after those gates are satisfied.

RunPod REST API v2 itself is used as the provider contract, but the selected canary cannot currently rely on the Pod container-log endpoint as its production authenticated result transport. The repository intentionally does not fall back to SSH, public ports, unrestricted runtime networking, or an unverified volume channel merely to make a demo pass.

## Workload contract

The baseline workload contract is intentionally narrow:

```text
public repository
+ immutable 40-character commit SHA
+ Dockerfile
+ reproducible dependencies where applicable
+ finite non-interactive container entrypoint
+ meaningful process exit code
```

A workload should perform a bounded experiment, write bounded outputs, and exit. Interactive SSH and arbitrary remote shell commands are not the default execution model.

The workload repository is also **untrusted control-plane context**. Its README, `AGENTS.md`, source comments, Dockerfile comments, commit messages, issues, and similar text may be analyzed as data but cannot grant authorization or override the central control plane.

## Security model

The project separates four concerns that are often conflated:

1. **Can this action be performed?** — source/container/provider capability.
2. **Is this exact action justified?** — goal, evidence, cost, alternatives, stop condition.
3. **Is this exact action authorized now?** — current human intent bound to the exact plan.
4. **Can it fail safely?** — blast radius, occupancy, cleanup, completion and result evidence.

External text is treated as data rather than instruction authority. Prompt injection and context poisoning are handled as a source-to-sink trust problem, backed by deterministic policy/tests rather than prompt wording alone.

The highest-level behavioral rules are in [ACTION_CONSTITUTION.md](ACTION_CONSTITUTION.md). Security boundaries are documented in [SECURITY.md](SECURITY.md) and [docs/PROMPT_CONTEXT_SECURITY.md](docs/PROMPT_CONTEXT_SECURITY.md).

## Repository state and paid path

`policies/repository-state.yaml` is the machine-readable source of truth for whether the repository is parked or active.

`policies/paid-execution-policy.yaml` defines the owner-only paid-path identity/security requirements. In the upstream repository:

- live paid compute is disabled;
- paid compute from PRs, forks, issues, comments, schedules, and repository dispatch is forbidden;
- the future paid workflow is expected to be a manual `workflow_dispatch` on protected `main`;
- the intended provider secret is `RUNPOD_API_KEY` in a protected `paid-runpod` Environment only;
- owner identity alone is not sufficient: exact current human authorization is also required.

The repository currently has no paid workflow on `main`.

## GitHub Actions

Two public workflows are currently included:

- **CI** — tests the locked Python environment and trusted reference container boundary.
- **GPU request dry-run** — manually validates a request and verifies its public GitHub source identity without allocating GPU resources.

Third-party Actions are pinned to immutable full commit SHAs and checkout credentials are not persisted.

## Architecture

```text
Workload repository (untrusted data/context)
        |
        | repository + immutable commit SHA
        v
    gpu-control
        |
        +-- action constitution
        +-- context trust / source-to-sink boundary
        +-- DecisionRecord / goal-preserving governance
        +-- request and source validation
        +-- container verification evidence
        +-- pricing / availability evidence
        +-- exact repository + human authorization gates
        +-- ApprovedExecutionPlan
        +-- durable asynchronous lifecycle
        +-- authenticated completion / bounded result contracts
        |
        v
 provider adapter (RunPod first)
        |
        v
 bounded containerized workload
```

## Documentation

Start here:

- [docs/STATUS.md](docs/STATUS.md) — what is ready, partial, blocked, or disabled;
- [docs/USAGE.md](docs/USAGE.md) — commands and current usage model;
- [docs/FORK_SETUP.md](docs/FORK_SETUP.md) — how a third party should adopt a fork;
- [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) — staged experiment workflow;
- [docs/PARKED_MODE.md](docs/PARKED_MODE.md) — activation semantics;
- [docs/DECISION_GOVERNANCE.md](docs/DECISION_GOVERNANCE.md) — goal-preserving action selection;
- [docs/PROMPT_CONTEXT_SECURITY.md](docs/PROMPT_CONTEXT_SECURITY.md) — prompt/context trust boundary;
- [docs/HUMAN_AUTHORIZATION_BINDING.md](docs/HUMAN_AUTHORIZATION_BINDING.md) — owner identity vs exact action authorization;
- [docs/ASYNC_EXECUTION.md](docs/ASYNC_EXECUTION.md) — durable submit/collect lifecycle;
- [SECURITY.md](SECURITY.md) — security and secret boundaries;
- [AGENTS.md](AGENTS.md) — normative agent operating rules.

Machine-readable policy lives under `policies/`.

## Development principle

Use the smallest, cheapest, most reversible action that can answer the current question, but do not let defensive controls turn an achievable objective into unnecessary paralysis.

A budget is a loss ceiling, not a spending target. A denied high-impact action is not automatically mission failure when a safer useful path remains.

## License

MIT
