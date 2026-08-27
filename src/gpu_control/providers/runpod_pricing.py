from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Mapping

from ..execution import ApprovedExecutionPlan
from ..pricing import PricingVerificationResult
from ..validation import WorkloadRequest
from .runpod_v2 import (
    PublishedImageEvidence,
    RunPodV2Error,
    build_create_pod_payload,
    validate_created_pod,
)


_ALLOWED_CLOUDS = {"SECURE", "COMMUNITY"}
_MAX_EVIDENCE_TTL_SECONDS = 300


@dataclass(frozen=True)
class RunPodCatalogPricingEvidence:
    """Normalized pricing/availability evidence from one RunPod v2 catalog row."""

    gpu_profile: str
    gpu_type_id: str
    cloud: str
    memory_gb: int
    hourly_price_usd: Decimal
    availability: str
    verification_reference: str
    verified_at_utc: str
    valid_until_utc: str
    schema_version: int = 1

    def to_pricing_result(self) -> PricingVerificationResult:
        self.validate_shape()
        return PricingVerificationResult(
            provider="runpod",
            gpu_profile=self.gpu_profile,
            provider_resource_id=self.gpu_type_id,
            hourly_price_usd=self.hourly_price_usd,
            verification_reference=self.verification_reference,
            verified_at_utc=self.verified_at_utc,
            valid_until_utc=self.valid_until_utc,
            price_verified=True,
            availability_verified=True,
        )

    def validate_shape(self) -> None:
        if self.schema_version != 1:
            raise RunPodV2Error("unsupported RunPod catalog pricing evidence schema_version")
        if not isinstance(self.gpu_profile, str) or not self.gpu_profile.strip():
            raise RunPodV2Error("RunPod catalog gpu_profile is required")
        if not isinstance(self.gpu_type_id, str) or not self.gpu_type_id.strip():
            raise RunPodV2Error("RunPod catalog gpu_type_id is required")
        if self.cloud not in _ALLOWED_CLOUDS:
            raise RunPodV2Error("RunPod catalog cloud must be SECURE or COMMUNITY")
        if isinstance(self.memory_gb, bool) or not isinstance(self.memory_gb, int) or self.memory_gb <= 0:
            raise RunPodV2Error("RunPod catalog memory_gb must be a positive integer")
        if not isinstance(self.hourly_price_usd, Decimal) or not self.hourly_price_usd.is_finite() or self.hourly_price_usd <= 0:
            raise RunPodV2Error("RunPod catalog hourly_price_usd must be a finite positive Decimal")
        if self.availability != "HIGH":
            raise RunPodV2Error("RunPod MVP requires HIGH catalog availability")
        if not isinstance(self.verification_reference, str) or not self.verification_reference.strip():
            raise RunPodV2Error("RunPod catalog verification_reference is required")
        verified_at = _parse_utc(self.verified_at_utc, "verified_at_utc")
        valid_until = _parse_utc(self.valid_until_utc, "valid_until_utc")
        if valid_until <= verified_at:
            raise RunPodV2Error("RunPod catalog valid_until_utc must be after verified_at_utc")
        if valid_until - verified_at > timedelta(seconds=_MAX_EVIDENCE_TTL_SECONDS):
            raise RunPodV2Error("RunPod catalog pricing evidence TTL exceeds 300 seconds")

    def validate_against_plan(self, plan: ApprovedExecutionPlan) -> None:
        self.validate_shape()
        plan.validate_shape()
        if plan.provider != "runpod":
            raise RunPodV2Error("RunPod catalog evidence requires a runpod approved plan")
        if self.gpu_profile != plan.gpu_profile:
            raise RunPodV2Error("RunPod catalog gpu_profile does not match approved plan")
        if self.gpu_type_id != plan.provider_resource_id:
            raise RunPodV2Error("RunPod catalog GPU type does not match approved plan")
        if self.hourly_price_usd != plan.verified_hourly_price_usd:
            raise RunPodV2Error("RunPod catalog price does not match approved plan")
        if self.verification_reference != plan.pricing_verification_reference:
            raise RunPodV2Error("RunPod catalog verification reference does not match approved plan")
        if self.verified_at_utc != plan.pricing_verified_at_utc:
            raise RunPodV2Error("RunPod catalog verified_at does not match approved plan")
        if self.valid_until_utc != plan.pricing_valid_until_utc:
            raise RunPodV2Error("RunPod catalog validity window does not match approved plan")


