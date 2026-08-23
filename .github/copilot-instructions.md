# Repository instructions

Before making changes or proposing execution steps, read and follow the root `AGENTS.md`, `SECURITY.md`, `policies/repository-state.yaml`, and `policies/decision-policy.yaml`.

If `policies/repository-state.yaml` says `mode: parked`, preserve parked mode unless the human explicitly asks to activate the repository for a concrete workload. In parked mode, do not create a paid workflow, reference provider secrets, enable RunPod live calls, enable generic external Dockerfile execution, or treat code-completeness as authorization to move toward paid execution.

Use **goal-preserving restraint**. Defensive controls should constrain unjustified actions without needlessly abandoning the user's objective. If a proposed action is too broad, too costly, insufficiently evidenced, or unauthorized, prefer reducing scope, choosing a cheaper or safer alternative, or requesting human judgment before denying the specific action. If that action is denied, keep the objective active whenever a useful safe path remains.

Do not treat remaining budget, provider availability, a previous stage's success, or a previous stage's failure as justification for escalation. Before a higher-impact experiment, define the current question, expected decision impact, success condition, stop condition, and useful information that remains if the experiment fails.

The operating model is local-first and escalation-based:

1. inspect the workload and repository context;
2. define the current question and smallest justified next action;
3. run or validate the workload locally in a container when practical;
4. minimize the experiment;
5. use an authorized workload repository pinned to an immutable commit SHA;
6. run `gpu-control` policy and exact-source verification gates;
7. keep arbitrary workload container execution isolated from credential-bearing control-plane jobs;
8. require a successful dry-run, current decision rationale, verified provider price, cleanup guarantee, and explicit human authorization;
9. produce an immutable `ApprovedExecutionPlan`;
10. allow a paid provider adapter to consume only that approved plan;
11. use RunPod only as the final escalation stage.

Paid compute is denied by default. Editing code, preparing a Dockerfile, validating a request, or being given repository access does not authorize provider spending.

Do not introduce arbitrary remote shell inputs, floating workload refs, secret logging, untrusted paid-compute triggers, silent cost/runtime escalation, open-ended experiments without stop conditions, long-lived GitHub Actions polling, or provider adapters that accept raw workload requests.

Prefer small, bounded, reproducible experiments and preserve useful progress when a higher-impact action is blocked. Keep provider-specific operations behind both the policy layer and the approved execution-plan gate.
