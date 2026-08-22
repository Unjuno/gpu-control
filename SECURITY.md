# Security Policy

## Scope

`gpu-control` is intended to be safe to publish. Its source code, workflow definitions, policy files, and GitHub Actions logs must be treated as public information.

## Secrets

Do not commit provider credentials, personal access tokens, `.env` files, private datasets, or private model artifacts.

When provider integration is enabled, credentials such as `RUNPOD_API_KEY` must be stored in GitHub Actions Secrets and must never be printed to logs.

Use restricted provider credentials where the provider supports them. Rotate a credential immediately if exposure is suspected.

## Paid-compute triggers

Paid GPU resources must not be launched directly from untrusted events such as:

- `pull_request`
- `pull_request_target`
- issues
- issue comments
- forks
- public webhooks without independent authorization

The initial paid-compute workflow will use `workflow_dispatch` and repository write access as the authorization boundary.

## Workflow permissions

Every workflow must declare `permissions:` explicitly and grant the minimum permissions required.

Trusted third-party Actions must be pinned to immutable full commit SHAs before they are used in workflows that can access credentials or paid resources.

## Input handling

Workflow input is hostile by default.

The control plane must:

- require `owner/repository` syntax for public workload repositories;
- require immutable 40-character hexadecimal commit SHAs;
- reject shell metacharacters and malformed repository identifiers;
- reject absolute paths and path traversal such as `../`;
- reject unknown GPU profiles;
- enforce hard runtime, cost, and GPU-count limits independently of caller input;
- never accept an arbitrary shell command as a workflow input.

## Provider lifecycle

Once paid provider integration is added, any created resource must be cleaned up on normal completion, failure, timeout, cancellation where possible, and provider/API errors after allocation.

Resource cleanup behavior must have automated tests. A failure to determine price or policy compliance must fail closed and must not launch paid compute.

## Reporting a vulnerability

Open a GitHub security advisory for sensitive reports when available. Do not place credentials, exploit tokens, or other secrets in a public issue.
