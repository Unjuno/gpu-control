# Project status

## Sites Version 32, environment revision 34, and current execution gates — 2026-11-13

- Production Site Version 32 is live at
  `https://gpu-control-sites.unjuno.chatgpt.site` from Site-source commit
  `7aacaac46a0111621d450c89a85fde7ce8cca6a2`; environment revision 34 and MCP
  are active. D1 contains `modal_authorized_health_checks`, the per-plan
  one-use reservation for separately billed Modal health diagnostics.
- The Worker requires the exact owner-confirmed `run_id` and plan fingerprint
  for a standalone Modal health call, checks unexpired unconsumed authorization,
  requires admission enabled, and reserves both a workspace cooldown and a
  unique plan row before calling Modal. No health call is made when admission
  is closed. The exact-plan confirmation remains one-use and expires within
  10 minutes.
- CPU admission is enabled for the fixed registered workload. ChatGPT
  capability read reports `available=true`, `provider_configured=true`,
  `human_authorization_store_ready=true`, and `admission_enabled=true`; provider
  readiness remains deferred until a plan-authorized submission. The runtime
  ceiling is 30 seconds, one in-flight run, estimated Sandbox cost $0.0013,
  and maximum Sandbox cost $0.01. Control-function charges are separate.
- Sites runtime values now advertise fingerprint
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec` and
  registered digest
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  The digest has not been reconciled with the locally rebuilt image or an
  authenticated Modal response. No current inference is accepted.
- Modal browser state shows the `gpu-control-sites` app with one inactive CPU
  control function, zero live function calls, and zero live Sandboxes. The app
  Details view exposes its resource configuration but not a trusted current
  OCI digest. Authentication/readiness and digest parity are still unverified.
- The current ChatGPT connector metadata still exposes the previous empty
  input schema for the separate provider-health diagnostic. Normal preparation
  and exact-plan submission remain the primary path; connector schema refresh
  for the optional diagnostic is unverified.
- The latest recorded Modal workload attempts failed with exit code 2 and
  cleanup confirmed, but predate the current Modal deployment. No inference
  has been run since that deployment.
- Modal Usage & Billing currently shows a $1 Workspace usage limit, $0.10 in
  credits used, $0 in charges, and an “Add payment method” action. This is a
  snapshot, not a durable no-charge guarantee. Modal documents the Workspace
  usage limit separately from the net spend limit and describes automatic
  monthly and incremental billing; see
  [Modal budgets](https://modal.com/docs/guide/budgets) and
  [Modal billing](https://modal.com/docs/guide/billing).
- Modal's API-token inventory is empty; the named main-environment Proxy Token
  remains available to the Site. No temporary Workspace API token is retained.
- PR #68 remains open and Draft. CI reruns on each push; preceding head
  `3e31de5` passed all six checks. The D1 migration test includes migration
  0008.
- Security diff review of this change found no source-level candidate
  vulnerability. Coverage is partial: live Sites identity-header provenance,
  cross-account denial, provider image/readiness, payment limits, and the
  connector's health schema remain unverified. Report:
  `~/.codex/state/plugins/codex-security/scans/gpu-control-pr58-current-candidate/d119bd791f26775b9887c79ec7315db7cda9f16a_20261113T121318Z_e9aj3n3p/report.md`.
- Next gates: obtain one-use owner confirmation for a fresh exact plan; verify
  the authenticated Modal preflight, inference artifact, provenance and
  cleanup; reconcile the deployed image digest; then complete independent
  cross-account denial and P0 security review. The live Modal UI showed the $1
  Workspace usage limit, $0.10 credit usage, $0 charges, and a prompt to add a
  payment method to raise the limit. Preserve that limit and the $0.01 Sandbox
  ceiling. RunPod GPU and paid training remain parked.
- Evidence: [Sites Version 32 and environment 34 acceptance](acceptance/2026-11-13-sites-v32-admission-enabled.md).

## ChatGPT Sites and Modal fingerprint refresh — 2026-11-13

- Reconciled the live Sites fingerprint environment key to the fixed Modal
  workload fingerprint and redeployed existing Site Version 31. Sites
  environment revision 33 is active; MCP remains enabled and admission remains
  `false`.
- ChatGPT capabilities now return the matching fingerprint, but still report
  `provider_ready=null`, `CPU_WORKLOAD_ADMISSION_DISABLED`, and
  `paid_execution=parked`. No provider health request or new Sandbox was
  started during this refresh.
- The two newest owned Modal Sandbox runs remain failed with
  `MODAL_WORKLOAD_EXIT_2`; cleanup is confirmed and neither produced an
  artifact. They predate the current fingerprint refresh and do not validate
  the refreshed path. Modal currently shows zero concurrent Sandboxes.
- Current Modal Usage Limit snapshot: `$1` Workspace usage limit, `$0.10`
  credit usage, `$0` charges. Recheck before any run. See
  [`ChatGPT Sites and Modal fingerprint refresh`](acceptance/2026-11-13-chatgpt-sites-modal-fingerprint-refresh.md).

## Authenticated Modal health diagnostic and Site publish — 2026-11-13

- Added the owner-allowlisted `experiment_provider_health` MCP operation. It
  makes an authenticated GET to Modal `/v1/health`, compares readiness, source,
  workload, digest, fingerprint and runtime limit, and explicitly reports that
  no Sandbox or inference was started. Its description discloses separately
  billed control-function requests; the MCP annotation does not mislabel this
  billable/stateful diagnostic as read-only or idempotent.
- A D1 atomic workspace-wide cooldown permits at most one health request per
  60 seconds. Migration `0007_modal_health_check_limit.sql` adds one shared
  limiter row without storing user IDs. D1 migration replay passed, Site Worker
  tests passed **32/32**, and Site build plus packaged-artifact validation
  succeeded. `git diff --check` passed.
- The candidate is on GitHub PR #68 and deployed as Sites Version 30 from
  Site-source commit `b97c5ceaad1d509c262d66a07015f74bb4e17546`; Version 31
  then republished the corrected source README from
  `7be42adca5306a7cd3d7ecd84718af47969dd9b0`. Both deploys succeeded with MCP
  enabled and environment revision 32; Version 31 has the same packaged
  Worker archive hash as Version 30. Live D1 now lists
  `modal_health_check_limits`; live admission remains false and the previously
  registered digest/fingerprint remain unchanged.
- The existing ChatGPT GPU Control connector still exposes its prior tool
  schema in this session, so the new diagnostic has not yet been invoked through
  ChatGPT. An anonymous public `tools/list` request received HTTP 401; no
  authentication was fabricated. No Modal health call or Sandbox was started
  from this change.
- Full deployment evidence and the exact remaining acceptance are recorded in
  [`Sites Version 30 acceptance`](acceptance/2026-11-13-sites-v30-modal-health-diagnostic.md).
- A follow-up failure-path regression now also proves a D1 limiter-write error
  prevents any Modal request. The worker suite is **33/33** after this addition;
  this changes tests only and does not alter the deployed Worker archive.

## Modal candidate deployment update — 2026-11-13

- PR #68 head `496e28cdb1b257c2a508e56a11fcdb07f6aa8028` is deployed to
  Modal `unjuno/main`. The first attempt exposed an image build-order error
  (`add_local_dir` after a non-copy local source); the fix copies the bootstrap
  into the API image. Full Python verification passed **573 tests, 1 skipped**;
  `git diff --check` passed. All six exact-head GitHub checks pass.
- Modal created API image IDs `im-4K01UJNs0MRcjkglisct1w` and
  `im-Z63nygRSH8lcUALSM2Pfrn`. This is deployment evidence only: unauthenticated
  `/v1/health` returned HTTP 401, and authenticated health/readiness and
  inference have not been verified. The imported source fingerprint is
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`;
  Sites still advertises `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`
  and digest `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  No trusted rebuilt OCI digest has been registered, so admission remains
  disabled and no Sandbox was started.
- Modal UI showed a `$1` Workspace cap, `$0.10` cycle usage, `$0` charges,
  `$1 of $30/mo` free credits, and zero live containers/Sandboxes. The temporary
  Workspace token was revoked; token inventory showed zero API tokens and its
  temporary config was deleted. During the first UI issuance, the token value
  appeared in tool output; it was not used and was immediately revoked. The
  subsequent CLI config had mode `0644`, but its token was also revoked and the
  config removed. No credential is retained.
- Details: [`Modal deployment and credential cleanup`](acceptance/2026-11-13-modal-main-deploy.md).

## Sites production reconciliation — 2026-11-13

- Sites Version 29 is now deployed from the GitHub candidate's synchronized
  source. The Site-only source commit is
  `6144d58acf6de609c8ac42d0b06542e29d89b1ab`; production environment revision
  remains 32. The publish applied D1 migrations 0005–0006; the live schema
  overview now includes `authorization_challenges`, `human_authorizations`,
  `provider_account_leases`, and `provider_account_lease_events`.
- Fresh ChatGPT capabilities confirm the exact-plan authorization flow is
  present and the owner authorization store is ready. Admission remains
  `false`; capabilities report unavailable with
  `CPU_WORKLOAD_ADMISSION_DISABLED`. Worker error logs were empty in the
  five-minute post-deploy window. No inference or D1 row read/write was made.
- The synchronized archive SHA-256 is
  `e1a7a2666e895df1133a7ef1690e8ac1a54fff9ec67cc81c8fd8a0ad21b0092a`.
  Site-source `npm test` passed 30/30, and build and validation succeeded.
  Modal showed zero live Sandboxes and zero running control calls; no provider
  compute was started. See
  [`Sites Version 29 production acceptance`](acceptance/2026-11-13-sites-v29-production-deploy.md).
- PR #68 remains Draft at GitHub head `496e28cdb1b257c2a508e56a11fcdb07f6aa8028`;
  all six exact-head checks pass. The Site-only deploy commit is separate from
  GitHub history. Modal's rebuilt
  OCI image digest and fingerprint still do not match the current candidate,
  and the independent-account browser check, independent PR review, repository
  P0 audit, Modal image readiness, and post-deploy authorized inference remain
  open. Keep admission closed.
- Recomputed the Modal candidate fingerprint by importing the checked-out
  `app.py` under its pinned Modal/FastAPI dependencies: current source yields
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`.
  Earlier current-state notes listed `0fc60d18…`; that value is stale for
  this exact checkout. Live Sites still advertises `3bf90f4c…`.

