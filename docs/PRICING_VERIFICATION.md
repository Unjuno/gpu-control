# Provider Pricing Verification

Provider pricing is part of the paid-compute authorization boundary. A numeric hourly price supplied by a caller is not sufficient evidence to approve a billable GPU resource.

## Why pricing is evidence

GPU prices and availability can change independently of source code and workload policy. The control plane therefore treats pricing as short-lived evidence tied to a concrete provider offering rather than as a static configuration value.

The current provider-agnostic model is `PricingVerificationResult` in `src/gpu_control/pricing.py`.

It records:

- provider name;
- control-plane GPU profile;
- concrete provider resource/offer identifier;
- verified hourly USD price;
- verification/audit reference;
- UTC verification time;
- UTC expiration time;
- whether price verification succeeded;
- whether the resource was available when verified.

## Freshness

Pricing evidence has an explicit validity window.

When an `ApprovedExecutionPlan` is created, the decision time must be:

```text
verified_at <= decision_time < valid_until
```

Evidence from the future relative to the approval decision is rejected. Evidence whose validity window has expired is rejected.

The future provider integration should keep the validity window short enough that the selected offer is still meaningful at submission time. The exact duration is provider-specific and must not be guessed by an agent when the provider API cannot establish it.

## Resource identity

An abstract profile such as `cheap-24gb` is not a billable provider resource.

Pricing evidence therefore also carries `provider_resource_id`, an opaque identifier for the concrete offering selected by the provider integration. The approved plan carries this identifier forward so submission cannot silently substitute a different offering whose price or resource properties were not verified.

## Cost calculation

The paid gate computes worst-case spend from:

```text
verified hourly price × requested runtime
```

and rounds the result upward to the nearest cent before comparing it with the caller's explicit cost ceiling.

This avoids approving a run because of favorable rounding.

## Trust boundary

`PricingVerificationResult` is structured evidence, not a cryptographic attestation.

The trusted provider-pricing stage is responsible for establishing that:

- the price came from an authoritative provider source;
- the resource identifier refers to the offering being priced;
- availability was actually checked when required;
- timestamps and validity windows are truthful;
- the verification reference can be audited.

An agent must not manufacture a synthetic pricing result for a real paid submission merely to satisfy the execution-plan function signature.

## Fail closed

Do not approve paid compute when:

- price is missing or non-positive;
- the price does not belong to the requested GPU profile;
- the provider resource identifier is missing;
- the verification reference is missing;
- price verification failed;
- availability verification failed;
- evidence is expired;
- the evidence time range is malformed;
- worst-case spend exceeds the requested or policy cost ceiling.

No provider API call is implemented by this document or the current pricing model.
