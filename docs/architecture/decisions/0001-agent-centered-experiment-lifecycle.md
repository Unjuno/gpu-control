# ADR 0001: Agent-centered experiment lifecycle

- **Status:** proposed baseline; current code is a staged implementation, not
  proof of release.
- **Date:** 2026-11-28
- **Scope:** ChatGPT/Work initiated research and training using owner-authorized
  source repositories and external compute.

## Context

The product is meant to let an owner say in ordinary conversation what they
want to test. The agent should inspect the available project and current
provider capabilities, select a compatible route, run a bounded experiment,
and return interpretable results and artifacts. Internal registration IDs,
commit SHAs, idempotency keys, provider payloads and repeated browser
ceremonies should not be user chores.

The system must still prevent unselected source access, prompt injection,
unbounded commands/resources, duplicate jobs after a lost response, cross-owner
reads, silent paid fallback, and false success without result/cleanup evidence.

## Decision

1. **ChatGPT Sites remains the owner-facing control plane** for the current
   product. It authenticates the Sites owner and stores the durable user-facing
   plan, reservation, run, result references and cleanup evidence in D1. R2 or
   an explicitly configured private artifact store holds large bytes.
2. **Repository access and run authority are separate.** The owner selects a
   repository in a least-privilege GitHub App connection. The service pins an
   immutable commit and inspects a versioned experiment contract. A repository
   connection permits reading that source; it never permits spending.
3. **The initial custom-code interface is declarative and narrow.** The source
   declares a supported task, Python entrypoint, exact locked dependencies,
   resource profile and outputs. The agent recommends task parameters; it does
   not invent a shell command, Dockerfile, image, network policy or secret.
4. **A provider adapter owns provider details.** It accepts a validated,
   owner-bound immutable plan and implements submit/reconcile/status/cancel,
   bounded output and cleanup evidence. It does not decide user intent or
   authority. Adapter hosting (Modal) is distinct from the selected compute
   provider (Modal, RunPod, Kaggle, Hugging Face, or a future Colab path).
5. **One agent-visible lifecycle is the product contract:** discover/select
   source -> inspect/preview -> prepare -> one exact native destructive write
   confirmation -> submit -> recover/poll -> retrieve/verify -> cleanup.
   Explicit user intent is carried through the lifecycle; the agent does not
   ask the same conversational question after prepare. Native client write
   confirmation and required security/release reviews remain separate gates.
6. **Provider selection is evidence-based.** The agent chooses only a currently
   compatible and admitted route under the user's provider-specific cost/quota
   ceiling. Free-only intent never falls back to paid compute. Unknown quota,
   missing cleanup, or unsupported workload blocks that route with a concrete
   reason.
7. **Colab must join through the same lifecycle to count as GPU Control.** A
   direct Colab MCP connection can be a separate user tool, but it is outside
   GPU Control run history, authorization, budgets and cleanup; do not report it
   as an integrated provider. The integration choice remains subject to proof
   of Google identity delegation, quota evidence, cancellation and artifact
   recovery.
8. **Keep production/provider execution parked until gates pass.** The current
   implementation can be developed and tested offline while admission is
   disabled. Merging, deploying, migration, enabling a provider and spending
   are separate state changes with separate evidence.

## Consequences

- A registered fixed workload and an owner-selected source use the same
  user-facing lifecycle, but may have different validated execution contracts.
- Existing fixed workload routes stay intact until callers, run history and
  cleanup evidence have migrated. Compatibility is kept only while a real
  caller or contract requires it.
- Provider capabilities must describe executable tasks and cleanup behavior,
  not merely configured credentials or a reachable adapter.
- The agent needs concise tool descriptions and a reusable project Skill that
  state the sequence, recovery rule and stop condition. It should discover
  names/IDs from tools instead of asking the user to construct them.
- D1 and adapter recovery state need an explicit transition authority map;
  local journals may prevent duplicate provider allocation but may not become a
  competing user-facing run ledger.

## Current implementation gap

PR #70 implements a Modal-only owner-selected source lane in source. It is not
merged or verified live in this checkpoint. RunPod/Kaggle/Hugging Face custom
repository routes and Colab integration are not implied. `parked` policy and
closed admission remain authoritative. See the
[repository map](../repository-map.md) and
[refactoring backlog](../refactoring-backlog.md).

## Revisit when

- ChatGPT/Work cannot expose the lifecycle without forcing out-of-band setup;
- a provider cannot supply durable idempotency/recovery, bounded cost or
  verifiable cleanup under this interface;
- Colab's hosted API identity or quota contract makes a Sites-owned adapter
  impossible; or
- an independently deployed Gateway has an actual supported user-facing
  contract and ownership that materially changes the control-plane boundary.