## Build backend dependency pin — 2026-11-13

- PEP 517 requirements now pin setuptools and wheel, and `build-constraints.txt`
  pins and hashes their build dependencies. CI verifies the build before
  syncing the locked environment. Local verification on uv 0.11.17 passed:
  `uv lock --offline`, hash-checked `uv build`, locked offline sync, and the
  complete Python suite (**573 passed, 1 skipped**). At code commit `cc076b8`,
  all six exact-head CI checks passed using the repository-pinned uv 0.10.0;
  the exact-range Codex Security diff scan reported zero findings. This is not
  the repository-wide P0 audit.
- See [`build backend lock acceptance`](acceptance/2026-11-13-build-backend-lock.md).

## Current goal recheck — 2026-11-13 05:46 UTC

- PR #68 remains open as Draft, with no independent GitHub review. Current
  source update is the migration replay test; subsequent commits only update
  documentation. The latest full six-job CI run passed Python 3.11, 3.12,
  3.13, Sites Worker/D1 contract, Project bridge tests, and trusted reference
  container. No independent review is recorded.
- A fresh Semgrep 1.161.0 `p/security-audit` scan reported one warning at
  `project_control/runner.py:147`, the documented SHA-1 use for Git blob object
  ID compatibility with `usedforsecurity=False`.
