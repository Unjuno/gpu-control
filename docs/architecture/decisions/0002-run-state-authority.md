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
  Dict fences its atomic Sandbox create claim, while the run-scoped Modal
  Volume stores checkpoint/artifact bytes and the fixed runner's terminal
  receipt. Sites D1 stores the bounded, validated terminal result metadata.
  None of the provider records is a second user-facing run ledger, and none
  can change the immutable plan or authorization.
3. **Provider/runtime inspection is authoritative evidence of current
  execution and cleanup.** The adapter validates that evidence; Sites persists
  its bounded terminal projection and confirmed cleanup fact in D1. Large
  artifacts remain outside D1.
4. **Reconcile by the same immutable run identity and provider operation
  identity.** After response loss, status reads the route's existing
  coordination record and inspects the recorded provider resource. For custom
  Modal training, a signed Sites request can reconstruct the exact approved
  plan from owner-bound D1; the adapter may then inspect only the deterministic
  Sandbox or the run-scoped durable Volume receipt. This recovery never calls
  `start`. A missing or conflicting plan/resource/result remains uncertain.
  Never create a replacement run to resolve uncertainty.
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
  `modal/custom_training_lifecycle.py`, the adapter's Modal Dict, and the
  per-run checkpoint Volume.
- Shared owner-visible status and reconciliation:
  `worker/experiment_status.js`, `worker/run_reconciliation.js`, and the
  provider lifecycle modules.
- Existing adapter tests cover one start under duplicate submit, uncertain
  start without retry, cleanup-pending behavior, and cancellation to confirmed
  cleanup: `modal/test_custom_training_lifecycle.py`.

This contract has not yet been proven by a deployed integration test. The
provider-specific records above are implemented in source, but response-loss,
duplicate delivery, terminal-state mismatch, cleanup and durable-record-loss
conformance must be verified independently for each route. Modal Dict entries
expire after seven days without a read or write ([security and data
retention](https://modal.com/docs/guide/security#data-privacy)). The owner-
training route now recovers after that expiry from the exact D1 plan plus either
the deterministic Sandbox or the run-scoped Volume result receipt. If both the
provider resource and durable receipt are missing or contradictory, it remains
uncertain and never resubmits. Modal Volumes persist until deleted and may incur
storage charges ([Volumes guide](https://modal.com/docs/guide/volumes)); an
artifact-retention and deletion policy is still required before promising
cost-bounded indefinite retention. No background reconciler is configured,
so recovery still requires a compatible client to call status/reconcile.

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
