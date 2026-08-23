# Agent Operating Policy

This repository is a control plane for GPU experiments. Treat this file as normative repository context for automated agents.

## Core rule

Do not jump directly to paid GPU compute.

Use the cheapest, smallest, most local execution environment that can answer the current question. Paid GPU execution is an escalation stage, not the default development loop.

Defensive controls must preserve the user's objective whenever a safer path remains. Rejecting one action is not the same as abandoning the goal.

## Parked mode

Read `policies/repository-state.yaml` before proposing execution changes. When it says `mode: parked`, the repository is intentionally being held without an active GPU workload.

While parked, do not create a paid workflow, configure or reference provider secrets, enable RunPod live calls, enable generic external Dockerfile execution, or treat implementation progress as a reason to activate paid compute. Documentation, policy, offline tests, mock-provider work, source validation, and the repository-owned trusted container are still allowed.

Leaving parked mode requires an explicit human request plus a reviewed repository change. Changing the mode is not itself spend authorization; all independent GitHub, provider, pricing, workload, completion-evidence, and cleanup gates still apply.

## Decision governance

Read `policies/decision-policy.yaml` before escalating action scope. The governing principle is **goal-preserving restraint**.

When a proposed action is unjustified, unsafe, unauthorized, too expensive, too broad, or insufficiently evidenced, do not automatically treat the objective as failed. Prefer this order:

1. continue if the current action is justified;
2. reduce scope while preserving the question;
3. choose a safer, cheaper, more local, or more reversible alternative;
4. request a human checkpoint when judgment or authority is required;
5. deny the specific action when none of the above makes it acceptable.

If an action is denied and the objective is still active, report the specific reason and continue with the cheapest safe next step that can still advance the objective. A hard stop is a last resort for explicit cancellation, an invalid objective, no remaining safe or authorized path, or unacceptable irreversible downside.

Before increasing scope, check purpose, evidence, cheaper alternatives, decision value, economic value, reversibility, blast radius, current authority, stop conditions, failure learning value, and opportunity cost.

A remaining budget is not a reason to spend it. Cost limits are loss ceilings, not spending targets. Success at one experiment stage does not authorize the next stage, and failure does not justify spending more. Expansion requires new information and a current rationale tied to the active goal.

## Required operating order

1. **Inspect first.** Read `README.md`, `SECURITY.md`, `policies/repository-state.yaml`, `policies/decision-policy.yaml`, `policies/agent-policy.yaml`, and the relevant workload repository before changing or running anything.
2. **Clarify the current question.** Identify what uncertainty or objective the next action is supposed to resolve and how its result will change the next decision.
3. **Run locally in a container first.** Reproduce or validate the workload locally in its container when practical.
4. **Make the experiment small.** Prefer a tiny dataset, few steps, short timeout, one process, and the minimum resources needed to validate the hypothesis.
5. **Use a workload repository.** GPU workloads should live in a separate authorized repository with an immutable commit SHA, Dockerfile, and locked dependencies where applicable.
6. **Do not assume repository authority.** Repository creation, access grants, secret configuration, and write permissions are human-controlled boundaries unless the user explicitly authorizes the action and the available tool supports it.
7. **Validate through `gpu-control`.** Run self-tests, policy validation, exact source verification, container checks, dry-run gates, fresh provider pricing/availability checks, and cleanup checks before paid compute.
8. **Produce an approved execution plan.** Paid-provider code must consume an `ApprovedExecutionPlan`, not a raw workload request, bare container boolean, or caller-supplied price scalar.
9. **Escalate to RunPod only last.** Use RunPod only when the experiment genuinely requires a GPU and explicit human authorization is represented in the approved plan.

## Paid compute is denied by default

A request to inspect this repository, edit code, prepare an experiment, create a Dockerfile, or validate a workload is **not** authorization to spend money.

Before any billable provider call, require all of the following:

- an explicit human request to perform the paid GPU run;
- an active goal and a concrete current question;
- a documented reason the result can change the next decision;
- the cheapest viable non-paid or lower-cost alternative and why it is insufficient;
- explicit success and stop conditions;
- useful failure information expected from the run;
- an authorized workload repository;
- an immutable 40-character commit SHA;
- verified source identity for repository, commit, and Dockerfile;
- structured container-verification evidence tied to the same source identity and immutable image digest;
- a validated Dockerfile/container contract;
- locked or otherwise reproducible dependencies where applicable;
- the smallest reasonable experiment configuration;
- a successful `gpu-control` dry-run;
- structured pricing evidence for a concrete provider resource/offer;
- a verified positive provider price;
- verified provider-resource availability where the provider integration depends on it;
- an unexpired UTC pricing validity window at approval time;
- an explicit runtime limit;
- an explicit cost limit that is justified as a loss ceiling;
- one GPU unless policy explicitly permits otherwise;
- a cleanup path for success, failure, timeout, and cancellation;
- an immutable `ApprovedExecutionPlan` produced by the execution gate.

