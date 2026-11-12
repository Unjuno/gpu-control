# Sites owner-scope unit checks — 2026-11-12

Status: **PASS for local Worker query and response contracts only.** This is
not separate-account or deployed authentication acceptance.

The Sites Worker unit suite now exercises a different authenticated owner
against the run read/write surface:

- status and result return `RUN_NOT_FOUND` and do not disclose the stored result;
- list returns no other owner's run metadata;
- artifact lookup is denied before the R2 bucket is read;
- reusing an idempotency key under a different owner creates an independent
  plan identity; and
- submitting another owner's prepared plan is rejected, with owner predicates
  present on both the plan update and run insert.

The pre-existing tests also verify that another owner cannot cancel a run.
`node --test worker/index.test.js` passed **28/28** tests, and
`git diff --check` passed.

## Live unauthenticated forged-header probe

On 2026-11-12, a direct unauthenticated POST to the published `/mcp` endpoint
called only the read-only `experiment_list` tool while supplying a synthetic
`oai-authenticated-user-id` header. The Site edge returned HTTP **401**; no run
was submitted and no database rows were read. A Sites database overview
confirmed only the `DB` binding and the `plans`, `runs`, and `runner_heartbeats`
tables; row contents were not inspected.

This is supplemental evidence that an unauthenticated request with a forged
identity header is rejected. It does not prove isolation between two
authenticated ChatGPT accounts, verify revocation, or close the owner-isolation
gate.

These tests use an in-process D1-shaped test double. They do not prove Cloudflare
Sites' authenticated-user header cannot be forged, test access from a genuinely
separate ChatGPT account, or verify access revocation. Those deployed checks
remain open; see [`RELEASE_MATRIX.md`](../RELEASE_MATRIX.md).
