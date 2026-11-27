# Architecture index

This directory describes the source architecture, the ChatGPT product boundary,
and the staged work needed to make ordinary agent conversations a reliable
front end for external compute.

## Current source snapshot

- [Repository map](repository-map.md): module ownership, runtime/data flow,
  state authority, duplicated concepts, and measured complexity hotspots.
- [ADR 0001](decisions/0001-agent-centered-experiment-lifecycle.md): the
  proposed product and control-plane boundary for agent-operated experiments.
- [Refactoring backlog](refactoring-backlog.md): ordered, evidence-linked
  architecture work with dependencies and acceptance conditions.
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
