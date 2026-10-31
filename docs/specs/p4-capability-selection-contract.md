# P4 capability and selection contract

Status (2026-10-31): **offline selection and exact-plan evidence revalidation
are wired through Gateway; provider inventory is partial and no candidate-bound
GPU execution backend is accepted**. This contract turns the P4 roadmap
into interfaces and observable decisions while keeping provider selection,
cost classification, and authorization separate.

## Existing interfaces to preserve

- `src/gpu_control/pricing.py::PricingVerificationResult` currently binds one
  provider, GPU profile, concrete provider resource, hourly price, evidence
  reference, verification window, price result, and availability result.
- `src/gpu_control/execution.py::ApprovedExecutionPlan` binds a provider
  resource and workload identity to current pricing, a positive cost ceiling,
  human authorization, and source/container/cleanup gates. It is the paid
  execution boundary. Capability discovery must not construct or imply this
  authorization.
- `gateway/gpu_gateway/config.py::Workload` is operator-owned and restricts
  Modal to an existing image ID and fixed argv. `gateway/gpu_gateway/registry.py`
  is the Gateway's trusted provider registry. MCP callers select a registered
  workload; they do not supply providers, image IDs, or commands.
- `gateway/gpu_gateway/admission.py` only grants the separately reviewed local
  CPU lane when its exact zero-cost policy is enabled. Do not broaden that
  policy to GPU providers.

## Proposed data contract

Add immutable, JSON-serializable values in the core package. Exact names may be
adjusted to match the implementation, but preserve these semantics:

### `WorkloadRequirements`

- workload ID and immutable source revision;
- OS and architecture requirements;
- accelerator kind, model/profile, count, and minimum VRAM;
- CPU and RAM bounds;
- image/runtime requirements, maximum wall time, and an optional queue-wait ceiling;
- network requirements and whether outbound network can be disabled;
- result transport requirements and maximum result size;
- cancellation and resource-release proof required by the workload.

Requirements come from an operator-registered workload manifest. They are not
loosened to make a candidate fit.

### `CapabilityEvidence`

- provider and concrete resource ID, or a reason no concrete resource can yet
  be resolved;
- `availability`: `AVAILABLE`, `UNAVAILABLE`, or `UNKNOWN`;
- `cost_classification`: one of `LOCAL`, `FREE`, `FREE_QUOTA`,
  `CREDIT_BACKED`, `PAID`, `MANUAL_ONLY`, `UNSUPPORTED`, or `UNKNOWN`;
- explicit cost components for accelerator, CPU, RAM, storage, egress, and
  other provider charges; unknown components remain null/unknown;
- quota/credit evidence, whether a hard spend cap is enforceable, and the
  provider's stated overage behavior;
- supported OS/architecture/runtime, accelerator and VRAM capacity, timeout,
  estimated queue wait, result transport, cancellation, and cleanup behavior;
- evidence reference, observed-at time, expiry, and evidence source.

Availability and cost classification are independent. For example,
`availability=AVAILABLE` with `cost_classification=UNKNOWN` is not selectable
for a zero-additional-cost requirement. `CREDIT_BACKED` does not mean free, and
`FREE_QUOTA` is acceptable only while current quota evidence is valid and
overage is prevented or explicitly authorized.

For a credit-backed provider, keep gross per-run charges separate from current
usage headroom, credit coverage, and out-of-pocket exposure. Quota evidence
must identify usage headroom, credit balance, expiry, and eligible cost
components; a zero net-spend cap does not prove enough usage headroom or
eligible credit remains to finish a run. Re-evaluate the evidence at prepare,
approval, submit, and worker launch. Modal's public billing guide documents
separate usage and net-spend limits, and says credit-covered work may continue
until the usage limit even after the spend limit is reached; the selected
workspace's values still require owner inspection.

### Selection decision

