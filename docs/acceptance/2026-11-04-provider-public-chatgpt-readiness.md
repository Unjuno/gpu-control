# RunPod and Modal public ChatGPT readiness

Date: 2026-11-04

## Goal

Expose the reviewed `gpu-control` Gateway through a stable HTTPS MCP endpoint,
complete a security review, configure narrowly scoped provider credentials,
and prove from a normal ChatGPT web conversation that an owner-authorized
training job can be submitted, monitored, cancelled and retrieved.

## Current verified state

- `gpu-control.vercel.app` is externally reachable. `/healthz` returned HTTP
  200 with `configured=true` and `auth_configured=true`; protected-resource
  metadata returned HTTP 200 and advertised the MCP resource and scopes.
- `/readyz` returned HTTP 404. An unauthenticated JSON-RPC initialize at `/mcp`
  returned HTTP 401 `invalid_token`, as expected for a protected endpoint. No
  ChatGPT OAuth exchange or tool scan was performed in this acceptance.
- GitHub `main` is `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. PR #60 remains
  Draft at `14361c32091db9789e38ffe84d0150a0527185f8`. The current candidate
  was `97f4d3887005c9c7cf42bd2dbf1c8c923c0815ba` at the start of the
  2026-11-05 continuation, 12 commits ahead of its remote branch, with
  additional uncommitted worktree changes. It is not the
  revision deployed at the existing public URL.
- Repository policy is `parked`. GitHub Preview and Production environments
  have no protection rules or deployment branch policy; repository and both
  environment secret counts are zero.
- The Modal account is Starter. The UI showed no API tokens, no service users,
  no payment method, and conflicting account-specific credit/usage figures.
  A least-privilege service-user token is unavailable on Starter, and Modal
  documents that GPU use requires a valid payment method. No token or job was
  created.
- RunPod is not currently signed in through the available browser session.
  No current account balance, token, Pod, or live provider call was verified.
- The worker has a Modal Sandbox backend. The RunPod Gateway registration is
  only an adapter to an operator-provided existing-pipeline factory; no such
  factory is configured here. The checked-in live RunPod paid path remains
  disabled by policy.
- The independent Codex Security Diff Scan did not start: the scan tool
  rejected the selection because the repository HEAD changed after working
  tree selection. A second attempt using the current exact base/head returned
  the same error. The Mac is locked and the Review UI cannot be reselected in
  the current session. No scan ID or findings exist, so this is not a completed
  Codex Security scan. An independent Astra source review and manual review
  identified and helped fix concrete issues; this does not replace the
  required official scan.
- Local CPU, PostgreSQL, and MCP contract tests recorded in
  `2026-11-04-current-worktree-local-validation.md` passed; they do not prove
  public deployment, real ChatGPT, Modal GPU, or RunPod execution.
- During this continuation, the Gateway suite passed **571 tests** with
  **7 environment-dependent skips** against a fresh disposable PostgreSQL
  17.11 database; the container was removed afterward. The separate Core
  suite passed **559 tests** with **1 Python-version-specific skip**. A
  deterministic predecessor-revocation
  race test observed the actual database lock wait and proved all six
  predecessor/current/successor access and refresh tokens were revoked.
- Vercel's official request-header documentation confirms that
  `x-vercel-forwarded-for` carries the client IP even when an upstream proxy
  can overwrite `x-forwarded-for`. Repeated identical IPs are accepted and
  conflicting values rejected. See [Vercel request headers](https://vercel.com/docs/headers/request-headers).

## Acceptance gates

1. Reconcile and review the complete candidate diff, preserve existing local
   work, and commit/push only the intended reviewed changes. Deploy the exact
   reviewed revision to a stable HTTPS origin; confirm `/healthz`, `/readyz`,
   OAuth metadata, database readiness, and worker/supervisor heartbeats.
2. Finish an independent security review against the exact deployed revision
   and working-tree delta. Resolve findings, re-run the scan, and record the
   scanner identity, revision, scope and result.
3. Configure separate Preview/Production environments with owner-only deploy
   protection, restricted branch policy and least-privilege secret handling.
   Keep provider secrets on worker infrastructure; never expose them to the
   public API, GitHub Actions artifacts, MCP arguments or ChatGPT.
4. For Modal, establish account-specific available compute, usage cap and
   zero out-of-pocket spend limit, then use a dedicated service-user token
   with access only to a dedicated environment. If the Starter plan cannot
   supply this scope, stop until the account owner deliberately selects an
   appropriate plan and billing configuration.
5. For RunPod, authenticate to the intended account, verify balance and
   limits, issue a narrowly scoped/revocable credential if available, and
   implement/configure the exact candidate-bound bridge with permit, quote,
   occupancy, result verification, cancellation and cleanup gates. Do not
   use a raw generic Pod-create call as a substitute.
6. Add immutable workload images and workload-specific limits. Prove estimate,
   authorization, submit, loss monitoring, cancellation, checkpoint/artifact
   retrieval and provider cleanup. Begin with one explicitly bounded run whose
   resource, runtime and maximum charge have been reviewed.
7. Connect the public MCP endpoint in the intended ChatGPT workspace using
   OAuth, complete tool discovery, and execute the same bounded workflow in a
   normal ChatGPT web conversation. Record OAuth refresh/revocation, tool
   inputs/outputs, actual GPU evidence, charge and cleanup evidence.

## Manual security review of current uncommitted delta

Scope: current worktree changes relative to
`534c84402f7e1ba8bcef246a06bfae7d29622e22`, reviewed on 2026-11-04. This is
source-level review only; no production secrets, provider credentials, or
payment state were accessed.

- `gateway/gpu_gateway/client_ip.py` accepts only a canonical direct client
  address, a Vercel-injected address when `VERCEL=1`, or the rightmost
  untrusted address in `X-Forwarded-For` when the immediate peer belongs to an
  explicitly configured, non-global trusted proxy CIDR. Direct mode ignores
  arbitrary forwarded headers.
- Login rate limits use a keyed digest, not the raw address. Hosted mode
  requires the client-IP secret key. Vercel mode trusts the platform-injected
  client-IP header and must only be used behind Vercel's controlled ingress.
- The first source review found that the source bucket was an unkeyed SHA-256
  digest, allowing low-entropy client addresses to be guessed offline. It is
  now an HMAC keyed by a unique API-only secret; hosted API startup fails
  closed if the secret is absent or the local development default is used.
- An independent Astra review found that shared settings validation would
  require API-only client-IP settings in worker/supervisor/migration processes.
  API ingress requirements now live in `validate_api_security()` and are
  applied by FastAPI only; common worker configuration remains free of API
  secrets. A regression test covers the documented `gateway.env`-only worker.
- A second Astra review found that revoking a rotated predecessor could race
  refresh of its current successor. Refresh and revocation now lock all
  persisted family rows in deterministic token-hash order before mutation.
  The PostgreSQL regression test proves the revoker waits on the family lock
  and that tokens created by the winning refresh are included in revocation.
- Authorization code issuance still requires an explicit owner POST. New
  refresh tokens are grouped into persisted grant families. Existing pre-v7
  credentials retain null grant IDs because their historical token families
  cannot be reconstructed.
- Runtime DB roles are separated from bootstrap/table-owner privileges. The
  bootstrap SQL is a privileged one-time operator artifact and must never run
  from the public HTTP process. Runtime API grants exclude DDL; worker updates
  are narrowed to lifecycle fields it owns.
- Worker terminalization locks the run row, checks its lease token, releases a
  reserved slot atomically, and clears only that claim, preventing a stale
  worker from releasing a newer worker's reservation.
- The identified review findings above are fixed and regression-tested. The reviewed
  SQL ACLs, HMAC/IP resolver, OAuth grant locks, and worker lease terminalization
  passed locally. Residual risks are the unexecuted Codex Security scan,
  deployment-specific proxy-header provenance, and no current proof that
  production DB grants match the intended files. Scan and runtime-configuration
  verification against the exact deployment remain required before activation.

## Current disposition

Partial public liveness and local contracts are verified. The production
deployment is not ready, independent security scan is incomplete, no provider
credential is available, the RunPod Gateway bridge is unconfigured, and no
ChatGPT conversation has run a job. Therefore provider activation and live
compute remain disabled.

## Continuation update — 2026-11-04

The status above records the earlier checks in this file. The following
read-only checks and review supersede only the stated current status; the
earlier events and evidence remain part of the history.

- The candidate was committed as `073201b056b72cd04872272d0d83c029dd60469f`.
  Codex Security Diff Scan `c6e65f0f-8ec2-4afa-be20-1150fc518dad` completed
  against `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e..073201b056b72cd04872272d0d83c029dd60469f`.
  The scan reviewed 67 changed source items, recorded zero reportable findings,
  and left external account/deployment state outside scope. Its report is
  `/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control-pr58-current-candidate/073201b056b72cd04872272d0d83c029dd60469f_20261104T025442Z_7t1wyn3q/report.md`.
- A fresh Vercel read showed `gpu-control` has `live=false`; its latest READY
  deployment is still the old `main`-era SHA
  `22e3caf2de079e35345b39aef4e5215eaa40993f` and has no Production target.
  The project has SSO protection enabled for deployments except custom domains.
  The public custom-domain liveness response therefore does not prove that this
  candidate, its database, or workers are deployed and ready.
- Modal and RunPod account screens were not revalidated in this continuation.
  Earlier account observations in this document may be stale. No provider token,
  payment method, workload, or paid call was created. The Mac became locked
  during the attempt to inspect the logged-in provider dashboard.
- Current Modal documentation says Starter includes $30 monthly compute credit,
  GPU use requires a valid payment method, and Service Users are available only
  on Team/Enterprise. Team is listed at $250/month plus compute. No plan upgrade
  or payment change is authorized by this record. Sources:
  [Modal GPU requirements](https://modal.com/docs/guide/gpu),
  [Modal Service Users](https://modal.com/docs/guide/service-users),
  [Modal pricing](https://modal.com/pricing).
- Current RunPod documentation supports scoped API keys, including per-endpoint
  permissions; a created key still carries access to the account balance and
  must be scoped to the exact operations required. RunPod REST v2 is the
  current integration target, but the repository's live paid path remains
  disabled and no provider acceptance or result transport was live-tested.
  Sources: [RunPod scoped API keys](https://www.runpod.io/blog/scoped-api-keys-runpod),
  [RunPod REST API v2](https://www.runpod.io/blog/runpods-rest-api-v2-is-here-one-api-for-your-entire-gpu-stack).
- A separate ChatGPT web session opened logged out. OpenAI's current guidance
  lists full MCP with write actions for Business, Enterprise, and Edu, with
  workspace admin/owner controls for developer mode and publication. The
  account plan and workspace role for the intended ChatGPT workspace remain
  unverified. Source:
  [ChatGPT developer mode and full MCP](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt).

The candidate security review is complete, but the public ChatGPT workflow is
not live. The remaining execution blockers are current Modal/RunPod account
state and appropriately scoped credentials, the selected public Gateway host
and its persistent worker/database readiness, and an eligible ChatGPT web
workspace. Keep provider activation parked until those facts and the exact
bounded first workload are reviewed.

## Continuation update — RunPod included — 2026-11-04

The user explicitly confirmed that RunPod is in scope alongside Modal. The goal
is both providers usable through the same normal ChatGPT web conversation, not
just a Modal proof or an offline RunPod adapter.

- The local candidate branch is `codex/gpu-control-current-p5-on-pr58`, at
  `9792100` (`docs: reconcile provider readiness after security scan`), ten
  commits ahead of its remote branch; the worktree was clean at inspection.
- GitHub PR #60 is still open, Draft, and unmerged. Its remote head remains
  `14361c32091db9789e38ffe84d0150a0527185f8`; latest recorded local code
  candidate is `073201b056b72cd04872272d0d83c029dd60469f`. The candidate has no
  combined commit statuses. Do not mistake the existing PR or deployment for
  the local candidate being released.
- Vercel project `gpu-control` is still `live=false`. Its latest READY
  deployment uses `22e3caf2de079e35345b39aef4e5215eaa40993f`, has no target,
  and is not the candidate. SSO protection is enabled except on custom domains.
  Listing project environment variables returned 403 to the connected Vercel
  identity; values were not requested or read.
- The in-app Modal dashboard is logged in, but its tab is unavailable to this
  computer-control session (`browser.user is unavailable`). No current account
  balance, cap, token, or provider configuration was inspected. The other
  available browser session is logged out of ChatGPT. No RunPod account state
  was observed.
- Source inspection confirms that `ExistingRunPodBridge` still requires an
  operator-supplied factory. The separate RunPod v2 adapter, signed paid
  authorization verifier, lease contracts, and credit verifier exist, but the
  ChatGPT-origin authorization issuer, durable authorization integration,
  concrete Gateway-to-RunPod v2 wiring, and external acceptance are incomplete.
  Modal credit authorization is likewise not wired into worker admission. Live
  provider calls remain disabled by repository policy.
- No provider token, payment method, plan, deployment, database, or paid
  resource was changed. No ChatGPT OAuth/tool call, provider call, or GPU job
  was attempted.

## Continuation update — production database read-only check — 2026-11-04

The connected Neon integration was used for read-only inventory and `SELECT`
queries against project `delicate-smoke-00521013`, branch
`br-raspy-cell-b3l93n46`, database `gpu_control`:

- Project `gpu-control-gateway` is PostgreSQL 17 in `aws-ap-southeast-1`.
  Its default `production` branch is `ready` but unprotected. The branch's
  read-write endpoint was `idle` when listed; the project allows public
  connections. No Neon setting or branch was changed.
- `gateway_runs_v1` exists with zero rows. `gateway_schema_version` does not
  exist, so this is still the legacy unversioned shape rather than the current
  local schema (v15). No migration was run.
- The only matching role is `gpu_control`; it is a login role with
  `CREATEROLE`, `CREATEDB`, `BYPASSRLS`, and `INHERIT`. Separate
  `gpu_control_api`, `gpu_control_worker`, and `gpu_control_migrate` roles
  were not present. The query used this role only to read metadata and a row
  count. No secret, hash, token, session, password, or run content was read.
- Do not connect current deployed services to this branch or run the current
  migration with this role as-is: that would not establish the reviewed runtime
  least-privilege boundary. First identify all consumers and preserve existing
  OAuth state; perform an isolated branch rehearsal with reviewed backup/restore,
  role ownership/grants, migration to current schema, and `/readyz` checks.

### RunPod and Modal completion work

1. **Prepare a release candidate:** reconcile the complete local branch with
   PR #60 and its base; review/update CI and security evidence for the exact
   release SHA; retain the security scan record for `073201b` and scan any
   later source changes. Resolve conflicts and publish the reviewed code only
   through the repository's accepted release flow.
2. **Finish the shared public control plane:** choose the stable HTTPS host;
   deploy the exact reviewed SHA; configure protected Preview/Production
   environments, persistent Postgres, runtime roles, backups, artifact store,
   worker/supervisor, secrets, logs/alerts, and verify `/healthz`, `/readyz`,
   OAuth metadata, migrations, and worker heartbeats. Preserve provider
   secrets exclusively on worker infrastructure.
3. **Connect ChatGPT:** verify the intended ChatGPT plan/workspace and admin
   authority for full MCP tools; publish/register the public MCP service with
   OAuth; perform authorization-code/PKCE, tool discovery, refresh, and revoke
   checks in an ordinary ChatGPT web chat.
4. **Finish RunPod's exact path:** implement a reviewed independent issuer for
   human spend decisions; bind a short-lived, revocable signed permit to the
   owner, run, Gateway and core plan fingerprints, control-plane SHA, exact
   immutable image, GPU/resource, runtime and maximum total cost. Persist and
   recheck it before worker intent and provider create. Wire the REST v2
   adapter with scoped credential loading, account-wide lease/fencing,
   inventory/reconciliation, status, cancellation, authenticated result
   collection, cleanup, and spend evidence. Preserve no-retry-on-ambiguous
   create and all parked defaults until acceptance gates pass.
5. **Finish Modal's credit path:** obtain current account-specific quota and
   spend-cap evidence and a worker-only credential. If appropriate least
   privilege cannot be achieved on the current plan, record the account-owner
   plan/billing decision before any upgrade. Wire the separate signed
   credit-consumption decision to worker admission and quota revalidation;
   hard-enforce zero out-of-pocket cost and stop-on-overage.
6. **Review and verify:** independently threat-review authority, OAuth,
   credential boundaries, result integrity, replay, concurrency, spend caps,
   cleanup, and rollback. Run local contract/security suites and the exact
   release scan. Test account access read-only first; do not create keys until
   exact permissions and revocation are established.
7. **Bounded live acceptance:** only after each provider's code, release,
   security, account, authority, and cost gates pass, present a concrete
   resource/image/runtime/charge-ceiling/cleanup plan for action-time review.
   For separately authorized RunPod and Modal runs, capture ChatGPT tool
   request/response, OAuth refresh/revocation, actual device/training/loss and
   checkpoint evidence, provider charge or credit debit, cancellation, and
   independent resource-cleanup proof. A provider dashboard, connected MCP,
   or synthetic lifecycle alone does not satisfy acceptance.

## Continuation update — P5 authorization coordinator source slice — 2026-11-04

Implemented an internal-only seam to remove the disconnected verifier/Store
gap without making the provider executable:

- The signed RunPod paid-authorization envelope now uses schema version 2 and
  includes the exact Gateway `approval_id`. The verifier rejects an envelope
  issued for an older approval generation, including when the same plan is
  approved again. The verified claim carries the approval ID, and the Store
  requires it to match the exact persisted browser approval before writing.
- Added `PaidAuthorizationCoordinator`, which accepts only an injected
  server-owned resolver for current actor, DecisionRecord, control-plane SHA,
  exact Gateway/core plans, and approval. It verifies the real Ed25519
  signature, issuer/key/policy, expiry and live revocation state before Store
  write; then reloads and verifies again. Reload repeats the trusted-context,
  approval, signature, expiry, and revocation checks. Returned persistence
  metadata contains only authorization ID, approval ID, and issuer.
- The coordinator has no HTTP/MCP or worker caller, holds no signing key, and
  cannot issue a provider permit. The Worker still refuses RunPod paid plans
  with `runpod_authorization_persistence_unavailable`; RunPod and Modal live
  registrations remain unchanged and disabled. No credit path was changed.
- Independent security review found a stale-clock race: a database reader
  blocked on the run-row lock could validate expiry using a timestamp captured
  before the browser approval expired. Store persistence and reload now accept
  a trusted clock callback and re-read it after acquiring the run lock. Added a
  PostgreSQL regression that held the row lock, observed the reader waiting in
  `pg_stat_activity`, advanced time beyond the approval deadline, and confirmed
  the reader returned no authorization after the lock released.
- Verification on this source: full Gateway suite **552 passed, 26 skipped**;
  disposable PostgreSQL integration suite **12 passed** (including the actual
  lock wait); Core suite **559 passed, 1 skipped**; `git diff --check` passed.
  The only warning was the existing Starlette deprecation. The disposable
  PostgreSQL 17 container was stopped after the run. These are source-level
  checks only; no issuer, ChatGPT OAuth, provider account, paid call, hosted
  deployment, or GPU run was involved. This slice does not enable worker
  admission or establish paid execution acceptance.

### Live account-session recheck — 2026-11-04

Opened the RunPod console read-only in the available in-app browser. It
redirected to `console.runpod.io/signup?redirect=%2Fpods` and displayed the
account creation page; this browser session is not authenticated to RunPod.
The Chrome session also shows ChatGPT logged out. The existing Modal in-app tab
remains on the signed-in `unjuno` workspace, but no Modal quota or credential
settings were opened. No login, token, billing, resource, deployment, or
provider setting was changed. Account-specific RunPod and ChatGPT checks cannot
proceed from the currently available browser sessions.

## Continuation update — RunPod and Modal execution boundary — 2026-11-04

The user reiterated that RunPod must be delivered alongside Modal, with both
usable from an ordinary ChatGPT conversation. This remains the active product
acceptance target.

- The local candidate is `97f4d3887005c9c7cf42bd2dbf1c8c923c0815ba` on
  `codex/gpu-control-current-p5-on-pr58`, 12 commits ahead of the remote PR
  branch. The worktree was clean before this documentation/status correction.
- The existing older Vercel deployment is reachable, but its source SHA is not
  this candidate; the current candidate has not been deployed. PR #60 remains
  Draft and unmerged. No push or deployment was performed.
- RunPod v2 adapter and account-lease contracts exist in source, but the
  default Gateway registry still points to `ExistingRunPodBridge`, requiring
  an operator factory. No ChatGPT-origin issuer or durable paid authorization
  caller is wired. Worker admission continues to refuse RunPod paid/credit
  plans with `runpod_authorization_persistence_unavailable`.
- Modal Sandbox backend exists, but Modal credit authorization is not wired to
  Worker admission. The account-specific quota, zero-out-of-pocket cap, and a
  worker-only least-privilege credential are not verified. Neither provider is
  currently accepted for live ChatGPT GPU execution.
- The Codex Security Diff Scan completed for the exact range
  `14361c32091db9789e38ffe84d0150a0527185f8..97f4d3887005c9c7cf42bd2dbf1c8c923c0815ba`
  (scan `60d410e1-83aa-420d-b01f-d9fd63572899`). It covered all 14 changed
  security source files and reported zero reportable findings. Report:
  `/Users/taka/.codex/state/plugins/codex-security/scans/gpu-control-pr58-current-candidate/97f4d3887005c9c7cf42bd2dbf1c8c923c0815ba_20261104T034224Z_glxmqtwk/report.md`.
  This is a source-diff scan, not a deployment, account, credential, or live
  provider security acceptance.
- README status was corrected to say the reachable Vercel deployment is older,
  the current candidate is not deployed or ChatGPT-verified, and RunPod's
  authorization/Gateway wiring and Modal's credit admission remain incomplete.
- No provider credential, billing setting, database, resource, token, public
  deployment, or GitHub PR state was changed. No ChatGPT tool call or GPU job
  was attempted.

The next technical acceptance sequence is: reconcile and publish the reviewed
candidate through the repository release flow; establish a correctly protected
public Gateway and least-privilege runtime; complete normal ChatGPT OAuth and
tool discovery; then finish and separately accept the RunPod and Modal worker
paths with explicit account, cost, cleanup, and result evidence. Keep policy
`parked` until all of these gates pass.

## Continuation update — live account and GitHub checks — 2026-11-05

The user authenticated in the RunPod browser and asked to use RunPod through
GitHub Actions as well as Modal. The following checks were read-only; no
credentials, billing settings, workflows, or provider resources were changed.

- RunPod Billing shows a prepaid balance of **$15.00**, current spend
  **$0.000/hour**, a spend-rate limit of **$80/hour**, and Auto-Pay disabled.
  The account currently has zero GPUs, vCPUs, storage, and endpoints. The
  credentials page has no API key rows, and there is no existing Network
  Volume. The saved payment method was not used. The account's hourly rate
  limit is not a cumulative $15 cap. RunPod says compute/storage usage is
  deducted from prepaid credits, top-ups are non-refundable, and an existing
  Network Volume continues to incur storage cost; see [RunPod billing
  documentation](https://github.com/runpod/docs/blob/main/accounts-billing/billing.mdx).
- Modal remains on Starter. Its dashboard shows **$1 of $30/month** free
  compute credit remaining, with a payment method required to unlock the
  remainder. Workspace limits show 0/10 concurrent GPUs and the API tokens
  page has no tokens. No upgrade, payment method, token, or resource was
  created. Service Users are restricted to Team/Enterprise per [Modal Service
  Users](https://modal.com/docs/guide/service-users) and [Modal
  pricing](https://modal.com/pricing).
- GitHub `Unjuno/gpu-control` main has required review and CI protections, but
  its only Actions environments are Preview and Production and both have zero
  protection rules. There is no `paid-runpod` environment, repository Actions
  secret, or RunPod GPU workflow. The live paid-compute policy remains parked.
- `Unjuno/orbitune` run `41629597889` succeeded publishing the immutable
  selected-source image. Its evidence artifact records source SHA
  `fc131174a9b529a9825f54fccf1a7df4c63c9a1a` and image digest
  `sha256:489348337940c858f83ab056769a5c843ed8f778b906e7e16a8120581b0dd08e`.
  The existing `runpod-canary-smoke` is a CPU-only GitHub Actions contract
  smoke; image publication does not create a RunPod Pod or prove GPU training.
- The present candidate cannot safely spend the $15 from GitHub: there is no
  protected paid environment, scoped RunPod credential, concrete live
  Gateway-to-RunPod workflow, existing result-storage volume, or verified
  live result/cleanup path. No GPU was started and no money was spent. Keep
  the existing balance intact until these gates and the exact first-run
  resource, runtime, cumulative charge ceiling, storage cost, and cleanup are
  reviewed together.

The next roadmap work is to reconcile the current P1 CPU/recovery candidate
with the P5 authorization changes, close the deployment credential-isolation
and trusted-proxy gaps, then complete the actual hosted ChatGPT CPU acceptance.
Only after those release, operational, provider, result-transport, and human
authorization gates are independently satisfied may a paid RunPod workflow be
added and a bounded live run considered. A GitHub image build or a successful
CPU smoke must not be reported as a paid GPU execution.

## Continuation update — branch protection and image evidence — 2026-11-05

- The live GitHub API showed `main` required one approving review and seven
  required checks. The initial query mistakenly selected the code-owner-review
  field under the alias `strict`, so it did not establish the prior
  required-status-check strict value. Updated only required-status-check
  protection to `strict=true`, retaining the seven known contexts. A
  follow-up API read confirmed strict checks, one approving review, and admin
  enforcement are enabled. The prior strict value is unknown. No source branch,
  PR, deployment, or billing state was changed by this GitHub setting update.
- Read-only inspection confirmed open Draft PRs #51–#66 remain a stacked
  release sequence; PR #66 is the current P1 CPU vertical/recovery candidate,
  not a merged or deployed release. No PR was approved or merged.
- The published Orbitune image digest was reconciled into the machine policy,
  correcting its stale `published: false` value. The corresponding parked-mode
  documentation now records that publication does not itself authorize or
  prove GPU execution.
- `pytest -q tests/test_repository_state.py` passed (4 tests), and
  `git diff --check` passed. No provider secret, paid workflow, GPU resource,
  RunPod balance, or Modal billing setting was touched. ChatGPT MCP acceptance
  and live provider execution remain unverified.

## Continuation update — P1 deployment credential isolation — 2026-11-05

Applied the bounded deployment-hardening changes from PR #66 to the current
P5 candidate without merging the diverged PR stack:

- Removed the shared database URL from `gateway.env.example` and added
  separate API, worker/supervisor, and migration URL templates for
  `gpu_control_api`, `gpu_control_worker`, and `gpu_control_migrate`, all
  requiring TLS hostname verification. Systemd units now load only their
  service's URL; API-only IP-hash/OIDC settings remain in `api.env.example`.
- Added the read-only `gpu-control-config` group to API, worker/supervisor,
  and migration services so they can read operator-owned workload/policy
  files. Updated the Operations runbook for directory/file ownership, role
  provisioning, installation, and the distinct database URLs. The runbook now
  explains the SQL bootstrap roles start `NOLOGIN`; each same-named least-
  privilege role must be provisioned as a distinct `LOGIN` out of band, without
  cross-role membership, before its URL is used.
- Added Uvicorn `--no-proxy-headers` to the API systemd unit and container
  entrypoint so the application's trusted-proxy resolver sees the actual
  socket peer. The API-only HMAC key stays out of common and worker settings.
- Reworked the CI systemd verifier to copy units into a disposable temporary
  directory and validate there; it no longer creates host users/groups or
  installs placeholders under `/etc` and `/opt`.
- Astra's second pass found that `verify-full` alone was incomplete for these
  no-home, `ProtectHome=true` services. All DB URL examples now specify the
  trusted CA bundle by absolute `sslrootcert` path, and the runbook requires a
  root-owned readable CA file plus certificate-hostname verification.
- The separate Vercel/API `.env.example` uses an explicit placeholder CA path
  and warns against deploying it unchanged. Current Vercel docs identify
  Amazon Linux 2023 for the build image, but do not establish the deployed
  Function's CA-bundle path; that runtime path must be measured before hosted
  DB connectivity is accepted. No assumption was copied from the build image
  into the function-runtime configuration.
- Extended deployment-boundary tests for DB-role separation, API-only secrets,
  trusted-proxy configuration, and the safe CI verifier. Result:
  `gateway/.venv/bin/python -m pytest -o addopts= -q tests/test_deploy_units.py`
  — **15 passed**, one existing Starlette deprecation warning. The installed
  Uvicorn help confirms `--no-proxy-headers` is supported, and `git diff
  --check` passed.
- The full PR #66 P1 stack is still not integrated: only the deployment
  credential/proxy slice was carried over. No systemd host, PostgreSQL role,
  GitHub PR, deployment, provider credential, paid workflow, or GPU was
  changed or used. Actual host `systemd-analyze`, live DB-role permissions,
  hosted ChatGPT CPU acceptance, and independent review of this new delta
  remain pending. Keep provider policy `parked`.

## Continuation update — local registered CPU/MCP rerun — 2026-11-05

Built the repository-owned CPU smoke image from
`gateway/workloads/cpu-smoke/Dockerfile` on the current worktree and exercised
the authenticated local MCP integration route:

- Image ID: `sha256:daf290a3a6d909d5791c0cbcac7f0f1854f49fc4c2994f2649fdd67702085192`
  (`linux/arm64`), with OCI source label `Unjuno/gpu-control` and a deliberately
  synthetic all-`a` source SHA required by this local fixture. This label is
  not a claim that the image was built from a published commit.
- Command from `gateway/`:
  `GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST=sha256:daf290a3a6d909d5791c0cbcac7f0f1854f49fc4c2994f2649fdd67702085192 GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY=Unjuno/gpu-control GPU_CONTROL_CPU_SMOKE_SOURCE_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ./.venv/bin/python -m pytest -o addopts= -q tests/test_local_mcp_integration.py`
- Result: **1 passed** in 1.26 seconds, with one existing Starlette
  deprecation warning. The assertion path listed tools, prepared and replayed
  a registered workload idempotently, submitted it, ran the real local Docker
  container through the Worker, retrieved the result and artifact through a
  second MCP client, verified the exact artifact bytes/digest, and confirmed
  terminal cleanup. The returned result was `simulation=false`, `gpu_used=false`,
  and `cost_classification=LOCAL`.
- After the run, no container using the unique image tag remained. The
  pre-existing unrelated Docker container remained running and was not touched.
  This is local MCP/CPU evidence with synthetic OAuth and source identity; it
  does not prove a hosted deployment, ChatGPT conversation, real model
  inference, GPU use, provider billing, or paid execution.

## Continuation update — full local regression — 2026-11-05

- Gateway with disposable PostgreSQL 17.11: **571 passed, 7 skipped** in
  15.88 seconds. Database ACL, migration, OAuth and provider-lease tests ran;
  the temporary container was removed after the run.
- Core: **559 passed, 1 skipped** in 0.99 seconds. The skip is the documented
  Python 3.11-only malformed RunPod decoder reproducer.
- `git diff --check` passed after the recorded implementation changes.
- These are local source regression results. Hosted OAuth, Vercel deployment,
  ChatGPT web conversation, live worker heartbeats, provider credentials and
  real GPU execution remain unverified. Policy remains `parked`.

## Continuation update — hosted PR #66 preview recheck — 2026-11-05

Using the previously approved, account-scoped temporary Vercel share-link
access, read-only GETs rechecked the existing preview deployment. Vercel's
deployment API identifies it as READY at source
`1adc2417ef506bd0b9bac4dacafc8b0f5f8ea0f2` on
`codex/pr58-cpu-vertical-reconcile-20261102` (deployment
`dpl_HXNz6AnPwCpdtaUDfeFesRjDpK7T`, target `null`). The registered custom
domain and Production settings were not changed.

- `/healthz`: HTTP 200, `configured=false`, `auth_configured=false`,
  `auth_mode=local_oauth`.
- `/readyz`: HTTP 503, `{"ready":false}`.
- `/.well-known/oauth-protected-resource/mcp` and
  `/.well-known/oauth-authorization-server`: HTTP 503 with
  `configuration_required` during Gateway configuration initialization. The
  shared response does not identify the specific missing or invalid setting;
  external OIDC is not necessarily required when built-in OAuth is selected.
- A metadata-only Vercel environment-variable listing returned HTTP 403. No
  environment values were requested or read; the denied listing does not prove
  which variables are present or absent. The Vercel MCP has no authorized CLI
  fallback available in this workspace.

This proves the preview is reachable and fail-closed, but not ready for
ChatGPT OAuth or MCP use. No deployment, project setting, environment variable,
database, provider credential, or billing state was changed. Keep the release
and spending gates closed until an authorized operator configures and verifies
the Preview database, CA trust, OAuth and registered workload, then repeats
these checks against the exact reviewed revision.
