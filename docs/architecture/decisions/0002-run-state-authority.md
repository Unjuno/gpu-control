# ADR 0002: Run state authority across Sites and provider adapters

- **Status:** accepted for Sites product-ledger ownership. Provider-specific
  coordination records are inventoried below; route-by-route failure and
  retention conformance remains open.
- **Date:** 2026-11-28
- **Scope:** Sites product-ledger ownership and provider-specific recovery
  records in the PR #70 source candidate. This decision does not imply
  deployment or provider-route acceptance.

## Context

One experiment crosses multiple durable systems. Sites D1 owns the user,
immutable plan, authorization, budget reservation and product run history.
Provider-specific records coordinate external work: RunPod serializes use of
an account scope; Colab persists the identity and recovery state for its
runtime operations in D1; the Modal custom-training adapter uses a Modal Dict
for atomic Sandbox dispatch recovery. Providers report execution and cleanup
evidence. Treating any of these records as interchangeable replicas would make
retries and terminal claims ambiguous.

## Decision

1. **Sites D1 is authoritative for product intent and accounting:** owner,
   immutable plan and fingerprint, one-time authorization, dispatch reservation,
   rejection, and the fact that required cleanup has been verified.
2. **Provider-specific coordination records own only their bounded workflow
   facts:** RunPod's `provider_account_leases` and event table fence one
   account-scoped create/recovery sequence; Colab's
   `google_colab_run_operations` binds a run to its runtime request, session,
   execution and recovery state; the Modal custom-training adapter's Modal
   Dict owns its atomic create claim, deterministic Sandbox handle and latest
   adapter receipt. None is a second user-facing run ledger, and none can
   change the immutable plan or authorization.
3. **Provider/runtime inspection is authoritative evidence of current
   execution and cleanup.** The adapter validates that evidence, records its
   receipt, and Sites persists only the confirmed cleanup fact in D1.
4. **Reconcile by the same immutable run identity and provider operation
   identity.** After response loss, status reads the route's existing
   coordination record and inspects the recorded provider resource. A missing
   or stale record/handle remains uncertain unless provider inspection proves
   the outcome. Never create a replacement run to resolve uncertainty.
5. **Terminal execution is not terminal product completion until cleanup is
   confirmed.** Do not expose checkpoints/artifacts as complete before the
   adapter proves the allowed terminal state and required cleanup.
6. **No cross-system transaction is assumed.** D1 reserves before dispatch;
   the adapter's atomic journal claim fences provider creation. A definitive
   pre-create rejection may be recorded as rejected. An ambiguous post-claim
   failure remains reserved/uncertain and is reconciled, not refunded or
   resubmitted automatically.

## Evidence and limits

- Sites plan authorization and budget reservation: `worker/training_submit.js`,
  `worker/provider_budget_policy.js`, `worker/training_dispatch_claim.js`, and
  the D1 lifecycle tables.
- RunPod account lease state machine: `worker/provider_account_lease.js` and
  `worker/runpod_lifecycle.js`. `resumeTerminalAccountLease` resumes a
  partially completed D1 account-lease cleanup only when the owner run is
  terminal and its saved RunPod cleanup receipt matches the required transition.
  The SQLite-backed lifecycle tests inject a failure after run terminalization
  in both cancellation and ambiguous-submit TTL recovery, then verify that
  status resumes the same D1 lease without repeating provider calls. This is
  source-level recovery evidence, not deployed/provider acceptance.
- Colab run-operation journal: `worker/google_colab_operation_store.js` and
  `worker/google_colab_lifecycle.js`.
- Modal fixed-GPU lease and owner-training adapter recovery:
  `worker/delegated_experiment_lifecycle.js`,
  `modal/custom_training_lifecycle.py`, and the adapter's Modal Dict.
- Shared owner-visible status and reconciliation:
  `worker/experiment_status.js`, `worker/run_reconciliation.js`, and the
  provider lifecycle modules.
- Existing adapter tests cover one start under duplicate submit, uncertain
  start without retry, cleanup-pending behavior, and cancellation to confirmed
  cleanup: `modal/test_custom_training_lifecycle.py`.

This contract has not yet been proven by a deployed integration test. The
provider-specific records above are implemented in source, but response-loss,
duplicate delivery, terminal-state mismatch, cleanup and durable-record-loss
conformance must be verified independently for each route. The Modal custom
training journal has a known retention bound: Modal documents that Dict entries
expire after seven days without a read or write
([security and data retention](https://modal.com/docs/guide/security#data-privacy)).
The Sites repository configures no background refresher. Therefore the adapter
journal is not permanent recovery storage; a custom-training run left untouched
past that window can remain `dispatching` in D1 while its provider handle and
terminal result are no longer recoverable through the current adapter. A
durable recovery store or a verified, cost-bounded journal-refresh mechanism is
required before claiming indefinite resume after an interrupted chat.

## Consequences

- D1 and the adapter journal intentionally hold different facts rather than
  duplicating a full state machine.
- Read tools may combine D1 identity/accounting with a fresh provider receipt;
  responses must distinguish verified, stale and uncertain observations.
- A durable journal's retention period must exceed the maximum provider
  lifetime plus the recovery horizon. If it does not, admission must remain
  closed until an alternate provider-side recovery path is proven.
- Future providers use the same owner-bound product lifecycle while keeping
  only the provider-specific recovery state their API requires. Do not add a
  second run ledger or force incompatible provider operations into one
  artificial state machine.