Selection returns a stable decision object with selected workload/provider
candidate, evidence fingerprint, rejected candidates with machine-readable
reasons, and a blocking reason when no candidate is admissible. It does not
submit, authorize, or silently rewrite a plan.

`FREE_FIRST` orders only candidates that satisfy all resource requirements and
have current evidence. An explicit zero-additional-cost request requires every
charge component to be known and zero and a verified hard cap against overage;
included credit alone is insufficient. Unknown quota returns `QUOTA_UNKNOWN`.
No matching currently free GPU returns `FREE_GPU_UNAVAILABLE` and exposes a
separate local CPU alternative plus the separately authorized paid-prepare
path. An alternative is presented for human choice, never silently selected.

Runtime requirements are exact operator-owned identifiers (for example,
`python:3.12` or `cuda:12.4`). Evidence must enumerate supported identifiers;
missing or incompatible runtime evidence rejects that candidate. A workload may
set `max_queue_wait_seconds`; then the current capability observation must
include `estimated_queue_wait_seconds` no greater than that limit. An absent
estimate is unknown and rejects the candidate. Both fields are part of the
workload/evidence fingerprints so approval cannot outlive a change to either.

After a human approves an exact plan, the plan fingerprint fixes the provider
and resource. If pricing/quota evidence expires or changes before submit or
worker launch, fail closed and require a new prepare/approval; do not fall back
to another provider.

## Required tests and acceptance evidence

Unit tests must cover at least:

1. independently changing availability and cost class;
2. each resource mismatch (GPU/VRAM, architecture, OS, CPU/RAM, timeout,
   network, result transport, cancellation, cleanup);
3. unknown or expired quota/price evidence and hard-cap absence;
4. zero-cost selection rejection when any component or overage behavior is
   unknown;
5. `FREE_FIRST` order with only compatible, currently admissible candidates;
6. `QUOTA_UNKNOWN` and `FREE_GPU_UNAVAILABLE` results and explicit CPU/paid
   alternatives;
7. evidence invalidation between prepare, approval, submit, and worker launch
   without provider substitution. Core `revalidate_approved_candidate` compares
   the approved workload/provider/resource/evidence fingerprints, re-runs
   compatibility and quota checks on the exact candidate, and returns
   `APPROVED_PLAN_STALE` instead of selecting a replacement. `PlanV2` now
   persists an optional strict `selection_binding` and includes it in the plan
   fingerprint, while preserving legacy unbound v2 fingerprints. Gateway now
   verifies signed provider observations, creates bound GPU plans, and
   revalidates before prepare persistence, inside submit's transaction, and
   before worker submission intent. The local CPU admission lane now
   rejects any candidate-bound `PlanV2`, because that path uses its separate
   static CPU policy and does not revalidate provider-selection evidence.
8. deterministic canonical serialization/fingerprint and rejection of unknown
   fields or non-finite monetary values.
9. exact runtime-identifier compatibility and unknown-evidence rejection;
10. unknown/above-ceiling queue-wait estimates and their inclusion in evidence
    fingerprints.

Offline tests can accept deterministic classification and selection only. They
cannot prove a provider quota, account budget, real GPU, actual spend cap,
result collection, or cleanup. Those need separate account inspection and an
approved live GPU smoke. Keep `mode: parked`, provider switches false, and all
paid calls disabled until those external gates pass.

## Implementation order

1. [x] Thread the registered workload manifest into the new core types without
   changing the MCP payload. Pure `WorkloadRequirements`, `CapabilityEvidence`,
   `CostBreakdown`, and `SelectionResult` types exist; Gateway maps complete
   operator manifests into requirements and invokes the selector. Provider
   inventory gaps remain unknown and therefore non-selectable.