def _parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RunPodV2Error(f"{field} is required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RunPodV2Error(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RunPodV2Error(f"{field} must be timezone-aware UTC")
    return parsed


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise RunPodV2Error("verified_at_utc must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _positive_decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RunPodV2Error(f"{field} must be a decimal number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise RunPodV2Error(f"{field} must be finite and positive")
    return parsed


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RunPodV2Error(f"{field} must be an object")
    return value


def build_catalog_pricing_evidence(
    catalog: Mapping[str, Any],
    request: WorkloadRequest,
    effective_policy: Mapping[str, Any],
    *,
    gpu_type_id: str,
    cloud: str,
    verified_at_utc: datetime,
    validity_seconds: int = 120,
) -> RunPodCatalogPricingEvidence:
    """Normalize one exact v2 catalog GPU row into short-lived pricing evidence."""

    if cloud not in _ALLOWED_CLOUDS:
        raise RunPodV2Error("cloud must be SECURE or COMMUNITY")
    if isinstance(validity_seconds, bool) or not isinstance(validity_seconds, int) or not 1 <= validity_seconds <= _MAX_EVIDENCE_TTL_SECONDS:
        raise RunPodV2Error("validity_seconds must be between 1 and 300")
    if effective_policy.get("profile") != request.gpu_profile:
        raise RunPodV2Error("effective policy profile does not match workload request")
    if effective_policy.get("gpu_count") != 1:
        raise RunPodV2Error("RunPod MVP pricing requires exactly one GPU")
    try:
        min_vram_gb = int(effective_policy.get("min_vram_gb", 0))
    except (TypeError, ValueError) as exc:
        raise RunPodV2Error("effective policy min_vram_gb is invalid") from exc
    if min_vram_gb <= 0:
        raise RunPodV2Error("effective policy min_vram_gb must be positive")

    gpus = catalog.get("gpus")
    if not isinstance(gpus, list):
        raise RunPodV2Error("RunPod GPU catalog response is missing gpus")
    matches = [item for item in gpus if isinstance(item, Mapping) and item.get("id") == gpu_type_id]
    if len(matches) != 1:
        raise RunPodV2Error("RunPod GPU catalog must contain exactly one requested GPU type")
    gpu = matches[0]

    memory = gpu.get("memory")
    if isinstance(memory, bool) or not isinstance(memory, int) or memory < min_vram_gb:
        raise RunPodV2Error("RunPod GPU memory does not satisfy the selected profile")
    cloud_key = cloud.lower()
    if gpu.get(cloud_key) is not True:
        raise RunPodV2Error(f"RunPod GPU is not offered in {cloud} cloud")

    price = _positive_decimal(_require_mapping(gpu.get("price"), "RunPod GPU price").get(cloud_key), "RunPod GPU price")
    max_count = _require_mapping(gpu.get("maxCount"), "RunPod GPU maxCount").get(cloud_key)
    if isinstance(max_count, bool) or not isinstance(max_count, int) or max_count < 1:
        raise RunPodV2Error("RunPod GPU has no one-GPU capacity in the selected cloud")
    if gpu.get("availability") != "HIGH":
        raise RunPodV2Error("RunPod MVP requires HIGH catalog availability")
    data_centers = gpu.get("dataCenters")
    if not isinstance(data_centers, list) or not any(
        isinstance(item, Mapping) and item.get("availability") == "HIGH" for item in data_centers
    ):
        raise RunPodV2Error("RunPod GPU has no HIGH-availability data center")

    verified_at = _format_utc(verified_at_utc)
    valid_until = _format_utc(verified_at_utc + timedelta(seconds=validity_seconds)
    )
    normalized = {
        "gpu_profile": request.gpu_profile,
        "gpu_type_id": gpu_type_id,
        "cloud": cloud,
        "memory_gb": memory,
        "hourly_price_usd": format(price, "f"),
        "availability": "HIGH",
        "verified_at_utc": verified_at,
        "valid_until_utc": valid_until,
    }
    digest = hashlib.sha256(
        json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    evidence = RunPodCatalogPricingEvidence(
        gpu_profile=request.gpu_profile,
        gpu_type_id=gpu_type_id,
        cloud=cloud,
        memory_gb=memory,
        hourly_price_usd=price,
        availability="HIGH",
        verification_reference=f"runpod-v2-catalog:sha256:{digest}",
        verified_at_utc=verified_at,
        valid_until_utc=valid_until,
    )
    evidence.validate_shape()
    return evidence


def build_priced_create_pod_payload(
    plan: ApprovedExecutionPlan,
    image: PublishedImageEvidence,
    pricing: RunPodCatalogPricingEvidence,
    *,
    disk_gb: int = 20,
    execution_name: str | None = None,
    system_env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Build a create request whose cloud is bound to approved catalog evidence."""

    pricing.validate_against_plan(plan)
    return build_create_pod_payload(
        plan,
        image,
        disk_gb=disk_gb,
        cloud=pricing.cloud,
        execution_name=execution_name,
        system_env=system_env,
    )


def validate_created_pod_with_pricing(
    plan: ApprovedExecutionPlan,
    image: PublishedImageEvidence,
    pricing: RunPodCatalogPricingEvidence,
    pod: Mapping[str, Any],
    *,
    expected_name: str | None = None,
    allow_exited: bool = False,
) -> str:
    pricing.validate_against_plan(plan)
    if pod.get("cloud") != pricing.cloud:
        raise RunPodV2Error("RunPod create response cloud does not match approved catalog evidence")
    return validate_created_pod(
        plan,
        image,
        pod,
        expected_name=expected_name,
        allow_exited=allow_exited,
    )
