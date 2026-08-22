# Repository instructions

Before making changes or proposing execution steps, read and follow the root `AGENTS.md` and `SECURITY.md`.

The operating model is local-first and escalation-based:

1. inspect the workload and repository context;
2. run or validate the workload locally in a container when practical;
3. minimize the experiment;
4. use an authorized workload repository pinned to an immutable commit SHA;
5. run `gpu-control` policy and exact-source verification gates;
6. keep arbitrary workload container execution isolated from credential-bearing control-plane jobs;
7. require a successful dry-run, verified provider price, cleanup guarantee, and explicit human authorization;
8. produce an immutable `ApprovedExecutionPlan`;
9. allow a paid provider adapter to consume only that approved plan;
10. use RunPod only as the final escalation stage.

Paid compute is denied by default. Editing code, preparing a Dockerfile, validating a request, or being given repository access does not authorize provider spending.

Do not introduce arbitrary remote shell inputs, floating workload refs, secret logging, untrusted paid-compute triggers, silent cost/runtime escalation, long-lived GitHub Actions polling, or provider adapters that accept raw workload requests.

Prefer small, bounded, reproducible experiments. Keep provider-specific operations behind both the policy layer and the approved execution-plan gate.
