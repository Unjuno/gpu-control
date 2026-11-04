# PR #60 Preview and security evidence — 2026-11-05

This record began with the pushed PR #60 candidate at commit
`0c1cef2c1d9446d283c12833db2394e57b9fe1d5`; the incremental update below
covers head `a21623114a696b15020db04c0bdc55765a31d3ef`. It does not establish
production readiness, authenticated ChatGPT use, or GPU-provider acceptance.

## GitHub and Preview

- PR #60 remains OPEN and Draft, based on the Draft OAuth branch for PR #58.
- The initial published head was `0c1cef2c1d9446d283c12833db2394e57b9fe1d5`;
  its CI, Gateway offline tests, Gateway comment bridge tests, Project bridge
  tests, Python 3.11/3.12/3.13 jobs, trusted reference container, Vercel
  deployment, and Vercel Preview Comments passed.
- The incremental head `a21623114a696b15020db04c0bdc55765a31d3ef` has a READY
  Preview deployment `dpl_2e8jinmr5Eyxxpu2QwafCyfhfURY` at
  `gpu-control-3jp7ho454-unjunos-projects.vercel.app` (`target: null`, not
  production). Its GitHub Actions jobs were still queued at the latest check;
  do not infer that the previous head's successful checks cover this SHA.
- After Owner/Admin login, the exact deployment's `/healthz` returned
  `configured=false`, `auth_configured=false`, `auth_mode=local_oauth`;
  `/readyz` returned HTTP 503 with `ready=false`; both OAuth discovery endpoints
  returned HTTP 503 `configuration_required` on the initial head. On the
  incremental head, both OAuth discovery endpoints still return 503 but now
  with the corrected generic message `The Gateway is not configured`. These
  are direct runtime observations from authenticated Vercel fetches.
- The Vercel Preview environment-variable screen listed
  `GATEWAY_WORKLOADS_JSON`, `GATEWAY_ENABLE_MODAL`,
  `GATEWAY_ENABLE_RUNPOD_BRIDGE`, `GATEWAY_MAX_INFLIGHT`, and
  `GATEWAY_MAX_JOB_COST_USD`. `DATABASE_URL` is Production-only; it is not in
  the Preview filter. `GATEWAY_CLIENT_IP_HASH_KEY` and
  `GATEWAY_PUBLIC_URL` were not listed for Preview. Secret values were not
  opened or read, and no variables were added, edited, or deleted.
- Read-only Neon inventory showed the existing `gpu-control-gateway` project
  has only its `production` branch and only the `gpu_control` database role.
  No branch, database, role, or credential was created or changed. Preview
  must not reuse or clone Production data for an acceptance database.
- The Neon project is on the Free v3 plan with a 0.25 CU minimum/maximum
  compute setting and zero-second idle suspend. Neon documents 100 CU-hours per
  Free project per month; a continuously active 0.25 CU compute for a 30-day
  month would use about 180 CU-hours. Actual usage depends on suspend behavior
  and traffic, so a persistent worker is not guaranteed to remain within the
  Free allowance. See [Neon's current Free plan limits](https://neon.com/blog/neon-free-plan-1-gb-per-project).

## Security review

- Official Codex Security diff scan `319e5d05-05ec-4c16-a529-a92fdf4bb699`
  completed over the exact range `97f4d388..8bd0446`, covering all 21 changed
  files and relevant supporting authentication, configuration, worker, and
  service code. It recorded zero reportable findings.
- This was a static diff review. It does not verify live host configuration,
  database grants, proxy CIDRs, TLS CA readability, credentials, or runtime
  behavior.
- Repository policy remains `mode: parked`; no provider call, paid compute,
  production setting, database role, secret, or deployment promotion was made.

## Configuration-error message regression

- The Preview's shared `configuration_required` text said to configure OIDC,
  although source supports built-in local OAuth without external OIDC. A new
  route-level test reproduced the misleading response before the fix and
  passed after changing it to the non-prescriptive `The Gateway is not
  configured` message.
- Current local suites: Gateway **553 passed, 26 skipped**; root/Core **559
  passed, 1 skipped**. The Gateway run emitted one upstream Starlette
  `BlockingPortal` deprecation warning.
- This corrects the error message only; it does not repair the absent Preview
  database/API key, initialize OAuth, start the worker, or change the Preview's
  readiness result.

## Remaining acceptance gates

- Create or select an isolated, empty Preview database project; the only
  existing Neon branch is Production. Provision least-privilege API, worker,
  and migration database roles without copying Production's OAuth/run data.
- Configure the Preview-only `GATEWAY_DATABASE_URL`, a unique API-only
  `GATEWAY_CLIENT_IP_HASH_KEY` (at least 32 bytes), and an exact public
  `GATEWAY_PUBLIC_URL`; keep the values out of the repository and logs. The
  current Vercel/Neon environment has not been changed.
- Initialize the Preview schema, bootstrap the built-in single-owner OAuth
  account through the documented trusted procedure, and run the dedicated
  worker/supervisor so `/readyz` can verify both fresh heartbeats.
- Select a persistent worker/API topology and public HTTPS policy. Vercel SSO
  currently protects the Preview; removing that protection would expose the
  Gateway's public health and login surfaces and requires an explicit
  Preview-only rollout decision after app authentication is configured.
- Select and configure a persistent Linux worker/API host (or an independently
  reviewed equivalent) with the documented service, storage, network, and
  recovery boundaries. A READY Vercel Preview alone does not supply these.
- Complete eligible ChatGPT workspace authorization-code/PKCE connection,
  tool discovery, registered CPU run, and cross-conversation result/artifact
  retrieval.
- Keep GPU-provider acceptance separate; no live GPU or paid execution was
  performed by this record.


## Incremental head refresh — 2026-11-05

- Commit `a21623114a696b15020db04c0bdc55765a31d3ef` changes the shared
  `configuration_required` response message and adds a regression test; the
  exact Preview confirms the new message. `/healthz` remains
  `configured=false` and `auth_configured=false`; `/readyz` remains HTTP 503
  with database, migration, worker, supervisor, registry, and authentication
  false. ChatGPT OAuth and experiment execution remain unavailable.
- Incremental Codex Security diff scan
  `ebd260db-3a17-4625-8969-18122ba9ebc1` recorded zero findings for the
  `0c1cef2..a216231` delta. Its coverage is marked partial; this narrow static
  review is not a service-wide security certification or runtime assessment.
- GitHub Actions runs for this head remained queued with no job steps started
  during the observation window. Vercel deployment succeeded.
