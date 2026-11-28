# ADR 0013: Bind current Modal account evidence to MAP training plans

- **Status:** accepted for the parked MAP acceptance lane
- **Date:** 2026-11-28
- **Scope:** MAP-44M's fixed Modal L4 owner-confirmed training route

## Context

The Sites D1 reservation is a project-side accounting ceiling; it does not
prove the Modal Workspace usage limit or current usage. The MAP parked-mode
exception independently requires the Modal Workspace limit to be at most
$1.00 and the account's current usage to leave enough room for the exact run.
Before this change, the fixed T4 canary required short-lived Modal account
evidence, but MAP L4 training did not bind equivalent evidence to its plan.

## Decision

1. MAP plans are rejected unless the operator supplies a recent, schema-checked
   account observation in `MAP_TRAINING_ACCOUNT_EVIDENCE_JSON`.
2. The observation is restricted to Workspace `unjuno`, environment `main`, an
   exact `$1.00` usage limit, the L4 GPU and an hourly price equal to the plan's
   configured quote. It expires within one hour and must leave room for the
   full per-run ceiling plus one cent after current credits and charges.
3. The complete evidence object, including its content hash, is part of the
   approved plan fingerprint and is shown on the owner confirmation page.
4. Submit re-reads and validates the current binding before it reserves budget,
   consumes authorization, or contacts the adapter. Expired, changed, or
   exhausted evidence blocks the run.
5. The Sites ledger's hard MAP monthly maximum is $1.00 even if an environment
   binding attempts to configure a larger value.

## Consequences

- A configured price or D1 budget alone cannot make MAP executable.
- Account evidence is operator-supplied and time-bounded; it is not a signed
  Modal billing API attestation. Admission remains disabled until the separate
  provider-side limit and the observation are verified.
- The evidence contract is intentionally separate from RunPod, Kaggle and
  Hugging Face account models. Provider limits are not collapsed into one
  global budget.
