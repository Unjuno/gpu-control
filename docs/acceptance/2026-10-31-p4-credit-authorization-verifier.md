# P4 signed credit authorization verifier — 2026-10-31

Status: **PASS for offline signed-envelope and exact-plan verification only.**
This does not enable credit-backed execution or accept Modal as a GPU provider.
Repository policy remains `mode: parked`.

## Implemented boundary

`gateway/gpu_gateway/credit_authorization_bridge.py` verifies a strict Ed25519
envelope from an independently trusted issuer. The claims bind the authorization
to its audience and issuer/key namespace, run, owner, actor, decision record,
control-plane SHA, Gateway PlanV2 fingerprint, provider, exact resource, image,
runtime, current capability-evidence fingerprint, maximum gross credit debit,
and zero out-of-pocket ceiling. Expiry, policy version, signature and a required
revocation lookup are checked; lookup errors fail closed.

The verifier requires current `CREDIT_BACKED` cost and quota evidence; every
gross cost component must be known and covered, usage headroom and eligible
credits must cover the run, a hard spend cap must be enforced, and overage must
stop. Default-empty `Settings` fields parse issuer-scoped Ed25519 trust keys.
Neither the settings nor verifier are connected to worker admission. No provider
implements `validate_credit_authorization`, and there is no durable one-use
authorization record or provider pre-create recheck.

## Evidence

- Checkout HEAD: `a794438f42bd7246f463eaaa40d963af0aae9d13`; the implementation
  and tests are uncommitted additions in a broadly dirty worktree.
- Focused command from `gateway/`:
  `./.venv/bin/python -m pytest -q tests/test_credit_authorization_bridge.py tests/test_paid_authorization_bridge.py`
- Result: **52 passed**, one existing Starlette deprecation warning.
- Cases cover successful signing and exact binding; run/owner/actor/decision,
  resource, quota fingerprint and debit mismatches; nonzero out-of-pocket
  ceiling; expiry; revocation; missing hard-stop behavior; and issuer-key
  configuration scoping. Two additional cases reject omitted zero-cost
  components and a plan ceiling below the gross credit debit. Fixtures use
  synthetic evidence and test-only keys.
- Independent read-only Security Review of the initial verifier/configuration
  diff found no actionable findings. The subsequent two fail-closed checks
  were added after that review and are not independently reviewed yet. The
  reviewer specifically required durable one-use authorization and
  revocation/quota/spend rechecks immediately before provider creation before
  any execution enablement.
- `git diff --check` passed. The three main source/test files had SHA-256:
  `537ee44b77add57207fabbb58331b32c1a1d683434b80194e6f93709091af72f`
  (verifier), `9c5f2dd79335bfc90e7f1f86f6f059fefe80083c879d75505395ed5102156fdf`
  (tests), and `7a750b327e599911aca0033901c49ab426ba378f560af3e197dd1cf7e63eb7da`
  (settings).

## Explicit limits

No live account quota, actual provider spend cap, credit consumption, provider
call, GPU allocation, deployment, or ChatGPT action was performed. The current
ChatGPT browser is logged out, the desktop app is unavailable to computer
control, and P1 GitHub PRs #57/#58 remain Draft awaiting independent GitHub
approval. This record is local verifier evidence only; it does not close the
P4 adapter or P1 product acceptance gates.