2. [x] Add gross cost decomposition and evidence freshness while leaving the current
   `PricingVerificationResult`/`ApprovedExecutionPlan` authorization boundary
   unchanged.
   [partial] Core `QuotaEvidence` now binds usage headroom, credit balance,
   eligible cost components, reference, and expiry to immutable capability evidence. The
   selector accepts zero-additional-cost `CREDIT_BACKED` candidates only when
   current credits cover every gross component, the hard spend cap is enforced,
   and overage stops; insufficient/stale balances return `QUOTA_UNKNOWN`, and
   uncovered costs fail closed. Gateway verifies and rechecks signed candidate
   evidence, but the Modal billing collector deliberately emits no quota
   evidence; no Modal credit-backed candidate is eligible.
3. [x] Add deterministic candidate selection and structured refusal reasons.
4. [partial] Surface selection and registered CPU alternatives in the
   Gateway read-only capability response; do not permit prepare/submit to
   infer approval from discovery. Operator manifests can now state OS,
   architecture, GPU count/VRAM, network, result transport/size, cancellation,
   and cleanup requirements. Missing fields remain unknown. Complete manifests
   are converted to `WorkloadRequirements` and passed to the pure selector.
   The worker publishes signed RunPod catalog observations, and Gateway maps
   them into selector evidence. Inventory completeness means every configured
   GPU/datacenter mapping returned an unambiguous catalog row; it does not
   establish runtime, OS, CPU/RAM, result transport, cleanup, quota, or total
   cost. Those fields remain unknown, so the candidate is still rejected as
   non-runnable. Do not call the partial quote/stock observation complete
   capability evidence.
   Provider credentials stay out of the API process. A worker-produced,
   provenance-preserving observation path is implemented for partial RunPod
   catalog evidence. `gpu-control` is installed as a
   local dependency in Gateway tests/containers; the Vercel project has not
   been redeployed to verify its outside-root source inclusion setting. The
   capability response now also exposes `provider_availability` separately
   from Gateway submission `availability` and `cost_classification`; an enabled
   but unverified GPU provider is `UNKNOWN`, while a disabled provider is
   `UNAVAILABLE`. This keeps configuration/readiness from being mistaken for
   live inventory evidence.
5. Reassess the Modal-first candidate sequence against the existing RunPod
   price/stock source and its separately gated credential path. Select the
   first integration only after comparing the evidence needed for full
   capability, quota, spend-stop, result collection, and cleanup. Require
   owner-read account evidence and a bounded actual GPU smoke before marking
   any provider usable. Do not substitute one provider's missing evidence with
   another's assumptions; retain other candidates as unavailable until their
   own gates pass.

## Gateway integration boundary

The offline Gateway integration now implements the following independently
reviewable steps; its external acceptance remains open:

1. A worker-only collector performs bounded, read-only provider observations
   using a dedicated environment file loaded by the normal worker only. The API
   process, recovery supervisor, MCP request, and workload manifest never carry
   provider credentials or the observation signing key. Polling is rate-limited
   and happens only while the worker has no claimed job. Missing credentials,
   provider errors, or an unconfigured exact resource/datacenter mapping produce
   no observation, not a synthetic empty inventory.
2. Persist a normalized observation with provider/source identity, source
   contract revision, observed/expiry timestamps, a canonical normalized-payload digest, and
   a monotonic observation version. Never persist credentials or unbounded raw
   provider payloads. Write and replacement are atomic. Expired observations
   remain unavailable to selection even if the provider API is down. The
   current systemd templates give API and worker the same database URL, so
   worker-only provider credentials do not authenticate who wrote a database
   row. The implemented path signs the canonical envelope with a worker-only
   Ed25519 key and verifies it against API-pinned public keys. It binds the
   monotonic provider version and all observation fields, rejects equal/lower
   versions atomically, and enforces the observation TTL. Operational key
   rotation and retirement still need acceptance; a plain digest alone is not
   trusted as provenance.
