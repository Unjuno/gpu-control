# ChatGPT MCP and CPU acceptance record

Status: **NOT RUN**. This file is an evidence template, not acceptance evidence.
Repository tests, generated credentials, and local MCP clients do not satisfy
the real ChatGPT account and conversation checks below.

## Current-session gate recheck (2026-10-31 11:39 JST; read-only)

- Fresh probes against the configured production alias
  `https://gpu-control.vercel.app` returned `/healthz` **200**,
  `/readyz` **404**, authorization-server metadata **200**, and unauthenticated
  `/mcp` **401**. A probe against the unrelated hostname
  `gpu-control-gateway.vercel.app` returned 404 for every path and is not
  evidence about this repository's deployment. The production readiness
  contract is still absent.
- GitHub lists PRs #51–#59 and #43 as OPEN/DRAFT. PRs #51–#59 each have nine
  successful status entries; PR #43 has five. PR #52 and #43 report
  `REVIEW_REQUIRED`; no independent approval or merge is established. The
  branch-protection endpoint returned HTTP 403 due to API rate limiting, so
  this session did not refresh its detailed settings.
- The local checkout is `codex/chatgpt-cpu-vertical` at `a794438`, with 92
  modified or untracked paths. Those changes are not covered by the published
  PR checks. `policies/repository-state.yaml` remains `mode: parked` and paid
  execution remains disabled.
- The local full-suite evidence recorded above remains local evidence. This
  session did not obtain an authenticated ChatGPT workspace, deploy a revision,
  use credentials, or run an experiment through ChatGPT. OAuth, tool
  discovery, CPU execution, and cross-conversation result retrieval remain
  **NOT RUN**.

## Current-session gate recheck (2026-10-31 09:51 JST; read-only)

- A fresh in-app browser visit to `https://chatgpt.com/` shows **Log in** and
  **Sign up for free**. This session has no authenticated ChatGPT account or
  workspace, so OAuth consent, custom MCP setup, tool discovery, a ChatGPT
  experiment, and cross-conversation result retrieval could not be exercised.
- Fresh unauthenticated requests to `https://gpu-control.vercel.app` returned
  `/healthz`=200, `/readyz`=404, authorization-server metadata=200, and an
  unauthenticated JSON-RPC POST to `/mcp`=401 with the protected-resource
  Bearer challenge. This proves liveness/discovery/auth boundary only; the
  deployed alias does not expose the current readiness contract.
- Separately, the current local dirty Gateway snapshot passed **513 tests with
  2 optional skips** using a dedicated PostgreSQL 16 service and a CPU image
  tied by OCI labels to immutable repository HEAD `a794438f42bd7246f463eaaa40d963af0aae9d13`.
  The local authenticated MCP integration completed CPU execution and fetched
  its result/artifact from a second client. This is not a ChatGPT-originated
  call or deployed acceptance. Full local evidence:
  `docs/acceptance/2026-10-31-current-snapshot-full-suite.md`.
- No OAuth grant, ChatGPT setting, deployment, provider call, or GitHub write
  occurred. Repository mode remains `parked`.

## Current-session recheck (2026-10-31 08:59 JST; read-only, not acceptance)

Fresh requests to the production alias returned `/healthz`=200, `/readyz`=404,
and unauthenticated `/mcp`=401. PR #52 remains OPEN/DRAFT at
`bc9b0305e6b2e86f9d8c214161b10511ce9f012c`, based on `main`, with all seven
required Actions checks and Vercel successful but `REVIEW_REQUIRED` and no
submitted reviews. PRs #51 (`e3ffcef`), #58 (`561a6c7`), and #59 (`76c2a1a`)
also remain OPEN/DRAFT with successful published checks and no submitted
reviews. Those checks cover their published heads, not the dirty local worktree.
No authenticated ChatGPT workspace call, deployment, GitHub write, or
credential change occurred. `policies/repository-state.yaml` remains
`mode: parked`.

## Current-session recheck (2026-10-31 09:15 JST; read-only, not acceptance)

Fresh requests to the production alias returned `/healthz`=200, `/readyz`=404,
and unauthenticated `/mcp`=401. GitHub still lists PRs #51 through #59 as
OPEN/DRAFT; review decisions are empty except PR #52, which requires review.
Their published heads differ from the current local worktree and do not cover
its uncommitted lease-store changes. No authenticated ChatGPT call, deployment,
GitHub write, provider action, or credential change occurred. The repository
remains `mode: parked`.

## Current gate recheck (2026-10-31 08:33 JST; read-only, not acceptance)

Fresh public alias requests returned `/healthz`=200, `/readyz`=404, and
unauthenticated `/mcp`=401. GitHub still lists PR #58 at
`561a6c7ac697dfdf22f304b60e313fccb2c806a4` as OPEN/DRAFT/CLEAN with its seven
Actions contexts and Vercel successful and no submitted review decision. PR
#59 remains OPEN/DRAFT/CLEAN at `76c2a1a1b4439cf093c4e6efdd39d5121eb08959`
with its seven Actions contexts and Vercel successful and no review decision.
The local P1+P3 integration candidate and its new PostgreSQL+CPU full-suite
result are not present on either published head. ChatGPT remains unaccepted:
authenticated workspace connection, tool invocation, CPU run, cross-conversation
retrieval, and result verification are **NOT RUN**. The production readiness
route is still missing. No GitHub write, deployment, credential, or account
change was made.

At 08:35 JST, a fresh read-only visit to `https://chatgpt.com/` in the
available in-app browser again displayed `Log in` and `Sign up for free`. No
account, workspace, plugin, or MCP controls were accessible in this session.
This refreshes the unauthenticated-session observation only; it does not satisfy
or alter any acceptance gate.

## Current-session recheck (2026-10-31 08:44 JST; read-only, not acceptance)

Fresh GitHub CLI reads show PR #51 OPEN/DRAFT from
`codex/chatgpt-cpu-vertical` at `e3ffcef` based on PR #59's checkpoint
`51b88f6`; PR #58 OPEN/DRAFT at `561a6c7` based on `e3ffcef`; and PR #59
OPEN/DRAFT at `76c2a1a` based on `51b88f6`. Each has nine published status
contexts successful and zero submitted reviews. The local checkout is at
`a794438`; the 2026-10-31 P1+P3 integration candidate and later dirty changes
are not represented by those published heads/checks.

Fresh public production-alias requests returned `/healthz`=200, `/readyz`=404,
and unauthenticated `/mcp`=401. ChatGPT was last observed logged out at 08:35
JST. No authenticated ChatGPT call, deployment, GitHub write, or credential
change occurred. `policies/repository-state.yaml` remains `mode: parked`.

## Current gate recheck (2026-10-31 07:42 JST; read-only, not acceptance)

Fresh public alias requests returned `/healthz`=200, `/readyz`=404, and
unauthenticated `/mcp`=401. Production is live and enforces bearer
authentication, but it does not serve the current readiness contract. Current
GitHub PR listing shows PR #58 at `561a6c7` and PR #52 at `bc9b030` are both
OPEN/DRAFT with no submitted review decision (#52 reports
`REVIEW_REQUIRED`). `gh pr checks` reports all seven required Actions contexts
and Vercel successful on each exact head. These checks cover the pushed heads,
not the dirty local candidate. A separate branch-protection API read was
rate-limited (HTTP 403), so no fresh protection-setting claim is made here.
The logged-out ChatGPT account observation remains the latest account-access
evidence. Authenticated workspace connection, tool invocation, CPU run,
cross-conversation retrieval, and result verification remain **NOT RUN**.

## ChatGPT access recheck (2026-10-31; read-only)

Opened `https://chatgpt.com/` in the available in-app browser. It displayed
`Log in` and `Sign up for free`; the session is logged out. No account,
workspace, plugin, OAuth, or MCP settings were inspected or changed, and no
ChatGPT-originated tool call could be performed. The account/workspace and
custom-MCP write-action gates therefore remain **NOT RUN**. Continue with
offline implementation and review preparation; this observation is not a
product acceptance result.

## Production alias recheck (2026-10-31; read-only, not acceptance)

Fresh unauthenticated GETs to `https://gpu-control.vercel.app` returned
`/healthz`=200 (`configured=true`, `auth_configured=true`,
`auth_mode=local_oauth`), `/readyz`=404, OAuth authorization-server and
protected-resource metadata=200, and `/mcp`=401 (`Bearer access token is
required`). This confirms liveness, discoverability, and the unauthenticated
boundary. Production still lacks the current readiness route, so it cannot
serve as the P1 acceptance target. No token, deployment, or configuration was
changed.

## Production provenance and probe refresh (2026-10-30 22:03 UTC; not acceptance)

