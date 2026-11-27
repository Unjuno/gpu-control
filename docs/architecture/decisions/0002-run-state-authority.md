# ADR 0002: Run state authority across Sites and provider adapters

- **Status:** accepted for the current Sites-owned training lifecycle; other
  provider routes still require conformance review.
- **Date:** 2026-11-28
- **Scope:** owner-selected training implemented in PR #70 and its Sites to
  Modal adapter path.

## Context

One experiment crosses multiple durable systems. Sites D1 owns the user,
immutable plan, authorization, budget reservation and product run history. The
Modal adapter needs an atomic claim to prevent two requests from creating two
Sandboxes after a lost response. The provider and Sandbox report execution and
cleanup evidence. Treating these records as interchangeable replicas would
make retries and terminal claims ambiguous.

## Decision

1. **Sites D1 is authoritative for product intent and accounting:** owner,
   immutable plan and fingerprint, one-time authorization, dispatch reservation,
   rejection, and the fact that required cleanup has been verified.
2. **The adapter journal is authoritative for adapter dispatch recovery:**
   owner/run/fingerprint binding, its atomic create claim, deterministic
   resource handle, and the latest adapter receipt. It is not an independent
   user-facing run ledger and cannot change the plan or authorization.
3. **Provider/Sandbox inspection is authoritative evidence of current
   execution and cleanup.** The adapter validates that evidence, records its
   receipt, and Sites persists only the confirmed cleanup fact in D1.
4. **Reconcile by the same immutable run identity.** After response loss,
   status reads the existing adapter journal and reconciles its recorded
   provider handle. A missing or stale record/handle remains uncertain unless
   provider inspection proves the outcome. Never create a replacement run to
   resolve uncertainty.
5. **Terminal execution is not terminal product completion until cleanup is
   confirmed.** Do not expose checkpoints/artifacts as complete before the
   adapter proves the allowed terminal state and required cleanup.
6. **No cross-system transaction is assumed.** D1 reserves before dispatch;
   the adapter's atomic journal claim fences provider creation. A definitive
   pre-create rejection may be recorded as rejected. An ambiguous post-claim
   failure remains reserved/uncertain and is reconciled, not refunded or
   resubmitted automatically.

## Evidence and limits

- Sites reservation and cleanup receipt: `worker/training_plan.js`.
- Sites same-run status reconciliation: `worker/index.js`.
- Modal custom dispatch, recovery and cleanup checks:
  `modal/custom_training_lifecycle.py`.
- Existing adapter tests cover one start under duplicate submit, uncertain
  start without retry, cleanup-pending behavior, and cancellation to confirmed
  cleanup: `modal/test_custom_training_lifecycle.py`.

This contract has not yet been proven by a deployed integration test. It is
specific to the owner-selected Modal-backed training route. Other providers,
adapter journal retention, and recovery after durable journal loss still need
conformance tests before extending this decision to them.

## Consequences

- D1 and the adapter journal intentionally hold different facts rather than
  duplicating a full state machine.
- Read tools may combine D1 identity/accounting with a fresh provider receipt;
  responses must distinguish verified, stale and uncertain observations.
- A durable journal's retention period must exceed the maximum provider
  lifetime plus the recovery horizon. If it does not, admission must remain
  closed until an alternate provider-side recovery path is proven.
- Future providers implement this lifecycle contract behind the same
  owner-bound interface, with provider-specific evidence adapters.
