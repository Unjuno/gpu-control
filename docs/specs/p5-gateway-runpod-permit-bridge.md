# P5 Gateway–RunPod Paid Permit Bridge

Status: design and implementation boundary; no paid execution is enabled.

## Goal

Allow a Gateway run to use the existing RunPod core only when a trusted,
short-lived paid authorization is bound to the exact Gateway plan and provider
resource. Preserve the core `ApprovedExecutionPlan`, human authorization,
repository-security, pricing, occupancy, and cleanup gates. A browser approval
is necessary for the Gateway workflow but is not by itself paid authorization.

## Current boundary

`ExperimentService.approve` persists a browser approval ID and expiry for the
exact PlanV2 fingerprint. The worker requires a backend
`validate_paid_authorization(run)` to return literal `True` before persisting
submission intent. `ExistingRunPodBridge` delegates to an operator factory and
currently has no authenticated permit loader or plan adapter.

The core `LiveExecutionPermit` is a plain Python dataclass, not a signed token.
It is created from `HumanAuthorizationEvidence` and
`PaidAuthorizationEvidence`; the latter is bound to GitHub actor, triggering
actor, repository, protected workflow/ref, Environment, concurrency group, and
repository-security evidence. `validate_for_plan` checks plan fingerprint and
expiry, while the provider adapter rechecks the permit, price, and occupancy
before allocation. Consequently, copying a permit-shaped JSON object into the
Gateway database would not prove its issuer or provenance. The existing
GitHub-only paid authorization flow cannot be represented as a ChatGPT/browser
authorization without a separately reviewed authority design.

## Required trust chain

1. Gateway approval binds authenticated owner, run ID, PlanV2 fingerprint,
   expiry, and the running control-plane SHA. It remains a distinct approval.
2. A separately trusted paid-authority service validates the human's explicit
   spend decision, policy, repository/control-plane identity, and requested
   limit. It returns an authenticated, short-lived authorization envelope.
   The issuer and verification key must be independent of the Gateway worker
   process that consumes the envelope.
3. A deterministic adapter maps the exact PlanV2 and candidate binding to an
   `ApprovedExecutionPlan`; unsupported or absent inputs fail closed. The
   mapping must preserve repository/SHA, image digest, provider and resource
   ID, GPU profile/count, runtime, cost ceiling, and authorization reference.
   It must not infer GPU identity or price from workload parameters.
4. The envelope binds run ID, Gateway plan fingerprint, core-plan fingerprint,
   owner/actor, control-plane SHA, provider/resource, image, runtime/cost
   ceilings, issuer/policy version, issued time, and expiry. Verify signature,
   issuer/key scope, exact schema, validity window, and revocation state before
   submission intent and again immediately before provider allocation.
5. Persist the verified envelope durably with the run (or a separately
   encrypted authorization table referenced transactionally by run ID). Add
   additive migration and conservative legacy defaults. Never place bearer
   credentials or private signing material in run plans, logs, API responses,
   or provider handles. Recovery must retrieve the same authorization and
   must never mint a replacement or retry an uncertain allocation.
6. The provider adapter still checks fresh pricing, account-wide allocation
   limits, occupancy/serialization, immutable image verification, result
   transport, reconciliation, cancellation, and independent cleanup evidence.
   Authorization expiry before provider acceptance prevents create; after an
   uncertain create, enter reconciliation-only state.

## Implementation sequence

### P5.1 Authority contract and threat review

- Choose the paid-authority issuer and actor semantics for ChatGPT-driven runs.
- Decide how the user's explicit spending decision is captured outside a
  tool-supplied argument, how approval is revoked, and how issuer keys rotate.
- Decide whether the trusted issuer runs in GitHub protected Environment or a
  separately controlled service. Do not silently reinterpret the current
  GitHub Actions identity evidence as a Gateway user identity.
- Threat-model replay, confused deputy, stale/revoked consent, owner changes,
  database disclosure/tampering, control-plane rollback, and concurrent runs.
- Keep P5 registry acceptance false pending independent review.

### P5.2 Envelope and exact plan mapping

- Define strict versioned serialization, canonical signing bytes, allowed
  algorithms/key IDs, issuer/audience, and revocation lookup.
- Implement pure mapping and verification functions with no network/provider
  side effects. Reject any mismatch between PlanV2, candidate binding, core
  plan, Gateway run ID/fingerprint, price cap, resource ID, or image.
- Add adversarial contract cases for replay, expiry, wrong owner/run/plan,
  wrong key scope, changed resource/image/cost, malformed fields, and revocation.

### P5.3 Durable worker integration

- Add a migration for the envelope reference/payload with restricted access;
  bind it transactionally to owner, run, and plan fingerprint.
- Issue/store authorization only after exact browser approval and explicit
  paid authorization have both been validated. Do not accept an envelope from
  MCP tool parameters or the browser client.
- At worker pre-intent, verify the envelope and permit. At provider pre-create,
  reverify expiry/revocation and all current pricing/occupancy evidence.
- On worker restart, reload and verify the same envelope. Fail closed when
  missing, expired, revoked, corrupt, or bound to an older plan. Never auto
  renew or fall back to browser approval.

### P5.4 Independent acceptance

- Review the authority, schema, signature handling, storage/migration, logs,
  worker race behavior, and adapter mapping independently.
- Exercise offline end-to-end tests with fake keys and a fake provider before
  any live setting is considered.
- Verify account-wide single-allocation behavior, uncertain-create recovery,
  cancellation and resource release, all-in cost bounds, receipt provenance,
  and result retrieval.
- Only after user-approved canary scope and evidence are concrete may the
  RunPod paid registration be reconsidered. Keep repository policy parked and
  switches off until then.

## Acceptance evidence

The bridge is not accepted by passing unit tests alone. Record exact control
plane SHA, authority policy/key version, run and plan fingerprints, issued and
expiry times, provider object identity, price and occupancy snapshots, create
request outcome, result receipt, cancellation/reconciliation, cleanup proof,
and realized/unknown costs. Do not record secret values. Report authority,
provider lifecycle, GPU/device, semantic workload quality, and cost evidence
as separate claims.

## Explicit non-goals

- Do not treat Gateway OAuth scopes or browser approval as spend authorization.
- Do not fabricate `HumanAuthorizationEvidence` or `PaidAuthorizationEvidence`
  from PlanV2 fields.
- Do not accept unsigned serialized `LiveExecutionPermit` as proof of origin.
- Do not enable paid RunPod/Modal flags, contact a provider, allocate a GPU, or
  change parked policy as part of this bridge design.