GitHub's newest `Production` deployment record is successful deployment
`6660954255`; Vercel independently identifies the active `READY` deployment as
`dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`. Both map to `main` SHA
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` (2026-09-25 12:43 UTC), at
`https://gpu-control-mrinn4czy-unjunos-projects.vercel.app`.
Fresh unauthenticated GETs to the production alias returned `/healthz`=200
with configured local OAuth, `/readyz`=404, OAuth authorization-server and
protected-resource metadata=200, and `/mcp`=401 requiring a bearer token. This
confirms the alias still exposes the old deployed baseline's liveness and OAuth
discovery, but not the local P1 candidate's readiness or ChatGPT acceptance.
No account, credential, deployment, or provider state was changed.

## Latest production-alias probe (2026-10-30 21:49 UTC; not acceptance)

Read-only unauthenticated GETs to `https://gpu-control.vercel.app` returned
`/healthz`=200 with `configured=true`, `auth_configured=true`, and
`auth_mode=local_oauth`; OAuth authorization-server and protected-resource
discovery each returned 200 with the production alias as issuer/resource;
`/readyz` returned 404; and `/mcp` returned 401 with a Bearer challenge pointing
to protected-resource metadata. This confirms public liveness, OAuth discovery,
and an authentication boundary only. The deployed revision still lacks the
Gateway readiness route, and no authenticated Gateway readiness, ChatGPT tool
call, CPU execution, or result retrieval was performed. No credentials, account
settings, deployment, or provider were changed.

## Latest PR #52 deployment probe (2026-10-30 20:23 UTC; not acceptance)

GitHub associates Vercel deployment `7447898417` with exact candidate SHA
`c824b9018ea9dfd3d9f8b45f65b7b3fd60c4fb01`; Vercel reports deployment
`https://gpu-control-b9kuhy1rl-unjunos-projects.vercel.app` as successful.
Unauthenticated GETs to `/healthz`, `/readyz`, both OAuth discovery paths, and
`/mcp` all resolved to `https://vercel.com/login` and returned Vercel's login
HTML (HTTP 200). The `dpl_Hqoqex5Pfr4ptEqGGxx9aXFsus9w` HTML marker belongs to
that login response, so these responses reveal nothing about the Gateway
runtime or route behavior. No protected fetch/share link, credentials,
deployment mutation, or ChatGPT call was used. Runtime readiness and every
ChatGPT acceptance gate remain **NOT RUN**. Production `/readyz` separately
returned 404 in this session.

## PR stack refresh (2026-10-30 21:02 UTC; not runtime acceptance)

PR #57 is at `51b88f6110e2fc12de1c475e6e3d07c5438eaa3b`. Its seven
standard GitHub Actions contexts and Vercel pass. Two initial CI failures were
caused by the clean jobs not installing the repository's `gpu_control`
package; both Gateway workflows now install it explicitly. A clean Python
3.12 bridge run passed 82 tests with one optional Torch test skipped. A
read-only Security Review of the P1 CPU lifecycle/OAuth branch found no
reportable issues. The stacked base branch reports no required contexts via
`gh pr checks --required`; main branch protection still requires an
independent GitHub approval when this work reaches main. PR #57 remains
OPEN/DRAFT with no GitHub review.

PR #58 is a focused P1 OAuth DCR/schema-v9 follow-up at
`cb37a630e1609b6166bc0122f3aba86a759beb50`, based on PR #51 head
`3346d0818dd1dd195d8105c348f00b51e2879daa`. It passes seven standard GitHub
Actions contexts and Vercel. The CI Gateway suite passed **428 passed / 1
skipped / 1 warning** with PostgreSQL 16 and the digest-identified CPU
container; WebMCP and Project bridge also passed. Locally, 17 OAuth/migration
tests passed in a clean Python 3.12 environment. PR #58 remains OPEN/DRAFT
with no GitHub review. Its base PR #51 is still a broad unmerged aggregate, so
#58 is stacked and not independently mergeable yet.

PRs #52–#56 remain OPEN/DRAFT with successful recorded CI and Vercel statuses;
PR #52 still has `REVIEW_REQUIRED`. PR #51 is based on #57 now, so its earlier
green checks are stale for the current base. The primary checkout still has
41 modified or untracked paths outside these PR heads. A fresh unauthenticated
read-only production probe at 20:52 UTC returned `/healthz`=200,
`/readyz`=404, both OAuth discovery paths=200, and `/mcp`=401. This confirms
public liveness and OAuth discovery only; readiness, configured worker/database,
and authenticated ChatGPT execution remain unverified. No ChatGPT call was
performed in this refresh.

## PR stack refresh after conflict repair (2026-10-31; not runtime acceptance)

PR #51 is now at `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`, `MERGEABLE` and
`CLEAN` against PR #57 head `51b88f6`. All seven required Actions contexts and
Vercel pass after merging the current base and retaining the package-install
steps in Gateway CI. PR #51 remains OPEN/DRAFT with no review.

PR #58 has been refreshed to head
`561a6c7ac697dfdf22f304b60e313fccb2c806a4`, which merges current PR #51 head
`e3ffcef` into the OAuth schema-v9 follow-up. This retains the focused seven-
path OAuth change and includes the latest Gateway CI fix in its history. All
seven standard Actions contexts and Vercel passed on this exact head; no status
from the previous `cb37a63` head was carried forward. PR #58 is
`MERGEABLE`/`CLEAN` but remains OPEN/DRAFT with no GitHub review. This branch
refresh is CI provenance only; ChatGPT runtime
readiness and authenticated OAuth/tool/CPU acceptance remain NOT RUN.

The original PR #52 candidate `c824b90` passed its seven required Actions
contexts and Vercel. The P1 branch was then advanced to
`bc9b0305e6b2e86f9d8c214161b10511ce9f012c` with three workflow fixes after
finding that job names did not match three protected check contexts and those
workflows were path-filtered on pull requests. The new exact head passed all
seven protected Actions contexts and Vercel; `gh pr checks --required` reports
all seven successful. PR #52 remains Draft with `REVIEW_REQUIRED`, zero
reviews, and no requested reviewer. The original Security Review covered
`c824b90` only; the workflow-only follow-up was not in that review.

At the earlier 20:32 UTC snapshot, PR #53 (19 files), #54 (21 files), and #55
(38 files) were stacked in order; PR #56 was still running and PR #51 followed
#56. Those statuses are superseded by the 20:52 UTC refresh above. CI results
do not prove deployed runtime readiness or authenticated ChatGPT acceptance.

## Run metadata

- Date/time (UTC): NOT RUN
- Operator:
- ChatGPT plan/workspace type (do not record account email): NOT VERIFIED
- MCP endpoint origin or tunnel ID (do not record API keys):
- Connection type: public HTTPS / Secure MCP Tunnel / NOT RUN
- Gateway commit SHA:
- Worker/supervisor commit SHA:
- Database schema version:
- Workload ID and immutable image digest:
- Local admission policy version and expiry (do not paste policy secrets):
- Release matrix revision:

## Local Secure MCP Tunnel preflight (2026-10-30 13:10 UTC; not a ChatGPT run)

- Host inventory: macOS arm64 with Docker/OrbStack available. `gateway/.env`,
  native `tunnel-client` on `PATH`, and the standard tunnel-client profile
  directories were absent. Environment variable names had no OpenAI, ChatGPT,
  MCP, or tunnel credentials configured; no values were read.
- The cached image
  `ghcr.io/openai/tunnel-client@sha256:486321616c197fed2d3fbe7d44f22433ce9a1e6c1ee434c0d6652868a5fda5c1`
  was inspected and run with `--network none --read-only --cap-drop=ALL
  --security-opt=no-new-privileges`. `help quickstart` and
  `runtimes connect --help` returned successfully. The current quickstart
  confirms that actual use requires a Platform `tunnel_id`, a separate Runtime
  API key with Tunnels Read + Use, a reachable local MCP server, and a running
  client; long-lived local operation should use `runtimes connect` and verify
  `runtimes status <alias>`.
- No tunnel identifier or API key was available in the local environment or
  standard config locations. No Platform tunnel API operation, tunnel process,
  Gateway listener, or ChatGPT connection was started. The host reported no
  running containers; two stopped `gpu-control` test containers from two days
  earlier were left untouched.
- ChatGPT/browser UI state could not be inspected in this execution
  environment (browser use is disabled and CUA access to the ChatGPT app was
  denied). Workspace plan/role, Platform organization, tunnel association, and
  write-action entitlement therefore remain NOT VERIFIED. This is tool/client
  preflight only; all real ChatGPT and CPU execution gates below remain NOT RUN.

Latest PR preview evidence (2026-10-28; not a ChatGPT acceptance run): Vercel
deployment `dpl_DFmSmWfMKE2Nbox5ufWDxKBa7Y9p`, PR head
`f054aebe96460fe033dde8d91d7e3bbab0255655`, target `null`. Read-only fetches
observed `/healthz`=200 but `configured=false` and `auth_configured=false`,
`/readyz`=503 with database/migration/worker/supervisor/registry/authentication
false, and protected-resource discovery=503 `configuration_required`. The
preview build is READY, but the runtime cannot serve ChatGPT until deployment
configuration and durable services are available. The live acceptance gates
below remain **NOT RUN**.

