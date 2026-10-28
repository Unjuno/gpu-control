# P4 capability and selection contract

Status: **pure core models and selector are implemented; Gateway converts
explicit GPU workload requirements and calls the selector, but provider
inventory/evidence and live acceptance remain incomplete**. This contract turns the P4 roadmap
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
- image/runtime requirements and maximum wall time;
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
  result transport, cancellation, and cleanup behavior;
- evidence reference, observed-at time, expiry, and evidence source.

Availability and cost classification are independent. For example,
`availability=AVAILABLE` with `cost_classification=UNKNOWN` is not selectable
for a zero-additional-cost requirement. `CREDIT_BACKED` does not mean free, and
`FREE_QUOTA` is acceptable only while current quota evidence is valid and
overage is prevented or explicitly authorized.

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
7. evidence invalidation between prepare, approval, and submit without provider
   substitution;
8. deterministic canonical serialization/fingerprint and rejection of unknown
   fields or non-finite monetary values.

Offline tests can accept deterministic classification and selection only. They
cannot prove a provider quota, account budget, real GPU, actual spend cap,
result collection, or cleanup. Those need separate account inspection and an
approved live GPU smoke. Keep `mode: parked`, provider switches false, and all
paid calls disabled until those external gates pass.

## Implementation order

1. [ ] Thread the registered workload manifest into the new core types without
   changing the MCP payload. Pure `WorkloadRequirements`, `CapabilityEvidence`,
   `CostBreakdown`, and `SelectionResult` types now exist; registry wiring is
   still open.
2. [x] Add cost decomposition and evidence freshness while leaving the current
   `PricingVerificationResult`/`ApprovedExecutionPlan` authorization boundary
   unchanged.
3. [x] Add deterministic candidate selection and structured refusal reasons.
4. [partial] Surface selection and registered CPU alternatives in the
   Gateway read-only capability response; do not permit prepare/submit to
   infer approval from discovery. Operator manifests can now state OS,
   architecture, GPU count/VRAM, network, result transport/size, cancellation,
   and cleanup requirements. Missing fields remain unknown. Complete manifests
   are converted to `WorkloadRequirements` and passed to the pure selector.
   Since there is no provider inventory/evidence source yet, the selector is
   called with `inventory_complete=false` and fails closed with
   `PROVIDER_EVIDENCE_UNAVAILABLE`; the API labels this `not_evaluated` and
   does not imply that no free GPU exists. `gpu-control` is installed as a
   local dependency in Gateway tests/containers; the Vercel project has not
   been redeployed to verify its outside-root source inclusion setting.
5. Add Modal as the first candidate only after owner-read workspace billing,
   quota, and hard-stop evidence. Require a bounded actual GPU smoke to mark it
   usable. If it cannot meet the cost or result-collection requirements, keep
   it unavailable and research exactly one alternative provider.

The offline core slice is covered by `tests/test_capabilities.py` (16 cases) and
`tests/test_selection.py` (36 cases). The current root suite passed 517 tests
with 1 skipped on 2026-10-28. Gateway selector wiring now has regression coverage, but this
does not establish provider availability, account quota, real GPU execution,
spend protection, result collection, cleanup, or deployed Vercel packaging.