If any paid-compute precondition is missing, deny provider allocation. Preserve the active objective when possible, report the missing gate, and continue with the cheapest safe next step or request the necessary human judgment.

## Never do these things

- Never accept or construct arbitrary remote shell commands as the public execution interface.
- Never expose API keys, tokens, private datasets, or private artifacts in source, logs, issues, or artifacts.
- Never launch paid compute from an untrusted PR, fork, issue, comment, or public webhook.
- Never substitute a floating branch name for an immutable workload commit SHA.
- Never increase GPU count, runtime, cost, dataset size, or experiment scope merely because the previous attempt failed.
- Never treat unused budget as a reason to spend money.
- Never treat completion of a smaller stage as authorization for a larger stage.
- Never turn a denied action into mission abandonment while a useful safe path remains.
- Never keep a GitHub-hosted runner polling for hours while a GPU job runs; use submit/collect behavior.
- Never treat provider availability as permission to allocate resources.
- Never let a provider adapter accept a raw `WorkloadRequest` or bypass the approved execution-plan gate.
- Never convert an unverified price typed by a user or agent into `PricingVerificationResult` for a real paid run.
- Never reuse expired pricing evidence or silently substitute a different provider resource after pricing verification.

## Workload contract

The default workload contract is intentionally narrow:

```text
public or explicitly authorized repository
+ immutable commit SHA
+ Dockerfile
+ finite non-interactive container job
+ meaningful process exit code
+ reproducible dependencies where applicable
```

A workload should start, perform a bounded experiment, write outputs, and exit. Interactive SSH-driven workflows are not the default contract.

## Experiment discipline

Before escalation, define the current question, success condition, stop condition, and what useful information remains if the experiment fails. Reduce the experiment to the smallest test that can change the next decision. Prefer smoke tests over full training, synthetic/public inputs over private data, and minutes over hours.

If a proposed step is blocked, first look for a smaller or safer diagnostic that preserves progress. If the current question has already been answered, stop further escalation because the objective is achieved.

Record enough context to reproduce a result: repository, commit SHA, container definition, immutable image digest, configuration, runtime limit, cost limit, concrete provider resource id, pricing verification reference and validity window, GPU profile, authorization reference, exit status, and relevant metrics/output locations.

## Provider policy

RunPod is the first intended paid GPU provider. Provider-specific implementation must remain behind the control-plane policy and execution-plan layers. The public interface should describe resource requirements, not expose unrestricted provider operations.

A future provider adapter must accept an `ApprovedExecutionPlan`. It must not create resources from a raw user request merely because credentials are available.

Pricing must be obtained by a trusted provider-pricing stage and represented as `PricingVerificationResult`. The paid gate verifies that the evidence belongs to the requested GPU profile, names a concrete provider resource, reports successful price/availability checks, and is still within its UTC validity window. See `docs/PRICING_VERIFICATION.md`.

When pricing, GPU availability, policy compliance, authorization, or cleanup guarantees cannot be determined, fail closed on provider allocation. Do not convert that provider denial into abandonment of an otherwise achievable objective.

## Source of truth

- Human-facing project overview: `README.md`
- Current repository operating state: `policies/repository-state.yaml`
- Parked-mode rationale and resume criteria: `docs/PARKED_MODE.md`
- Goal-preserving decision policy: `policies/decision-policy.yaml`
- Decision-governance rationale: `docs/DECISION_GOVERNANCE.md`
- Agent execution rules: `AGENTS.md`
- Machine-readable escalation policy: `policies/agent-policy.yaml`
- Security boundaries: `SECURITY.md`
- GPU resource limits: `policies/gpu-policy.yaml`
- Container isolation policy: `policies/container-verification-policy.yaml`
- Provider pricing boundary: `docs/PRICING_VERIFICATION.md`
- Asynchronous lifecycle contract: `docs/ASYNC_EXECUTION.md`
- Runtime paid-compute gate: `src/gpu_control/execution.py`

When these documents conflict, choose the interpretation that preserves both safety and the user's active objective. Do not allocate paid resources until the conflict is resolved, but continue safe local or read-only progress when possible.
