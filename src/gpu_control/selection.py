from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .capabilities import (
    Availability,
    CapabilityEvidence,
    CostClassification,
    OverageBehavior,
)
from .pricing import PricingVerificationError, parse_utc_timestamp
from .workloads import AcceleratorKind, NetworkRequirement, WorkloadRequirements


class SelectionBlocker(str, Enum):
    QUOTA_UNKNOWN = "QUOTA_UNKNOWN"
    FREE_GPU_UNAVAILABLE = "FREE_GPU_UNAVAILABLE"
    NO_COMPATIBLE_PROVIDER = "NO_COMPATIBLE_PROVIDER"
    PROVIDER_EVIDENCE_UNAVAILABLE = "PROVIDER_EVIDENCE_UNAVAILABLE"


@dataclass(frozen=True)
class RejectedCandidate:
    provider: str
    resource_id: str | None
    evidence_fingerprint: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "resource_id": self.resource_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class SelectionResult:
    workload_id: str
    workload_fingerprint: str
    selected: CapabilityEvidence | None
    rejected: tuple[RejectedCandidate, ...]
    blocking_reason: SelectionBlocker | None

    def to_dict(self) -> dict[str, object]:
        return {
            "workload": self.workload_id,
            "workload_fingerprint": self.workload_fingerprint,
            "selected": None if self.selected is None else {
                "provider": self.selected.provider,
                "resource_id": self.selected.resource_id,
                "evidence_fingerprint": self.selected.fingerprint(),
            },
            "rejected": [candidate.to_dict() for candidate in self.rejected],
            "blocking_reason": None if self.blocking_reason is None else self.blocking_reason.value,
        }


def _candidate_reasons(requirements: WorkloadRequirements, candidate: CapabilityEvidence,
                       *, now: datetime, max_cost_usd: Decimal) -> tuple[str, ...]:
    reasons: list[str] = []
    if candidate.availability is Availability.UNAVAILABLE:
        reasons.append("PROVIDER_UNAVAILABLE")
    elif candidate.availability is Availability.UNKNOWN:
        reasons.append("PROVIDER_AVAILABILITY_UNKNOWN")

    observed = parse_utc_timestamp(candidate.observed_at_utc, "observed_at_utc")
    valid_until = parse_utc_timestamp(candidate.valid_until_utc, "valid_until_utc")
    if now < observed:
        reasons.append("EVIDENCE_NOT_YET_CURRENT")
    elif now >= valid_until:
        reasons.append("EVIDENCE_EXPIRED")

    if candidate.supported_operating_systems is None:
        reasons.append("OPERATING_SYSTEM_UNKNOWN")
    elif requirements.operating_system.casefold() not in {
            item.casefold() for item in candidate.supported_operating_systems}:
        reasons.append("OPERATING_SYSTEM_UNSUPPORTED")
    if candidate.supported_architectures is None:
        reasons.append("ARCHITECTURE_UNKNOWN")
    elif requirements.architecture.casefold() not in {
            item.casefold() for item in candidate.supported_architectures}:
        reasons.append("ARCHITECTURE_UNSUPPORTED")
    if candidate.accelerator_kind is None:
        reasons.append("ACCELERATOR_CAPABILITY_UNKNOWN")
    elif candidate.accelerator_kind is not requirements.accelerator_kind:
        reasons.append("ACCELERATOR_UNSUPPORTED")
    elif requirements.accelerator_kind is AcceleratorKind.GPU:
        if candidate.gpu_profiles is None:
            reasons.append("GPU_PROFILE_UNKNOWN")
        elif requirements.gpu_profile not in candidate.gpu_profiles:
            reasons.append("GPU_PROFILE_UNAVAILABLE")
        if candidate.max_gpu_count is None:
            reasons.append("GPU_COUNT_UNKNOWN")
        elif candidate.max_gpu_count < requirements.gpu_count:
            reasons.append("GPU_COUNT_INSUFFICIENT")
        if candidate.max_vram_mib is None:
            reasons.append("VRAM_UNKNOWN")
        elif candidate.max_vram_mib < requirements.minimum_vram_mib:
            reasons.append("VRAM_INSUFFICIENT")

    if candidate.max_cpu_cores is None:
        reasons.append("CPU_CAPACITY_UNKNOWN")
    elif candidate.max_cpu_cores < requirements.minimum_cpu_cores:
        reasons.append("CPU_CAPACITY_INSUFFICIENT")
    if candidate.max_memory_mib is None:
        reasons.append("MEMORY_CAPACITY_UNKNOWN")
    elif candidate.max_memory_mib < requirements.minimum_memory_mib:
        reasons.append("MEMORY_CAPACITY_INSUFFICIENT")
    if candidate.max_runtime_seconds is None:
        reasons.append("TIMEOUT_UNKNOWN")
    elif candidate.max_runtime_seconds < requirements.max_runtime_seconds:
        reasons.append("TIMEOUT_INSUFFICIENT")
    if candidate.max_result_bytes is None:
        reasons.append("RESULT_SIZE_UNKNOWN")
    elif candidate.max_result_bytes < requirements.max_result_bytes:
        reasons.append("RESULT_SIZE_INSUFFICIENT")

    modes = candidate.network_modes_supported
    if modes is None:
        reasons.append("NETWORK_POLICY_UNKNOWN")
    elif requirements.network_requirement not in modes:
        reasons.append("NETWORK_POLICY_UNSUPPORTED")
    if candidate.result_transports is None:
        reasons.append("RESULT_TRANSPORT_UNKNOWN")
    elif requirements.result_transport not in candidate.result_transports:
        reasons.append("RESULT_TRANSPORT_UNSUPPORTED")
    if requirements.cancellation_required:
        if candidate.cancellation_supported is None:
            reasons.append("CANCELLATION_UNKNOWN")
        elif not candidate.cancellation_supported:
            reasons.append("CANCELLATION_UNSUPPORTED")
    if requirements.cleanup_proof_required:
        if candidate.cleanup_proof_supported is None:
            reasons.append("CLEANUP_PROOF_UNKNOWN")
        elif not candidate.cleanup_proof_supported:
            reasons.append("CLEANUP_PROOF_UNSUPPORTED")

    if candidate.cost_classification is CostClassification.UNKNOWN:
        reasons.append("QUOTA_UNKNOWN")
    elif candidate.cost_classification is CostClassification.MANUAL_ONLY:
        reasons.append("MANUAL_ACTION_REQUIRED")
    elif candidate.cost_classification is CostClassification.UNSUPPORTED:
        reasons.append("COST_CLASS_UNSUPPORTED")

    total = candidate.costs.known_total_usd
    if total is None:
        reasons.append("COST_UNKNOWN")
    elif total > max_cost_usd:
        reasons.append("COST_LIMIT_EXCEEDED")
    elif max_cost_usd == 0 and not candidate.zero_additional_cost_proven:
        if (candidate.cost_classification is CostClassification.FREE_QUOTA and
                (candidate.hard_spend_cap_enforced is not True or
                 candidate.overage_behavior not in {OverageBehavior.STOPS,
                                                    OverageBehavior.NOT_APPLICABLE})):
            reasons.append("QUOTA_UNKNOWN")
        else:
            reasons.append("ZERO_COST_NOT_PROVEN")

    return tuple(dict.fromkeys(reasons))


