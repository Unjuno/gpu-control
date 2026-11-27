# Architecture index

This directory describes the source architecture, the ChatGPT product boundary,
and the staged work needed to make ordinary agent conversations a reliable
front end for external compute.

## Current source snapshot

- [Repository map](repository-map.md): module ownership, runtime/data flow,
  state authority, duplicated concepts, and measured complexity hotspots.
- [ADR 0001](decisions/0001-agent-centered-experiment-lifecycle.md): the
  proposed product and control-plane boundary for agent-operated experiments.
- [ADR 0002](decisions/0002-run-state-authority.md): which system owns each
  durable experiment fact across Sites, adapters and providers.
- [ADR 0003](decisions/0003-owner-training-profile-readiness.md): the
  Sites/adapter readiness parity check before preparing and reserving a run.
- [ADR 0004](decisions/0004-provider-budget-policy-authority.md): historical
  capability budget authority decision, superseded by ADR 0005.
- [ADR 0005](decisions/0005-shared-modal-compute-budget.md): one Sites-side
  Modal CPU/GPU compute reservation ceiling across routes.
- [ADR 0006](decisions/0006-chat-first-external-compute.md): normal chat is
  the primary interface and external GPU routes must share one owner-bound
  lifecycle.
- [Refactoring backlog](refactoring-backlog.md): ordered, evidence-linked
  architecture work with dependencies and acceptance conditions.
- [Refactoring progress](refactoring-progress.md): completed batches and
  remaining product/release acceptance, kept separate from the task pool.
- [Chat operations](chat-operations.md): registered workload lifecycle and
  provider contract.
- [Selected-repository experiments](chatgpt-selected-repository-experiments.md):
  owner-selected GitHub source and constrained custom training lane.
- [Sites provider control plane](sites-four-provider-control-plane.md):
  fixed-workload provider topology and Colab's future integration boundary.

The current source candidate is PR #70, branch `codex/owner-training-workloads`.
That is not the deployed Site revision. `policies/repository-state.yaml` is
authoritative for activation and remains `parked`; a source implementation,
green CI, or a historical live canary does not change that policy.

## Evidence convention

Every architecture statement about runtime availability must identify whether
it describes checked-in source, merged main, deployed Site, provider account,
or a completed end-to-end run. Historical acceptance records remain immutable
evidence for their exact date, revision, configuration, and workload only.