- A fresh redacted, worktree-only Gitleaks scan found five
  `generic-api-key` matches: four `TOKENIZER_SHA256` checksum occurrences in
  source/generated code and one test-only completion-key fixture. No live
  credential was verified. This scan did not cover Git history; the earlier
  full-history scan's 11 reviewed matches is recorded above.
- The Sites source reconciliation and read-only D1 overview found production
  Version 28 source drift and missing human-authorization tables. The live
  submit route remains unsafe to call; production environment revision 32
  explicitly keeps admission `false`. Modal secret values were not returned by
  the environment reader. See
  [`2026-11-13 Sites source reconciliation`](acceptance/2026-11-13-sites-source-reconciliation.md).
- Static scans of the separately fetched deployed Version 28 source completed:
  Semgrep `p/security-audit` reported 0 findings; redacted Gitleaks reported
  three `TOKENIZER_SHA256` 64-character hex checksums and no verified provider
  credential. These scans cover the deployed source snapshot only and do not
  close the P0 audit.
- Added a SQLite replay regression covering migrations 0000–0005 and synthetic
  existing D1 rows; `uv run --locked pytest` passes 573 tests with 1 skipped.
  This proves migration compatibility on local SQLite, not on live D1.
- Sites applies hosted D1 migrations before Worker upload; failed deployments
  may leave the schema advanced. Migration 0005 is additive, and the runbook
  now requires deployment/schema reconciliation before retry instead of manual
  reapplication or rollback.
- Repository-wide Codex Deep Scan and independent review remain incomplete.
  Local scans and green CI are not substitutes for either.

## Dependency audit and remediation — 2026-11-12 17:31 UTC

- PR #68 is open as Draft. The dependency fix at code head
  `7b16186cd35c621a33f550efded78aabe63a64d4` passed all six required
  exact-head checks, including the new audit step in Python 3.12. No independent
  review is recorded.
