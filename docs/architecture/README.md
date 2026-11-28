# Architecture index

This directory describes the source architecture, the shared authenticated
MCP product boundary, and the staged work needed to make ordinary agent
conversations a reliable front end for external compute.

## Current architecture and release references

- [Project status](../STATUS.md) is the current-state entry point. GitHub PR
  and deployment records remain authoritative for live review, CI, and hosted
  state; architecture documents link to them instead of copying volatile
  checkpoints.

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
- [ADR 0006](decisions/0006-chat-first-external-compute.md): natural-language
  agent use is the interface and external GPU routes must share one owner-bound
  lifecycle across compatible MCP clients.
- [ADR 0007](decisions/0007-github-installation-owner-proof.md): GitHub
  installation callbacks require one-time user authorization before an
  owner-bound source connection is trusted.
- [ADR 0008](decisions/0008-runpod-owner-selected-execution.md): the RunPod
  fixed canary is not an owner-selected execution route; retry, isolation,
  billing, and durable results must be proven before adding one.
- [ADR 0010](decisions/0010-colab-cli-owner-runner.md): superseded proposal
  for a local Colab CLI runner; retained as history and must not be revived.
- [ADR 0011](decisions/0011-hosted-colab-mcp-provider.md): integrate Google's
  hosted Colab API MCP through an owner-scoped Sites provider adapter.
- [ADR 0012](decisions/0012-mcp-oauth-multi-client.md): authenticate
  compatible external MCP clients to the same owner-scoped experiment ledger.
- [ADR 0013](decisions/0013-map-modal-account-evidence.md): bind current
  Modal account usage evidence to MAP training plans without treating the
  Sites reservation as a provider billing cap.
- [ADR 0014](decisions/0014-github-user-repository-scope.md): revalidate the
  owner's current GitHub identity and repository IDs before source discovery
  or read-token issuance.
- [Colab provider specification](google-colab-provider.md): OAuth, runtime,
  idempotency, quota, artifact and cleanup contracts for the integration.
- [Google Colab CLI guide](../GOOGLE_COLAB_CLI.md): what the official CLI can
  do in local/CI workflows, how it differs from GPU Control, and why chat use
  must go through the shared Sites lifecycle.
- [MCP client connection](../../sites/gpu-control-sites/MCP_CLIENTS.md):
  source-level OAuth client requirements, owner link, scopes and release gate.
- [Refactoring backlog](refactoring-backlog.md): ordered, evidence-linked
  architecture work with dependencies and acceptance conditions.
- [Refactoring progress](refactoring-progress.md): completed batches and
  remaining product/release acceptance, kept separate from the task pool.
- [Chat operations](chat-operations.md): registered workload lifecycle and
  provider contract.
- [Selected-repository experiments](chatgpt-selected-repository-experiments.md):
  owner-selected GitHub source and constrained custom training lane.
- [Sites provider control plane](sites-four-provider-control-plane.md):
  fixed-workload provider topology and Colab's shared-lifecycle integration.

The current source candidate is PR #70, branch `codex/owner-training-workloads`.
That is not the deployed Site revision. `policies/repository-state.yaml` is
authoritative for activation and remains `parked`; a source implementation,
green CI, or a historical live canary does not change that policy.

## Evidence convention

Every architecture statement about runtime availability must identify whether
it describes checked-in source, merged main, deployed Site, provider account,
or a completed end-to-end run. Historical acceptance records remain immutable
evidence for their exact date, revision, configuration, and workload only.
