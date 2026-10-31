# P5 Gateway–RunPod Paid Permit Bridge

Status: pure signed-envelope verifier and exact-plan binding implemented
offline; issuer selection, durable worker integration, and provider acceptance
remain incomplete. No paid execution is enabled.

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

### Credit-backed authorization boundary

The registry now routes `CREDIT_BACKED` plans through an independent credit
authorization hook. `gateway/gpu_gateway/credit_authorization_bridge.py`
implements a pure offline Ed25519 verifier for a signed credit-consumption
decision. It binds exact run, owner, actor, decision record, PlanV2, provider
resource, image, runtime, gross credit debit, zero out-of-pocket ceiling, and
the current quota-evidence fingerprint. It requires complete current cost
coverage, sufficient usage headroom and eligible credits, an enforced hard cap,
stop-on-overage, trusted issuer/key configuration, and a working revocation
lookup. This advances the contract only: no provider implements the hook, the
verifier is not connected to worker admission, and no credit-backed path is
executable. Do not weaken the registry gate or relabel credit-backed cost as
`FREE` to make Modal usable.

If Modal credits are to be consumed, the authority contract must explicitly
bind the human's maximum gross credit debit, a zero out-of-pocket ceiling,
current quota-evidence fingerprint and coverage, and the exact owner, actor,
run, PlanV2, provider resource, image, and expiry. Recheck quota immediately
before submission and provider creation; fail closed if credits, usage headroom,
or hard-stop settings changed. The issuer must distinguish credit consumption
from new cash charges in its signed decision. Until this contract and issuer
are independently selected and reviewed, `CREDIT_BACKED` remains blocked.

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
- If the issuer uses a GitHub Environment, require configured independent
  reviewers, prevent self-review, and restrict eligible deployment branches.
  Verify these controls through the GitHub API before any paid-environment
  activation. The 2026-10-31 audit found no protection rules or deployment
  branch policy on either current GitHub Environment; the machine policy now
  lists all three controls as activation prerequisites. The prerequisite list
  is a governance/release gate, not runtime verification: its YAML values and
  presence tests do not prove that GitHub currently enforces these settings.
  Any activation or authority issuer must consume fresh, trusted environment
  policy evidence and fail closed when it is missing or stale.
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
- Decide and implement the separate credit-consumption claim above before
  accepting any `CREDIT_BACKED` plan. The present verifier's PAID-only rule is
  not permission to consume workspace credits and must remain fail-closed.

2026-10-31 progress: `gateway/gpu_gateway/paid_authorization_bridge.py` now
verifies a strict Ed25519 envelope from an independently configured key map.
`Settings` accepts `GATEWAY_PAID_AUTHORIZATION_ISSUER`,
`GATEWAY_PAID_AUTHORIZATION_POLICY_VERSION`, and the namespaced Ed25519 public
key map in `GATEWAY_PAID_AUTHORIZATION_PUBLIC_KEYS_JSON`; it requires all three
to agree when configured. These settings are not yet consumed by worker
admission. The verifier
requires a revocation lookup on every validation, and binds the Gateway and
RunPod core fingerprints plus owner/actor/decision/run/control-plane/provider/
resource/image/runtime/cost claims. It rejects non-PAID, missing, zero, stale,
or over-cap cost evidence before trust acceptance, and rejects a core-plan
worst-case quote above the current Gateway total-cost evidence. Focused tests
passed 38/38; the full Gateway suite passed 467 with 15 environment-dependent skips. This pure
verifier is not wired to persistence, worker admission, or provider create and
does not create `HumanAuthorizationEvidence`, `PaidAuthorizationEvidence`, or
`LiveExecutionPermit`. Authority selection and independent review remain open;
provider and paid flags stay disabled. Evidence:
`docs/acceptance/2026-10-31-p5-paid-authorization-verifier.md`.

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

2026-10-31 persistence foundation: schema v12 adds a separate
`gateway_paid_authorizations_v1` record keyed by run. The Store can persist an
already verified envelope only while the exact browser approval is current,
and binds it to owner, run, plan fingerprint, approval ID, issuer, and
authorization ID. Reload checks the same identity tuple and a canonical
SHA-256 digest; malformed or changed payloads fail closed. This is storage
plumbing only: no issuer/API caller, worker reload/revalidation, provider
pre-create recheck, revocation source, or RunPod paid registration is wired.
The RunPod worker's explicit persistence-unavailable refusal remains in place.
No authorization was issued or stored during implementation.

### P5.3a Account-wide allocation lease

The adapter's short-lived account occupancy snapshot is a precondition check,
not a concurrency primitive. Two independent workers can read the same empty
account snapshot and both create a Pod. A process mutex or a PostgreSQL advisory
lock held only around `create_pod` is also insufficient: it releases on worker
death, and a provider list that has not yet reflected an ambiguous create can
then authorize a second allocation.

2026-10-31 progress: `Store.read_provider_account_lease_for_run` now reloads a
durable lease only for the current, unexpired Gateway worker claim and exact
run/owner/plan/attempt/authorization/challenge bindings. It locks the provider
lease before relocking the run row to keep the reservation lock order, checks
the persisted challenge digest, and refuses released or malformed active states.
SQLite and independent PostgreSQL process tests exercise recovery reads. This is
a Store primitive; `Worker` and the RunPod adapter still do not use it, and the
HMAC credential identity, signed authorization persistence, create/reconcile,
and independent cleanup path remain unimplemented. Acceptance record:
`docs/acceptance/2026-10-31-p5-account-lease-recovery-read.md`.

