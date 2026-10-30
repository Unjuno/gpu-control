# ChatGPT MCP and CPU acceptance record

Status: **NOT RUN**. This file is an evidence template, not acceptance evidence.
Repository tests, generated credentials, and local MCP clients do not satisfy
the real ChatGPT account and conversation checks below.

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
