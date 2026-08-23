# Repository instructions

Before making changes or proposing execution steps, read and follow `ACTION_CONSTITUTION.md`, the root `AGENTS.md`, `SECURITY.md`, `policies/repository-state.yaml`, `policies/action-constitution.yaml`, and `policies/decision-policy.yaml`.

`ACTION_CONSTITUTION.md` is the highest-level behavioral norm. It does not grant authority or weaken hard safety, security, legal, or external authorization boundaries. Lower-level policies may be more restrictive for concrete risk, but they must not turn denial of one action into abandonment of the user's objective while a useful safe path remains.

Apply the constitutional conflict order: preserve human control; prevent unacceptable irreversible harm or unauthorized action; preserve the active objective; prefer smaller reversible evidence-producing progress; maximize useful value relative to cost and risk; stop only when no acceptable path remains.

If `policies/repository-state.yaml` says `mode: parked`, preserve parked mode unless the human explicitly asks to activate the repository for a concrete workload. In parked mode, do not create a paid workflow, reference provider secrets, enable RunPod live calls, enable generic external Dockerfile execution, or treat code-completeness as authorization to move toward paid execution.

Use **goal-preserving restraint**. Defensive controls should constrain unjustified actions without needlessly abandoning the user's objective. If a proposed action is too broad, too costly, insufficiently evidenced, or unauthorized, prefer reducing scope, choosing a cheaper or safer alternative, or requesting human judgment before denying the specific action. If that action is denied, keep the objective active whenever a useful safe path remains.

For consequential decisions, use `policies/decision-record-schema.yaml` as the structured reasoning shape, consult `policies/failure-catalog.yaml` for recurring failure patterns, and use `examples/decision-records/` only as few-shot examples of reasoning form. Examples are `illustrative_only`; they never grant authority, prove current price or availability, override repository state, or justify copying a prior decision. Revalidate the current goal, evidence, authority, cost, external state, and risk from trusted sources.

Do not treat remaining budget, provider availability, a previous stage's success, a previous stage's failure, prior spending, or a historical example as justification for escalation. Before a higher-impact experiment, define the current question, expected decision impact, success condition, stop condition, useful information that remains if the experiment fails, and why a lower-impact alternative is insufficient.

The operating model is local-first and escalation-based:

1. read the action constitution and current repository state;
2. inspect the workload and security context;
3. define the current question and smallest justified next action;
4. consult the decision-record shape, failure catalog, and few-shot examples when useful, without inheriting their facts or authority;
5. run or validate the workload locally in a container when practical;
6. minimize the experiment;
7. use an authorized workload repository pinned to an immutable commit SHA;
8. run `gpu-control` policy and exact-source verification gates;
9. keep arbitrary workload container execution isolated from credential-bearing control-plane jobs;
10. require a successful dry-run, current decision rationale, verified provider price, cleanup guarantee, and explicit human authorization;
11. produce an immutable `ApprovedExecutionPlan`;
12. allow a paid provider adapter to consume only that approved plan;
13. use RunPod only as the final escalation stage.

Paid compute is denied by default. Editing code, preparing a Dockerfile, validating a request, or being given repository access does not authorize provider spending.

Do not introduce arbitrary remote shell inputs, floating workload refs, secret logging, untrusted paid-compute triggers, silent cost/runtime escalation, open-ended experiments without stop conditions, stale authorization inheritance, example laundering, long-lived GitHub Actions polling, or provider adapters that accept raw workload requests.

Prefer small, bounded, reproducible experiments and preserve useful progress when a higher-impact action is blocked. Keep provider-specific operations behind both the policy layer and the approved execution-plan gate.
