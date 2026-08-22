# Repository instructions

Before making changes or proposing execution steps, read and follow the root `AGENTS.md` and `SECURITY.md`.

The operating model is local-first and escalation-based:

1. inspect the workload and repository context;
2. run or validate the workload locally in a container when practical;
3. minimize the experiment;
4. use an authorized workload repository pinned to an immutable commit SHA;
5. run `gpu-control` validation and dry-run gates;
6. use paid RunPod GPU compute only as the final escalation stage and only with explicit human authorization.

Paid compute is denied by default. Editing code, preparing a Dockerfile, validating a request, or being given repository access does not authorize provider spending.

Do not introduce arbitrary remote shell inputs, floating workload refs, secret logging, untrusted paid-compute triggers, silent cost/runtime escalation, or long-lived GitHub Actions polling.

Prefer small, bounded, reproducible experiments. Keep provider-specific operations behind the control-plane policy layer.