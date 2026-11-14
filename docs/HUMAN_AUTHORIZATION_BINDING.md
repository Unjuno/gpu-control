# Human Authorization Binding

`gpu-control` distinguishes **who is authenticated** from **what the human actually authorized**.

An agent may act using the repository owner's GitHub identity while having been influenced by indirect prompt injection or poisoned context. Therefore `github.actor == owner` is necessary for the future paid path but is not sufficient evidence that the owner intended the exact paid action.

## Current state

The repository has a strict runtime `HumanAuthorizationEvidence` validator in `src/gpu_control/human_authorization.py`.

It binds one short-lived human approval to:

- the current DecisionRecord id;
- the exact control-plane commit SHA;
- the exact `ApprovedExecutionPlan` fingerprint;
- workload repository and immutable commit;
- immutable image digest;
- provider and provider resource;
- GPU count;
- maximum runtime and cost;
- the authorized GitHub actor;
- authorization time, expiry, and trusted authorization reference.

The maximum validity window is 15 minutes. A materially changed plan, control-plane commit, DecisionRecord, actor, workload, image, resource, runtime, cost, or authorization reference requires new authorization.

`authorize_live_plan(...)` combines that evidence with `PaidAuthorizationEvidence` and trusted repository-security evidence to produce a `LiveExecutionPermit`.

The RunPod adapter now requires that permit and revalidates its exact plan binding and expiry immediately before submission. A bare `ApprovedExecutionPlan` or an expired permit cannot reach the RunPod occupancy/create path.

**Live paid execution is still disabled.** The paid workflow and provider credentials are not present, the repository remains parked, provider reconciliation is not live-verified, and the selected canary still lacks a verified production-supported authenticated result transport. `runtime_enforced: false` therefore remains accurate for the complete end-to-end live path.

## Sites CPU confirmation paths

The fixed Modal CPU inference has two owner-authenticated approval surfaces.
The deployed Site Version 34 currently uses the browser path: `experiment_prepare`
returns a Site URL showing workload, repository commit, prompt, token limit,
seed, runtime, Sandbox ceiling, and the separate Modal control-function cost
caveat. The owner opens it while signed in and submits a same-origin form. The
Worker stores a challenge hash and an owner-, plan-fingerprint-, and expiry-
bound authorization in D1.

The current PR candidate adds a ChatGPT-native path. `experiment_prepare`
returns the same exact plan fields in its structured result. `experiment_submit`
is marked as a destructive MCP write and its confirmed tool call must repeat
the plan fields; the Worker compares each field with the current owner-bound
D1 plan and image digest before it creates an authorization with source
`chatgpt_mcp_write_confirmation`. The authorization expires no later than the
plan (at most 10 minutes), permits one run, and is consumed in the same D1 batch
that reserves that run. A separate browser login is not part of this intended
ChatGPT flow.

The ChatGPT host's write confirmation is a user-facing approval surface, not a
cryptographic attestation that a human operated the UI. MCP annotations do not
replace the Worker's owner authorization, exact-plan validation, short expiry,
one-use record, provider gates, or cleanup checks. The browser path has the
same limitation. Neither path proves human interaction against a compromised
ChatGPT client or an untrusted identity header. The repository-wide structured
evidence format above still governs the protected RunPod/GPU path. The candidate
is not live acceptance: verify the actual ChatGPT confirmation UI, trusted
identity-header provenance, cross-account denial, D1 migration, provider
result, and cleanup before publishing or spending compute.

## Why exact plan binding matters

Without exact binding, an approval for a small canary could be reused for a larger runtime, a different GPU, a different workload commit, or a different image. It could also be replayed after the control-plane code changed.

Authorization evidence must not behave like a reusable permission token for a class of actions. It authorizes one bounded execution identity.

## Prompt-injection boundary

Authorization may not originate from:

- target repository text;
- repository-level agent instructions in a workload repository;
- README or documentation;
- code comments or Dockerfile comments;
- commit messages;
- PRs, issues, reviews, or comments;
- provider output or logs;
- few-shot examples or prior decisions;
- model-generated summaries.

Those sources may describe or request an action, but they do not prove current human intent.

## Relationship to GitHub authorization

`PaidAuthorizationEvidence` establishes that the GitHub workflow identity is allowed to approach the paid boundary. `HumanAuthorizationEvidence` establishes that the human approved the exact execution identity.

Both are required. Neither substitutes for:

- protected control-plane `main`;
- required status checks;
- protected GitHub Environment approval;
- environment-scoped provider secret;
- current pricing and provider evidence;
- cleanup and completion guarantees.

## Remaining live migration rule

Before enabling live paid compute:

1. preserve the current RunPod `LiveExecutionPermit` requirement and submission-time expiry check;
2. wire the protected paid workflow so the running control-plane SHA and current DecisionRecord are the values actually validated;
3. keep negative tests for stale, copied, mismatched, expired, and prompt-injected authorization evidence;
4. verify live provider occupancy, reconciliation, image identity, completion transport, and cleanup behavior;
5. keep all provider/live flags disabled until those remaining GitHub/provider prerequisites are verified.
