# Resource retirement inventory — 2026-11-12

This read-only inventory verifies that Vercel and Neon are not required by the
current ChatGPT product path and records what remains before resource deletion.
No database row contents, secrets, credentials, or tokens were read.

## Current Sites path

- Sites project `appgprj_6af482670c2081919ffe27a6faa0f746` is active at the
  existing URL. Its custom access policy has one allowed user, no groups, and
  zero external visitors. Version 11's deployment
  (`appgdep_6af4d87aee20819197c9ff12ed9e81fa`) reports `succeeded` and
  `has_mcp=true`; Versions 12 and 13 are saved but have not been deployed.
- Its D1 binding is `DB`, with `plans`, `runs`, and `runner_heartbeats` tables.
- The ChatGPT capabilities tool reports the Runner ready and the registered
  free `tiny-stories-inference-v1` CPU workload available, with a 30-second
  runtime ceiling and one in-flight run. This is the current control path;
  PostgreSQL is not required for it.
- A live recheck on 2026-11-12 completed and retrieved run
  `1fdfe901fda14798a42e33e492edd538` through ChatGPT. It generated four tokens
  in 155 ms, passed model digest, registered source, bounded-parameter, non-root,
  no-secret, no-Docker-socket, read-only-rootfs, and network-disabled checks;
  it reported `gpu_used=false`, `$0.00`, and confirmed cleanup. This verifies
  the current CPU route only, not cancellation or forced-restart recovery.

## Vercel

- Project `gpu-control` (`prj_fMufIBiFDlXtWcuJ0bWpAekEMIAp`) reports
  `live=false`; the latest deployment is `BLOCKED`. Three Vercel domains remain
  attached to the project metadata.
- No Vercel application is serving the current product path. The project and
  domains have not been deleted.
- PR #60's latest GitHub Actions run passes all six repository-required checks,
  while the Vercel integration still posts an optional `Vercel` status of
  `FAILURE` (`Deployment was blocked`). The required-check policy does not
  include Vercel, so this status does not block the Sites release path. It does
  confirm that the Vercel-to-GitHub project integration remains connected.
