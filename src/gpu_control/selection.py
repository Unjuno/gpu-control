from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
import re

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
    APPROVED_PLAN_STALE = "APPROVED_PLAN_STALE"


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
    if requirements.runtime_requirements:
        supported_runtimes = candidate.supported_runtime_requirements
        if supported_runtimes is None:
            reasons.append("RUNTIME_REQUIREMENTS_UNKNOWN")
        elif not set(requirements.runtime_requirements).issubset(supported_runtimes):
            reasons.append("RUNTIME_REQUIREMENT_UNSUPPORTED")
    if requirements.max_queue_wait_seconds is not None:
        if candidate.estimated_queue_wait_seconds is None:
            reasons.append("QUEUE_WAIT_UNKNOWN")
        elif candidate.estimated_queue_wait_seconds > requirements.max_queue_wait_seconds:
            reasons.append("QUEUE_WAIT_EXCEEDED")
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

    if candidate.cost_classification in {
            CostClassification.FREE_QUOTA, CostClassification.CREDIT_BACKED}:
        quota = candidate.quota_evidence
        if quota is None or not quota.is_current(now.isoformat().replace("+00:00", "Z")):
            reasons.append("QUOTA_UNKNOWN")

    total = candidate.costs.known_total_usd
    if max_cost_usd == 0:
        if not candidate.zero_additional_cost_proven_at(now.isoformat().replace("+00:00", "Z")):
            if candidate.cost_classification is CostClassification.CREDIT_BACKED:
                quota = candidate.quota_evidence
                covered = None if quota is None else quota.covered_cost_usd(candidate.costs)
                if (quota is None or not quota.is_current(now.isoformat().replace("+00:00", "Z")) or
                        candidate.hard_spend_cap_enforced is not True or
                        candidate.overage_behavior is not OverageBehavior.STOPS or
                        total is None or covered is None or
                        quota.remaining_credits_usd < covered or
                        quota.remaining_usage_usd < total):
                    reasons.append("QUOTA_UNKNOWN")
                else:
                    reasons.append("ZERO_COST_NOT_PROVEN")
            elif (candidate.cost_classification is CostClassification.FREE_QUOTA and
                  (candidate.hard_spend_cap_enforced is not True or
                   candidate.overage_behavior not in {OverageBehavior.STOPS,
                                                      OverageBehavior.NOT_APPLICABLE})):
                reasons.append("QUOTA_UNKNOWN")
            else:
                reasons.append("ZERO_COST_NOT_PROVEN")
    elif total is None:
        reasons.append("COST_UNKNOWN")
    elif total > max_cost_usd:
        reasons.append("COST_LIMIT_EXCEEDED")

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
            0 if item.zero_additional_cost_proven_at(now.isoformat().replace("+00:00", "Z")) else 1,
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


def revalidate_approved_candidate(
    requirements: WorkloadRequirements,
    *,
    approved_workload_fingerprint: str,
    approved_provider: str,
    approved_resource_id: str,
    approved_evidence_fingerprint: str,
    current_evidence: CapabilityEvidence | None,
    now_utc: str,
    max_cost_usd: Decimal,
) -> SelectionResult:
    """Recheck one exact approved resource; never substitute another candidate."""
    if not isinstance(requirements, WorkloadRequirements):
        raise TypeError("requirements must be WorkloadRequirements")
    if (not isinstance(approved_workload_fingerprint, str) or
            not re.fullmatch(r"sha256:[0-9a-f]{64}", approved_workload_fingerprint)):
        raise ValueError("approved_workload_fingerprint must be a sha256 fingerprint")
    if (not isinstance(approved_provider, str) or not approved_provider or
            approved_provider != approved_provider.strip()):
        raise ValueError("approved_provider must be canonical text")
    if (not isinstance(approved_resource_id, str) or not approved_resource_id or
            approved_resource_id != approved_resource_id.strip()):
        raise ValueError("approved_resource_id must be canonical text")
    if (not isinstance(approved_evidence_fingerprint, str) or
            not re.fullmatch(r"sha256:[0-9a-f]{64}", approved_evidence_fingerprint)):
        raise ValueError("approved_evidence_fingerprint must be a sha256 fingerprint")
    if (not isinstance(max_cost_usd, Decimal) or not max_cost_usd.is_finite() or
            max_cost_usd < 0):
        raise ValueError("max_cost_usd must be a finite nonnegative Decimal")
    try:
        parse_utc_timestamp(now_utc, "now_utc")
    except PricingVerificationError as exc:
        raise ValueError(str(exc)) from exc

    if requirements.fingerprint() != approved_workload_fingerprint:
        rejected = (RejectedCandidate(
            provider=approved_provider,
            resource_id=approved_resource_id,
            evidence_fingerprint=approved_evidence_fingerprint,
            reasons=("APPROVED_WORKLOAD_CHANGED",),
        ),)
        return SelectionResult(
            requirements.workload_id, requirements.fingerprint(), None,
            rejected, SelectionBlocker.APPROVED_PLAN_STALE,
        )

    if current_evidence is not None and not isinstance(current_evidence, CapabilityEvidence):
        raise TypeError("current_evidence must be CapabilityEvidence or None")

    if current_evidence is None:
        rejected = (RejectedCandidate(
            provider=approved_provider,
            resource_id=approved_resource_id,
            evidence_fingerprint=approved_evidence_fingerprint,
            reasons=("APPROVED_RESOURCE_EVIDENCE_MISSING",),
        ),)
        return SelectionResult(
            requirements.workload_id, requirements.fingerprint(), None,
            rejected, SelectionBlocker.APPROVED_PLAN_STALE,
        )

    current_fingerprint = current_evidence.fingerprint()
    if (current_evidence.provider != approved_provider or
            current_evidence.resource_id != approved_resource_id or
            current_fingerprint != approved_evidence_fingerprint):
        rejected = (RejectedCandidate(
            provider=current_evidence.provider,
            resource_id=current_evidence.resource_id,
            evidence_fingerprint=current_fingerprint,
            reasons=("APPROVED_CANDIDATE_CHANGED",),
        ),)
        return SelectionResult(
            requirements.workload_id, requirements.fingerprint(), None,
            rejected, SelectionBlocker.APPROVED_PLAN_STALE,
        )

    result = select_candidate(
        requirements, [current_evidence], now_utc=now_utc,
        max_cost_usd=max_cost_usd, free_first=False, inventory_complete=True,
    )
    if result.selected is None:
        return SelectionResult(
            result.workload_id, result.workload_fingerprint, None,
            result.rejected, SelectionBlocker.APPROVED_PLAN_STALE,
        )
    return result