- Fresh ChatGPT capabilities still report Modal health ready but
  `admission_enabled=false`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`. Run `e9330c5bb5454f42bb3dabe058091dc0`
  remains failed with confirmed cleanup and no artifact. Earlier successful
  records predate retirement of the local Runner and do not establish current
  Modal success.
- The signed-in Modal UI shows a `$1` Workspace limit, `$0.07` credits used,
  `$0` charges, and zero deploy API tokens. No app deployment, setting change,
  or provider run occurred in this refresh.
- Dependency audit found 10 advisory records (five distinct advisories) for
  Starlette in the previous Modal API image dependency resolution
  (`fastapi==0.128.2` selected `starlette==0.50.0`). The candidate API image
  now installs a hash-locked dependency
  set from `sites/gpu-control-sites/modal/requirements.txt`, generated from
  `requirements.in` with FastAPI `0.162.2` and Starlette `1.10.0`. A fresh
  pip-audit scan of 42 development and Modal API packages found no known
  vulnerabilities. CI now audits both locked dependency sets in the required
  Python 3.12 job. The findings correspond to Starlette's [advisory list](https://github.com/Kludex/starlette/security/advisories);
  the fixes are documented in its [release notes](https://github.com/Kludex/starlette/blob/main/docs/release-notes.md).
  This candidate change has not been deployed.
- The whole-repository Codex Deep Scan remains incomplete because the current
  host still lacks its required managed read-only filesystem profile. Do not
  treat dependency scanning or local Semgrep/Gitleaks checks as a replacement.

## Local security-tool refresh — 2026-11-13

- PR #68 already exists as a Draft and currently points at this checkout's
  exact head `9cdb8eb88e6eca9c8384045ce87ea269a65ba848`; creating another Draft
  would duplicate the same candidate. The GitHub API confirms the PR is open,
  based on `codex/gpu-control-p1-dcr-v9-review`, and its six required exact-head
  checks are green.
- A local Gitleaks scan across the full Git history reported 11
  `generic-api-key` matches. All 11 were inspected without treating their
  strings as credentials: they map to pinned SHA-256 checksums, test-only
  fixtures/idempotency values, or synthetic encoded test data. No live
  credential was verified. This is a reviewed false-positive set, not proof
  that all secret exposure risks are absent.
- A local Semgrep `p/security-audit` scan parsed about 100% of 254 tracked
  files (50 excluded by `.semgrepignore`) and produced one warning for SHA-1
  in `project_control/runner.py`. That code reproduces GitHub Contents API's
  Git blob object ID solely for source-integrity matching; it is not used for
  signatures, credentials, or security tokens. The official API example links
  `sha` to the Git blob endpoint. The code now sets `usedforsecurity=False` and
  documents the purpose. Semgrep still reports the rule because it does not
  account for that flag; the warning remains visible and reviewed rather than
  suppressed. All 19 Project Control unit tests pass.
- GitHub Code Scanning has no analysis recorded, and Dependabot alerts are
  disabled. The Codex Security repository-wide P0 scan remains unstarted
  because the active session lacks its required managed read-only filesystem
  profile. These local checks do not replace that audit or an independent PR
  review.

## Live refresh — 2026-11-13 17:05 UTC

- PR #68 is open as Draft at head
  `e816eae970f9fe04443c1e56708a4f3a3a8ae9d5`, stacked on
  `codex/gpu-control-p1-dcr-v9-review`. All six required exact-head GitHub
  checks passed. It still has no independent approval and remains Draft.
- Current PR changes include historical execution-origin labels, bounded Modal
  exit-2 preflight diagnostics, a D1 cancellation/finalization guard, and
  regression coverage for the real workload's missing-identity guard.
  Local verification passed: Sites Worker 25/25, Modal bootstrap 5/5, build,
  Site artifact validation, and `git diff --check`.
- The focused Codex Security diff scan
  `ce9035fb-329e-4b5d-a51b-d5a00c895286` reviewed the Worker, its tests, and
  the acceptance record; it reported zero findings. It is not the P0
  repository-wide audit and does not cover the latest PR changes. A new diff
  scan attempt did not start and returned no scan ID.
- The `gpu-control-sites` Site remains public at Version 28, source commit
  `237c0bed24277cf7c808f8c0e9946c71d517288c`, environment revision 32. The
  current PR patch has not been deployed to Sites, and live `experiment_list`
  responses still omit `execution_origin`. Production remains on the prior
  response contract.
- A fresh ChatGPT capability read reports Modal provider health ready, but
  `admission_enabled=false`, `available=false`, and
  `CPU_WORKLOAD_ADMISSION_DISABLED`. Recent live run history still includes
  five Modal failures and older successes attributed to the retired local
  Runner. The latest run `e9330c5bb5454f42bb3dabe058091dc0` remains failed
  with `MODAL_WORKLOAD_EXIT_2`, cleanup confirmed, and no artifact. The live
  fingerprint is `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`;
  the current PR Modal candidate computes
  `0fc60d1890c26a646330a0d848750a0dedc03ff8a56a6e6dd214dba1e3471560`.
  The candidate is not deployed; no deployment, D1 write, or provider run was
  performed in this refresh.
- The Sites runtime environment inventory has no `RUNNER_BEARER_TOKEN` or
  `RUNNER_SERVICE_TOKEN` key; Sites masks secret values, so this records key
  names only. The current checkout has no tracked macOS Keychain launcher or
  LaunchAgent manager, and the host has no matching GPU Control launchd job or
  Runner process. Historical D1 `runner_heartbeats` and run records are kept as
  data evidence. `project_control/runner.py` is a separate GitHub Project
  bridge component, not the retired personal-host compute Runner.
- The P0 Deep Security Scan remains unstarted because this active session does
  not provide the required managed read-only filesystem profile. Cross-account
  Sites identity isolation, D1/R2 restore and retention, and current Modal
  execution acceptance remain open. RunPod/GPU and paid execution remain
  parked under `policies/repository-state.yaml`.

## Main branch protection refresh — 2026-11-12 15:56 UTC

- GitHub owner settings show a classic protection rule for `main`. It requires
  pull requests, one approval, dismissal of stale approvals, and approval of
  the latest reviewable push by someone other than its pusher. It requires
  these six checks: `Python 3.11`, `Python 3.12`, `Python 3.13`,
  `Trusted reference container`, `Project bridge tests`, and
  `Sites Worker and D1 contract`.
- The rule also requires the branch to be up to date, all review conversations
  to be resolved, and linear history; it applies to administrators and
  prohibits force pushes and branch deletion. The rulesets API returned an
  empty list, so the protection is the classic branch rule visible in the owner
  UI. The API's 403 did not establish that protection was absent.
- PR #68 is stacked on `codex/gpu-control-p1-dcr-v9-review`, not directly on
  `main`; the main rule describes the eventual merge gate. PR #68 remains Draft
  and has no independent review submissions, so it does not yet satisfy the
  one-approval rule.

## CI compatibility refresh — 2026-11-12 15:52 UTC

- PR #68 code branch head `2ca43d18d364213d4aa74b996d746bd643b7966a`
  upgrades the pinned `actions/setup-node` from v6.0.0 to official immutable
  v7.1.0 commit `949feb2413d6458794dcd2491c4babbbce0c15c1`, addressing the
  GitHub Actions Node 20 deprecation warning.
- Exact-head CI and Project bridge tests both passed on `2ca43d1`; all six
  reported checks succeeded and the prior Node runtime warning was absent.

## Current checkout and live capability refresh — 2026-11-12 15:48 UTC

- At the 15:48 UTC observation, PR #68 was at head
  `ac8efc265021e4dfe6d9169ef0c4a3b7e417229a` on `codex/sites-modal-runner`,
  matching `origin`; that commit updates only operations documentation. The
  latest code commit is
  `504e492ec2e03f79a94cfad41729d6e30531f598`, which adds
  `gpu_control_modal_bootstrap` to the Modal API image after the earlier
  `67f60a2` bounded Sandbox exit-marker change. PR #68 remains open as a Draft
  against `codex/gpu-control-p1-dcr-v9-review`.
- The code commit's exact-head GitHub runs passed: CI `43249691251` and Project
  bridge tests `43249691590`. No checks were created for the documentation-only
  head `ac8efc2`. A Security Review of the one-line image-packaging change found
  no issue; this is not an independent review of the full PR. No full-PR review
  is recorded.
- The ChatGPT Sites capability tool reports Modal provider health ready,
  admission disabled, and availability false with
  `CPU_WORKLOAD_ADMISSION_DISABLED`. Live Sites still expects fingerprint
  `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`; the
  current Modal candidate computes
  `0fc60d1890c26a646330a0d848750a0dedc03ff8a56a6e6dd214dba1e3471560`.
  The candidate has not been deployed and the Sites environment has not been
  updated to the candidate fingerprint.
- Latest run `e9330c5bb5454f42bb3dabe058091dc0` is still failed with
  `MODAL_WORKLOAD_EXIT_2`, cleanup confirmed, and no result or artifact.
  Modal's app overview shows 0 live containers and 0 live Sandboxes (5 Sandbox
  creations in the last 24 hours); no Sandbox was started during this refresh.
- Modal Usage & billing shows `$0.07` in credits, `$0` in charges, and a `$1`
  Workspace usage limit. The API-token page shows 0 tokens. The earlier `$0.05`
  snapshot is superseded; no token was created in this refresh.
- The repository-wide P0 Deep Security Scan did not start: the scanner requires
  a managed read-only filesystem permission profile, which was unavailable in
  the current session. Do not treat the one-line diff review as the P0 audit.
- Deployment and another Sandbox run remain unperformed. Modal admission is
  still closed; RunPod/GPU execution remains parked.

## Live branch refresh — 2026-11-13

- PR #68 remains open as a Draft, based on `codex/gpu-control-p1-dcr-v9-review`;
  head `67f60a2b39fd08840173e07fe6a049a1b3a66bec` adds a fixed Modal bootstrap
  marker for `SystemExit(2)`. Its PR-triggered CI (`43246512972`) passed the
  Python 3.11–3.13 matrix, trusted reference container, and Sites Worker/D1
  contract jobs; Project bridge tests (`43246512950`) also passed. No PR reviews
  are recorded yet.
- A Codex Security diff review of the four tracked code changes reported no
  findings. The new Python bootstrap test was manually inspected but was
  untracked and omitted from that scan's inventory. This is not the repository-
  wide P0 audit; that audit still requires a managed read-only filesystem
  profile, which this active session does not provide.
- Current ChatGPT capabilities remain `provider_ready=true`,
  `admission_enabled=false`, and `available=false`. Live Site registration
  advertises Modal fingerprint `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`;
  PR #68's bootstrap source computes `0fc60d1890c26a646330a0d848750a0dedc03ff8a56a6e6dd214dba1e3471560`.
  The Modal deployment and Site environment have not been updated to the new
  fingerprint, and no new Sandbox was started.
- Latest run `e9330c5bb5454f42bb3dabe058091dc0` remains failed with
  `MODAL_WORKLOAD_EXIT_2`, confirmed cleanup, and no result artifact. The new
  bootstrap marker has not yet been deployed or validated end to end.
- Modal's current Workspace cap is `$1`, with `$0.05` credits used and `$0`
  charges; API token inventory is empty. These facts do not authorize a run.
- The current checkout contains no tracked Keychain Runner implementation or
  active Sites Worker route for RunPod. A local process query found no matching
  Runner process. RunPod/GPU and paid execution remain parked.
- The GitHub integration returned 403 for branch-protection details and the
  rulesets API returned an empty list in that API read. A later owner-UI read
  confirmed the classic `main` protection rule documented above.

The full delivery objective remains open: complete the repository-wide P0
audit, obtain independent PR review, deploy and verify the fixed Modal
diagnostic, secure the exact-plan CPU run, complete recovery and cross-account
acceptance, then separately implement and validate the RunPod GPU path.

## Hosted Sites and provider status — refreshed 2026-11-12

Latest verified capability — 2026-11-12 13:46 UTC: the public ChatGPT Sites MCP Worker is
deployed as Version 28 from Site source commit
`237c0bed24277cf7c808f8c0e9946c71d517288c`, with production environment
revision 32 and D1/R2. The live ChatGPT capability read reported
`provider_ready=true`, all provider identity/health checks true,
`admission_enabled=false`, and `available=false` for `modal_cpu`. Paid
execution remains parked. The owner's ChatGPT connection has called the Site;
cross-account plugin access remains unverified.

The refreshed ChatGPT tool signature accepts
`experiment_prepare.max_cost_usd=0.01`, matching the usage-billed Sandbox
ceiling. The 15-second bounded Modal request timeout is deployed. The one
authorized one-token run `e9330c5bb5454f42bb3dabe058091dc0` failed with
`MODAL_WORKLOAD_EXIT_2` after 247 ms; Modal Sandbox
`sb-01M77ZZRFC1090CXA2W3MHDH7V` had no logs. Sites confirmed cleanup, but no
result or artifact was produced and the expected preflight line marker was
absent. Environment revision 32 has admission false; capabilities are ready but
unavailable. Another attempt needs a new exact-run authorization after a useful
diagnostic change.

An earlier 16-token ChatGPT-initiated Modal Sandbox run
`b3380814d0854d93a5d978799d670013` failed with exit code 2; cleanup was
confirmed and no artifact was produced. A fresh read-only history check also
found an earlier failed run `0f2a3ddaa7da40648600bae21ccd9ed1` at 11:25 UTC
with the same exit code and confirmed cleanup; its deployment/authorization
provenance is unknown. Modal Usage last showed a `$1` Workspace limit,
`$0.04` credits used, and `$0` charges at 12:35 UTC. The bounded preflight
diagnostic from `d1dd4fe` was deployed to Modal `unjuno/main` at 12:49 UTC;
the CLI returned success and the dashboard showed the app deployed just now
with zero live containers and zero live Sandboxes. The later authorized
diagnostic attempt and current admission state are recorded in the current
operational snapshot above. The one-hour Workspace deploy token was deleted
immediately after deployment; reloading the API-token page showed zero tokens.

The Modal dashboard's deployment timeline showed v4 at 2026-11-12 18:06 JST,
but its history row did not identify a source commit. The successful ChatGPT
run `eacc26ff2ad54cf69a1ee7665325b197` generated four tokens in 142 ms and its
complete R2 artifact was verified, but the run was performed by the local
Runner under Sites Version 16; it is not Modal evidence. Two Modal runs
(`96d7efef9542463d9fc51f47ffbfd5d7` and
`599473dcc1ed4034a42d849bcb42e261`) failed with cleanup confirmed before v4.
No successful inference after v4 is recorded. Site Version 24 now stores a
bounded Modal exit-code failure code without provider stderr, but no live run
has tested that diagnostic. A fresh ChatGPT capability read reports provider
health ready, admission disabled, and unavailable. Modal's account page
previously showed `$0.01` usage this cycle. The earlier temporary deploy token
was deleted; Modal's API-token page showed zero tokens after each revocation.
The Sites Worker has no
RunPod route; live RunPod and paid GPU execution remain parked.

The personal-host CPU Runner and its Keychain authentication path are retired.
Do not restore them. Older TinyStories successes remain historical evidence;
they do not establish current Modal execution success.

Before retirement, a ChatGPT-originated TinyStories 15M inference completed on
Sites Version 15 after a Runner process-loss recovery test.
Run `aa45b7d899de4c9aaff2ee73fa985cc6` used the registered workload source commit
`3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288` and image
`sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
With prompt `A little bird found a bright blue feather.`, seed `719243`, and an
8-token limit, it generated 8 tokens in 291 ms, passed identity/sandbox checks,
returned `gpu_used=false`, and confirmed cleanup at `$0.00`. Its complete
999-byte R2 artifact was retrieved through ChatGPT; its locally computed
SHA-256 matches D1 metadata. A separate active-run process-loss probe expired
after 180 seconds and recovered as `runner_lost_recovered` with cleanup
confirmed, no retry, and no leftover container. A follow-up inference proved
the free CPU slot was available again.

