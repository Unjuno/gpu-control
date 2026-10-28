# ChatGPT MCP and CPU acceptance record

Status: **NOT RUN**. This file is an evidence template, not acceptance evidence.
Repository tests, generated credentials, and local MCP clients do not satisfy
the real ChatGPT account and conversation checks below.

## Run metadata

- Date/time (UTC): NOT RUN
- Operator:
- ChatGPT plan/workspace type (do not record account email): NOT VERIFIED
- MCP endpoint origin:
- Gateway commit SHA:
- Worker/supervisor commit SHA:
- Database schema version:
- Workload ID and immutable image digest:
- Local admission policy version and expiry (do not paste policy secrets):
- Release matrix revision:

## Gate results

Use `PASS`, `FAIL`, `BLOCKED`, `UNCERTAIN`, or `NOT RUN`. A `PASS` must link to
redacted evidence collected during this acceptance run.

| Gate | Status | Evidence reference | Notes / blocker |
| --- | --- | --- | --- |
| Account plan supports custom MCP with write actions on ChatGPT web (Business/Enterprise/Edu) | NOT RUN | | |
| Tester has workspace permission to create and test a custom MCP app (Business admin/owner; Enterprise/Edu admin/owner or RBAC-authorized member) | NOT RUN | | |
| Run/cancel write actions are enabled for the test app; if publishing workspace-wide, publisher is an admin/owner | NOT RUN | | |
| Reviewed Gateway revision is deployed at stable HTTPS origin | NOT RUN | | |
| `/healthz` and `/readyz` match the deployed revision and are healthy | NOT RUN | | |
| PostgreSQL migration, worker, recovery supervisor, and persistent artifact storage are healthy | NOT RUN | | |
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
