from dataclasses import replace
from decimal import Decimal

import pytest

from gpu_control.capabilities import (
    Availability,
    CapabilityEvidence,
    CostBreakdown,
    CostClassification,
    QuotaEvidence,
    OverageBehavior,
)
from gpu_control.workloads import AcceleratorKind, NetworkRequirement, ResultTransport, WorkloadRequirements


SHA = "0123456789abcdef0123456789abcdef01234567"


def make_requirements(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "workload_id": "tiny-lm-t4",
        "source_repository": "example/tiny-lm",
        "source_sha": SHA,
        "operating_system": "linux",
        "architecture": "x86_64",
        "accelerator_kind": AcceleratorKind.GPU,
        "gpu_profile": "cheap-24gb",
        "gpu_count": 1,
        "minimum_vram_mib": 24576,
        "minimum_cpu_cores": Decimal("1"),
        "minimum_memory_mib": 4096,
        "max_runtime_seconds": 600,
        "network_requirement": NetworkRequirement.DISABLED,
        "result_transport": ResultTransport.SHARED_FILESYSTEM,
        "max_result_bytes": 1024 * 1024,
        "cancellation_required": True,
        "cleanup_proof_required": True,
    }
    values.update(overrides)
    return WorkloadRequirements(**values)


def make_evidence(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "provider": "modal",
        "resource_id": "modal-gpu-t4",
        "availability": Availability.AVAILABLE,
        "cost_classification": CostClassification.CREDIT_BACKED,
        "costs": CostBreakdown(
            accelerator_usd=Decimal("0.10"),
            cpu_usd=Decimal("0.01"),
            memory_usd=Decimal("0.01"),
            storage_usd=Decimal("0"),
            egress_usd=Decimal("0"),
            other_usd=Decimal("0"),
        ),
        "hard_spend_cap_enforced": False,
        "overage_behavior": OverageBehavior.CHARGED,
        "evidence_reference": "modal-account-check:synthetic",
        "evidence_source": "synthetic-fixture",
        "observed_at_utc": "2026-10-28T00:00:00Z",
        "valid_until_utc": "2026-10-28T01:00:00Z",
        "supported_operating_systems": ("linux",),
        "supported_architectures": ("x86_64",),
        "accelerator_kind": AcceleratorKind.GPU,
        "gpu_profiles": ("cheap-24gb",),
        "max_gpu_count": 1,
        "max_vram_mib": 24576,
        "max_cpu_cores": Decimal("2"),
        "max_memory_mib": 8192,
        "max_runtime_seconds": 3600,
        "max_result_bytes": 2 * 1024 * 1024,
        "network_modes_supported": (NetworkRequirement.DISABLED, NetworkRequirement.RESTRICTED),
        "result_transports": (ResultTransport.SHARED_FILESYSTEM,),
        "cancellation_supported": True,
        "cleanup_proof_supported": True,
    }
    values.update(overrides)
    return CapabilityEvidence(**values)


def test_capability_evidence_strict_json_round_trip():
    evidence = make_evidence(quota_evidence=QuotaEvidence(
        remaining_usage_usd=Decimal("2.00"),
        remaining_credits_usd=Decimal("1.00"),
        covered_components=("accelerator_usd", "cpu_usd", "memory_usd",
                            "storage_usd", "egress_usd", "other_usd"),
        evidence_reference="quota:fixture",
        observed_at_utc="2026-10-28T00:00:00Z",
        valid_until_utc="2026-10-28T00:30:00Z",
    ))
    restored = CapabilityEvidence.from_dict(evidence.to_dict())
    assert restored == evidence

    malformed = evidence.to_dict() | {"unrecognized": True}
    with pytest.raises(ValueError, match="fields are invalid"):
        CapabilityEvidence.from_dict(malformed)


def test_availability_and_cost_classification_are_independent() -> None:
    evidence = make_evidence(
        availability=Availability.AVAILABLE,
        cost_classification=CostClassification.UNKNOWN,
        hard_spend_cap_enforced=None,
        overage_behavior=OverageBehavior.UNKNOWN,
    )

    assert evidence.availability is Availability.AVAILABLE
    assert evidence.cost_classification is CostClassification.UNKNOWN
    assert evidence.is_current("2026-10-28T00:30:00Z") is True
    assert evidence.zero_additional_cost_proven is False


def test_cost_breakdown_is_unknown_if_any_component_is_unknown() -> None:
    costs = CostBreakdown(
        accelerator_usd=Decimal("0"), cpu_usd=Decimal("0"),
        memory_usd=Decimal("0"), storage_usd=Decimal("0"),
        egress_usd=None, other_usd=Decimal("0"),
    )

    assert costs.known_total_usd is None
    assert costs.all_components_known is False
    assert costs.all_known_zero is False


def test_cost_breakdown_sums_exact_decimal_components() -> None:
    costs = CostBreakdown(
        accelerator_usd=Decimal("0.10"), cpu_usd=Decimal("0.01"),
        memory_usd=Decimal("0.02"), storage_usd=Decimal("0"),
        egress_usd=Decimal("0"), other_usd=Decimal("0.03"),
    )

    assert costs.known_total_usd == Decimal("0.16")
    assert costs.all_components_known is True
    assert costs.all_known_zero is False


