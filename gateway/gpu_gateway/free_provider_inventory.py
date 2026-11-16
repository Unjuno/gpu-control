"""Fail-closed free-quota capability evidence for registered providers."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from gpu_control.capabilities import (
    Availability, CapabilityEvidence, CostBreakdown, CostClassification,
    OverageBehavior,
)
from gpu_control.workloads import AcceleratorKind, NetworkRequirement, ResultTransport

from .kaggle_backend import _remaining_gpu_seconds

KAGGLE_SOURCE = "kaggle-cli-quota"
KAGGLE_SOURCE_REVISION = "official-cli-quota-json-v1"
HF_SPACE_SOURCE = "huggingface-hub-zero-gpu-quota"
HF_SPACE_SOURCE_REVISION = "huggingface-hub-get-zero-gpu-quota-v1"
OBSERVATION_TTL_SECONDS = 120


def _time(value: int) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def _zero_cost() -> CostBreakdown:
    zero = Decimal("0")
    return CostBreakdown(zero, zero, zero, zero, zero, zero)


def _candidate(provider: str, workload: Any, *, observed_at: int, expires_at: int,
               source: str, quota_reference: str, cancellation: bool) -> dict[str, object]:
    evidence = CapabilityEvidence(
        provider=provider,
        resource_id=workload.provider_resource_id,
        availability=Availability.AVAILABLE,
        cost_classification=CostClassification.FREE_QUOTA,
        costs=_zero_cost(),
        hard_spend_cap_enforced=True,
        overage_behavior=OverageBehavior.STOPS,
        evidence_reference=quota_reference,
        evidence_source=source,
        observed_at_utc=_time(observed_at),
        valid_until_utc=_time(expires_at),
        supported_operating_systems=(workload.operating_system,),
        supported_architectures=(workload.architecture,),
        accelerator_kind=AcceleratorKind.GPU,
        gpu_profiles=(workload.gpu.lower(),),
        max_gpu_count=workload.gpu_count,
        max_vram_mib=workload.minimum_vram_mib,
        max_cpu_cores=Decimal(str(workload.cpu)),
        max_memory_mib=workload.memory_mib,
        max_runtime_seconds=workload.max_runtime_seconds,
        max_result_bytes=workload.max_result_bytes,
        network_modes_supported=(NetworkRequirement(workload.network_requirement),),
        result_transports=(ResultTransport(workload.result_transport),),
        cancellation_supported=cancellation,
        cleanup_proof_supported=True,
        supported_runtime_requirements=workload.runtime_requirements,
        estimated_queue_wait_seconds=workload.max_queue_wait_seconds,
    )
    return evidence.to_dict()


def collect_kaggle_inventory(workloads: Mapping[str, Any], quota: object, *,
                             observed_at: int, expires_at: int) -> dict[str, object]:
    targets = [workload for workload in workloads.values()
               if getattr(workload, "provider", None) == "kaggle"]
    remaining = _remaining_gpu_seconds(quota)
    if not targets or remaining is None:
        return {"inventory_complete": False, "candidates": []}
    candidates = []
    for workload in targets:
        if (not workload.provider_resource_id or workload.cancellation_required is not False or
                remaining < workload.max_runtime_seconds):
            return {"inventory_complete": False, "candidates": []}
        candidates.append(_candidate(
            "kaggle", workload, observed_at=observed_at, expires_at=expires_at,
            source=KAGGLE_SOURCE,
            quota_reference=f"kaggle-gpu-seconds:{remaining}", cancellation=False,
        ))
    return {"inventory_complete": True, "candidates": candidates}


def collect_huggingface_space_inventory(workloads: Mapping[str, Any], quota: object, *,
                                        observed_at: int, expires_at: int) -> dict[str, object]:
    targets = [workload for workload in workloads.values()
               if getattr(workload, "provider", None) == "huggingface_space"]
    remaining = getattr(quota, "remaining", None)
    overquota = getattr(quota, "overquota_used", None)
    if (not targets or not isinstance(remaining, (int, float)) or isinstance(remaining, bool) or
            overquota not in {None, 0, 0.0}):
        return {"inventory_complete": False, "candidates": []}
    candidates = []
    for workload in targets:
        if (not workload.provider_resource_id or workload.cancellation_required is not True or
                workload.max_runtime_seconds > 60 or remaining < workload.max_runtime_seconds):
            return {"inventory_complete": False, "candidates": []}
        candidates.append(_candidate(
            "huggingface_space", workload, observed_at=observed_at, expires_at=expires_at,
            source=HF_SPACE_SOURCE,
            quota_reference=f"zero-gpu-included-seconds:{remaining:g}", cancellation=True,
        ))
    return {"inventory_complete": True, "candidates": candidates}
