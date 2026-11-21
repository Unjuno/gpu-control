# ChatGPT-native exact-plan confirmation candidate

Date: 2026-11-15

Status: implemented in the current PR #68 worktree; not deployed to Sites.

## Goal

Let the authenticated owner review and approve one exact, bounded Modal CPU
inference from the ChatGPT conversation without signing into the Site again in
a separate browser. The Site remains public for viewing. MCP reads and writes
remain restricted to the configured owner account.

## Candidate behavior

- `experiment_prepare` returns the exact workload, repository commit, prompt,
  token limit, seed, runtime, Sandbox cost estimate and ceiling, CPU/memory
  limits, GPU-disabled state, and separate control-function cost caveat.
- `experiment_submit` is marked as a destructive MCP write. Its arguments
  repeat the values that need review. The Worker requires an authenticated
  allowlisted Site owner and exact equality with that owner's prepared D1 plan,
  current image digest, and plan expiry before recording authorization.
- A D1 migration records `chatgpt_mcp_write_confirmation` as the authorization
  source. The short-lived authorization is owner- and fingerprint-bound,
  permits one run, and is consumed with the run reservation. The browser
  confirmation remains available as a fallback.
- ChatGPT's documented write confirmation is a host-side approval surface, not
  a cryptographic proof of manual interaction. Server-side identity, exact-plan
  validation, expiry, one-use, spend and cleanup controls remain mandatory.

## Local verification

- `node --test sites/gpu-control-sites/worker/index.test.js`: 42 passed.
- `npm run build && npm run validate` from `sites/gpu-control-sites`: passed.
- `PYTHONPATH=src python3 -m pytest tests/test_sites_d1_migrations.py -q` from
  the repository root: 1 passed.
- `git diff --check`: passed.

## Not verified

- Live Sites Version 34 still uses the separate browser confirmation page.
- The actual ChatGPT UI rendering and confirmation behavior for this Site tool
  has not been exercised against this candidate.
- The provenance and spoof resistance of the platform-injected
  `oai-authenticated-user-id` remain unverified, as does denial from a genuinely
  separate authenticated account.
- The new migration has not been applied to the live Site. No provider health
  call, Sandbox, or other paid operation was started for this candidate.
- No post-correction Modal inference result or cleanup is established by these
  local checks.

## Required next acceptance

Review the exact diff and run exact-head CI. On a non-production preview or
controlled Site release, verify that ChatGPT shows the full approved plan
before the user confirms the destructive tool call, that a non-owner and a
forged owner header cannot invoke it, and that unconfirmed or mismatched plans
make zero Modal calls. Apply and verify the D1 migration, then use one fresh
owner-approved plan within the existing aggregate `$1` testing allowance. Read
the result and artifact through the same ChatGPT account, verify the digest and
cleanup, and confirm CPU was used with no GPU. Keep admission closed if any
identity or spend gate cannot be verified.

## Platform references

- [ChatGPT requires manual confirmation for write actions](https://developers.openai.com/api/docs/mcp)
- [Tool annotations do not replace server-side authorization or confirmation](https://developers.openai.com/plugins/build/mcp-server)