Latest read-only production-alias probe (2026-10-28 04:54 UTC; not an
acceptance run): `/healthz` returned 200 with configured local OAuth,
`/readyz` returned 404, and unauthenticated `/mcp` returned 401 requiring a
bearer token. This shows only that the existing alias responds and rejects an
unauthenticated MCP request. It does not verify the deployed revision,
readiness, an OAuth grant, or ChatGPT tool execution; all acceptance gates
below remain **NOT RUN**.

Fresh public-alias probe (2026-10-28 11:13 UTC; unauthenticated, read-only):
`/healthz`=200 with configured local OAuth, `/readyz`=404,
`/.well-known/oauth-protected-resource/mcp`=200,
`/.well-known/oauth-authorization-server`=200 advertising authorization-code
and refresh-token grants, PKCE S256 and revocation, and `/mcp`=401 requiring a
bearer token. This confirms endpoint liveness, OAuth discovery and the
unauthenticated boundary only; deployed SHA, database/worker readiness, OAuth
grant, tool discovery and ChatGPT calls remain unverified. No token, account
data, authenticated request or ChatGPT conversation was used; acceptance is
still **NOT RUN**.

Refreshed production-alias probe (2026-10-28 06:21 UTC; not an acceptance
run): unauthenticated `/healthz` returned 200 with `configured=true` and
`auth_configured=true`; `/readyz` returned 404; protected-resource discovery
returned 200 and advertised `experiments:read`, `experiments:run`, and
`experiments:cancel`. This still does not establish that the P1 revision is
deployed or ready: `/readyz` is absent, and no OAuth grant or ChatGPT tool call
was performed. Acceptance gates remain **NOT RUN**.

GitHub PR #51 state rechecked at 05:53 UTC: OPEN/DRAFT at
`f054aebe96460fe033dde8d91d7e3bbab0255655`; four PR-triggered Actions workflows
completed successfully (CI `40614634054`, Gateway offline `40614633953`, Gateway
comment bridge `40614633965`, Project bridge `40614633942`), with no submitted
reviews or review threads. These checks cover the pushed commit only, not the
uncommitted worktree or live ChatGPT acceptance.

## Gate results

Use `PASS`, `FAIL`, `BLOCKED`, `UNCERTAIN`, or `NOT RUN`. A `PASS` must link to
redacted evidence collected during this acceptance run.

| Gate | Status | Evidence reference | Notes / blocker |
| --- | --- | --- | --- |
| Account plan supports custom MCP with write actions on ChatGPT web (Business/Enterprise/Edu) | NOT RUN | | |
| Tester has workspace permission to create and test a custom MCP app (Business admin/owner; Enterprise/Edu admin/owner or RBAC-authorized member) | NOT RUN | | |
| Run/cancel write actions are enabled for the test app; if publishing workspace-wide, publisher is an admin/owner | NOT RUN | | |
| The app's discovered tool snapshot is current, and run/cancel actions are explicitly enabled in workspace controls where required | NOT RUN | | |
| Any ChatGPT write-action confirmation prompt is recorded and answered by the tester; server-side owner/scope/policy checks still pass independently | NOT RUN | | |
| Reviewed Gateway revision is reachable through the selected connection (public HTTPS for release, or authorized Secure MCP Tunnel for bounded development smoke) | NOT RUN | | |
| OAuth issuer, authorization, token, and advertised revocation endpoints are reachable through the OAuth flow; tunnel reachability of `/mcp` alone is insufficient | NOT RUN | | |
| `/healthz` and `/readyz` match the deployed revision and are healthy | NOT RUN | | |
| PostgreSQL migration, worker, recovery supervisor, and persistent artifact storage are healthy | NOT RUN | | |
| Installed systemd services have the expected environment-file scope; API, migration, and capacity services receive no provider secrets, and capacity receives no DB credential (inspect names only; never record values) | NOT RUN | | |
| OAuth discovery, PKCE, audience/resource, required scopes, refresh, and revocation work in ChatGPT | NOT RUN | | |
| ChatGPT's selected OAuth client-registration mode succeeds (Gateway currently advertises DCR, not CIMD); DCR client remains usable across reconnection/token refresh | NOT RUN | | |
| ChatGPT discovers the expected eight canonical tools and current schemas | NOT RUN | | |
| `experiment_capabilities` reports only the currently verified CPU lane and its true blockers | NOT RUN | | |
| First conversation completes registered CPU prepare/submit/status/result | NOT RUN | | |
| Result binds the expected run ID, source SHA, plan fingerprint, and image digest | NOT RUN | | |
| Result reports `simulation=false`, `gpu_used=false`, and confirmed cleanup | NOT RUN | | |
| Result artifact digest and bytes are retrieved through the owner-scoped API | NOT RUN | | |
| Same idempotency key returns the same run; explicit rerun uses a new key/run | NOT RUN | | |
| Second conversation finds and retrieves the first conversation's run as the same owner | NOT RUN | | |
| Another owner cannot list, inspect, cancel, or fetch the first owner's run/artifact | NOT RUN | | |
| Cancel and worker restart reconcile the real backend resource without duplication | NOT RUN | | |
| Cost scope and zero additional provider charge are accurately represented | NOT RUN | | |

For a Secure MCP Tunnel development run, also record the Platform organization
and ChatGPT workspace association (names/IDs only), the operator's Tunnels Read
and Use authorization, and whether every call stayed within the documented
120-second deadline and 10 MiB serialized envelope limit. Tunnel evidence does
not count as public distribution, P3 continuous-operation, or large-artifact
acceptance. Never record the tunnel runtime API key.

## Run evidence

Keep this section redacted. Record timestamps, tool names, run IDs, response
status, source/image identity, result digest, and cleanup state. Do not include
access/refresh tokens, cookies, authorization codes, database URLs, private
keys, raw OAuth requests, or unrelated user data.

### First conversation

- Conversation/evidence reference:
- Tool sequence and timestamps:
- Run ID:
- Source SHA / plan fingerprint / image digest:
- Final state and cleanup proof:
- Artifact ID / SHA-256 / size:
- Cost evidence and scope:
- Deviations or failures:

### Second conversation

- Conversation/evidence reference:
- Same-owner list/search result:
- Retrieved run ID and result digest:
- Cross-owner negative check (use a dedicated test principal):
- Deviations or failures:

### Recovery and cancellation

- Worker stop/restart method and timestamps:
- Supervisor observations:
- Backend resource identity and final absence proof:
- Cancellation request/result:
- Duplicate-resource count:
- Deviations or failures:

## Decision

- CPU release decision: NOT DECIDED
- Blocking gates:
- Follow-up issue/PR references:
- Reviewer (independent of implementation):
- Reviewer decision and date (UTC):

Update `docs/RELEASE_MATRIX.md` only from the evidence above and retain the
evidence scope. ChatGPT write confirmations do not replace server-side
authorization. A successful CPU acceptance does not enable GPU or paid paths.

## Seven-day CPU operations observation

Status: **NOT STARTED**. Begin only after the account, deployment, OAuth,
readiness, recovery, storage-quota, alert-delivery, and single-run ChatGPT gates
above pass. This observation is not permission to change repository mode or run
GPU/provider workloads.

Keep Modal and RunPod disabled, local CPU admission restricted to the reviewed
`cpu-smoke-v1` workload, and concurrency at one. Run at most one smoke per UTC
day for seven consecutive UTC dates. Record the host/database/artifact fixed
cost for the observation period: CPU workload cost evidence does not mean the
hosting infrastructure is free. Do not enable automatic retries or let
monitoring create runs. If a request times out or a client disconnects, first
query the existing idempotency key/run and reconcile its state; do not submit a
new key until the first outcome is known.

During the seven days, observe normal cross-session continuity and day-boundary
result retrieval. Perform one planned worker restart while a smoke is active,
and one controlled client disconnect/reconnect; record both. Do not kill the
database, corrupt storage, fill the production volume, or deliberately break
the TLS endpoint as part of this low-volume period. Those failure modes belong
to isolated drills. After each restart or reconnect, verify the same run ID,
terminal result, artifact digest, owner boundary, and cleanup state.

Before starting, record the allowed worker-restart recovery interval and the
alert delivery SLO established by target-host acceptance; do not choose either
threshold after seeing a failure. Stop the observation and leave admissions
disabled if readiness remains false beyond that recovery interval, an outcome
is ambiguous, a duplicate resource appears, an artifact digest/owner check
fails, capacity or alerting fails, or unexpected cost appears. Preserve
evidence and reconcile the existing run; do not auto-retry. A stopped or
interrupted observation restarts its seven-consecutive-day count only after
the cause is understood and the operator records a new start date.