This does not establish general model quality, repeated crash-window coverage,
cross-owner isolation, or GPU capability. The local Runner result is historical;
the two Modal failures predate v4, and there is no accepted post-v4 inference.
Modal recovery and real RunPod GPU acceptance remain open. Full evidence and gates are tracked in
[`decisions/2026-11-11-sites-d1-architecture-pivot.md`](decisions/2026-11-11-sites-d1-architecture-pivot.md).
The current staged plan is [`SITES_MODAL_RUNPOD_DELIVERY.md`](SITES_MODAL_RUNPOD_DELIVERY.md).
Run evidence: [`Modal and CPU inference chronology`](acceptance/2026-11-12-modal-and-cpu-inference-chronology.md).

The rest of this document records standalone CLI and provider-adapter status on
`main`; it does not supersede the hosted Sites acceptance snapshot above.

This document describes what `gpu-control` on `main` can do today. It deliberately distinguishes implemented offline/control-plane contracts from live paid GPU execution.

## Readiness summary

| Capability | Status | Notes |
| --- | --- | --- |
| Installable standalone CLI | Ready | Python 3.11+, locked dependencies, offline self-test. |
| Request/resource-policy validation | Ready | `gpu-control validate`; no network or GPU required. |
| Public GitHub source verification | Ready | `gpu-control verify-source`; verifies public repository, exact 40-character SHA, and Dockerfile path. |
| Synthetic provider contract self-test | Ready | `gpu-control provider-self-test`; no network or billing. |
| Trusted repository-owned container isolation fixture | Ready | CI exercises a bounded, secret-free reference container. |
| Generic external workload container execution | Not enabled | External Dockerfiles are not generally executed by this repository yet. |
| Decision/context security policy | Ready at policy/CI level | Action constitution, source-to-sink trust policy, failure catalog, and adversarial fixtures are present. |
| Approved execution plan contracts | Ready offline | Immutable/fingerprinted plans, pricing evidence, durable lifecycle state, cleanup state, and bounded result manifests are implemented. |
| Structured exact human authorization | Ready for RunPod adapter boundary | Runtime validator and expiring `LiveExecutionPermit` exist; RunPod adapter construction/submission requires the exact unexpired permit. End-to-end paid workflow wiring remains absent. |
| Current RunPod REST v2 transport layer | Ready offline | Fixed `api.runpod.io/v2` client, cursor-paginated List Pods with bounded complete inventory, v2 create/get/delete, trusted Network Volume attachment, and response identity checks are mock-tested. |
| Current RunPod pricing/availability evidence | Ready offline | Fixed REST v2 GPU catalog, secure price/capacity, VRAM, exact Network Volume datacenter, HIGH stock, 300-second maximum TTL, and content-digest binding are mock-tested. |
| RunPod REST v2 provider adapter | Ready offline for selected canary | Canonical v2 adapter requires current pricing evidence, exact Network Volume DC, unexpired live permit, and v2-backed occupancy/reconciliation before create. |
| RunPod ambiguous create/cleanup reconciliation | Ready offline on REST v2 transport | Bounded occupancy/reconciliation consumes every cursor page and remains fail-closed. Provider behavior and cleanup remain unverified live. REST v1 is retained for offline compatibility only and is forbidden for live calls. |
| Authenticated Orbitune completion v3 | Ready offline | Root signer binds exact result bytes and the observed process exit code into HMAC-SHA256 evidence; legacy v2 remains only during migration. |
| RunPod Network Volume/S3 result transport | Ready offline | Fixed RunPod S3 origin, trusted `/outputs` mount, exact two-object bounded collection, and v3 authentication are mock-tested. Live verification and real credentials/volume are pending. |
| Orbitune paid-canary result acceptance | Ready offline | Workload-specific acceptance accepts authenticated log-v2 or durable volume-v3 evidence and remains separate from provider cleanup/finalization. |
| Pre-cleanup result capture/finalization | Ready offline | Provider-neutral ephemeral-result capture is durable and bounded. |
| Production Pod-log SSE | Unavailable | Current RunPod evidence records the Pod-log SSE operation as dev-only/unavailable in production; it is not used as the live result path. |
| Paid GitHub Actions workflow | Not present yet | `main` contains CI and dry-run workflows only. It must not be added/enabled until external GitHub gates and initial live provider verification are complete. |
| Live paid GPU execution | Disabled | Repository state is `parked`; paid/provider/result live flags remain off. |