3. The signed payload shape is exactly
   `{ "inventory_complete": boolean, "candidates": [CapabilityEvidence.to_dict()] }`
   with at most 256 candidates. The API capability response reads only the
   latest persisted observation, strictly reconstructs selector types, and
   checks provider/source/observation timestamps against the signed envelope.
   It converts only directly supported fields and preserves unknowns. RunPod
   `HIGH` stock means a recent offer signal, not a reservation. Its catalog
   price is not all-in cost; until CPU/RAM, storage, egress, usage headroom,
   and stop behavior are evidenced, zero-cost requests and bounded-total-cost
   plans must reject it.
4. Persist the selector's exact workload/provider/resource/evidence
   fingerprints in the approved plan. The submit path and worker immediately
   before provider creation fetch current evidence and compare the same
   identities. A missing, expired, changed, or newly incompatible observation
   fails the run and requires a new prepare/approval; it never substitutes a
   different GPU or provider. The normal API and worker both use verified
   signed observations. Candidate-bound plans remain non-submittable unless
   their provider registration explicitly declares a backend that has passed
   candidate-bound lifecycle acceptance; current Modal and RunPod registrations
   do not. This keeps plan binding and backend readiness separate.
5. Only after this offline-to-live observation path is reviewed should an
   explicitly authorized bounded GPU smoke exercise allocation, device
   identity, result retrieval, cancellation, spend limit, and cleanup. Passing
   selector tests or observing `HIGH` stock is not GPU execution acceptance.

The repository has the pure Ed25519 signed-envelope builder/verifier in
`gateway/gpu_gateway/provider_evidence.py` and schema v8 table
`gateway_provider_observations_v1`. Store methods verify signatures before
write, reject non-increasing provider versions atomically, detect row/index
digest mismatch, and verify signature/freshness on verified read. The idle
normal-worker RunPod collector, strict capability mapping, and Gateway binding
revalidation are wired. Public-key JSON parsing and worker private-key
configuration are available in `Settings`, and
`Worker.persist_provider_observation` restricts publication to the normal
worker role. The API and worker still share the database credential, so
provenance depends on protecting the worker signing key and API-pinned key set.
The API selection and revalidation helpers are in
`gateway/gpu_gateway/provider_selection.py`. A selected candidate is bound to
the v2 plan fingerprint; prepare rechecks before persistence, submit locks and
rechecks the provider observation in its transaction, and the worker rechecks
again immediately before writing submission intent. Any changed fingerprint,
manifest, cost evidence, or exact resource fails closed. Current provider
registrations still have `supports_candidate_binding=False`, so no such plan
can reserve a queue slot or reach an execution backend yet.

The runtime readiness check now requires candidate-bound start, authenticated
observation validation, capture, cancellation, no-create reconciliation,
cleanup, and independent clean-state confirmation. This closes a shape-check
gap where a backend could pass registration checks but lack the operations the
worker needs during cancellation or ambiguous-start recovery. The typed
`CandidateBoundBackend` protocol documents this adapter boundary. It does not
make either provider ready or verify a live adapter.

The current worker collector implementation is `gateway/gpu_gateway/runpod_inventory.py`.
It queries the official RunPod GraphQL GPU catalog and datacenter availability
using exact operator-owned `provider_resource_id` and
`provider_data_center_id` values. The signed source revision identifies the
official GraphQL spec revision `graphql-spec-1.1.0`. Inventory is marked
complete only when every registered RunPod workload has an unambiguous GPU,
datacenter, and availability row. The candidate preserves unknown OS, CPU,
RAM, runtime, network, output, cancellation, cleanup, and non-accelerator cost
fields, so the selector rejects it as non-runnable. The collector code and
signed storage path are covered with fake clients only; no RunPod API call or
GPU allocation has occurred.

The offline core slice is covered by `tests/test_capabilities.py` (16 cases) and
`tests/test_selection.py` (36 cases). The current root suite passed 517 tests
with 1 skipped on 2026-10-28. Gateway selector wiring now has regression coverage, but this
does not establish provider availability, account quota, real GPU execution,
spend protection, result collection, cleanup, or deployed Vercel packaging.