| UTC date | Gateway/worker revision | Readiness + heartbeat | Smoke run ID/result | Disconnect/restart event | Artifact hash + cleanup | Cost / anomalies |
| --- | --- | --- | --- | --- | --- | --- |
| Day 1 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Day 2 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Day 3 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Day 4 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Day 5 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Day 6 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Day 7 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

Pass requires seven consecutive daily records, no unexplained lost/duplicate
runs or artifacts, same-owner cross-day retrieval, completed worker-restart and
client-reconnect checks, all resources cleaned up, functioning low-capacity and
recovery alerts, and accounted-for fixed and variable costs. This procedure
does not assert that the observation has started or passed.

Latest local access observation (2026-10-28 11:40 UTC): opened a fresh
read-only ChatGPT web tab at `https://chatgpt.com/`. The page showed **Log in**
and **Sign up for free**; no authenticated workspace was available. This does
not establish the intended workspace's plan, role, custom MCP eligibility, or
write-action controls. No login, workspace connection, or tool call was
attempted; all ChatGPT acceptance gates remain **NOT RUN**. Recheck after an
authorized workspace session is available.

Fresh connection preflight (2026-10-30 18:23 UTC; not an acceptance run):
the CUA runtime again denied access to the ChatGPT desktop app, and its Chrome
browser surface was unavailable. The available in-app browser had no tabs. The
checked Gateway/OpenAI endpoint variables (`GATEWAY_PUBLIC_ORIGIN`,
`GATEWAY_BASE_URL`, `GATEWAY_OAUTH_CLIENT_ID`, `OPENAI_MCP_URL`) were unset; the
only matching local TCP listener was an unidentified `node` process on port
3000, with no Gateway listener observed. No login, tunnel, OAuth grant, or MCP
request was attempted. This confirms the current acceptance blocker is missing
reachable Gateway/ChatGPT connection state in this session; it does not change
any gate from **NOT RUN** or establish workspace eligibility.


Authenticated Vercel preview endpoint recheck (2026-10-28 09:00 UTC; not a
ChatGPT acceptance run): using the Vercel account's protected-URL fetch for
`https://gpu-control-65fenen47-unjunos-projects.vercel.app`, `/healthz`=200
with `configured=false` and `auth_configured=false`; `/readyz`=503 with
`ready=false` and database, migration, worker, supervisor, registry, and
authentication all false; protected-resource discovery at
`/.well-known/oauth-protected-resource/mcp`=503 `configuration_required`. This
confirms the preview runtime is reachable but unconfigured and not ready. The
authenticated fetch used a temporary Vercel share link; no application
credentials or user tokens were supplied. ChatGPT/OAuth and all acceptance gates
remain **NOT RUN**.

## PR and public runtime recheck — 2026-10-30 16:59 UTC (read-only; not acceptance)

`gh pr view 51` reports PR #51 OPEN/DRAFT at pushed head
`aa681f4062dac6b73bcf380a38a4258b96a47e1d`, `REVIEW_REQUIRED`, with seven
successful Actions checks and a successful Vercel status. These checks belong
to that pushed revision; they do not cover the current uncommitted worktree.

Fresh unauthenticated GETs to `https://gpu-control.vercel.app` returned
`/healthz`=200 (`configured=true`, `auth_configured=true`,
`auth_mode=local_oauth`), `/readyz`=404,
`/.well-known/oauth-protected-resource`=200 advertising the read/run/cancel
scopes, and `/mcp`=401 requiring a bearer token. The responses do not identify
the deployed SHA or establish readiness, an OAuth grant, or ChatGPT-originated
tool use. No account, credential, GitHub, deployment, or provider state was
changed. ChatGPT acceptance remains **NOT RUN**.

The live `main` branch protection API confirms strict required status checks:
`Python 3.11`, `Python 3.12`, `Python 3.13`, `Trusted reference container`,
`Gateway offline tests`, `Gateway comment bridge tests`, and `Project bridge
tests`. The successful checks reported above match these contexts on the
current pushed PR head. Local uncommitted changes still need to be pushed to a
reviewable PR head before these required checks can validate them.

Current local connection preflight (2026-10-28; not an acceptance run): Docker
CLI and daemon are available; the native `tunnel-client` binary is not on the
host PATH, and no `gpu_gateway`, Uvicorn, or tunnel-client process is running.
The official client is now available through the attested pinned Docker image
recorded below. No local Gateway or tunnel was started. The intended ChatGPT workspace's plan, tester/publisher
role, write-action permission, Platform tunnel permissions, and workspace
association remain unverified; no OAuth grant or ChatGPT-side setting was changed.

Fresh PR preview runtime check (2026-10-28 09:26 UTC; read-only, not an
acceptance run): latest Vercel READY preview for PR #51 head
`f054aebe96460fe033dde8d91d7e3bbab0255655` returned `/healthz`=200 with
`configured=false` and `auth_configured=false`; `/readyz`=503 with database,
migration, worker, supervisor, registry, and authentication all false; OAuth
protected-resource discovery returned 503 `configuration_required`. The preview
remains unconfigured and cannot be used for ChatGPT connection or CPU acceptance.
No variables, OAuth credentials, database state, or deployment were changed.

Current tunnel-client preparation (2026-10-28; not an acceptance run): the
official OpenAI `v0.0.18` multi-architecture Docker image was fetched by digest
`sha256:486321616c197fed2d3fbe7d44f22433ce9a1e6c1ee434c0d6652868a5fda5c1`.
`gh attestation verify oci://ghcr.io/openai/tunnel-client:v0.0.18 -R
openai/tunnel-client` exited successfully. The ARM64 image reported version
`0.0.18+274a5588414819f063d27100a4fb1096aae3830f`; `help quickstart` completed
with networking disabled, read-only rootfs, all Linux capabilities dropped,
and no-new-privileges. Native Homebrew inspection could not proceed because
this host has not accepted the Xcode license; no license was accepted and no
Gatekeeper bypass was attempted. No tunnel, Platform API request, runtime key,
ChatGPT workspace association, local Gateway process, or OAuth grant was used.
The client binary is available via its cached pinned Docker image, but live
connection acceptance remains **NOT RUN**.

Latest PR preview recheck (2026-10-28 09:52 UTC; authenticated Vercel fetch,
read-only): project metadata and deployment listing match READY deployment
`dpl_DFmSmWfMKE2Nbox5ufWDxKBa7Y9p`, target `null`, to PR #51 head
`f054aebe96460fe033dde8d91d7e3bbab0255655`. `/healthz`=200 but
`configured=false` and `auth_configured=false`; `/readyz`=503 with database,
migration, worker, supervisor, registry, and authentication false; protected-
resource discovery=503 `configuration_required`. Vercel environment-variable
listing returned 403 `forbidden`; the documented CLI fallback is not installed.
No environment values or secrets were read. The preview cannot accept ChatGPT
or CPU runs. No environment, deployment, DB, OAuth, or provider setting was
changed; all ChatGPT gates remain **NOT RUN**.

Latest P1 deployment recheck (2026-10-28 11:02 UTC; read-only): Vercel
deployment listing still identifies READY preview
`dpl_DFmSmWfMKE2Nbox5ufWDxKBa7Y9p` at commit
`f054aebe96460fe033dde8d91d7e3bbab0255655`. Authenticated fetch of its
`/readyz` returned HTTP 503 with `ready`, database, migration, worker,
supervisor, registry, and authentication all false. A direct read-only request
to `https://gpu-control.vercel.app` returned `/healthz`=200,
`/readyz`=404, authorization-server discovery=200, protected-resource
discovery=200, and unauthenticated `/mcp`=401. Thus public OAuth discovery and
liveness are reachable on the alias, but the alias does not serve the current
readiness route; the latest preview contains the route but is unconfigured.
No deployment setting, environment variable, database, OAuth grant, or
ChatGPT workspace was changed. This remains deployment preflight only; no
ChatGPT OAuth/tool call or CPU run occurred, and all acceptance gates remain
**NOT RUN**.

## P0/P1 access recheck (2026-10-28 11:25 UTC)

Opened the current ChatGPT web app in a fresh Codex in-app browser tab. It
showed **Log in / Sign up** and no authenticated workspace, so the account
plan, target workspace, tester/publisher role, custom-MCP permissions, and
existing plugins could not be inspected. No sign-in was attempted and no
workspace setting or plugin was changed. This observation does not prove the
user lacks access; workspace eligibility and every live ChatGPT acceptance
gate remain **NOT RUN** pending an authenticated session.

## P0/P1 ChatGPT and Platform access recheck (2026-10-28 11:42 UTC)

