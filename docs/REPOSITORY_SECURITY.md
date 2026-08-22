# Repository security boundary

Paid GPU execution remains disabled. Repository configuration is part of the future paid-compute trust boundary and must be verified independently from repository policy files.

## Protected main is mandatory

Before live paid authorization can succeed, a trusted preflight must read GitHub's actual repository and branch settings and produce `RepositorySecurityEvidence` proving that:

- `main` is protected;
- changes to `main` require a pull request;
- required status checks are enforced;
- required checks include `Python 3.11`, `Python 3.12`, `Python 3.13`, and `Trusted reference container`;
- force pushes are blocked;
- branch deletion is blocked.

`authorize_paid_execution(...)` rejects any live-enabled policy when this evidence is missing or incomplete. Setting `live_paid_compute_enabled: true` in YAML is therefore insufficient to enable billing.

At the time this document was added, the repository's actual `main` branch was not protected. Live compute must remain disabled until GitHub branch protection is configured. The connected GitHub automation interface does not currently expose a branch-protection mutation, so this repository cannot safely automate that account-level setting yet.

## GitHub Environment is a separate gate

A future `paid-runpod` Environment must contain `RUNPOD_API_KEY` as an environment-only secret, require the repository owner as reviewer, and restrict deployment to the protected `main` branch. Environment restrictions do not replace branch protection, and branch protection does not replace the Environment approval gate.

## Workflow supply chain

All third-party Actions in `.github/workflows/` must use full 40-character commit SHAs. Tests reject mutable tags and shortened SHAs.

`uv` bootstrap uses `astral-sh/setup-uv` pinned to a full commit SHA while requesting the repository's fixed `uv` version. Project dependencies continue to use `uv sync --locked`.

## Live enablement rule

Do not add or enable the paid workflow until branch protection evidence, owner identity, Environment protection, single-flight concurrency, provider account occupancy, immutable image evidence, fresh pricing, completion evidence, and cleanup guarantees are all present together.