## Current selected canary

The repository currently records this canary workload:

- repository: `Unjuno/orbitune`
- source SHA: `fc131174a9b529a9825f54fccf1a7df4c63c9a1a`
- Dockerfile: `workloads/runpod-training-canary/Dockerfile`
- workload id: `orbitune-runpod-training-canary-v1`
- GPU profile: `cheap-24gb`
- maximum runtime: 30 minutes
- maximum cost ceiling: USD 0.30
- completion protocol: `gpu-control-hmac-sha256-v3`
- exact-main full pytest run: `33313993621` — passed
- exact-main RunPod canary smoke run: `33313993623` — passed

The source CI, signer isolation, current REST v2 adapter contract, current v2 price/DC-stock contract, and central offline volume-transport tests have passed in earlier candidate runs. The legacy v3 workload-signing design is now disabled because its signing key had been exposed to the Pod. That does **not** mean the control plane is authorized to spend money today.

## Durable result transport

The Pod-log limitation has a candidate durable-transport implementation, but secure completion acceptance remains blocked:

1. a pre-existing RunPod Network Volume is mounted at trusted path `/outputs` when the Pod is created;
2. the workload writes `result.json`; legacy workload-signed `completion-v3.json` is not trusted because the old key was exposed;
3. the Pod may exit and be cleaned up without destroying the Network Volume;
4. the control plane can read bounded objects through RunPod's S3-compatible API;
5. RunPod v2's Pod schema has no documented process exit code, and controller-owned signed observation receipts are not implemented;
6. therefore the current transport must not promote an exited workload to `SUCCEEDED` or `FAILED`.

