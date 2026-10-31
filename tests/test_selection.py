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
from gpu_control.selection import (
    SelectionBlocker,
    revalidate_approved_candidate,
    select_candidate,
)
from gpu_control.workloads import (
    AcceleratorKind,
    NetworkRequirement,
    ResultTransport,
    WorkloadRequirements,
)


SHA = "0123456789abcdef0123456789abcdef01234567"
NOW = "2026-10-28T00:30:00Z"


def requirements(**overrides):  # type: ignore[no-untyped-def]
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


def evidence(provider="modal", resource_id="resource-1", **overrides):  # type: ignore[no-untyped-def]
    values = {
        "provider": provider,
        "resource_id": resource_id,
        "availability": Availability.AVAILABLE,
        "cost_classification": CostClassification.PAID,
        "costs": CostBreakdown(
            accelerator_usd=Decimal("0.10"), cpu_usd=Decimal("0.01"),
            memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
        "hard_spend_cap_enforced": True,
        "overage_behavior": OverageBehavior.STOPS,
        "evidence_reference": "provider-check:fixture",
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
        "network_modes_supported": (NetworkRequirement.DISABLED,),
        "result_transports": (ResultTransport.SHARED_FILESYSTEM,),
        "cancellation_supported": True,
        "cleanup_proof_supported": True,
    }
    values.update(overrides)
    return CapabilityEvidence(**values)


def test_selects_only_compatible_candidate_without_changing_requirements() -> None:
    wanted = requirements()
    too_small = evidence("provider-a", "small-gpu", max_vram_mib=16384)
    compatible = evidence("provider-b", "large-gpu")

    result = select_candidate(wanted, [too_small, compatible], now_utc=NOW,
                              max_cost_usd=Decimal("1.00"))

    assert result.selected is compatible
    assert result.selected.resource_id == "large-gpu"
    assert wanted.minimum_vram_mib == 24576
    assert result.rejected[0].reasons == ("VRAM_INSUFFICIENT",)


def test_runtime_and_queue_wait_requirements_fail_closed_when_unknown_or_incompatible() -> None:
    wanted = requirements(runtime_requirements=("python:3.12", "cuda:12.4"),
                          max_queue_wait_seconds=60)
    unknown = evidence(supported_runtime_requirements=None,
                       estimated_queue_wait_seconds=None)

    unknown_result = select_candidate(wanted, [unknown], now_utc=NOW,
                                      max_cost_usd=Decimal("1.00"))
    assert unknown_result.selected is None
    assert unknown_result.rejected[0].reasons == (
        "RUNTIME_REQUIREMENTS_UNKNOWN", "QUEUE_WAIT_UNKNOWN")

    incompatible = evidence(
        supported_runtime_requirements=("python:3.12",),
        estimated_queue_wait_seconds=61,
    )
    incompatible_result = select_candidate(wanted, [incompatible], now_utc=NOW,
                                           max_cost_usd=Decimal("1.00"))
    assert incompatible_result.selected is None
    assert incompatible_result.rejected[0].reasons == (
        "RUNTIME_REQUIREMENT_UNSUPPORTED", "QUEUE_WAIT_EXCEEDED")

    compatible = evidence(
        supported_runtime_requirements=("python:3.12", "cuda:12.4", "torch:2.8"),
        estimated_queue_wait_seconds=60,
    )
    compatible_result = select_candidate(wanted, [compatible], now_utc=NOW,
                                         max_cost_usd=Decimal("1.00"))
    assert compatible_result.selected is compatible


def test_runtime_and_queue_wait_evidence_are_part_of_candidate_fingerprint() -> None:
    baseline = evidence()
    changed_runtime = evidence(supported_runtime_requirements=("python:3.12",))
    changed_wait = evidence(estimated_queue_wait_seconds=12)

    assert baseline.fingerprint() != changed_runtime.fingerprint()
    assert baseline.fingerprint() != changed_wait.fingerprint()


def test_selection_result_binds_workload_and_evidence_fingerprints() -> None:
    wanted = requirements()
    candidate = evidence()
    result = select_candidate(wanted, [candidate], now_utc=NOW,
                              max_cost_usd=Decimal("1.00"))

    payload = result.to_dict()

    assert payload["workload"] == wanted.workload_id
    assert payload["workload_fingerprint"] == wanted.fingerprint()
    assert payload["selected"]["evidence_fingerprint"] == candidate.fingerprint()


def test_revalidation_keeps_the_exact_approved_provider_resource_and_evidence() -> None:
    wanted = requirements()
    approved = evidence(provider="provider-a", resource_id="resource-a")
    other_provider = evidence(provider="provider-b", resource_id="resource-b")

    result = revalidate_approved_candidate(
        wanted, approved_workload_fingerprint=wanted.fingerprint(),
        approved_provider=approved.provider,
        approved_resource_id=approved.resource_id,
        approved_evidence_fingerprint=approved.fingerprint(),
        current_evidence=other_provider, now_utc=NOW,
        max_cost_usd=Decimal("1.00"),
    )

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.APPROVED_PLAN_STALE
    assert result.rejected[0].reasons == ("APPROVED_CANDIDATE_CHANGED",)


def test_revalidation_accepts_the_current_exact_approved_candidate() -> None:
    approved = evidence(provider="provider-a", resource_id="resource-a")

    result = revalidate_approved_candidate(
        requirements(), approved_workload_fingerprint=requirements().fingerprint(),
        approved_provider=approved.provider,
        approved_resource_id=approved.resource_id,
        approved_evidence_fingerprint=approved.fingerprint(),
        current_evidence=approved, now_utc=NOW,
        max_cost_usd=Decimal("1.00"),
    )

    assert result.selected is approved
    assert result.blocking_reason is None


def test_revalidation_refuses_missing_approved_resource_without_fallback() -> None:
    approved = evidence(provider="provider-a", resource_id="resource-a")

    result = revalidate_approved_candidate(
        requirements(), approved_workload_fingerprint=requirements().fingerprint(),
        approved_provider=approved.provider,
        approved_resource_id=approved.resource_id,
        approved_evidence_fingerprint=approved.fingerprint(),
        current_evidence=None, now_utc=NOW,
        max_cost_usd=Decimal("1.00"),
    )

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.APPROVED_PLAN_STALE
    assert result.rejected[0].reasons == ("APPROVED_RESOURCE_EVIDENCE_MISSING",)


def test_revalidation_rejects_workload_requirement_change_after_approval() -> None:
    approved_requirements = requirements()
    changed_requirements = requirements(max_runtime_seconds=1800)
    approved = evidence(provider="provider-a", resource_id="resource-a")

    result = revalidate_approved_candidate(
        changed_requirements,
        approved_workload_fingerprint=approved_requirements.fingerprint(),
        approved_provider=approved.provider,
        approved_resource_id=approved.resource_id,
        approved_evidence_fingerprint=approved.fingerprint(),
        current_evidence=approved, now_utc=NOW,
        max_cost_usd=Decimal("1.00"),
    )

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.APPROVED_PLAN_STALE
    assert result.rejected[0].reasons == ("APPROVED_WORKLOAD_CHANGED",)


def test_revalidation_rejects_expired_quota_and_requires_new_approval() -> None:
    approved = evidence(
        cost_classification=CostClassification.CREDIT_BACKED,
        costs=CostBreakdown(
            accelerator_usd=Decimal("0.10"), cpu_usd=Decimal("0.01"),
            memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
        quota_evidence=QuotaEvidence(
            remaining_usage_usd=Decimal("0.12"), remaining_credits_usd=Decimal("0.12"),
            covered_components=("accelerator_usd", "cpu_usd", "memory_usd"),
            evidence_reference="workspace-billing-snapshot:abc123",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc="2026-10-28T00:30:00Z",
        ),
        hard_spend_cap_enforced=True,
        overage_behavior=OverageBehavior.STOPS,
    )

    result = revalidate_approved_candidate(
        requirements(), approved_workload_fingerprint=requirements().fingerprint(),
        approved_provider=approved.provider,
        approved_resource_id=approved.resource_id,
        approved_evidence_fingerprint=approved.fingerprint(),
        current_evidence=approved, now_utc="2026-10-28T00:30:00Z",
        max_cost_usd=Decimal("0"),
    )

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.APPROVED_PLAN_STALE
    assert "QUOTA_UNKNOWN" in result.rejected[0].reasons


def test_zero_cost_selection_rejects_credit_backed_candidate() -> None:
    credit = evidence(cost_classification=CostClassification.CREDIT_BACKED,
                      costs=CostBreakdown(
                          accelerator_usd=Decimal("0.40"), cpu_usd=Decimal("0.01"),
                          memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
                          egress_usd=Decimal("0"), other_usd=Decimal("0"),
                      ))

    result = select_candidate(requirements(), [credit], now_utc=NOW,
                              max_cost_usd=Decimal("0"))

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.QUOTA_UNKNOWN
    assert "QUOTA_UNKNOWN" in result.rejected[0].reasons


def test_zero_cost_selection_accepts_credit_covered_gross_cost_with_hard_net_cap() -> None:
    credit = evidence(
        cost_classification=CostClassification.CREDIT_BACKED,
        costs=CostBreakdown(
            accelerator_usd=Decimal("0.10"), cpu_usd=Decimal("0.01"),
            memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
        quota_evidence=QuotaEvidence(
            remaining_usage_usd=Decimal("0.12"), remaining_credits_usd=Decimal("0.12"),
            covered_components=("accelerator_usd", "cpu_usd", "memory_usd"),
            evidence_reference="workspace-billing-snapshot:abc123",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc="2026-10-28T01:00:00Z",
        ),
        hard_spend_cap_enforced=True,
        overage_behavior=OverageBehavior.STOPS,
    )

    result = select_candidate(requirements(), [credit], now_utc=NOW,
                              max_cost_usd=Decimal("0"))

    assert result.selected is credit
    assert result.blocking_reason is None


@pytest.mark.parametrize("hard_cap,overage", [
    (None, OverageBehavior.STOPS),
    (False, OverageBehavior.STOPS),
    (True, OverageBehavior.UNKNOWN),
    (True, OverageBehavior.CHARGED),
])
def test_credit_covered_zero_cost_requires_enforced_stop_on_overage(hard_cap, overage) -> None:
    candidate = evidence(
        cost_classification=CostClassification.CREDIT_BACKED,
        quota_evidence=QuotaEvidence(
            remaining_usage_usd=Decimal("0.12"), remaining_credits_usd=Decimal("0.12"),
            covered_components=("accelerator_usd", "cpu_usd", "memory_usd"),
            evidence_reference="workspace-billing-snapshot:abc123",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc="2026-10-28T01:00:00Z",
        ),
        hard_spend_cap_enforced=hard_cap,
        overage_behavior=overage,
    )

    result = select_candidate(requirements(), [candidate], now_utc=NOW,
                              max_cost_usd=Decimal("0"))

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.QUOTA_UNKNOWN
    assert "QUOTA_UNKNOWN" in result.rejected[0].reasons


@pytest.mark.parametrize("credits,usage,expires", [
    ("0.11", "0.12", "2026-10-28T01:00:00Z"),
    ("0.12", "0.11", "2026-10-28T01:00:00Z"),
    ("0.12", "0.12", "2026-10-28T00:30:00Z"),
])
def test_zero_cost_selection_rejects_insufficient_or_expired_quota(credits, usage, expires) -> None:
    credit = evidence(
        cost_classification=CostClassification.CREDIT_BACKED,
        costs=CostBreakdown(
            accelerator_usd=Decimal("0.10"), cpu_usd=Decimal("0.01"),
            memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
        quota_evidence=QuotaEvidence(
            remaining_usage_usd=Decimal(usage), remaining_credits_usd=Decimal(credits),
            covered_components=("accelerator_usd", "cpu_usd", "memory_usd"),
            evidence_reference="workspace-billing-snapshot:abc123",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc=expires,
        ),
        hard_spend_cap_enforced=True,
        overage_behavior=OverageBehavior.STOPS,
    )

    result = select_candidate(requirements(), [credit], now_utc=NOW,
                              max_cost_usd=Decimal("0"))

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.QUOTA_UNKNOWN
    assert "QUOTA_UNKNOWN" in result.rejected[0].reasons


def test_credit_backed_selection_does_not_assume_egress_is_credit_eligible() -> None:
    candidate = evidence(
        cost_classification=CostClassification.CREDIT_BACKED,
        costs=CostBreakdown(
            accelerator_usd=Decimal("0.10"), cpu_usd=Decimal("0.01"),
            memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0.02"), other_usd=Decimal("0"),
        ),
        quota_evidence=QuotaEvidence(
            remaining_usage_usd=Decimal("0.14"), remaining_credits_usd=Decimal("0.12"),
            covered_components=("accelerator_usd", "cpu_usd", "memory_usd"),
            evidence_reference="workspace-billing-snapshot:abc123",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc="2026-10-28T01:00:00Z",
        ),
        hard_spend_cap_enforced=True,
        overage_behavior=OverageBehavior.STOPS,
    )

    result = select_candidate(requirements(), [candidate], now_utc=NOW,
                              max_cost_usd=Decimal("0"))

    assert result.selected is None
    assert result.rejected[0].reasons == ("ZERO_COST_NOT_PROVEN",)


def test_unknown_quota_is_reported_before_free_gpu_unavailable() -> None:
    unknown = evidence(
        cost_classification=CostClassification.UNKNOWN,
        costs=CostBreakdown(),
        hard_spend_cap_enforced=None,
        overage_behavior=OverageBehavior.UNKNOWN,
    )

    result = select_candidate(requirements(), [unknown], now_utc=NOW,
                              max_cost_usd=Decimal("0"))

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.QUOTA_UNKNOWN
    assert "QUOTA_UNKNOWN" in result.rejected[0].reasons


def test_incomplete_provider_inventory_never_selects_a_known_partial_candidate() -> None:
    known = evidence()
    result = select_candidate(
        requirements(), [known], now_utc=NOW, max_cost_usd=Decimal("0"),
        free_first=True, inventory_complete=False,
    )
    assert result.selected is None
    assert result.blocking_reason.value == "PROVIDER_EVIDENCE_UNAVAILABLE"


def test_complete_inventory_without_free_gpu_reports_free_gpu_unavailable() -> None:
    result = select_candidate(
        requirements(), [], now_utc=NOW, max_cost_usd=Decimal("0"),
        free_first=True, inventory_complete=True,
    )

    assert result.selected is None
    assert result.blocking_reason.value == "FREE_GPU_UNAVAILABLE"


def test_zero_cost_first_orders_proven_free_before_paid_candidates() -> None:
    free = evidence(
        provider="provider-free", resource_id="free-gpu",
        cost_classification=CostClassification.FREE_QUOTA,
        costs=CostBreakdown(
            accelerator_usd=Decimal("0"), cpu_usd=Decimal("0"),
            memory_usd=Decimal("0"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
        quota_evidence=QuotaEvidence(
            remaining_usage_usd=Decimal("0"), remaining_credits_usd=Decimal("0"),
            covered_components=("accelerator_usd", "cpu_usd", "memory_usd",
                                "storage_usd", "egress_usd", "other_usd"),
            evidence_reference="provider-quota:fixture",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc="2026-10-28T01:00:00Z",
        ),
    )
    paid = evidence(provider="provider-paid", resource_id="paid-gpu")

    result = select_candidate(requirements(), [paid, free], now_utc=NOW,
                              max_cost_usd=Decimal("1.00"), free_first=True)

    assert result.selected is free
    assert result.rejected == ()


def test_free_first_does_not_prioritize_a_quota_candidate_with_positive_cost() -> None:
    quota_candidate = evidence(
        provider="provider-quota", resource_id="quota-gpu",
        cost_classification=CostClassification.FREE_QUOTA,
        costs=CostBreakdown(
            accelerator_usd=Decimal("0.40"), cpu_usd=Decimal("0.01"),
            memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
        quota_evidence=QuotaEvidence(
            remaining_usage_usd=Decimal("0.42"), remaining_credits_usd=Decimal("0.42"),
            covered_components=("accelerator_usd", "cpu_usd", "memory_usd",
                                "storage_usd", "egress_usd", "other_usd"),
            evidence_reference="provider-quota:fixture",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc="2026-10-28T01:00:00Z",
        ),
    )
    lower_cost_paid = evidence(
        provider="provider-paid", resource_id="paid-gpu",
        costs=CostBreakdown(
            accelerator_usd=Decimal("0.05"), cpu_usd=Decimal("0.01"),
            memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
    )

    result = select_candidate(requirements(), [quota_candidate, lower_cost_paid],
                              now_utc=NOW, max_cost_usd=Decimal("1.00"), free_first=True)

    assert result.selected is lower_cost_paid


def test_zero_cost_request_rejects_positive_cost_even_when_quota_covers_it() -> None:
    costs = CostBreakdown(
        accelerator_usd=Decimal("0.40"), cpu_usd=Decimal("0.01"),
        memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
        egress_usd=Decimal("0"), other_usd=Decimal("0"),
    )
    candidate = evidence(
        provider="provider-quota", resource_id="quota-gpu",
        cost_classification=CostClassification.FREE_QUOTA, costs=costs,
        quota_evidence=QuotaEvidence(
            remaining_usage_usd=Decimal("0.42"),
            remaining_credits_usd=Decimal("0"),
            covered_components=("accelerator_usd", "cpu_usd", "memory_usd",
                                "storage_usd", "egress_usd", "other_usd"),
            evidence_reference="provider-quota:fixture",
            observed_at_utc="2026-10-28T00:00:00Z",
            valid_until_utc="2026-10-28T01:00:00Z",
        ),
    )

    result = select_candidate(requirements(), [candidate], now_utc=NOW,
                              max_cost_usd=Decimal("0"), free_first=True)

    assert result.selected is None
    assert result.blocking_reason is SelectionBlocker.FREE_GPU_UNAVAILABLE
    assert "ZERO_COST_NOT_PROVEN" in result.rejected[0].reasons


def test_rejects_expired_evidence_and_cost_above_ceiling() -> None:
    expired = evidence(provider="provider-expired", resource_id="expired",
                       valid_until_utc="2026-10-28T00:30:00Z")
    over_budget = evidence(provider="provider-costly", resource_id="costly")

    result = select_candidate(requirements(), [expired, over_budget], now_utc=NOW,
                              max_cost_usd=Decimal("0.05"))

    assert result.selected is None
    assert result.rejected[0].reasons == ("EVIDENCE_EXPIRED", "COST_LIMIT_EXCEEDED")
    assert result.rejected[1].reasons == ("COST_LIMIT_EXCEEDED",)
    assert result.blocking_reason is SelectionBlocker.NO_COMPATIBLE_PROVIDER


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"supported_operating_systems": ("macos",)}, "OPERATING_SYSTEM_UNSUPPORTED"),
        ({"supported_architectures": ("aarch64",)}, "ARCHITECTURE_UNSUPPORTED"),
        ({"supported_operating_systems": None}, "OPERATING_SYSTEM_UNKNOWN"),
        ({"supported_architectures": None}, "ARCHITECTURE_UNKNOWN"),
        ({"gpu_profiles": None}, "GPU_PROFILE_UNKNOWN"),
        ({"gpu_profiles": ()}, "GPU_PROFILE_UNAVAILABLE"),
        ({"accelerator_kind": None}, "ACCELERATOR_CAPABILITY_UNKNOWN"),
        ({"max_gpu_count": None}, "GPU_COUNT_UNKNOWN"),
        ({"max_vram_mib": None}, "VRAM_UNKNOWN"),
        ({"network_modes_supported": None}, "NETWORK_POLICY_UNKNOWN"),
        ({"network_modes_supported": ()}, "NETWORK_POLICY_UNSUPPORTED"),
        ({"result_transports": None}, "RESULT_TRANSPORT_UNKNOWN"),
        ({"result_transports": ()}, "RESULT_TRANSPORT_UNSUPPORTED"),
        ({"max_result_bytes": None}, "RESULT_SIZE_UNKNOWN"),
        ({"max_result_bytes": 1024}, "RESULT_SIZE_INSUFFICIENT"),
        ({"max_cpu_cores": None}, "CPU_CAPACITY_UNKNOWN"),
        ({"max_cpu_cores": Decimal("0.5")}, "CPU_CAPACITY_INSUFFICIENT"),
        ({"max_memory_mib": None}, "MEMORY_CAPACITY_UNKNOWN"),
        ({"max_memory_mib": 2048}, "MEMORY_CAPACITY_INSUFFICIENT"),
        ({"max_runtime_seconds": None}, "TIMEOUT_UNKNOWN"),
        ({"max_runtime_seconds": 300}, "TIMEOUT_INSUFFICIENT"),
        ({"cancellation_supported": None}, "CANCELLATION_UNKNOWN"),
        ({"cancellation_supported": False}, "CANCELLATION_UNSUPPORTED"),
        ({"cleanup_proof_supported": None}, "CLEANUP_PROOF_UNKNOWN"),
        ({"cleanup_proof_supported": False}, "CLEANUP_PROOF_UNSUPPORTED"),
        ({"costs": CostBreakdown()}, "COST_UNKNOWN"),
        ({"cost_classification": CostClassification.MANUAL_ONLY}, "MANUAL_ACTION_REQUIRED"),
    ],
)
def test_rejects_candidates_missing_required_capabilities(override, reason) -> None:  # type: ignore[no-untyped-def]
    candidate = evidence(**override)

    result = select_candidate(requirements(), [candidate], now_utc=NOW,
                              max_cost_usd=Decimal("1.00"))

    assert result.selected is None
    assert reason in result.rejected[0].reasons


def test_rejects_a_candidate_with_too_few_gpus() -> None:
    wanted = requirements(gpu_count=2)

    result = select_candidate(wanted, [evidence()], now_utc=NOW,
                              max_cost_usd=Decimal("1.00"))

    assert result.selected is None
    assert result.rejected[0].reasons == ("GPU_COUNT_INSUFFICIENT",)
