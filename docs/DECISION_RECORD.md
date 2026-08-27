# DecisionRecord

`DecisionRecord` is the structured reasoning context used before a consequential action is escalated. It exists to make decisions inspectable and comparable without turning free-form rationale into authority.

The current repository is parked. This record is **not yet bound to `ApprovedExecutionPlan` or any live provider path**. The schema and examples are offline governance assets only.

## Purpose

A DecisionRecord should answer four questions:

1. What objective and current question are active?
2. Why is this action the smallest useful next step rather than a cheaper or safer alternative?
3. What value, cost, downside, authority, and stopping conditions govern it?
4. If the proposed action is rejected, what safe next step preserves useful progress?

The machine-readable shape is defined in `policies/decision-record-schema.yaml`.

## Few-shot examples are non-authoritative

Files under `examples/decision-records/` are deliberately useful as few-shot context, but they are not execution evidence.

An agent may learn from their **structure and comparison logic**. It must not copy their facts into a live decision.

In particular, an example never proves:

- current human authorization;
- current repository mode;
- current provider price or availability;
- current workload identity;
- current security posture;
- current risk or cleanup guarantees.

All examples set `illustrative_only: true`. Their authority references are intentionally absent. A live decision must re-establish current facts from trusted sources.

Treating an example as current evidence is `F013 example_laundering` in `policies/failure-catalog.yaml`.

## Required record content

Every record contains:

- `mission_state`, `active_goal`, and `current_question`;
- the `proposed_action` and evidence supporting the decision;
- alternatives considered and the cheapest viable alternative;
- expected impact on the next decision;
- expected and maximum justified cost as decimal strings;
- opportunity cost, reversibility, blast radius, worst-case downside, and recovery path;
- the authority required and whether current authority has actually been verified;
- success, stop, and failure-learning conditions;
- one action outcome: `continue`, `reduce_scope`, `safer_alternative`, `human_checkpoint`, or `deny_action`;
- a concrete `next_safe_step`.

The schema is intentionally provider-neutral.

## Action outcomes

`continue` means the action is justified at its current scope.

`reduce_scope` means the objective remains valid, but the proposed action is larger than necessary.

`safer_alternative` means a cheaper, more local, more reversible, or otherwise lower-impact action can answer the current question.

`human_checkpoint` means useful progress depends on human judgment or authority that the agent cannot supply.

`deny_action` rejects the specific action. It does not imply mission failure. If the goal is still active, the record should identify the safest useful next step. If the question is already answered, denial can prevent unnecessary escalation.

## Runtime integration rule

Do not add DecisionRecord fields to the live `ApprovedExecutionPlan` merely because the schema exists. Live binding is a separate security-sensitive design change and requires a concrete workload, reviewed persistence semantics, identity binding, stale-record handling, and tests at the submission boundary.

Until then, the record is a decision-quality and few-shot artifact, not a paid-compute credential.