Reopened `https://chatgpt.com/` in a fresh tab; it showed **Log in** and
**Sign up for free**. Opened the OpenAI Platform tunnel settings URL in a
separate fresh tab; it redirected to the Platform login page and displayed an
email sign-in form. No authenticated ChatGPT workspace or Platform organization
was available, so existing tunnel inventory, `tunnel_id`, runtime-key presence,
Tunnels Read + Manage/Use roles, and workspace association could not be read.
No login, key creation, tunnel creation, workspace change, or MCP call was
attempted. This blocks end-to-end connectivity verification in the current
session, but does not establish that the user lacks an eligible account or
workspace. ChatGPT/OAuth/tool acceptance remains **NOT RUN**.

The current [Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
requires Tunnels Read + Manage to create or edit a tunnel and Tunnels Read + Use
to run `tunnel-client` or select the tunnel in ChatGPT. The tunnel must also be
associated with the target ChatGPT workspace and the Platform organization
used for testing. Treat these as separate prerequisites from the ChatGPT
workspace's permission to add and use custom MCP servers.

The current official guides were re-read on 2026-10-28. Custom MCP with write
actions is available to Business and Enterprise/Edu workspaces on ChatGPT web;
Enterprise/Edu may grant creator/tester rights by RBAC while publication stays
admin/owner-only. Secure MCP Tunnel can carry OAuth discovery, but does not
automatically tunnel the authorization server itself. The MCP tool calls,
authorization endpoint reachability, token exchange, refresh, and revocation
must each be tested in the intended workspace before acceptance. See the
[current ChatGPT custom MCP guide](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
and [Secure MCP Tunnel OAuth guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels#oauth).

## P0/P1 access recheck (2026-10-29)

Opened `https://chatgpt.com/` in a fresh in-app browser tab; it displayed Log
in / Sign up. Opened the OpenAI Platform tunnel settings URL in a second fresh
tab; it redirected to Platform login. No authenticated account, workspace,
organization, tunnel, key, or permission could be inspected. No sign-in or
configuration change was attempted. This does not establish that the user
lacks an eligible account; the ChatGPT/OAuth/tool acceptance gates remain
**NOT RUN**.

## Public endpoint recheck (2026-10-28 11:52 UTC)

Read-only unauthenticated GETs to `https://gpu-control.vercel.app` returned
`/healthz`=200 (`configured=true`, `auth_configured=true`),
`/.well-known/oauth-authorization-server`=200, `/mcp`=401
(`invalid_token`: bearer access token is required), and `/readyz`=404. The
alias advertises OAuth and enforces authentication but does not expose the
readiness route required by the current P1 service contract. The branch-preview
hostname returned Vercel Authentication 401 to unauthenticated requests; this
probe did not perform an authenticated preview fetch or query deployment
metadata. No credentials, tokens, workspace, deployment settings, database,
or provider resources were changed. This does not establish the deployed source
revision or ChatGPT tool acceptance; all live ChatGPT gates remain **NOT RUN**.

## Public endpoint recheck (2026-10-29 02:41 UTC)

Read-only unauthenticated requests to `https://gpu-control.vercel.app` returned
`/healthz`=200 with configured local OAuth, OAuth authorization-server
discovery=200, `/mcp`=401 requiring a bearer token, and `/readyz`=404. The
readiness-route gap persists. This does not identify the deployed source
revision or prove tool usability; no authenticated ChatGPT/Platform session,
OAuth grant, deployment setting, or runtime was used or changed.

## P1 deployment refresh (2026-10-30)

- GitHub PR #51 is OPEN/DRAFT at head
  `144cccebca3351b42cd9261375b012784f3b8715`; all current required checks
  pass. The Gateway CI integration run passed 424 tests / 1 optional skip with
  PostgreSQL and the digest-pinned local CPU container. No GitHub review has
  been submitted; review remains required.
- Vercel's read-only deployment record identifies preview deployment
  `dpl_CWs7WJ4hKt2thQtmMZeVabiKV84f` as READY from that exact SHA. Project
  metadata shows preview SSO protection enabled. Direct unauthenticated
  requests to the preview redirect to Vercel login, so the preview's runtime
  `/healthz` and `/readyz` responses were not observed.
- The production alias still returns `/healthz`=200, `/readyz`=404, and
  unauthenticated `/mcp`=401. No ChatGPT OAuth grant, workspace tool scan,
  experiment call, or result retrieval has been completed; acceptance remains
  **NOT RUN**. No additional temporary Vercel share link was created for this
  recheck. Earlier authenticated preview-only GETs on 2026-10-28 used a
  temporary share link and found the preview unconfigured; approval to create
  or reuse a fresh link for another read-only readiness check remains pending.

## Local CPU and systemd checks — 2026-10-30 (not ChatGPT acceptance)

- With the cached local CPU smoke image pinned by digest, the Gateway suite
  completed **416 passed, 9 skipped**. Real local Docker CPU/MCP, worker-crash
  recovery, and cross-client artifact retrieval cases ran and passed. The
  skipped PostgreSQL outage/concurrency cases had no dedicated database
  configured. The image carries the tests' synthetic fixture source SHA, not a
  production workload provenance claim.
- All eight Gateway systemd templates passed `systemd-analyze verify` in an
  isolated Debian 12/systemd 252.39 container with a read-only repository mount
  and no network. No service was started.
- The root/core suite also passed: **550 passed, 1 skipped**; the single skip
  is a Python 3.11-specific RunPod malformed-log reproducer.
- These checks do not change the overall **NOT RUN** status: ChatGPT workspace
  eligibility, OAuth, tool discovery, ChatGPT-originated CPU execution, and
  second-conversation result retrieval remain unverified.

## Latest PR state — 2026-10-30 13:17 UTC

Read-only `gh pr view 51` reports PR #51 OPEN/DRAFT at head
`aa681f4062dac6b73bcf380a38a4258b96a47e1d`, `REVIEW_REQUIRED`, and merge
blocked, with no submitted reviews. All seven required GitHub Actions checks,
the Vercel status, and Vercel Preview Comments are successful for that remote
head. They do not cover this turn's uncommitted documentation-only updates;
no review, push, deployment, or merge was performed.

## Production alias recheck — 2026-10-30 13:41 UTC (read-only; not acceptance)

Fresh unauthenticated GETs to `https://gpu-control.vercel.app` returned:
`/healthz` 200 with `configured=true`, `auth_configured=true`, and
`auth_mode=local_oauth`; `/readyz` 404; `/mcp` 401 with
`invalid_token` / bearer token required. This confirms the public alias still
serves a revision without the readiness route. It does not establish its exact
source SHA, OAuth flow, backend readiness, or ChatGPT acceptance. No token or
other credential was supplied; no write request or deployment action occurred.

## Production alias recheck — 2026-10-30 14:36 UTC (read-only; not acceptance)

Fresh unauthenticated GETs again returned `/healthz` 200 with
`configured=true`, `auth_configured=true`, `auth_mode=local_oauth`; `/readyz`
404; and `/mcp` 401 with bearer token required. The public alias therefore
still does not expose the readiness contract required for the P1 acceptance
sequence. No token, ChatGPT connection, OAuth grant, write request, or deployment
action was used. The endpoint response does not identify its source SHA.

## `/readyz` source/deployment boundary — 2026-10-30 (read-only)

- The current local source at `aa681f4062dac6b73bcf380a38a4258b96a47e1`
  registers `GET /readyz` in `gateway/gpu_gateway/app.py`.
- `origin/main` at `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e` does not register
  `/readyz`; its app defines `/healthz` only. Current PR #51 is OPEN/DRAFT at
  `aa681f4`, still `REVIEW_REQUIRED`, with no submitted review.
- The public alias currently returns `/readyz` 404. This is consistent with
  serving code that predates the local readiness route, but the HTTP response
  does not identify the deployed SHA, so deployment provenance remains
  unverified. The local route is not production acceptance: it needs a reviewed
  and deployed revision, followed by an authenticated readiness/ChatGPT run.
- No GitHub write, deployment, OAuth grant, or ChatGPT connection was performed.

## Production alias recheck — 2026-10-30 14:44 UTC (read-only; not acceptance)

Fresh unauthenticated GETs to `https://gpu-control.vercel.app` returned
`/healthz`=200 (`configured=true`, `auth_mode=local_oauth`), `/readyz`=404,
and `/mcp`=401 (`Bearer access token is required`). This confirms the alias
still serves a runtime without the current readiness route. It does not identify
the deployed SHA or establish database/worker readiness, OAuth grant, or
ChatGPT tool execution. No credentials, token, deployment, DB, or ChatGPT
workspace setting was used or changed; all acceptance gates remain **NOT RUN**.

## Vercel deployment provenance recheck — 2026-10-30 14:49 UTC (read-only)

The Vercel API identifies the latest production deployment as
`dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`, target `production`, Git ref `main`, SHA
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. The latest PR preview is
`dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe`, target `null`, ref
`codex/chatgpt-cpu-vertical`, SHA `aa681f4062dac6b73bcf380a38a4258b96a47e1`,
state READY. Vercel project metadata shows SSO protection enabled for all
deployments except custom domains. Thus the production alias is confirmed to
run old `main`; PR #51's current head exists as a protected preview, not as the
production runtime.

No authenticated preview fetch was made: the available Vercel fetch operation
creates or reuses a temporary share link that expires after 23 hours, and no
authorization for that link was given. The public production probe above stays
unauthenticated. This deployment metadata does not establish preview runtime
readiness or ChatGPT acceptance; all acceptance gates remain **NOT RUN**.
The read-only Vercel deployment-file listing also returned `404 not_found`
(`File tree not found`) for this Git deployment, so no source bundle was
available through that endpoint. Read-only build events show Python 3.12,
uv 0.13.5, dependency installation from `gateway/uv.lock`, and a completed
deployment build. The lock resolves `gpu-control` from editable path `../`.
This is build evidence only; function importability and runtime readiness remain
unverified.

The names-only Preview environment-variable query (`decrypt=false`, branch
`codex/chatgpt-cpu-vertical`) returned `403 forbidden`. No values were fetched.
The Vercel CLI fallback is not installed in this environment, so Preview
configuration names and target scopes remain unverified; do not infer a missing
variable from `configured=false` alone.

## Production alias recheck — 2026-10-30 15:27 UTC (read-only; not acceptance)

Fresh unauthenticated GETs to `https://gpu-control.vercel.app` returned
`/healthz`=200 (`configured=true`, `auth_configured=true`,
`auth_mode=local_oauth`), `/readyz`=404, protected-resource discovery=200
advertising `experiments:read`, `experiments:run`, and `experiments:cancel`, and
`/mcp`=401 requiring a bearer token. This confirms the public alias still serves
a revision without the current `/readyz` route and continues to reject
unauthenticated MCP requests. The responses do not establish database/worker
readiness, OAuth grant, or ChatGPT tool execution. No credentials, token,
deployment, database, or workspace setting was used or changed; acceptance
gates remain **NOT RUN**.

## Production alias recheck — 2026-10-30 15:48 UTC (read-only; not acceptance)

A fresh unauthenticated GET to `https://gpu-control.vercel.app` returned
`/healthz`=200 (`configured=true`, `auth_mode=local_oauth`), `/readyz`=404,
protected-resource discovery=200, and `/mcp`=401. This confirms the public alias
still lacks the readiness route present in the current local Gateway source;
the response does not identify the deployed SHA. No OAuth grant, authenticated
MCP request, ChatGPT workspace action, deployment, database, or credential was
used or changed. Acceptance gates remain **NOT RUN**.

## Production and ChatGPT session recheck — 2026-10-30 16:11 UTC (read-only; not acceptance)

Fresh unauthenticated GETs to `https://gpu-control.vercel.app` returned
`/healthz`=200 (`configured=true`, `auth_configured=true`,
`auth_mode=local_oauth`), `/readyz`=404, protected-resource discovery=200
advertising `experiments:read`, `experiments:run`, and `experiments:cancel`,
and `/mcp`=401 because a bearer token is required. The alias still does not
serve the readiness route present in this checkout; its deployed SHA is not
identified by these responses.

The ChatGPT in-app browser displayed **Log in / Sign up** on `chatgpt.com`.
No sign-in, OAuth grant, workspace setting, ChatGPT action, or tool call was
attempted. This establishes that this browser session is unauthenticated; it
does not establish whether the user has another eligible workspace or role.
ChatGPT-originated execution and cross-conversation result retrieval remain
**NOT RUN**. No production or account state was changed.

## ChatGPT workspace access recheck — 2026-10-31 (read-only; not acceptance)

Opened a fresh visible in-app browser tab at `https://chatgpt.com/`. The page
showed **Log in** and **Sign up for free**, confirming the current browser
session is unauthenticated. No sign-in, workspace discovery, OAuth grant,
MCP connection, tool action, or account/workspace setting was attempted. The
target workspace and write-action eligibility remain unknown; all ChatGPT
acceptance gates remain **NOT RUN**. Continue local implementation while
waiting for the user to identify the authenticated target workspace.

## Public alias probe — 2026-10-30 16:34 UTC (JST 2026-10-31; not acceptance)

Unauthenticated GETs to `https://gpu-control.vercel.app` returned:

- `/healthz`: 200, configured with local OAuth.
- `/readyz`: 404; the alias does not expose the readiness endpoint in the
  current local Gateway source.
- `/.well-known/oauth-protected-resource/mcp`: 200, advertising the three
  `experiments:read`, `experiments:run`, and `experiments:cancel` scopes.
- `/mcp`: 401, requiring a bearer access token.

These responses confirm liveness, OAuth metadata, and the unauthenticated
boundary only. They do not identify the deployed SHA or establish database,
worker, supervisor, artifact-storage, OAuth-grant, or ChatGPT readiness. The
ChatGPT tab remains logged out, and all ChatGPT acceptance gates remain
**NOT RUN**. No credential or authenticated request was used.

## OpenAI custom MCP requirements recheck — 2026-10-31 (official docs; not acceptance)

Re-read OpenAI's [current custom MCP connection guide](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt),
which reports an update three days before this check. It confirms custom MCP
with full read/write support on ChatGPT Business and Enterprise/Edu web;
Business creation/publication is admin/owner-only, while Enterprise/Edu can
grant selected members create/test permission through RBAC and keeps workspace
publication admin/owner-only. The current Plugins path is Plugins → + → Add
custom MCP server; Developer Mode is not required for this flow. OAuth setup
must support refresh tokens; the guide specifically calls out `offline_access`
for OIDC discovery and warns that sessions can expire without refresh-token
issuance.

This current source check is consistent with the setup guidance and the local
OAuth metadata, which advertises `offline_access` and refresh-token grants. It
does not establish eligibility or permissions for the intended workspace,
successful ChatGPT OAuth, discovered tools, or a ChatGPT-originated run. The
browser still has no authenticated workspace; all ChatGPT acceptance gates
remain **NOT RUN**.

## PR and public runtime recheck — 2026-10-30 16:38 UTC (read-only; not acceptance)

`gh pr view 51` still reports PR #51 OPEN/DRAFT at head
`aa681f4062dac6b73bcf380a38a4258b96a47e1d`, `REVIEW_REQUIRED`, with no GitHub
review. The seven required Actions checks and Vercel status are successful for
that pushed head; they do not cover current local changes.

Fresh unauthenticated requests to `https://gpu-control.vercel.app` returned
`/healthz`=200, `/readyz`=404, protected-resource metadata=200 with the
read/run/cancel scopes, and `/mcp`=401. These responses do not identify the
deployed SHA or verify database, worker, supervisor, artifact storage, an OAuth
grant, or ChatGPT tool use. All live ChatGPT acceptance gates remain
**NOT RUN**. No GitHub or deployment setting was changed.

## ChatGPT login preflight refresh — 2026-10-30 16:43 UTC (read-only; not acceptance)

Opened a fresh hidden in-app browser tab at `https://chatgpt.com/`. It displayed
**Log in** and **Sign up for free**; no authenticated workspace is available in
this browser session. No sign-in, workspace discovery, OAuth grant, MCP
connection, or tool action was attempted. This does not establish whether
another eligible workspace exists. ChatGPT workspace and execution acceptance
remain **NOT RUN**.

## ChatGPT workspace preflight refresh — 2026-10-30 17:16 UTC (read-only; not acceptance)

Opened a fresh visible in-app browser tab at `https://chatgpt.com/`. The page
showed **Log in** and **Sign up for free**. This browser session has no
authenticated ChatGPT workspace, so no OAuth connection, tool discovery, or
execution was attempted. This says nothing about another workspace/account
being eligible. Live ChatGPT acceptance remains **NOT RUN**.

## PR preview source and production deployment recheck — 2026-10-30 17:18 UTC (read-only)

Vercel's deployment record and build events identify the READY PR preview as
source repository `Unjuno/gpu-control`, branch
`codex/chatgpt-cpu-vertical`, commit
`aa681f4062dac6b73bcf380a38a4258b96a47e1d`. The preview is therefore built
from the current pushed PR head. The local uncommitted changes are not in that
deployment. The latest production deployment record still points to `main` at
`24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`.

This confirms deployment source provenance only. No protected preview runtime
fetch was made in this recheck, and no Vercel environment values or secrets
were read. The latest public production-alias probe still returned
`/readyz`=404; no ChatGPT OAuth grant, tool discovery, or ChatGPT-originated
execution is verified. Live ChatGPT acceptance remains **NOT RUN**.

## Current external gate recheck — 2026-10-31 03:34 JST / 2026-10-30 18:34 UTC (read-only; not acceptance)

- A fresh visible `chatgpt.com` tab displayed **Log in** and **Sign up for free**. This session has no authenticated ChatGPT workspace. No sign-in, workspace discovery, OAuth grant, MCP connection, tool action, or account change was attempted.
- Unauthenticated GETs to `https://gpu-control.vercel.app` returned `/healthz`=200 (`configured=true`, `auth_mode=local_oauth`), `/readyz`=404, OAuth protected-resource metadata=200, OAuth authorization-server metadata=200 (including `authorization_code`, `refresh_token`, and `offline_access`), and `/mcp`=401 (`Bearer access token is required`). This is protocol/liveness evidence only; it does not prove a durable worker, database, or ChatGPT run.
- The PR preview deployment `dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe` is READY for remote PR head `aa681f4062dac6b73bcf380a38a4258b96a47e1d`. Unauthenticated requests to its `/healthz` and `/readyz` both redirected to Vercel SSO (302). No authenticated preview fetch or protection bypass was created.
- Read-only GitHub API shows PR #51 OPEN/DRAFT, base `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, head `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, zero submitted reviews and zero inline review comments. Its seven required Actions contexts passed at 2026-10-30 12:39 UTC. The local checkout is `a794438f42bd7246f463eaaa40d963af0aae9d13`, 68 commits ahead of local `origin/main` and 2 commits ahead of the PR branch, with 40 modified/untracked paths. These local commits and edits are not covered by those remote checks or reviews.
- `policies/repository-state.yaml` remains `mode: parked`; no GitHub, Vercel, ChatGPT, provider, or production setting was changed. ChatGPT OAuth/tool execution and cross-conversation result retrieval remain **NOT RUN**. The immediate acceptance dependencies are an authenticated eligible ChatGPT workspace and authorized access to the protected preview or a reviewed persistent endpoint.

## Local real-container MCP vertical plus current workspace check — 2026-10-31 04:08 JST / 2026-10-30 19:08 UTC

- The exact-source local MCP record at [`2026-10-31-p1-v9-source-matched-cpu-suite.md`](acceptance/2026-10-31-p1-v9-source-matched-cpu-suite.md#exact-committed-source-local-mcp-cpu-run--2026-10-31-jst) now includes a successful real Docker CPU run through the in-process MCP route: `experiment_prepare` with idempotent replay, `experiment_submit`, `experiment_result`, and byte-exact `experiment_artifact` retrieval through a second HTTP client. Run ID `bd23cb1f3c4b4165aa069cd8646f0125`; source `a794438f42bd7246f463eaaa40d963af0aae9d13`; image `sha256:15acf11d33636ac3dfd92eee59df028f9d65eae2524cdfd7cbda44bdf361b59b`; cleanup completed. This is a local MCP/backend test with synthetic OAuth, not a ChatGPT conversation or deployment acceptance.
- Opened a fresh in-app browser tab at `https://chatgpt.com/`; it displays **Log in** and **Sign up for free**. No authenticated target workspace is available in this browser session. No login, workspace change, OAuth grant, or ChatGPT tool call was attempted. This does not establish eligibility of another account/workspace.
- Overall ChatGPT acceptance remains **NOT RUN**. The live gates still require an authenticated eligible workspace, a reviewed reachable Gateway deployment with healthy `/readyz`, completed ChatGPT OAuth/tool discovery, and the actual CPU run/result-retrieval sequence in separate conversations.

## Production and preview source recheck — 2026-10-31 04:25 JST / 2026-10-30 19:25 UTC (read-only; not acceptance)

- Vercel deployment metadata identifies the production alias `gpu-control.vercel.app` as deployment `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`, built from `main` at `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. That is older than the local reviewed source at `a794438f42bd7246f463eaaa40d963af0aae9d13`.
- The latest PR preview `dpl_GEFjNPeWZF9zaVCV8pXks81eqZhe` is READY at pushed head `aa681f4062dac6b73bcf380a38a4258b96a47e1`, but unauthenticated requests to its `/healthz` and `/readyz` redirect to Vercel SSO (302). No authenticated share link was created and no deployment variables were read.
- Fresh unauthenticated production requests returned `/healthz`=200 (`configured=true`, `auth_configured=true`, `auth_mode=local_oauth`), `/readyz`=404, protected-resource metadata=200, authorization-server metadata=200 (authorization code, refresh token, PKCE S256, and `offline_access` advertised), and `/mcp`=401 requiring a bearer token.
- These responses establish public liveness, OAuth discovery, and the unauthenticated boundary only. The deployed SHA does not include the current vertical, preview readiness cannot be observed without the protected access path, and no OAuth grant, ChatGPT tool listing, or ChatGPT-originated CPU run was performed. All live ChatGPT acceptance gates remain **NOT RUN**; repository mode remains parked.
## Local Secure MCP Tunnel preflight refresh — 2026-10-31 04:27 JST (read-only; not acceptance)

Checked matching environment-variable names without reading values, expected
local config locations by existence only, the native `tunnel-client` binary,
and running Docker container names. No Gateway origin/OAuth client or tunnel
configuration files, native tunnel client, or Gateway/tunnel container were
present. The only matching environment name was a Codex-managed MCP node path,
not a tunnel credential. No tunnel ID or runtime API key is available in this
session, so no local Gateway, tunnel process, OAuth flow, or ChatGPT request
was started. ChatGPT acceptance remains **NOT RUN**; obtaining Platform
Tunnels Read + Use credentials and a tunnel associated with the eligible
ChatGPT workspace is still required for the bounded development smoke.

## Current-session workspace and PR recheck — 2026-10-31 19:32 UTC (read-only)

- Opened a fresh ChatGPT web tab in the available in-app browser. It displayed
  **Log in** and **Sign up for free**. The ChatGPT desktop app is present but
  CUA reported that this session is not allowed to control it; Chrome is not
  an available browser surface. No login, workspace change, OAuth grant, or
  tool action was attempted.
- Read-only `gh pr view 51` confirms PR #51 is OPEN/DRAFT, base `main` at
  `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`, head
  `aa681f4062dac6b73bcf380a38a4258b96a47e1d`, review decision
  `REVIEW_REQUIRED`, and no submitted reviews. Its seven required Actions
  checks and Vercel statuses succeed on that pushed head. The local checkout
  remains two commits ahead with an uncommitted worktree; those changes are
  outside the remote checks and review. A follow-up branch-protection API read
  hit GitHub's rate limit, so no new branch-protection claim is made here.
- This is a workspace-access and remote-PR state check, not ChatGPT acceptance.
  No custom MCP application, tunnel, deployment, provider call, or GPU run was
  created or used. All live acceptance gates remain **NOT RUN**.

## Current-session external-gate refresh — 2026-10-31 08:07 JST / 2026-10-30 23:07 UTC (read-only)

- A fresh visible ChatGPT web tab displays **Log in** and **Sign up for free**.
  This browser has no authenticated workspace, so no OAuth consent, MCP
  discovery, or ChatGPT-originated experiment was attempted.
- GitHub API reports PR #57 OPEN/DRAFT at
  `51b88f6110e2fc12de1c475e6e3d07c5438eaa3b`; PR #58 OPEN/DRAFT at
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4`; and aggregate PR #51
  OPEN/DRAFT at `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`. PR #57/#58
  currently have no submitted GitHub reviews. The connected GitHub API shows
  their latest PR workflow runs completed successfully (four named workflows
  per head); the combined status endpoint also reports Vercel success for both
  heads. These checks do not include the local uncommitted changes. PR #51 is
  still an unreviewed aggregate and is not a deployment candidate.
- Local checkout remains `a794438f42bd7246f463eaaa40d963af0aae9d13` on
  `codex/chatgpt-cpu-vertical`, 55 commits ahead and 56 behind its configured
  upstream, with 47 modified tracked and 20 untracked paths. No changes were
  staged or published. The exact 67-path ownership audit is in
  `docs/superpowers/plans/2026-10-28-gpu-control-worktree-slices.md`.
- Repository mode remains `parked`. This refresh performs no deployment,
  provider call, GPU allocation, or paid execution. P1 live acceptance remains
  **NOT RUN**; the immediate external prerequisites are an authenticated
  eligible ChatGPT workspace, an independently reviewed/published P1 head, and
  an authorized reachable deployment exposing healthy `/readyz`.

## Live production alias recheck — 2026-10-31 08:30 JST (read-only; not acceptance)

Unauthenticated GETs to `https://gpu-control.vercel.app/healthz`,
`/readyz`, and `/.well-known/oauth-authorization-server` returned **200, 404,
200** respectively. An unauthenticated JSON-RPC POST to `/mcp` returned **401**.
This confirms the alias is reachable and still enforces its bearer boundary,
but production does not expose the current `/readyz` contract and cannot prove
worker/database readiness or ChatGPT execution. No token, authenticated request,
OAuth grant, setting change, or deployment was used.

PR #58 remains OPEN/DRAFT at published head
`561a6c7ac697dfdf22f304b60e313fccb2c806a4`; its seven required Actions checks
and Vercel preview pass on that published head, with no review decision. The
complete local P1+P3 patch at `/tmp/gpu-control-p1-p3-on-58-complete.patch` is
not part of that head, so these remote checks do not cover the candidate. Live
ChatGPT CPU acceptance remains **NOT RUN**.

## Current-session recheck — 2026-10-31 09:41 JST (read-only; not acceptance)

- Fresh unauthenticated requests to production returned `/healthz`=200,
  `/readyz`=404, OAuth authorization-server metadata=200, and an unauthenticated
  `tools/list` POST to `/mcp`=401. These responses confirm liveness, OAuth
  discovery, and the bearer boundary only; production does not expose the
  current readiness contract and no authenticated MCP call was made.
- GitHub CLI reads show PR #51 OPEN/DRAFT at
  `e3ffcef580d4b7b13ec12f1b6c53014bbca254b1`, PR #58 OPEN/DRAFT at
  `561a6c7ac697dfdf22f304b60e313fccb2c806a4`, and PR #59 OPEN/DRAFT at
  `76c2a1a1b4439cf093c4e6efdd39d5121eb08959`. Each has the seven required
  Actions checks and Vercel successful on its published head, with no submitted
  review decision. None covers the local dirty worktree at
  `a794438f42bd7246f463eaaa40d963af0aae9d13` plus its uncommitted changes.
- No authenticated workspace, OAuth grant, ChatGPT tool call, deployment, or
  provider action was used in this refresh. Real ChatGPT CPU/result acceptance
  remains **NOT RUN** and repository policy remains `mode: parked`.
- At 2026-10-31 09:43 JST, a fresh visible ChatGPT web session displayed
  **Log in** and **Sign up for free**. No workspace controls or authenticated
  connection settings were available in this session.
- The current [OpenAI custom MCP connection guidance](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
  confirms that full MCP write actions are currently available for Business,
  Enterprise, and Edu workspaces; Pro custom connections are limited to
  read/fetch. The workspace must permit custom MCP connections and the user
  must have its create/test role. The documented connection uses public HTTPS
  or an available Secure MCP Tunnel. After workspace approval, ChatGPT uses a
  frozen tool/input snapshot, so published tool changes require refreshing the
  workspace app before acceptance. The intended workspace plan, role, policy,
  and tunnel availability remain unverified in this session.

## Current-session access and OAuth mode — 2026-10-31 11:07 JST (read-only; not acceptance)

- A fresh ChatGPT web tab showed **Log in** and **Sign up for free**. No
  authenticated workspace, plan, role, or custom-app controls were available;
  no login or settings change was attempted.
- The current Gateway authorization-server metadata advertises DCR at
  `/oauth/register`, `token_endpoint_auth_methods_supported: ["none"]`, and
  PKCE `S256`. It does not advertise
  `client_id_metadata_document_supported`; the implemented/testable ChatGPT
  registration lane is DCR.
- OpenAI's current authentication guide says DCR remains supported and
  recommends CIMD when the server supports it and the app creator selects it.
  CIMD would require a separately reviewed metadata-fetch and client-assertion
  implementation; it is not enabled by changing discovery metadata alone. The
  acceptance gate now requires successful DCR and reuse across reconnection.
- The complete Gateway/Core test suites and remote PR CI do not establish a
  ChatGPT DCR/OAuth exchange. OAuth/tool discovery, real CPU execution, and
  cross-conversation retrieval remain **NOT RUN**. Repository mode remains
  `parked`.

## Current GitHub and Vercel gate refresh — 2026-10-31 11:12 JST (read-only)

- PRs #51–#59 are still OPEN/DRAFT. All nine published status entries on each
  listed head report success; none has a submitted review decision. PR #52
  remains `REVIEW_REQUIRED`. PR #43 remains open with `REVIEW_REQUIRED` and
  five successful status entries. These checks cover published heads only,
  not the dirty primary worktree.
- Vercel deployment metadata maps production alias `gpu-control.vercel.app`
  to READY deployment `dpl_5XTNRHXiZ6C4zQmo949m2Mv9wDgJ`, built from `main`
  at `24ecb9bba0264c5370b2a5d94d2fe373e4afeb9e`. Public probes returned
  `/healthz` 200, `/readyz` 404, OAuth authorization-server metadata 200, and
  unauthenticated `/mcp` 401.
- PR #58 head `561a6c7ac697dfdf22f304b60e313fccb2c806a4` has READY Preview
  deployment `dpl_3QtLZEQudmfXMHexbmmUc46mVivv`. Direct unauthenticated requests
  to its `/healthz` and `/readyz` both return a Vercel SSO redirect (302), so
  the candidate's live readiness response remains unobserved. No temporary
  share link, deployment, setting change, OAuth grant, or provider action was
  made.
- The exact outstanding P1 dependencies are independent GitHub review, an
  authorized way to inspect a readiness-verified deployment, and an eligible
  authenticated ChatGPT workspace for OAuth, tool discovery, CPU execution,
  and result retrieval. Preserve `mode: parked`.

## Secure MCP Tunnel client refresh — 2026-10-31 11:17 JST (offline preflight)

- Read-only GitHub release metadata identifies `openai/tunnel-client` v0.0.19,
  published 2026-10-30. The official command
  `gh attestation verify oci://ghcr.io/openai/tunnel-client:v0.0.19 -R
  openai/tunnel-client` exited successfully. The multi-architecture index digest
  is `sha256:dcae53be336c062ffdc3f250a287b2a07724c344b8c370a50f54ad033af43151`;
  the Linux ARM64 manifest digest is
  `sha256:e38276d38eff1b962be792920a9374d86f5931792b70da6f1e14af43a21d4b9f`.
- The pinned image reported
  `0.0.19+01d67bb4da0d8359b808b4761f8db171ab682cd7`. With network disabled,
  read-only rootfs, dropped capabilities, and no-new-privileges, `help
  quickstart` and `help oauth` completed. The CLI documents `sample_mcp_with_dcr`
  for HTTP MCP with OAuth/DCR and expects protected-resource metadata followed
  by authorization-server metadata. This refresh replaces v0.0.18 as the
  current local client preflight reference in `docs/CHATGPT_SETUP.md`.
- No tunnel ID, runtime/API key, Platform request, Gateway process, workspace
  setting, or OAuth grant was used. Tunnel/ChatGPT acceptance remains **NOT
  RUN**; repository mode stays `parked`.
- Source review adds a reachability constraint: local built-in OAuth uses
  `GATEWAY_PUBLIC_URL` for both the resource URI and authorization-server
  issuer, and the non-Vercel default is `http://127.0.0.1:8000`. The tunnel
  carries MCP traffic and discovery but does not automatically tunnel the
  authorization server. The CLI's DCR sample cannot prove the browser-facing
  OAuth endpoints are reachable or that an externally issued token has the
  right resource audience. No local tunnel can be counted as ChatGPT OAuth
  acceptance until those bindings are demonstrated. Details:
  `docs/CHATGPT_SETUP.md`, “Development-only private tunnel path.”

## Current public deployment and PR check recheck — 2026-10-31 02:22 UTC (read-only)

- Public production probes returned `/healthz` **200**, `/readyz` **404**, and
  unauthenticated `/mcp` **401**. The deployed production alias therefore
  still does not expose the readiness route required by P1 acceptance. This
  is a live HTTP observation; it does not identify the serving SHA or prove
  database/worker readiness.
- The current local `gateway/gpu_gateway/app.py` defines `/readyz` and checks
  database/schema, worker and supervisor heartbeat, enabled workload
  registry, authentication, and enabled local-CPU storage/admission. The
  accompanying `gateway/vercel.json` selects the FastAPI framework. Therefore
  the production 404 is a source/deployment mismatch to resolve by identifying
  and deploying the reviewed candidate; adding a duplicate local route would
  not address the observed production state. The local route still requires
  its deployment and authenticated readiness response to be accepted.
- GitHub currently lists PRs #51–#59 as OPEN/DRAFT. Each has nine successful
  rollup entries: seven Actions checks, the Vercel deployment status, and
  Vercel Preview Comments. PR #52 has `REVIEW_REQUIRED`, and the other PRs
  have no review decision. PR #43 remains OPEN/DRAFT with five successful
  Actions checks and `REVIEW_REQUIRED`. These checks cover remote PR heads,
  not this dirty local worktree, and do not constitute independent review or
  merge.
- No source, GitHub, deployment, workspace, OAuth, or provider state was
  changed during this recheck. ChatGPT OAuth/tool/CPU acceptance remains
  **NOT RUN**. Repository mode remains `parked` and provider spending remains
  disabled.