def test_quota_evidence_is_explicit_fresh_and_component_scoped() -> None:
    quota = QuotaEvidence(
        remaining_usage_usd=Decimal("10"), remaining_credits_usd=Decimal("1.25"),
        covered_components=("accelerator_usd", "cpu_usd", "memory_usd"),
        evidence_reference="workspace-billing-snapshot:abc123",
        observed_at_utc="2026-10-28T00:00:00Z",
        valid_until_utc="2026-10-28T01:00:00Z",
    )
    assert quota.is_current("2026-10-28T00:30:00Z") is True
    assert quota.is_current("2026-10-28T01:00:00Z") is False
    assert quota.to_dict()["remaining_credits_usd"] == "1.25"


def test_capability_fingerprint_binds_quota_balance_and_expiry() -> None:
    base_quota = QuotaEvidence(
        remaining_usage_usd=Decimal("10"), remaining_credits_usd=Decimal("1.25"),
        covered_components=("accelerator_usd", "cpu_usd", "memory_usd"),
        evidence_reference="workspace-billing-snapshot:abc123",
        observed_at_utc="2026-10-28T00:00:00Z",
        valid_until_utc="2026-10-28T01:00:00Z",
    )
    less_credit = replace(base_quota, remaining_credits_usd=Decimal("1.24"))
    candidate = make_evidence(quota_evidence=base_quota)

    assert replace(candidate, quota_evidence=less_credit).fingerprint() != candidate.fingerprint()


@pytest.mark.parametrize("components", [(), ("storage_usd", "storage_usd"), ("not_a_cost",)])
def test_quota_evidence_rejects_invalid_component_coverage(components) -> None:
    with pytest.raises(ValueError):
        QuotaEvidence(
            remaining_usage_usd=Decimal("1"), remaining_credits_usd=Decimal("1"),
            covered_components=components,
            evidence_reference="workspace-billing-snapshot:abc123",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc="2026-10-28T01:00:00Z",
        )


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("NaN"), 0.1])
def test_cost_breakdown_rejects_negative_nonfinite_or_float_values(value) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="cost component"):
        CostBreakdown(accelerator_usd=value)


def test_gpu_requirements_bind_immutable_source_and_resources() -> None:
    requirements = make_requirements()
    payload = requirements.to_dict()

    assert payload["source_sha"] == SHA
    assert payload["gpu_count"] == 1
    assert payload["minimum_vram_mib"] == 24576
    assert requirements.fingerprint().startswith("sha256:")
    assert requirements.fingerprint() == requirements.fingerprint()
    assert replace(requirements, minimum_cpu_cores=Decimal("1.0")).fingerprint() == requirements.fingerprint()
    assert replace(requirements, max_runtime_seconds=601).fingerprint() != requirements.fingerprint()


def test_source_sha_must_be_canonical_lowercase() -> None:
    with pytest.raises(ValueError, match="lowercase canonical"):
        make_requirements(source_sha=SHA.upper())


@pytest.mark.parametrize("field", ["source_repository", "source_sha"])
def test_source_identity_requires_text(field: str) -> None:
    with pytest.raises(ValueError, match="source"):
        make_requirements(**{field: None})


def test_cpu_requirements_cannot_accidentally_require_a_gpu() -> None:
    cpu = make_requirements(
        workload_id="cpu-smoke-v1",
        accelerator_kind=AcceleratorKind.CPU,
        gpu_profile=None,
        gpu_count=0,
        minimum_vram_mib=0,
    )

    assert cpu.accelerator_kind is AcceleratorKind.CPU
    assert cpu.gpu_count == 0
    with pytest.raises(ValueError, match="CPU requirements must not require GPU"):
        make_requirements(accelerator_kind=AcceleratorKind.CPU)


def test_available_capability_requires_a_concrete_resource_id() -> None:
    with pytest.raises(ValueError, match="available capability requires resource_id"):
        make_evidence(resource_id=None)


def test_provider_gpu_capacity_can_be_explicitly_unknown() -> None:
    evidence = make_evidence(max_gpu_count=None, max_vram_mib=None)

    assert evidence.max_gpu_count is None
    assert evidence.max_vram_mib is None


def test_capability_expiry_is_exclusive_and_serialization_is_stable() -> None:
    evidence = make_evidence()

    assert evidence.is_current("2026-10-28T00:59:59Z") is True
    assert evidence.is_current("2026-10-28T01:00:00Z") is False
    assert evidence.fingerprint() == evidence.fingerprint()
    assert evidence.to_dict()["cost_classification"] == "CREDIT_BACKED"


def test_zero_cost_requires_known_zero_components_and_enforced_stop() -> None:
    free = make_evidence(
        cost_classification=CostClassification.FREE_QUOTA,
        costs=CostBreakdown(
            accelerator_usd=Decimal("0"), cpu_usd=Decimal("0"),
            memory_usd=Decimal("0"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
        hard_spend_cap_enforced=True,
        overage_behavior=OverageBehavior.STOPS,
    )

    assert free.zero_additional_cost_proven is True
    assert replace(free, overage_behavior=OverageBehavior.CHARGED).zero_additional_cost_proven is False


def test_capability_network_support_is_explicit_and_serialized() -> None:
    evidence = make_evidence()

    assert evidence.network_modes_supported == (
        NetworkRequirement.DISABLED, NetworkRequirement.RESTRICTED,
    )
    assert evidence.to_dict()["network_modes_supported"] == ["disabled", "restricted"]
