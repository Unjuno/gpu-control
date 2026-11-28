# ADR 0006: Conversation-first experiments on external compute

- **Status:** accepted product direction; provider rollout is incomplete.
- **Date:** 2026-11-28
- **Scope:** experiments initiated in ordinary ChatGPT/Work or another
  authenticated compatible MCP client.

## Context

The product exists so its owner can ask an agent to try an experiment during
normal conversation and get real external compute when the workload needs it.
The user should not need to operate a CLI, supply internal registration/run
IDs, or translate provider-specific API details. A local container can support
development and validation, but it does not meet the product outcome by
itself.

## Decision

1. **Conversation is the primary control surface.** The agent discovers the
   repositories and routes already authorized for this owner, resolves
   immutable source identity and supported experiment settings, and carries
   internal identifiers through the lifecycle. It asks only for a missing
   product choice, such as which repository when several are plausible.
2. **External GPU execution is an explicit capability.** A provider is
   selectable for owner code only when its adapter advertises the exact task,
   resource, runtime, cost/quota, cancellation, result and cleanup guarantees
   currently supported. A configured API key or fixed-workload canary does
   not establish arbitrary-repository support.
3. **Selection is automatic within owner constraints.** The agent uses current
   route evidence and the owner's provider-specific authorization and budget.
   It must not silently move a free-only request to paid compute, change
   providers after a failed submission, or claim GPU execution from CPU
   evidence. If no route qualifies, report the concrete blocker and preserve
   the same experiment plan for recovery.
4. **All providers implement one product lifecycle.** Registration/source
   pinning, preview, immutable plan, authorization and reservation, idempotent
   submit/reconcile, status/cancel, bounded artifacts and verified cleanup
   remain behind the common Sites contract. Provider differences belong in
   adapters and capability data, not in agent instructions or separate user
   workflows.
5. **Provider rollout is evidence-based and staged.** Modal is the first
   owner-selected GPU implementation in PR #70. RunPod owner-selected source
   execution is the next required route. Kaggle and Hugging Face can be
   selected only for workload types their adapters actually support. Colab is
   a later adapter unless it can meet the same identity, budget, cancellation,
   artifact and cleanup contract. Each route is advertised only after live
   acceptance for its claimed capability.
6. **Authorization is durable but bounded.** Repository selection grants
   source-read scope; separate owner/provider authorization and budget bound
   compute. Internal prepare/submit protocol steps must not make the agent ask
   the user to repeat an already explicit request. Product code cannot bypass
   a connected client's native write-confirmation policy.

## Consequences

- “GPU available” and “this repository can run on that GPU” are separate
  capability statements.
- A single conversational journey can choose among providers without exposing
  provider payloads or requiring provider-specific plans from the user.
- The current PR #70 source is only a Modal owner-selected lane; it is not a
  released multi-provider route. Existing RunPod, Kaggle and Hugging Face fixed
  workloads do not imply arbitrary-source execution.
- Acceptance evidence must identify the exact source commit, selected provider,
  observed GPU, result provenance and cleanup. Unit tests, preview, CPU runs and
  old provider canaries do not prove this outcome.
- See [A1](../refactoring-backlog.md#a1-make-the-owner-selected-experiment-a-complete-conversational-journey)
  for implementation order and [ADR 0001](0001-agent-centered-experiment-lifecycle.md)
  for the complete lifecycle and trust constraints.

## Revisit when

- A provider cannot meet the shared execution, recovery or cleanup contract;
- the owner wants an explicitly separate direct-provider MCP path; or
- a supported client's native write-confirmation behavior changes the
  supported user experience.
