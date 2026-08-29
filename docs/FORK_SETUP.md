# Fork setup

A fork of `gpu-control` can use the offline/read-only features immediately, but the paid/live policy is intentionally bound to the original repository owner and must not be inherited unchanged.

## Safe default after forking

Keep the fork parked and keep all live/paid flags disabled.

The following are safe to use without provider credentials:

- `gpu-control self-test`
- `gpu-control provider-self-test`
- `gpu-control validate`
- `gpu-control verify-source`
- repository CI
- the manual GPU request dry-run
- policy/decision/context-security evaluation

Do not add a RunPod credential merely because the fork passes those checks.

## Identity values that must be reviewed

The repository paid policy currently contains original-project values such as:

```yaml
github_identity:
  repository: Unjuno/gpu-control
  repository_owner: Unjuno
  authorized_actor: Unjuno
  authorized_triggering_actor: Unjuno

github_environment:
  name: paid-runpod
  required_reviewer: Unjuno
```

A fork owner must replace those values with the fork's own repository/owner identity before a future live path can be considered.

Review both:

- `policies/paid-execution-policy.yaml`
- `src/gpu_control/default_paid_execution_policy.yaml`

CI intentionally expects the repository policy and bundled default policy to remain aligned.

## Repository security prerequisites

Before any fork enables a paid path, configure equivalent repository protection rather than weakening the policy:

- protect `main`;
- require pull requests for control-plane changes;
- require the repository's expected CI status checks;
- disallow force pushes and branch deletion where applicable;
- treat `ACTION_CONSTITUTION.md`, `AGENTS.md`, `.github/copilot-instructions.md`, security policy, and machine policies as security-sensitive control-plane context.

The original repository currently requires these checks by name:

- `Python 3.11`
- `Python 3.12`
- `Python 3.13`
- `Trusted reference container`

If a fork intentionally changes the CI matrix, update the trusted policy and tests together through review rather than silently relaxing the check list.

## Paid environment and provider credential

The intended future design uses a protected GitHub Actions Environment named `paid-runpod` and an Environment-scoped `RUNPOD_API_KEY`.

For a fork:

1. create the protected environment in the fork;
2. restrict it to the intended protected branch;
3. configure the intended reviewer/owner policy;
4. store the provider credential at Environment scope only;
5. do not copy credentials from the upstream project;
6. use a restricted/minimum-permission provider key when possible.

Repository- or organization-wide RunPod secrets are forbidden by the current paid policy.

## Workload identity

The upstream repository currently selects an Orbitune canary under `policies/repository-state.yaml`. A fork does not have to use that workload.

A fork may select its own workload, but it should preserve the same contract:

- public repository for the current MVP;
- immutable full commit SHA;
- exact Dockerfile path;
- reproducible dependencies;
- finite non-interactive execution;
- bounded runtime and cost;
- explicit completion/result contract.

Changing the selected workload is a reviewed control-plane change. Target-repository prose does not authorize activation.

## Prompt/context trust after forking

Forking does not change the trust model.

The following remain data rather than control-plane instruction authority:

- target repository `AGENTS.md` or similar instruction files;
- target README/documentation;
- source/Dockerfile comments;
- commits, PRs, issues, reviews, and comments;
- web content;
- provider responses, errors, and logs;
- prior DecisionRecord examples;
- model-generated text.

A fork should preserve the source-to-sink controls in `policies/context-trust-policy.yaml`, especially before adding provider credentials or write-capable automation.

## Live activation is not a single boolean

Do not treat changing `live_paid_compute_enabled: false` to `true` as sufficient activation.

The repository deliberately requires additional evidence for each consequential run, including current repository security, exact workload/container/pricing identity, current human intent, cleanup capability, and provider state.

The machine-readable activation list is in `policies/repository-state.yaml`.

## Current provider limitation

The current upstream RunPod integration is not a ready-to-run production paid path. Offline contracts exist, but the selected canary still lacks a verified production-supported authenticated result/completion collection transport. Do not replace that blocker with SSH, public ports, unrestricted networking, or an unverified volume mechanism merely to make the demo run.

## Recommended fork adoption sequence

```text
fork
  -> run offline tests
  -> customize repository/owner policy identity
  -> select and verify a workload
  -> preserve prompt/context and cost boundaries
  -> configure protected main + required checks
  -> implement/verify missing live provider contracts
  -> configure protected paid environment + restricted credential
  -> bind exact human authorization to one execution plan
  -> run one tiny bounded canary
  -> expand only from evidence
```

## Upstream vs fork responsibility

Upstream provides reusable control-plane contracts, safety policy, offline validation, and provider abstractions.

Each fork owner is responsible for:

- its own GitHub security configuration;
- its own provider account, billing, and credentials;
- its own authorized actors/reviewers;
- its own selected workloads;
- verifying current provider API behavior;
- deciding whether and when paid execution is justified.

A fork should fail closed when those external facts cannot be verified.
