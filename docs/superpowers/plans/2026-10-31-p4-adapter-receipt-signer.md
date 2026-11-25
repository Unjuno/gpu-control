# P4 adapter receipt signer

## Goal

Implement the P4 receipt-contract's adapter-attestation construction primitive.
It must sign only bounded claims tied to a candidate-bound `PlanV2`, the
persisted run/fingerprint, normalized result claims, and a bounded authenticated
provider-object projection. The existing verifier remains authoritative.

## Global constraints

- Do not wire or enable any provider registration, alter provider switches, or
  call provider APIs.
- The caller must supply an operator-held Ed25519 private key and a bounded
  projection obtained from an authenticated provider API observation. The
  helper does not claim to authenticate the input projection.
- Do not accept a receipt for a non-successful GPU result, another provider,
  another selected resource, or an expired/overlong validity interval.
- Keep `policies/repository-state.yaml` at `mode: parked`; paid execution gates
  remain unchanged.
- Existing uncommitted work is part of the current candidate state. Work on
  the existing non-main branch because a clean detached worktree would omit
  the uncommitted schema-v9 and receipt-verifier state this task must build on.
  Ruling: use current feature checkout — preserves the exact current API and
  tests — risk: worktree isolation from other local dirty changes is reduced.

## Task 1: Add and verify the bounded adapter receipt signer

Interfaces: existing `PlanV2`, `CandidateBinding`, `candidate_result_digest`,
`verify_candidate_receipt`, and the P4 signed envelope in
`docs/specs/p4-candidate-execution-receipt-contract.md`.

1. Add a test for a success receipt signed by an adapter key and verified by
   the current verifier. Assert the provider projection digest, selected
   resource, plan fingerprint, result digest, signer namespace, and canonical
   Ed25519 signature all match.
2. Add rejection tests for malformed/overlong time windows, mismatched
   `evidence_source`, unsuccessful GPU claims, and provider projections that
   are not strict recursive JSON objects (including non-string keys, tuples,
   and cycles).
3. Run the new tests before implementation and confirm they fail because the
   signer is absent.
4. Implement the minimal signer in `candidate_receipts.py`, constructing the
   exact receipt shape and self-checking through `verify_candidate_receipt`
   with the supplied key's public half.
5. Run focused receipt tests, the complete Gateway suite, and `git diff
   --check`. Do not change registration state.

Expected: the new tests fail before implementation for the missing signer,
then pass with a complete Gateway suite. A bad or unverified provider API
projection remains a caller trust failure and is documented as such.
