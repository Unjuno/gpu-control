# Sites + D1 is the canonical ChatGPT runtime

Date: 2026-11-12
Status: Accepted

## Decision

Use the private ChatGPT Site as the only ChatGPT-facing experiment runtime. Its Worker owns MCP requests and uses D1 for plans, idempotency, run state, leases, and Runner heartbeats. R2 stores bounded result artifacts. The macOS Runner performs registered local CPU work.

Do not provision or configure Vercel, Neon, or hosted PostgreSQL for this path. PostgreSQL support and Linux deployment templates remain with the legacy Python Gateway for local recovery evidence; they are outside the Sites runtime and can be ported or retired separately.

## Evidence

- Sites version 14 is deployed to the existing owner-only Site.
- The Worker manifest binds D1 as `DB` and R2 as `BUCKET`; the Sites source has no Vercel, Neon, or PostgreSQL runtime dependency.
- A registered TinyStories CPU inference was submitted through ChatGPT, completed, returned its result, and confirmed cleanup with `gpu_used=false`.
- The Vercel project is inactive. The former Neon project is not referenced by Sites source; deleting it remains a separate destructive cleanup because it contains Auth and OAuth records.

## D1 fit and limits

D1 is appropriate for the current single-Site workload. It keeps state access in the Worker and avoids an extra database service and credential path. D1 processes queries serially per database and has a storage ceiling of 500 MB on Free or 10 GB on Workers Paid. Reassess if measured write contention, database size, or query requirements exceed those limits. Store large result files in R2, not D1 rows. See [Cloudflare D1 limits](https://developers.cloudflare.com/d1/platform/limits/) and [D1 overview](https://developers.cloudflare.com/d1/).

## Cleanup rules

- Remove retired Vercel entrypoints and deployment configuration from the active tree; preserve history under `docs/archive/legacy-vercel-gateway/`.
- Do not let generic `DATABASE_URL`, `VERCEL`, or Vercel deployment variables auto-configure the legacy Gateway.
- Preserve local PostgreSQL recovery evidence while useful; it does not imply Neon is required.
- Delete the Neon project only after current human confirmation names the exact project, because it contains authentication and OAuth state.
- Keep provider GPU paths parked; this hosting decision does not authorize provider calls or spend.
