# Security Policy

## Scope

`gpu-control` is intended to be safe to publish. Its source code, workflow definitions, policy files, agent instructions, and GitHub Actions logs must be treated as public information.

The project separates three boundaries that must not be conflated:

1. repository access;
2. permission to modify or validate code;
3. authorization to create billable GPU resources.

Having the first or second does not imply the third.

## Agent authorization boundary

Automated agents must follow `AGENTS.md` and `policies/agent-policy.yaml`.

Paid compute is denied by default. A request to inspect a repository, edit code, prepare a Dockerfile, create a workload repository, run tests, or perform a dry-run is not authorization to spend provider credits.

Before a billable provider call, require explicit human authorization plus the technical gates defined in `AGENTS.md`. Missing or ambiguous authorization must fail closed.

Repository creation, collaborator grants, secret configuration, and write permissions are human-controlled security boundaries unless the user explicitly authorizes the action and the connected tool supports it.

## Approved execution plan boundary

Provider adapters must not accept a raw `WorkloadRequest`. A billable provider adapter is expected to accept an immutable `ApprovedExecutionPlan` produced by `src/gpu_control/execution.py`.

The execution-plan gate requires verified source identity, container verification, a successful dry-run, verified provider pricing, policy-compliant runtime and cost, a cleanup guarantee, and explicit human authorization with an audit reference.

The execution-plan gate is defense in depth, not an identity provider. The trusted caller or workflow is responsible for establishing that the authorization evidence actually came from an authorized human. An agent must not manufacture authorization evidence merely to satisfy the function signature.

The worst-case cost calculation rounds upward to the nearest cent so the control plane does not approve a run by underestimating spend.

## Secrets

Do not commit provider credentials, personal access tokens, `.env` files, private datasets, or private model artifacts.

When provider integration is enabled, credentials such as `RUNPOD_API_KEY` must be stored in GitHub Actions Secrets or an equivalent secret store and must never be printed to logs.

Use restricted provider credentials where supported. Rotate a credential immediately if exposure is suspected.

## Paid-compute triggers

Paid GPU resources must not be launched directly from untrusted events such as:

- `pull_request`;
- `pull_request_target`;
- issues;
- issue comments;
- forks;
- public webhooks without independent authorization.

The initial paid-compute workflow will use an explicitly authorized manual or authenticated control path. Public visibility must never become public spending authority.

## Workflow permissions

Every workflow must declare `permissions:` explicitly and grant the minimum permissions required.

Trusted third-party Actions must be pinned to immutable full commit SHAs before they are used in workflows that can access credentials or paid resources.

Long-running provider jobs must not keep a GitHub-hosted runner polling for hours. Use an asynchronous submit/collect lifecycle.

## Input handling

Workflow input is hostile by default.

The control plane must:

- require `owner/repository` syntax for workload repositories;
- require immutable 40-character hexadecimal commit SHAs;
- reject shell metacharacters and malformed repository identifiers;
- reject absolute paths and path traversal such as `../`;
- reject unknown GPU profiles;
- reject monetary limits that require implicit sub-cent rounding;
- enforce hard runtime, cost, and GPU-count limits independently of caller input;
- never accept an arbitrary shell command as a public workflow input.

A floating branch name is not a valid workload identity for paid execution.

## Source verification

The public MVP verifies that the target GitHub repository exists and is public, that the requested full SHA resolves to the exact commit, and that the requested Dockerfile path resolves to a file at that SHA.

Source verification is read-only and must not execute code from the workload repository. Private repositories remain rejected in the current MVP even if a supplied token could access them.

## Container verification boundary

Building or running a Dockerfile from an arbitrary public repository executes untrusted code. Do not add generic container build/run behavior to a credential-bearing GitHub Actions job without a separate sandbox and threat model.

Until that isolation boundary exists, source verification and container execution must remain separate stages.

## Escalation and cost safety

Agents and workflows must prefer local/container validation and the smallest useful experiment before paid compute.

A paid run requires an explicit cost limit and runtime limit. GPU count defaults to one. An agent must not silently raise cost, runtime, GPU count, or resource class merely to make a failing workload pass.

Unknown price, missing policy data, ambiguous authorization, invalid workload identity, missing approved execution plan, or inability to guarantee cleanup must stop allocation.

## Provider lifecycle

Once paid provider integration is added, any created resource must be cleaned up on normal completion, failure, timeout, cancellation where possible, and provider/API errors after allocation.

Resource cleanup behavior must have automated tests. A failure to determine price or policy compliance must fail closed and must not launch paid compute.

## Reporting a vulnerability

Open a GitHub security advisory for sensitive reports when available. Do not place credentials, exploit tokens, or other secrets in a public issue.
