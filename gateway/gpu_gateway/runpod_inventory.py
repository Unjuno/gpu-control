"""Conservative normalization of registered RunPod GPU/DC inventory.

This is capability evidence only. Advertised accelerator prices are not an
all-in quote and the module deliberately leaves all other execution dimensions
unknown so the selector cannot treat a catalog row as runnable capacity.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from gpu_control.capabilities import (
    Availability,
    CapabilityEvidence,
    CostBreakdown,
    CostClassification,
    OverageBehavior,
)
from gpu_control.providers.runpod_current_pricing import RunPodPricingGraphQLClient
from gpu_control.workloads import AcceleratorKind

SOURCE = "runpod-graphql-gpu-catalog"
OBSERVATION_TTL_SECONDS = 120


def _one(items: list[Any], key: str, expected: str) -> Mapping[str, Any] | None:
    matches = [item for item in items if isinstance(item, Mapping) and item.get(key) == expected]
    return matches[0] if len(matches) == 1 else None


def _positive_int(value: object) -> int | None:
    return value if type(value) is int and value > 0 else None


def _price(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def collect_runpod_inventory(workloads: Mapping[str, Any], client: Any, *,
                             observed_at: int, expires_at: int) -> dict[str, object]:
    """Return bounded signed-payload data for explicitly mapped workloads.

    A catalog is complete only when every registered RunPod workload with a
    resource mapping has one unambiguous matching GPU type, data center and
    availability row. Missing or malformed rows remain UNKNOWN and make the
    overall snapshot incomplete.
    """
    targets = [(name, workload) for name, workload in workloads.items()
               if getattr(workload, "provider", None) == "runpod"]
    if not targets:
        return {"inventory_complete": False, "candidates": []}

    gpu_types = client.gpu_types()
    data_centers = client.data_centers()
    if not isinstance(gpu_types, list) or not isinstance(data_centers, list):
        raise ValueError("invalid inventory response")

    observed = datetime.fromtimestamp(observed_at, timezone.utc).isoformat().replace("+00:00", "Z")
    expires = datetime.fromtimestamp(expires_at, timezone.utc).isoformat().replace("+00:00", "Z")
    candidates: list[dict[str, object]] = []
    complete = True
    for _name, workload in targets:
        gpu_id = getattr(workload, "provider_resource_id", None)
        dc_id = getattr(workload, "provider_data_center_id", None)
        if not isinstance(gpu_id, str) or not isinstance(dc_id, str):
            complete = False
            continue
        gpu = _one(gpu_types, "id", gpu_id)
        dc = _one(data_centers, "id", dc_id)
        if gpu is None or dc is None:
            complete = False
            continue
        availability_rows = dc.get("gpuAvailability")
        if not isinstance(availability_rows, list):
            complete = False
            continue
        availability = _one(availability_rows, "gpuTypeId", gpu_id)
        if availability is None:
            complete = False
            continue

        memory_gb = _positive_int(gpu.get("memoryInGb"))
        secure_max = _positive_int(gpu.get("maxGpuCountSecureCloud"))
        requested_count = getattr(workload, "gpu_count", None)
        if type(requested_count) is not int or requested_count < 1:
            requested_count = 1
        available_count = availability.get("availableCount")
        available_flag = availability.get("available")
        if type(available_count) is not int or available_count < 0 or type(available_flag) is not bool:
            complete = False
            availability_state = Availability.UNKNOWN
        elif (gpu.get("secureCloud") is True and available_flag and
              available_count >= requested_count):
            availability_state = Availability.AVAILABLE
        else:
            availability_state = Availability.UNAVAILABLE
        if memory_gb is None:
            complete = False
        secure_cloud = gpu.get("secureCloud")
        if type(secure_cloud) is not bool:
            complete = False
            availability_state = Availability.UNKNOWN
        elif secure_cloud is False:
            availability_state = Availability.UNAVAILABLE

        price = _price(gpu.get("securePrice"))
        if secure_max is not None and secure_max < requested_count:
            availability_state = Availability.UNAVAILABLE
        runtime = getattr(workload, "max_runtime_seconds", None)
        if type(runtime) is not int or runtime < 1:
            runtime = None
        accelerator_cost = (price * Decimal(runtime) * Decimal(requested_count) / Decimal(3600)
                            if price is not None and runtime is not None else None)
        resource_id = f"{gpu_id}@{dc_id}"
        evidence = CapabilityEvidence(
            provider="runpod",
            resource_id=resource_id if availability_state is Availability.AVAILABLE else None,
            availability=availability_state,
            cost_classification=(CostClassification.PAID if price is not None
                                 else CostClassification.UNKNOWN),
            costs=CostBreakdown(accelerator_usd=accelerator_cost),
            hard_spend_cap_enforced=None,
            overage_behavior=OverageBehavior.UNKNOWN,
            evidence_reference=f"runpod-catalog:{gpu_id}@{dc_id}",
            evidence_source=SOURCE,
            observed_at_utc=observed,
            valid_until_utc=expires,
            supported_operating_systems=None,
            supported_architectures=None,
            accelerator_kind=AcceleratorKind.GPU,
            gpu_profiles=(getattr(workload, "gpu", "").lower(),),
            max_gpu_count=secure_max,
            max_vram_mib=memory_gb * 1024 if memory_gb is not None else None,
            max_cpu_cores=None,
            max_memory_mib=None,
            max_runtime_seconds=None,
            max_result_bytes=None,
            network_modes_supported=None,
            result_transports=None,
            cancellation_supported=None,
            cleanup_proof_supported=None,
            supported_runtime_requirements=None,
            estimated_queue_wait_seconds=None,
        )
        candidates.append(evidence.to_dict())
    return {"inventory_complete": complete, "candidates": candidates}


def default_client(api_key: str) -> RunPodPricingGraphQLClient:
    return RunPodPricingGraphQLClient(api_key)
