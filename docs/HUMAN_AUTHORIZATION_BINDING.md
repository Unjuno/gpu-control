# Human Authorization Binding

`gpu-control` must distinguish **who is authenticated** from **what the human actually authorized**.

An agent may act using the repository owner's GitHub identity while having been influenced by indirect prompt injection or poisoned context. Therefore `github.actor == owner` is necessary for the future paid path but is not sufficient evidence that the owner intended the exact paid action.

## Current state

The current `ApprovedExecutionPlan` contains `explicit_human_authorization: bool` and an `authorization_reference`. Those fields are adequate for offline contract development but are not the final live authorization design.

Live paid execution remains disabled until structured human authorization evidence is bound into the execution plan and paid-authorization path.

## Required binding

`policies/human-authorization-evidence-schema.yaml` defines the intended evidence shape. Authorization must be tied to one exact consequential action, including:

- current decision-record identity;
- exact control-plane commit SHA;
- exact execution-plan fingerprint;
- workload repository and immutable commit;
- immutable image digest;
- provider and provider resource;
- GPU count;
- maximum runtime;
- maximum justified cost ceiling;
- authorization actor;
- authorization time and expiration;
- trusted authorization reference.

A materially changed plan requires new authorization.

## Why exact plan binding matters

Without exact binding, an approval for a small canary could be reused for a larger runtime, a different GPU, a different workload commit, or a different image. It could also be replayed after the control-plane code changed.

Authorization evidence therefore must not behave like a reusable permission token for a class of actions. It authorizes one bounded execution identity.

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

`PaidAuthorizationEvidence` establishes that the GitHub workflow identity is allowed to approach the paid boundary. Future `HumanAuthorizationEvidence` establishes that the human approved the exact execution identity.

Both are required. Neither substitutes for:

- protected control-plane `main`;
- required status checks;
- protected GitHub Environment approval;
- environment-scoped provider secret;
- current pricing and provider evidence;
- cleanup and completion guarantees.

## Live migration rule

Before enabling live paid compute:

1. implement a strict runtime `HumanAuthorizationEvidence` type;
2. validate it independently of model-generated text;
3. bind it to the exact `ApprovedExecutionPlan` fingerprint and control-plane SHA;
4. make the paid provider path require that structured evidence instead of relying on a bare authorization boolean;
5. add negative tests for stale, copied, mismatched, expired, and prompt-injected authorization evidence.

Until that migration is complete, live paid compute must remain disabled.
