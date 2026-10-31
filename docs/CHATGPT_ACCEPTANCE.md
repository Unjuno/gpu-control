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
| Account/workspace permits custom MCP with required write actions | NOT RUN | | |
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
