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