def select_candidate(requirements: WorkloadRequirements,
                     candidates: list[CapabilityEvidence] | tuple[CapabilityEvidence, ...], *,
                     now_utc: str, max_cost_usd: Decimal,
                     free_first: bool = False,
                     inventory_complete: bool = True) -> SelectionResult:
    """Select a currently evidenced compatible resource without submitting it."""
    if not isinstance(requirements, WorkloadRequirements):
        raise TypeError("requirements must be WorkloadRequirements")
    if not isinstance(candidates, (list, tuple)) or any(
            not isinstance(item, CapabilityEvidence) for item in candidates):
        raise TypeError("candidates must contain CapabilityEvidence values")
    if (not isinstance(max_cost_usd, Decimal) or not max_cost_usd.is_finite() or
            max_cost_usd < 0):
        raise ValueError("max_cost_usd must be a finite nonnegative Decimal")
    if type(free_first) is not bool:
        raise ValueError("free_first must be a boolean")
    if type(inventory_complete) is not bool:
        raise ValueError("inventory_complete must be a boolean")
    try:
        now = parse_utc_timestamp(now_utc, "now_utc")
    except PricingVerificationError as exc:
        raise ValueError(str(exc)) from exc

    accepted: list[CapabilityEvidence] = []
    rejected: list[RejectedCandidate] = []
    for candidate in candidates:
        reasons = _candidate_reasons(requirements, candidate, now=now,
                                     max_cost_usd=max_cost_usd)
        if reasons:
            rejected.append(RejectedCandidate(
                provider=candidate.provider,
                resource_id=candidate.resource_id,
                evidence_fingerprint=candidate.fingerprint(),
                reasons=reasons,
            ))
        else:
            accepted.append(candidate)

    if not inventory_complete:
        return SelectionResult(
            requirements.workload_id, requirements.fingerprint(), None,
            tuple(rejected), SelectionBlocker.PROVIDER_EVIDENCE_UNAVAILABLE,
        )

    if free_first:
        accepted.sort(key=lambda item: (
            0 if item.zero_additional_cost_proven else 1,
            item.costs.known_total_usd,
            item.provider,
            item.resource_id or "",
            item.fingerprint(),
        ))
    else:
        accepted.sort(key=lambda item: (
            item.costs.known_total_usd,
            item.provider,
            item.resource_id or "",
            item.fingerprint(),
        ))

    selected = accepted[0] if accepted else None
    blocker = None
    if selected is None:
        if any("QUOTA_UNKNOWN" in item.reasons for item in rejected):
            blocker = SelectionBlocker.QUOTA_UNKNOWN
        elif (max_cost_usd == 0 and
              requirements.accelerator_kind is AcceleratorKind.GPU):
            blocker = SelectionBlocker.FREE_GPU_UNAVAILABLE
        else:
            blocker = SelectionBlocker.NO_COMPATIBLE_PROVIDER
    return SelectionResult(requirements.workload_id, requirements.fingerprint(),
                           selected, tuple(rejected), blocker)
