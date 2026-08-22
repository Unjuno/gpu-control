# Paid execution ownership

Paid GPU execution is intentionally **owner-exclusive** and remains disabled.

The public repository may accept pull requests and run ordinary CI, but those events must never consume the repository owner's RunPod balance or occupy the paid GPU queue.

## Identity boundary

A future paid workflow must be a dedicated `.github/workflows/paid-runpod.yml` workflow on `refs/heads/main` and must accept only `workflow_dispatch` initiated by the repository owner.

The trusted preflight must verify all of the following before a job is admitted to paid concurrency:

- `github.repository == Unjuno/gpu-control`;
- `github.repository_owner == Unjuno`;
- `github.actor == Unjuno`;
- `github.triggering_actor == Unjuno`;
- `github.actor == github.triggering_actor`;
- `github.event_name == workflow_dispatch`;
- `github.ref == refs/heads/main`;
- `github.workflow_ref == Unjuno/gpu-control/.github/workflows/paid-runpod.yml@refs/heads/main`.

Checking `triggering_actor` separately is required because GitHub workflow re-runs keep the privileges of the original actor even when a different write-capable user initiates the re-run.

## Environment secret boundary

`RUNPOD_API_KEY` must exist only as an environment secret on a protected `paid-runpod` GitHub Environment. It must not be a repository-level or organization-level secret.

Before live enablement, that Environment must be configured with:

- required reviewer: `Unjuno` only;
- deployment branches restricted to the protected `main` branch;
- self-review allowed, because the same single owner initiates and approves the paid run;
- no provider credentials exposed to preflight, CI, PR, fork, issue, comment, or dry-run jobs.

Environment protection is a separate hard gate. The Python authorization check does not replace it.

## Queue ownership

A paid job must use one global concurrency group: `gpu-control-paid-runpod`, with `cancel-in-progress: false` and at most one in-flight paid job.

The owner authorization preflight must occur **before** the job is admitted to this concurrency group. Otherwise an unauthorized run could occupy the queue even though it would later fail before receiving provider credentials.

## Provider account occupancy

GitHub single-flight is not sufficient by itself because a RunPod Pod could exist outside the workflow. Immediately before `POST /pods`, the provider adapter requires short-lived account occupancy evidence showing zero non-terminated Pods.

Immediately after create, the account is checked again. The only non-terminated Pod allowed is the newly created Pod. If another Pod appears during the create race window, gpu-control terminates the new Pod and fails closed.

For occupancy purposes, only `TERMINATED` means released. `EXITED`, `ERROR`, `RUNNING`, provisioning states, and unknown/future states remain busy until explicitly terminated.

This intentionally prioritizes owner availability and spend control over automatic parallelism.

## Live enablement checklist

Live compute must remain disabled until all of these exist together:

1. owner-only GitHub Environment configuration;
2. owner identity preflight wired before paid concurrency;
3. global single-flight paid concurrency;
4. environment-scoped `RUNPOD_API_KEY`;
5. read-only account occupancy query wired to the short-lived occupancy evidence;
6. post-create account exclusivity re-check;
7. immutable published image evidence;
8. fresh pricing and availability evidence;
9. authenticated workload completion evidence and reliable cleanup.

Until then, `live_paid_compute_enabled`, `live_calls_enabled`, `live_adapter_enabled`, and provider workflow wiring remain false.