- Vercel's connected deletion flow returned `requires_user_action` and made no
  change. The owner can review the project deletion here:
  [Review gpu-control project deletion in Vercel](https://vercel.com/d?to=%2Funjunos-projects%2Fgpu-control%2Fsettings%2Fgeneral%23delete-project&title=Review+in+Vercel).

## Neon

- Project `delicate-smoke-00521013`, production branch
  `br-raspy-cell-b3l93n46`, has a suspended compute endpoint
  (`ep-small-night-b3a74joo`, `suspended_at=2026-11-11T19:47:02Z`). The project
  and stored database have not been deleted.
- Exact aggregate row counts on the production branch, queried without reading
  row contents on 2026-11-12:

  | Schema/table group | Rows |
  | --- | ---: |
  | `neon_auth.account`, `invitation`, `jwks`, `member`, `organization`, `session`, `user`, `verification` | 0 each |
  | `neon_auth.project_config` | 1 |
  | `public.gateway_oauth_bootstrap_v1`, `gateway_oauth_clients_v1`, `gateway_oauth_codes_v1`, `gateway_oauth_tokens_v1`, `gateway_runs_v1` | 0 each |
  | `public.gateway_control_v1`, `gateway_oauth_admin_v1`, `gateway_oauth_login_guard_v1`, `gateway_oauth_sessions_v1` | 1 each |

- The remaining session/config/control rows were not inspected or copied. They
  may contain security-sensitive state. There is no verified export and no
  verified D1 copy for those rows.
- A fresh read-only catalog review listed all 18 non-system tables and checked
  each table's schema only. The schemas confirm that some legacy tables can
  hold OAuth tokens, session values, auth signing keys, and provider identity
  data. No row values were selected. This review does not change the earlier
  aggregate counts or establish that the remaining rows are disposable.
- Neon project deletion has not been attempted. Deletion requires explicit
  owner confirmation because it permanently removes the legacy database and
  its remaining session/config/control state.

## Source provenance and Runner lifecycle refresh

- Sites Version 13 records source commit
  `52416ec02fcf3b755e1763edc617cd0a67f4ab91`. A fresh read-only fetch from the
  configured `cloudflare_artifact` source repository verified that its current
  `main` HEAD is the same commit. Version 13's source provenance is therefore
  reconciled; deployment and Runner replacement are still pending.
- The macOS Runner process is still running under PID 34930. The planned login
  Keychain entries (`runner-bearer` and `sites-service`) are absent, and the
  LaunchAgent is not loaded. Do not stop the current Runner until replacement
  credentials and the coordinated migration are ready.

## Decision

D1 is the active product database. Keep the Neon compute suspended and the
legacy rows untouched until the owner chooses between a deliberate fresh start
(discard all remaining legacy data) and an approved export/retention plan. The
old FastAPI/PostgreSQL Gateway source has since been removed from the working
tree. Its dated acceptance records remain historical; it is not a deployment
or rollback dependency for the Sites path.

## Post-Version-15 refresh — 2026-11-12

The earlier inventory above is a dated snapshot and is superseded for current
Sites and Runner state by this refresh:

- The private Sites deployment is Version 15, deployment
  `appgdep_6af5169fa69c8191b4dca5bb77272c84`, Sites source commit
  `e3cfaf71c5f084c6a6ab40adbae8e189327197ad`. The active D1 binding remains
  the product database; no PostgreSQL or Neon dependency was added.
- A post-deployment ChatGPT-originated CPU inference
  (`a1cdf7e9516b4a00802b6b606f228b08`) succeeded, its complete R2 artifact was
  retrieved and verified, container cleanup was confirmed, and cost was `$0.00`.
- The macOS LaunchAgent is already running. Both Keychain items are present
  (credential values were not read). The installed `run.py` and Keychain
  launcher hashes match the published source; plist/runtime file modes are
  `0600`. This supersedes the older PID 34930/no-Keychain snapshot above.
- The Neon project was not deleted. Its remaining session/config/control rows
  were not inspected or exported; retain the prior deletion boundary until the
  owner explicitly decides to discard them or authorizes a verified export.
- Vercel is not used by the product path. The current Sites candidate removes
  the Vercel entrypoint, deployment manifest, client-IP autodetection, and
  Vercel-specific CI bridge from the active runtime; provider adapters remain
  available for the roadmap and are not Vercel dependencies. Historical code
  and evidence are archived. GitHub still receives an optional `Vercel`
  failure status from the external Vercel-to-GitHub connection; this is not a
  repository workflow or a required check. The Vercel project and attached
  domains remain inactive and undeleted. The owner must confirm deletion in
  Vercel; the current review link is above. PR #67 is based directly on `main`
  and predates the Sites implementation in PR #60, so it is not the integration
  path and must not be merged as the Sites replacement.

## Vercel retirement recheck — 2026-11-12 03:27 UTC

- A fresh Vercel project read still reports `gpu-control` as `live=false`,
  framework `fastapi`, with latest deployment `BLOCKED` and SSO protection
  enabled. It lists three `vercel.app` aliases; the dedicated project-domain
  listing returns only the verified `gpu-control.vercel.app` domain. No
  user-owned custom domain was returned by that listing. Treat the alias
  discrepancy as unresolved metadata until deletion completes.
- PR #60 remains OPEN/DRAFT at `72564168cbcfc8d0e6e98df48b8d7a453486b3a0`,
  stacked on `codex/gpu-control-p1-dcr-v9-review`. Its six repository-required
  checks pass; the Vercel deployment status remains an optional failure
  (`Deployment was blocked`) and Vercel Preview Comments is successful.
- The Vercel connector verified the project and returned
  `requires_user_action`; no project change was made. To remove the remaining
  external integration and stop its status reports, the owner must review and
  confirm deletion at [the Vercel project deletion page](https://vercel.com/d?to=%2Funjunos-projects%2Fgpu-control%2Fsettings%2Fgeneral%23delete-project&title=Review+in+Vercel).

## D1 recovery-access check — 2026-11-12

- The private Site remains on Version 15. Its read-only database overview
  reports only the `DB` binding and user tables `plans`, `runs`, and
  `runner_heartbeats`; the Sites connector does not return the physical D1
  database ID or provide export/restore operations. No data rows were read.
- Wrangler 4.160.1 was run from a temporary npm execution context. A read-only
  `wrangler d1 list` could not authenticate in this noninteractive process
  because no `CLOUDFLARE_API_TOKEN` was supplied. No credential values were
  read or added to the repository.
- Cloudflare documents D1 Time Travel on the production backend, with 7 days
  on Workers Free or 30 days on Workers Paid; the Sites connector does not
  reveal this database's backend version or account plan. A Time Travel restore
  overwrites the selected database in place, so it is not a safe production
  rehearsal. See [Cloudflare D1 Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/).
- **Acceptance remains open:** verify the managed D1 backend/retention and run
  a restore rehearsal against an isolated D1 target. The required database
  identity and appropriately scoped Cloudflare access must be supplied through
  an approved secure path; live rows must not be exported into this repository.

## Vercel owner-removal handoff — 2026-11-12

- A fresh Vercel read reports the `gpu-control` project as `live=false`, with
  its latest deployment `BLOCKED`. Project metadata lists three `vercel.app`
  aliases; the separate domain endpoint returns only the verified
  `gpu-control.vercel.app` domain. The alias mismatch is unresolved, and no
  user-owned custom domain appears in the domain list.
- PR #60 identifies six required checks:
  Python 3.11, 3.12 and 3.13, Trusted reference container, Project bridge tests,
  and Sites Worker and D1 contract. Vercel is explicitly not required. Its
  Vercel is explicitly not required. On implementation head `e818a41`, the
  optional `Vercel` status was `FAILURE` (`Deployment was blocked`). The latest
  docs-only head `e99c8fd` also receives an optional Vercel failure, confirming
  the integration still runs even on documentation-only changes. Its GitHub
  Actions workflows `CI` and `Project bridge tests` both completed
  successfully. Removing the Vercel project will stop this non-required status
  without removing a required repository check under current PR policy.
- The Vercel connector cannot enumerate project connectors (its API returned
  `Connector Project not found`), so this was not treated as proof that no
  connector is attached. Project/domain metadata and the required-check list
  were inspected independently.
- The owner deletion handoff is
  [Review gpu-control project deletion in Vercel](https://vercel.com/d?to=%2Funjunos-projects%2Fgpu-control%2Fsettings%2Fgeneral%23delete-project&title=Review+in+Vercel).
  The connector returned `requires_user_action` and `mutationExecuted=false`;
  project deletion and integration cleanup are not yet complete.

## Runner-host orphan-container inventory — 2026-11-12

- The LaunchAgent reports `loaded`; its managed Runner and Keychain launcher
  processes are present. Sites capabilities report the Runner ready and free
  admission enabled. The D1 run list contains no active run.
- Docker lists 14 containers carrying the exact
  `io.unjuno.gpu-control.run-id` label namespace. All 14 are `exited`, were
  created between 2026-10-28 and 2026-11-02, and have zero mounts. Their run IDs
  are absent from the current D1 database: the authenticated status tool
  returned `RUN_NOT_FOUND` for each. No container environment, command output,
  or logs were read; no image or container was removed.
- These are orphaned historical containers, not active Site runs. They may
  retain container configuration and logs. Disposal remains pending owner
  choice; any cleanup must target only these 14 stopped containers and must
  leave images and unrelated Docker resources untouched.

## Runner heartbeat and sanitized transport-log recheck — 2026-11-12 13:03 JST

- A live Sites D1 read returned one `local-cpu-1` heartbeat at Unix time
  `1794456214` (13:03:34 JST), five seconds before the local check. Its image
  digest, source SHA, and cancellation protocol 1 match the registration. The
  Site capabilities tool independently reported `runner_ready=true` and free
  CPU admission enabled.
- The Runner log contained 13 fixed-code `SITE_REQUEST_FAILED` entries and no
  credential or response-body data. Its modification time was 10:47:12 JST;
  no later errors appeared by 13:03 JST. A successful inference and artifact
  retrieval completed after that log time. Treat these as historical transient
  failures, not proof of an ongoing outage; monitor again during the repeated
  recovery-window acceptance.

## Fresh provider retirement check — 2026-11-12 04:18 UTC

- Vercel's project API still reports `gpu-control` as `live=false`, framework
  `fastapi`, and latest deployment `BLOCKED`; SSO protection is enabled and
  project metadata still lists three Vercel aliases. On PR #60 head
  `fdb486f398d01810f8a0beb61af0c8e01bf2dbbe`, all six repository checks
  (Python 3.11/3.12/3.13, trusted reference container, Project bridge tests,
  and Sites Worker/D1 contract) completed successfully. The separate combined
  commit status contains only the failed `Vercel` status. The Vercel
  deletion-link operation returned
  `requires_user_action` and `mutationExecuted=false`; no Vercel resource was
  changed. Branch rulesets are empty, while the legacy branch-protection API
  returned 403, so required-check policy could not be independently refreshed
  through this connection.
- Neon project `delicate-smoke-00521013` has one primary/default `production`
  branch (`br-raspy-cell-b3l93n46`), logical size 31,670,272 bytes. Its sole
  read-write compute is `idle` and reports `suspended_at=2026-11-12T00:34:17Z`;
  the branch itself is `ready`. No SQL or row contents were read. Existing
  inventory counts still show one OAuth session, three singleton control/auth
  records, and one Neon Auth configuration row; their contents and required
  retention status remain unknown. No export, D1 copy, or deletion was made.
- The user's current architecture direction is Sites + D1/R2, with no Vercel
  or Neon product dependency. Removing these cloud resources is a separate
  retirement action: Vercel requires owner confirmation in its dashboard, and
  Neon deletion requires an explicit choice to discard its residual data or
  export it first. The Neon project remains idle pending that choice.
