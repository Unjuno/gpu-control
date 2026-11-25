# Internal P5 paid authorization coordinator

## Goal

Close the uncalled verifier/Store seam for RunPod paid authorization without
publishing an issuer, adding an HTTP/MCP intake route, changing worker admission,
or enabling any provider. A future independently operated issuer may use this
internal coordinator after its authority and deployment design is reviewed.

## Spec and constraints

- Binding spec: `docs/specs/p5-gateway-runpod-permit-bridge.md`.
- Keep `policies/repository-state.yaml` at `mode: parked`.
- Preserve the Worker refusal `runpod_authorization_persistence_unavailable`.
- Browser plan approval remains separate from paid spending consent.
- The signed authorization must bind the exact current `approval_id` to prevent
  replaying an old signed envelope after a plan is re-approved.
- Trusted actor, DecisionRecord, control-plane SHA, core plan, issuer/key map,
  policy version, revocation lookup, and clock come from injected server-owned
  context; callers provide none of these as trusted values.
- No private signing key, provider credential, or permit is created or returned.
- Modal credit authorization remains a separate contract and is unchanged.

## Task 1 — Exact approval-bound signed envelope and offline coordinator

### Steps

1. Add RED tests for signed `approval_id` binding and the coordinator's
   verify/persist/reload/reverify path, using real Ed25519 signing keys.
2. Add wrong-owner/run/plan/core-plan/approval, stale or cancelled approval,
   revoked/unavailable revocation source, expiry, changed stored envelope,
   and missing trusted context cases. Assert invalid input never writes.
3. Implement strict approval binding in the paid envelope verifier and extend
   its verified value to carry that binding.
4. Implement an internal coordinator with only `persist()` and
   `reload_verified()`; use Store's exact-approval locked persistence/read APIs.
   Re-resolve trusted context and refresh time on each operation.
5. Confirm this coordinator has no HTTP/MCP/Worker callers; keep the current
   worker refusal and provider registry flags false.
6. Run focused authorization, Store, worker-gate, and credit-boundary tests,
   then the complete Gateway and core suites; inspect `git diff --check`.
7. Record evidence and limitations in an append-only acceptance document.

### Expected outcome

- Only an independently signed envelope binding the exact still-current plan,
  owner, approval generation, actor, core plan, control-plane revision, issuer,
  and current non-revoked decision is persisted/reloaded.
- Invalid, expired, revoked, stale, changed, or owner-mismatched inputs fail
  closed before storage or before returning verified context.
- No path can submit a provider job from this change.

### Commit

Commit the verified local implementation and acceptance record on the existing
candidate branch. Do not push, merge, deploy, create credentials, or alter
provider/production settings in this task.

## Review focus

- Approval-generation replay and reapproval after expiry/cancellation.
- Forged public `VerifiedPaidAuthorization` dataclass construction.
- Store lock wait and stale `now` / approval race.
- Revocation lookup outage and issuer/key rotation behavior.
- No new public endpoint or Worker/provider call path.
