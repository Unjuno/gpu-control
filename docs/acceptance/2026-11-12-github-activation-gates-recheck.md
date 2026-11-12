# GitHub activation gate recheck

Checked: 2026-11-12 09:37 UTC using authenticated, read-only GitHub API calls.

## `main` branch protection

- Strict required status checks are enabled:
  `Python 3.11`, `Python 3.12`, `Python 3.13`,
  `Trusted reference container`, `Project bridge tests`, and
  `Sites Worker and D1 contract`.
- One approving pull request review is required; stale approvals are dismissed.
- Admin enforcement is enabled.
- Code-owner review is not required.

## Deployment environments

- `Production` and `Preview` both exist.
- Both currently have zero protection rules and no deployment branch policy.
- GitHub's environment secret metadata endpoint returned zero secret names for
  both environments. Secret values were not read.

## Gate disposition

The repository policy remains `mode: parked`. Main CI and review enforcement
are present, but the paid environment lacks owner/reviewer and branch
restrictions, and no environment-scoped provider secrets are configured. These
gaps prevent treating RunPod or paid execution as activated. Do not weaken the
policy or enable paid admission to work around them. Resolve these controls
through the repository owner's approved settings and reviewed policy changes,
then re-read the live GitHub configuration before any provider canary.