2026-10-31 follow-up: `Settings` now reads the dedicated account-scope HMAC
key from `GATEWAY_PROVIDER_ACCOUNT_SCOPE_HMAC_KEY_B64`, rejects invalid
Base64 and decoded keys outside 32-4096 bytes, and omits the setting from its
representation. The key remains optional until an operator configures the
account-lease path. It is not yet wired into Worker or provider dispatch;
recorded checks are in `docs/acceptance/2026-10-31-p5-account-scope-key-config.md`.

2026-10-31 follow-up: added
`Store.transition_provider_account_lease_for_run`, which fences provider
lease state changes by both the durable account lease token and the current,
unexpired Gateway worker claim. It verifies the exact run intent, provider
challenge digest, plan, core-plan, and authorization bindings under the same
lease-before-run lock order as recovery reads. Stale workers cannot mark an
allocation active or uncertain after a successor has claimed the run. This is
still a Store primitive with no Worker/adapter caller; lease release is not
yet atomic with the terminal cleanup record. See
`docs/acceptance/2026-10-31-p5-account-lease-worker-fencing.md`.

2026-10-31 follow-up: the Worker now recognizes a persisted RunPod account
lease during both normal terminal cleanup and recovery of a pending cleanup.
It checks the adapter's handle-to-provider-job-ID mapping, moves the exact
lease to `cleanup_pending` before cleanup, requires literal `True` from the
adapter's cleanup check, and then calls one Store transaction to release the
lease, mark the run and result cleanup complete, and release the admission
slot. A failed check or crash leaves the lease held for recovery. Fake-provider
Worker tests cover ordinary cleanup and cleanup recovery. This does not yet
create the lease from Worker submission or bind a persisted signed paid
authorization; the acceptance record retains those limits.

2026-10-31 follow-up: RunPod candidate readiness now requires the explicit
`RunPodAccountLeaseBackend` prepare/create/reconcile/resource-ID contract.
The request object contains only core-plan and authorization identities plus
the non-secret create challenge; the provider credential remains in Worker
settings. The Worker checks structural readiness before submission intent, so
the current legacy RunPod bridge cannot dispatch candidate plans without a
lease-capable adapter. This is a fail-closed interface gate; no adapter yet
implements it. See
`docs/acceptance/2026-10-31-p5-runpod-lease-contract-gate.md`.

Implement a durable, shared single-allocation lease before enabling any
RunPod candidate or paid registration:

1. Derive an opaque account-scope key from a stable, operator-configured
   `GATEWAY_RUNPOD_ACCOUNT_SCOPE_ID` and a server-held HMAC key. The scope ID
   must be shared by all credentials for one RunPod account and remain stable
   across credential rotations. Never derive the identity from the API key:
   old and new credentials during a rolling rotation must serialize through
   the same lease row. Never persist or log the provider credential or scope
   ID; separate provider accounts must use distinct scope IDs.
2. In the Gateway database, atomically reserve that account for the exact
   owner, run ID, Gateway plan fingerprint, core-plan fingerprint, and
   authorization ID before submission intent/provider create. A unique account
   scope allows at most one non-released lease. The reservation and run intent
   must commit together or fail closed.
3. Use explicit durable states: `reserved`, `submitting`, `active`,
   `uncertain`, and `cleanup_pending`. Persist the provider request challenge
   before the network call. Store the provider Pod ID only after it is
   validated against the exact approved plan. Never treat lease expiry as
   proof that the provider resource is absent.
4. On a definitive pre-create refusal, release only when evidence proves no
   create request was sent. On timeout, connection loss, worker death, or any
   other ambiguous outcome, retain `uncertain`; the supervisor reconciles by
   the exact persisted challenge and may attach to exactly one matching Pod.
   Zero matches are not enough to clear the lease unless the provider offers a
   documented consistency/absence guarantee that has elapsed and been
   independently validated. Multiple matches remain a manual incident.
5. Keep the account lease occupied for the full provider-resource lifetime.
   On cancel/terminal processing, transition to `cleanup_pending`; release the
   lease only after an independent account inventory proves the exact Pod is
   `TERMINATED` or absent under a validated provider contract, and the durable
   run cleanup record commits. A crash before that commit must leave the lease
   blocking new allocations for recovery.
6. Make reservation, transition, replay, stale-worker, and cleanup operations
   conditional on the current lease version/token and exact run/plan identity.
   A stale worker must not release or overwrite a successor's lease. Recovery
   reuses the original permit and challenge and never submits a replacement.

Required offline acceptance uses at least two independent processes and DB
connections sharing the same account scope, with a barrier that makes both
attempt allocation from an initially empty fake provider. Assert exactly one
provider create call and one active lease. Repeat with the winner killed
before create, during an ambiguous create with delayed inventory visibility,
after Pod-ID persistence, and after termination but before lease release.
Assert no second create occurs while outcome or cleanup is uncertain, recovery
attaches to the original Pod, and the next allocation succeeds only after
confirmed release. Also prove different account scopes remain independent,
stale lease tokens cannot release a newer lease, and SQLite/dev behavior cannot
be mistaken for cross-host production locking. A live competition canary is a
separate acceptance gate and is not authorized by these tests.

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

2026-10-31 follow-up: Worker account scope now uses the non-secret
`GATEWAY_RUNPOD_ACCOUNT_SCOPE_ID` rather than `RUNPOD_API_KEY`, so a credential
rotation does not create a parallel lease namespace. The ID is omitted from
Settings representations, like credentials and the HMAC key. This fixes the
identity contract for local/fake dispatch; production secret distribution and
live provider acceptance remain separate gates.

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
