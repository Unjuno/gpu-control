# Repository security boundary

Paid GPU execution remains disabled. Repository configuration is part of the future paid-compute trust boundary and must be verified independently from repository policy files.

## Protected main is mandatory

Before live paid authorization can succeed, a trusted preflight must read GitHub's actual repository and branch settings and produce `RepositorySecurityEvidence` proving that:

- `main` is protected;
- changes to `main` require a pull request;
- required status checks are enforced;
- all seven current required checks pass: `Python 3.11`, `Python 3.12`, `Python 3.13`, `Trusted reference container`, `Gateway offline tests`, `Gateway comment bridge tests`, and `Project bridge tests`;
- force pushes are blocked;
- branch deletion is blocked.

`authorize_paid_execution(...)` rejects any live-enabled policy when this evidence is missing or incomplete. Setting `live_paid_compute_enabled: true` in YAML is therefore insufficient to enable billing.

The 2026-10-31 read-only GitHub API audit confirms main protection is configured with the seven checks above, one approval, approval after the last push, strict/up-to-date history, conversation resolution, linear history, and admin enforcement. Current P1 PR #52 still needs its independent approval. This satisfies the branch-integrity prerequisite only; paid execution remains disabled. The same audit found the `Production` and `Preview` Environments have no protection rules or deployment-branch policy, and no dedicated `paid-runpod` Environment exists.

## GitHub Environment is a separate gate

A future `paid-runpod` Environment must contain `RUNPOD_API_KEY` as an environment-only secret, require an independent repository-owner reviewer, prevent self-review, and restrict deployment to the protected `main` branch. These settings must be read from GitHub and verified as fresh `RepositorySecurityEvidence`; their presence in repository policy YAML is not proof of live enforcement. Environment restrictions do not replace branch protection, and branch protection does not replace the Environment approval gate.

## Workflow supply chain

All third-party Actions in `.github/workflows/` must use full 40-character commit SHAs. Tests reject mutable tags and shortened SHAs.

`uv` bootstrap uses `astral-sh/setup-uv` pinned to a full commit SHA while requesting the repository's fixed `uv` version. Project dependencies continue to use `uv sync --locked`.

## Live enablement rule

Do not add or enable the paid workflow until branch protection evidence, owner identity, Environment protection, single-flight concurrency, provider account occupancy, immutable image evidence, fresh pricing, completion evidence, and cleanup guarantees are all present together.
