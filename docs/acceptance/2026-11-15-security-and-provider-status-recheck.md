# Security and provider status recheck — 2026-11-15 02:49 JST

## Local secret-pattern scans

- Gitleaks version **8.30.1** scanned the current checkout (`gitleaks dir`)
  and all Git history (`gitleaks git`, 1,150 commits), with `--redact=100`.
- The current tree returned five `generic-api-key` matches; full history
  returned twelve. The matched contexts were reviewed without printing secret
  values: four current code matches and three historical code matches are
  pinned TinyStories tokenizer SHA-256 digests; the remaining matches are
  test/idempotency literals and a documented `attacker-probe` header. No
  provider credential was identified among these matches.
- This does not clear findings outside Gitleaks' pattern coverage and is not a
  replacement for the repository-wide Codex P0 security scan.

## GitHub security configuration

- Repository `Unjuno/gpu-control` is public. Secret scanning and push
  protection are enabled.
- The dependency graph and Dependabot alerts are disabled. Dependabot security
  updates are also disabled. The user was asked whether to enable only the
  dependency graph and alerts; no setting change has been made pending their
  response.
- Code Scanning API returned `no analysis found` (404). Dependabot alert
  listing returned HTTP 403 because alerts are disabled and the current CLI
  credential lacks the `admin:repo_hook` scope.
- `main` enforces administrators, requires one approving review and approval
  after the latest push, and requires these six checks: Python 3.11, Python
  3.12, Python 3.13, Trusted reference container, Sites Worker and D1
  contract, and Project bridge tests.
- PR #68 remains open and Draft at `81a466554565f83a939fca71aab241214c449de1`;
  exact-head checks passed, but there is no independent PR review.

## Daybreak fallback

- The connected Daybreak workspace is eligible for a `$500` allowance, but its
  current `usage_status` is `available=false`, `outcome=credits_exhausted`.
- The connected GitHub repository was found as `Unjuno/gpu-control`. No listed
  Daybreak Cloud environment contains this repository, and environment
  creation is unavailable in the connected tool surface. No scan was launched.
- This result does not replace the Codex Deep Scan. Its last exact blocker is
  `Deep Scan cannot safely start a read-only worker: the parent must provide a
  managed filesystem permission profile.`

## Modal / RunPod boundary

- The last observed Modal Usage & Billing state remains `$0.10` in credits,
  `$0` in charges, and a `$1` Workspace limit. This is within the user's `$1`
  aggregate project-testing ceiling. No Modal deployment, health request,
  Sandbox, RunPod API call, or Pod allocation occurred in this recheck.
- Sites admission remains closed. The registered CPU run is still unaccepted;
  RunPod/GPU remains parked under `policies/repository-state.yaml`.
