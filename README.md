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

The public ChatGPT Site is active as Version 33. The connected owner account can read its capabilities and experiment history; the persistent Sites-to-Modal Proxy Token configuration is present, so provider credentials do not need to be re-entered for each chat. Each experiment still requires a fresh one-use confirmation for its exact plan. As of 2026-11-14, Sites environment revision 35 has `CPU_WORKLOAD_ADMISSION_ENABLED=false`; new inference is blocked while the Modal deployment is reconciled. The Site's configured Modal fingerprint (`53b5d84a…`) does not match the current candidate fingerprint (`8a786eb7…`), and the candidate hard CPU/memory limits have not been verified in a live Sandbox. The latest five Modal-origin runs failed with `MODAL_WORKLOAD_EXIT_2`; the newest run's cleanup was confirmed and no result artifact exists. No successful inference against the current Modal deployment is accepted yet. RunPod/GPU and paid training remain parked.

Modal execution is usage-billed, not inherently free. Modal's general Starter pricing advertises `$30` of monthly compute, but this Workspace's account-specific dashboard currently says only `$1` of `$30/mo` is available and the Credits tab says `$1` monthly. Usage & Billing shows `$0.10` in credits used, `$0` in charges, and a `$1` Workspace usage limit; at most `$0.90` of usage headroom remains under that cap. The provider is still classified as paid and credit-eligible. The `$0.01` ceiling covers only Sandbox CPU/memory, not separately billed Modal control-function calls. No billing settings were changed. See [Modal pricing](https://modal.com/pricing) and [Modal budgets](https://modal.com/docs/guide/budgets).

| Capability | Current state |
| --- | --- |
| Standalone CLI and locked install | Ready |
| ChatGPT MCP endpoint | Sites Worker is published at `https://gpu-control-sites.unjuno.chatgpt.site`; owner-scoped capabilities and experiment-list tools were accepted from this ChatGPT account |
| Registered CPU experiment through ChatGPT | Provider configuration and authenticated plan/read tools are connected. Admission is disabled at Sites environment revision 35 until the candidate Modal fingerprint and 1-core / 512-MiB hard limits are deployed and verified. Modal control-function charges are separate from the Sandbox estimate. |
| Real model inference through ChatGPT | No accepted successful inference against the current Modal deployment. The latest five Modal attempts failed with workload exit code 2; the newest cleanup is confirmed and has no result artifact. Older local-Runner successes are historical evidence only. |
| GPU execution | Not yet verified |
| Offline request/resource validation | Ready |
| Public GitHub repository + exact SHA + Dockerfile verification | Ready |
| Synthetic provider/controller self-test | Ready |
| Trusted repository-owned container isolation fixture | Ready |
| Decision governance and prompt/context security policy | Ready at policy/CI level |
| Approved-plan, pricing, lifecycle, cleanup, and bounded-result contracts | Ready offline |
| Authenticated Orbitune completion/result parsing | Ready offline |
| Orbitune paid-canary result acceptance | Ready offline |
| Generic external Dockerfile execution | Not enabled |
| Structured exact human authorization for paid live execution | Partial; RunPod authorization is not wired to Sites Worker admission |
| Production RunPod authenticated result transport | Blocked pending a verified supported transport |
| Paid RunPod workflow | Not enabled; RunPod stays offline-only and parked pending separate authorization, pricing, completion, and cleanup gates |
| Live paid GPU execution | Disabled / parked |

The current hosted product path is the ChatGPT Sites Worker with D1/R2. The
Site URL is public, while MCP calls are authenticated and stateful tools bind
the caller to the owner allowlist. This ChatGPT account successfully read its
capabilities and owned run history; a separate-account denial remains
unverified. Sites Version 33 is live at environment revision 35 with CPU
admission disabled. Modal proxy configuration is present, but its live
fingerprint does not match the current candidate and no successful inference
against the current Modal deployment is accepted. The candidate sets
request=limit to 1 CPU and 512 MiB but is not deployed. PR #68 remains an open
Draft; repository-wide security coverage and cross-account denial are open.
Historical ChatGPT CPU successes used the retired local Runner and do not
prove current Modal readiness. The latest Modal attempts failed with exit
code 2 and confirmed cleanup. The old local Runner and Keychain credentials
are retired. The target compute order is Modal for a small fixed workload,
then RunPod for separately gated GPU experiments. Vercel and Neon/PostgreSQL
are not target dependencies. The legacy FastAPI/PostgreSQL Gateway source and
runtime dependencies have been removed from the tracked tree; historical
acceptance evidence remains under `docs/acceptance/` and in Git history.

See [docs/CHATGPT_SETUP.md](docs/CHATGPT_SETUP.md) for the ChatGPT integration,
[docs/RELEASE_MATRIX.md](docs/RELEASE_MATRIX.md) for current acceptance gates,
[docs/STATUS.md](docs/STATUS.md) for current capability blockers, and
[docs/SITES_MODAL_RUNPOD_DELIVERY.md](docs/SITES_MODAL_RUNPOD_DELIVERY.md) for
the staged Sites/Modal/Runpod implementation plan. Historical Vercel/Postgres
records are archived, not deployment instructions.

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
source SHA       fc131174a9b529a9825f54fccf1a7df4c63c9a1a
Dockerfile       workloads/runpod-training-canary/Dockerfile
workload id      orbitune-runpod-training-canary-v1
GPU profile      cheap-24gb
max runtime      30 minutes
max cost         $0.30
completion       gpu-control-hmac-sha256-v3
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

## Action constitution

[ACTION_CONSTITUTION.md](ACTION_CONSTITUTION.md) is the repository's highest-level behavioral norm. Its machine-readable counterpart is [`policies/action-constitution.yaml`](policies/action-constitution.yaml). It governs how an already-authorized objective should be pursued; it does not create credentials, grant spending authority, or weaken hard security/legal/external-authorization boundaries.

Its practical priority is to preserve human control and prevent unacceptable irreversible or unauthorized action while still preserving useful progress toward the active objective when a safe path remains. Lower-level policies may be stricter for concrete risk, but denying one high-impact action must not silently become abandonment of an otherwise achievable goal.

Security boundaries are documented in [SECURITY.md](SECURITY.md) and [docs/PROMPT_CONTEXT_SECURITY.md](docs/PROMPT_CONTEXT_SECURITY.md).

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