The transport is implemented and mock-tested, but not yet live-verified. Network Volume creation/resizing is deliberately not automated because it is a persistent billable resource.

## Provider-control and pricing path

The selected RunPod path has offline/mock components from price selection through result collection, but end-to-end result acceptance is gated:

- current GPU price and VRAM come from the fixed-origin REST v2 GPU catalog;
- exact per-datacenter stock is checked for the Network Volume datacenter;
- current price/DC evidence is short-lived and content-digest bound;
- the approved plan carries the exact price/reference/time window;
- `RunPodV2CurrentAdapter` rechecks that evidence and the Network Volume DC immediately before submission;
- current REST v2 creates the Pod and cursor-paginated v2 List Pods backs account occupancy/reconciliation;
- durable Network Volume/S3 collection exists, while secure completion acceptance is disabled pending a controller-owned protocol;
- cleanup remains explicit and reconciliation-backed.

No live provider call is enabled. Provider live verification must wait until the secure completion protocol is implemented and reviewed; real account evidence alone cannot close that code-level blocker.

## Why live paid execution is still disabled

`policies/repository-state.yaml` remains the source of truth. Important remaining activation requirements include:

- protected `gpu-control/main` with required CI checks;
- control-plane context integrity and prompt/context gates;
- an owner-only protected `paid-runpod` Environment;
- Environment-scoped `RUNPOD_API_KEY` plus separate RunPod S3 credentials;
- a pre-existing Network Volume in a supported S3 datacenter;
- immutable published canary-image identity;
- live read-only verification of current pricing, exact-datacenter stock, and account occupancy;
- live verification of ambiguous-create, result collection, and cleanup reconciliation;
- protected paid-workflow wiring that constructs the exact current `LiveExecutionPermit` from trusted runtime evidence.

The 2026-10-31 GitHub API audit confirms `main` is protected with the seven
required Actions checks, one approval including approval after the last push,
strict/up-to-date checks, conversation resolution, linear history, and admin
enforcement. This satisfies the branch-protection prerequisite only; P1 PR #52
still awaits its independent approval. The same audit found no Environment
protection rules or deployment-branch policy on `Production` or `Preview`, and
no dedicated `paid-runpod` Environment. Do not treat repository access, a
successful dry-run, or available budget as authorization to spend money.

## What "ready" means here

A feature marked **Ready** is usable from `main` for the stated offline/read-only purpose. It does not imply that a downstream live provider action is enabled.

**Offline/mock only** means executable code and tests exist but no real provider credential or billable action was used to verify it.

**Live disabled** means policy intentionally prevents provider calls even if local code could otherwise construct them.

## Source of truth

When documentation and machine state differ, prefer:

1. `policies/repository-state.yaml` for current activation state;
2. `policies/paid-execution-policy.yaml` for paid-path identity/security requirements;
3. `policies/runpod-v2-policy.yaml` for the current Pod-control and pricing contract;
4. `policies/runpod-rest-v1-policy.yaml` for legacy offline compatibility state;
5. tests and current `main` implementation for executable behavior.
