# Resource retirement inventory — 2026-11-12

This read-only inventory verifies that Vercel and Neon are not required by the
current ChatGPT product path and records what remains before resource deletion.
No database row contents, secrets, credentials, or tokens were read.

## Current Sites path

- Sites project `appgprj_6af482670c2081919ffe27a6faa0f746` is active at the
  existing URL. Its custom access policy has one allowed user, no groups, and
  zero external visitors. Version 9's deployment reports `succeeded` and
  `has_mcp=true`.
- Its D1 binding is `DB`, with `plans`, `runs`, and `runner_heartbeats` tables.
- The ChatGPT capabilities tool reports the Runner ready and the registered
  free `tiny-stories-inference-v1` CPU workload available, with a 30-second
  runtime ceiling and one in-flight run. This is the current control path;
  PostgreSQL is not required for it.

## Vercel

- Project `gpu-control` (`prj_fMufIBiFDlXtWcuJ0bWpAekEMIAp`) reports
  `live=false`; the latest deployment is `BLOCKED`. Three Vercel domains remain
  attached to the project metadata.
- No Vercel application is serving the current product path. The project and
  domains have not been deleted.
- Vercel's connected deletion flow returned `requires_user_action` and made no
  change. The owner can review the project deletion here:
  [Review gpu-control project deletion in Vercel](https://vercel.com/d?to=%2Funjunos-projects%2Fgpu-control%2Fsettings%2Fgeneral%23delete-project&title=Review+in+Vercel).

## Neon

- Project `delicate-smoke-00521013`, production branch
  `br-raspy-cell-b3l93n46`, has a suspended compute endpoint
  (`ep-small-night-b3a74joo`, `suspended_at=2026-11-11T19:47:02Z`). The project
  and stored database have not been deleted.
- Aggregate-only row counts on the production branch:

  | Schema/table group | Rows |
  | --- | ---: |
  | `neon_auth.account`, `invitation`, `jwks`, `member`, `organization`, `session`, `user`, `verification` | 0 each |
  | `neon_auth.project_config` | 1 |
  | `public.gateway_oauth_bootstrap_v1`, `gateway_oauth_clients_v1`, `gateway_oauth_codes_v1`, `gateway_oauth_tokens_v1`, `gateway_runs_v1` | 0 each |
  | `public.gateway_control_v1`, `gateway_oauth_admin_v1`, `gateway_oauth_login_guard_v1`, `gateway_oauth_sessions_v1` | 1 each |

- The remaining session/config/control rows were not inspected or copied. They
  may contain security-sensitive state. There is no verified export and no
  verified D1 copy for those rows.
- Neon project deletion has not been attempted. Deletion requires explicit
  owner confirmation because it permanently removes the legacy database and
  its remaining session/config/control state.

## Decision

D1 is the active product database. Keep the Neon compute suspended and the
legacy rows untouched until the owner chooses between a deliberate fresh start
(discard all remaining legacy data) and an approved export/retention plan. The
old FastAPI/PostgreSQL Gateway remains historical reference code and is not a
deployment or rollback dependency for the Sites path.
