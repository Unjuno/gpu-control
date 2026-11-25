# P4 candidate adapter receipt signer

Status: **PASS for the receipt construction primitive only.** No provider
adapter is wired or accepted, and no GPU or provider operation was performed.

## Change

Commits `3d824053612be93a56c96142c7662c1a551d6a91` and
`a794438` add `sign_adapter_candidate_receipt()` in
`gateway/gpu_gateway/candidate_receipts.py`. It constructs the exact
`gateway_adapter` envelope, binds the exact PlanV2 fingerprint, persisted run,
source/image/selected resource, normalized success claims, and digest of a
bounded provider-object projection, signs with an operator-supplied Ed25519
private key, then self-checks the receipt through the existing verifier.

The projection must be a strict recursive JSON object: string keys only,
standard JSON value/container types, no cycles. Canonical serialization keeps
the existing finite-number and 16 KiB limits. The helper does not authenticate
the provider response; trusted adapter code must obtain and cross-check that
response before signing. Key separation and provisioning remain operator
responsibilities.

## Verification and review

- TDD RED for the absent signer: **4 failed, 9 passed**; failures were the
  expected missing-signer assertions.
- TDD RED for projection ambiguity: **4 failed, 15 passed**; malformed Python
  values were accepted before the fix.
- Focused receipt tests after the fix: **20 passed**.
- Full Gateway suite with PostgreSQL 16 and the digest-identified local CPU
  image: **442 passed, 2 skipped, 1 warning**. Skips were optional Torch and
  Modal tests. Full command and output are retained in the task ledger at
  `.superpowers/sdd/2026-10-31-p4-adapter-receipt-signer/task-1-tests.log`.
- Core suite under Python 3.12: **550 passed, 1 Python-3.11-specific skip**.
- Independent read-only code review first found numeric-key canonicalization
  ambiguity. The fix now rejects non-object roots, non-string keys, tuples,
  non-JSON values, cycles, and excessive nesting. Re-review of
  `3d82405..a794438` found no Critical, Important, or Minor issues.
- `policies/repository-state.yaml` remains `mode: parked`; the two commits are
  local and were not pushed.

## Acceptance boundary

This work does not implement RunPod/Modal execution, authenticate the supplied
provider projection, provision a distinct receipt key, prove hardware identity,
or establish quota, result transport, cancellation, cleanup, or live GPU
acceptance. Keep provider registration and switches disabled until those
independent gates pass.
