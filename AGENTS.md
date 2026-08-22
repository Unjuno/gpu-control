# Agent Operating Policy

This repository is a control plane for GPU experiments. Treat this file as normative repository context for automated agents.

## Core rule

Do not jump directly to paid GPU compute.

Use the cheapest, smallest, most local execution environment that can answer the current question. Paid GPU execution is an escalation stage, not the default development loop.

## Required operating order

1. **Inspect first.** Read `README.md`, `SECURITY.md`, `policies/agent-policy.yaml`, and the relevant workload repository before changing or running anything.
2. **Run locally in a container first.** Reproduce the workload with its Dockerfile or container contract when practical.
3. **Make the experiment small.** Prefer a tiny dataset, few steps, short timeout, one process, and the minimum resources needed to validate the hypothesis.
4. **Use a workload repository.** GPU workloads should live in a separate repository with an immutable commit SHA, Dockerfile, and locked dependencies where applicable.
5. **Do not assume repository authority.** Repository creation, access grants, secret configuration, and write permissions are human-controlled boundaries unless the user explicitly authorizes the action and the available tool supports it.
6. **Validate through `gpu-control`.** Run self-tests, policy validation, source/container checks, and dry-run gates before paid compute.
7. **Escalate to RunPod only last.** Use RunPod only when the experiment genuinely requires a GPU or the user explicitly requests a paid GPU run after the preceding checks are satisfied.

## Paid compute is denied by default

A request to inspect this repository, edit code, prepare an experiment, create a Dockerfile, or validate a workload is **not** authorization to spend money.

Before any billable provider call, require all of the following:

- an explicit human request to perform the paid GPU run;
- an authorized workload repository;
- an immutable 40-character commit SHA;
- a validated Dockerfile/container contract;
- locked or otherwise reproducible dependencies where applicable;
- the smallest reasonable experiment configuration;
- a successful `gpu-control` dry-run;
- an explicit runtime limit;
- an explicit cost limit;
- one GPU unless policy explicitly permits otherwise;
- a cleanup path for success, failure, timeout, and cancellation.

If any precondition is missing, stop before provider allocation and report the missing gate.

## Never do these things

- Never accept or construct arbitrary remote shell commands as the public execution interface.
- Never expose API keys, tokens, private datasets, or private artifacts in source, logs, issues, or artifacts.
- Never launch paid compute from an untrusted PR, fork, issue, comment, or public webhook.
- Never substitute a floating branch name for an immutable workload commit SHA.
- Never increase GPU count, runtime, or cost simply to make a failing experiment pass without explicit human approval.
- Never keep a GitHub-hosted runner polling for hours while a GPU job runs; use submit/collect behavior.
- Never treat provider availability as permission to allocate resources.

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

Before escalation, reduce the experiment to the smallest test that can falsify or support the current hypothesis. Prefer smoke tests over full training, synthetic/public inputs over private data, and minutes over hours.

Record enough context to reproduce a result: repository, commit SHA, container definition, configuration, runtime limit, cost limit, GPU profile, exit status, and relevant metrics/output locations.

## Provider policy

RunPod is the first intended paid GPU provider. Provider-specific implementation must remain behind the control-plane policy layer. The public interface should describe resource requirements, not expose unrestricted provider operations.

When pricing, GPU availability, policy compliance, or cleanup guarantees cannot be determined, fail closed and do not launch.

## Source of truth

- Human-facing project overview: `README.md`
- Agent execution rules: `AGENTS.md`
- Machine-readable escalation policy: `policies/agent-policy.yaml`
- Security boundaries: `SECURITY.md`
- GPU resource limits: `policies/gpu-policy.yaml`

When these documents conflict, choose the safer interpretation and do not allocate paid resources until the conflict is resolved.