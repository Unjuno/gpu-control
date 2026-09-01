from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..execution import ApprovedExecutionPlan
from ..validation import WorkloadRequest
from .runpod_network_volume import RunPodNetworkVolumeEvidence
from .runpod_pricing import RunPodCatalogPricingEvidence
from .runpod_v2 import RunPodV2Error


RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"
RUNPOD_PRICING_CONTRACT_COMMIT = "51ca7f02ab5cb57c09ad917172af36c29a58790c"
_MAX_EVIDENCE_TTL_SECONDS = 300
_GPU_TYPES_QUERY = """
query GpuControlGpuTypes {
  gpuTypes {
    id
    displayName
    memoryInGb
    secureCloud
    communityCloud
    securePrice
    communityPrice
  }
}
""".strip()
_DATA_CENTERS_QUERY = """
query GpuControlDataCenters {
  dataCenters {
    id
    name
    location
    gpuAvailability {
      gpuTypeId
      displayName
      stockStatus
    }
  }
}
""".strip()


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RunPodV2Error(f"{field} must be timezone-aware UTC")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise RunPodV2Error(f"{field} must be UTC")
    return value.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return _utc(value, "verified_at_utc").isoformat().replace("+00:00", "Z")


def _parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise RunPodV2Error(f"{field} must be a non-empty trimmed UTC timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RunPodV2Error(f"{field} must be ISO 8601") from exc
    return _utc(parsed, field)


def _positive_decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RunPodV2Error(f"{field} must be a decimal number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise RunPodV2Error(f"{field} must be finite and positive")
    return parsed


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RunPodV2Error(f"{field} must be a JSON object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise RunPodV2Error(f"{field} must be a JSON array")
    return value


def _evidence_digest(
    *,
    gpu_profile: str,
    gpu_type_id: str,
    data_center_id: str,
    memory_gb: int,
    hourly_price_usd: Decimal,
    stock_status: str,
    verified_at_utc: str,
    valid_until_utc: str,
    contract_commit: str,
) -> str:
    normalized = {
        "contract_commit": contract_commit,
        "data_center_id": data_center_id,
        "gpu_profile": gpu_profile,
        "gpu_type_id": gpu_type_id,
        "hourly_price_usd": format(hourly_price_usd, "f"),
        "memory_gb": memory_gb,
        "stock_status": stock_status,
        "valid_until_utc": valid_until_utc,
        "verified_at_utc": verified_at_utc,
    }
    return hashlib.sha256(
        json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class RunPodCurrentPricingEvidence:
    """Short-lived price and exact-datacenter availability evidence for one GPU."""

    gpu_profile: str
    gpu_type_id: str
    data_center_id: str
    memory_gb: int
    hourly_price_usd: Decimal
    stock_status: str
    verification_reference: str
    verified_at_utc: str
    valid_until_utc: str
    contract_commit: str = RUNPOD_PRICING_CONTRACT_COMMIT
    schema_version: int = 1

    def validate_shape(self) -> None:
        if self.schema_version != 1:
            raise RunPodV2Error("unsupported current RunPod pricing evidence schema_version")
        if not isinstance(self.gpu_profile, str) or not self.gpu_profile.strip() or self.gpu_profile != self.gpu_profile.strip():
            raise RunPodV2Error("current RunPod pricing gpu_profile is invalid")
        if not isinstance(self.gpu_type_id, str) or not self.gpu_type_id.strip() or self.gpu_type_id != self.gpu_type_id.strip():
            raise RunPodV2Error("current RunPod pricing gpu_type_id is invalid")
        if not isinstance(self.data_center_id, str) or not self.data_center_id.strip() or self.data_center_id != self.data_center_id.strip():
            raise RunPodV2Error("current RunPod pricing data_center_id is invalid")
        if isinstance(self.memory_gb, bool) or not isinstance(self.memory_gb, int) or self.memory_gb <= 0:
            raise RunPodV2Error("current RunPod pricing memory_gb must be a positive integer")
        if not isinstance(self.hourly_price_usd, Decimal) or not self.hourly_price_usd.is_finite() or self.hourly_price_usd <= 0:
            raise RunPodV2Error("current RunPod pricing hourly_price_usd must be a finite positive Decimal")
        if self.stock_status != "HIGH":
            raise RunPodV2Error("current RunPod pricing requires HIGH stock in the exact datacenter")
        if self.contract_commit != RUNPOD_PRICING_CONTRACT_COMMIT:
            raise RunPodV2Error("current RunPod pricing contract commit is not the pinned reviewed contract")
        checked = _parse_utc(self.verified_at_utc, "verified_at_utc")
        valid_until = _parse_utc(self.valid_until_utc, "valid_until_utc")
        if valid_until <= checked:
            raise RunPodV2Error("current RunPod pricing validity window is invalid")
        if valid_until - checked > timedelta(seconds=_MAX_EVIDENCE_TTL_SECONDS):
            raise RunPodV2Error("current RunPod pricing evidence TTL exceeds 300 seconds")
        expected = "runpod-current-pricing:sha256:" + _evidence_digest(
            gpu_profile=self.gpu_profile,
            gpu_type_id=self.gpu_type_id,
            data_center_id=self.data_center_id,
            memory_gb=self.memory_gb,
            hourly_price_usd=self.hourly_price_usd,
            stock_status=self.stock_status,
            verified_at_utc=self.verified_at_utc,
            valid_until_utc=self.valid_until_utc,
            contract_commit=self.contract_commit,
        )
        if self.verification_reference != expected:
            raise RunPodV2Error("current RunPod pricing verification_reference does not match evidence contents")

    def to_catalog_evidence(self) -> RunPodCatalogPricingEvidence:
        self.validate_shape()
        return RunPodCatalogPricingEvidence(
            gpu_profile=self.gpu_profile,
            gpu_type_id=self.gpu_type_id,
            cloud="SECURE",
            memory_gb=self.memory_gb,
            hourly_price_usd=self.hourly_price_usd,
            availability="HIGH",
            verification_reference=self.verification_reference,
            verified_at_utc=self.verified_at_utc,
            valid_until_utc=self.valid_until_utc,
        )

    def validate_against_plan(
        self,
        plan: ApprovedExecutionPlan,
        *,
        network_volume: RunPodNetworkVolumeEvidence,
        now_utc: datetime,
    ) -> None:
        self.validate_shape()
        plan.validate_shape()
        network_volume.validate_shape()
        now = _utc(now_utc, "now_utc")
        valid_until = _parse_utc(self.valid_until_utc, "valid_until_utc")
        verified_at = _parse_utc(self.verified_at_utc, "verified_at_utc")
        if now < verified_at:
            raise RunPodV2Error("current RunPod pricing evidence is newer than execution time")
        if now >= valid_until:
            raise RunPodV2Error("current RunPod pricing evidence expired before provider submission")
        if plan.provider != "runpod":
            raise RunPodV2Error("current RunPod pricing evidence requires a runpod plan")
        if self.gpu_profile != plan.gpu_profile:
            raise RunPodV2Error("current RunPod pricing gpu_profile does not match approved plan")
        if self.gpu_type_id != plan.provider_resource_id:
            raise RunPodV2Error("current RunPod pricing GPU does not match approved plan")
        if self.hourly_price_usd != plan.verified_hourly_price_usd:
            raise RunPodV2Error("current RunPod price does not match approved plan")
        if self.verification_reference != plan.pricing_verification_reference:
            raise RunPodV2Error("current RunPod pricing reference does not match approved plan")
        if self.verified_at_utc != plan.pricing_verified_at_utc or self.valid_until_utc != plan.pricing_valid_until_utc:
            raise RunPodV2Error("current RunPod pricing validity does not match approved plan")
        if self.data_center_id != network_volume.data_center_id:
            raise RunPodV2Error("current RunPod pricing datacenter does not match trusted network volume")


class RunPodPricingGraphQLClient:
    """Fixed-origin, bearer-authenticated client for the current GPU/DC pricing queries."""

    def __init__(self, api_key: str, *, timeout: float = 10.0, opener: Callable[..., Any] = urlopen) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise RunPodV2Error("RunPod API key is required for current pricing")
        if api_key != api_key.strip() or any(character.isspace() for character in api_key):
            raise RunPodV2Error("RunPod API key must not contain whitespace")
        if timeout <= 0:
            raise RunPodV2Error("RunPod pricing HTTP timeout must be positive")
        if not callable(opener):
            raise RunPodV2Error("RunPod pricing HTTP opener must be callable")
        self._api_key = api_key
        self._timeout = timeout
        self._opener = opener

    def _query(self, query: str) -> Mapping[str, Any]:
        body = json.dumps({"query": query}, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        request = Request(
            RUNPOD_GRAPHQL_URL,
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "gpu-control",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", None)
                raw = response.read()
        except HTTPError as exc:
            raise RunPodV2Error(f"RunPod pricing API returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RunPodV2Error("RunPod pricing API could not be reached") from exc
        if status != 200:
            raise RunPodV2Error(f"RunPod pricing API returned unexpected HTTP status {status}")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunPodV2Error("RunPod pricing API returned invalid JSON") from exc
        root = _mapping(payload, "RunPod pricing response")
        errors = root.get("errors")
        if errors is not None and errors != []:
            raise RunPodV2Error("RunPod pricing GraphQL response contained errors")
        return _mapping(root.get("data"), "RunPod pricing response data")

    def gpu_types(self) -> list[Any]:
        return _list(self._query(_GPU_TYPES_QUERY).get("gpuTypes"), "RunPod gpuTypes")

    def data_centers(self) -> list[Any]:
        return _list(self._query(_DATA_CENTERS_QUERY).get("dataCenters"), "RunPod dataCenters")


def build_current_pricing_evidence(
    gpu_types: list[Any],
    data_centers: list[Any],
    request: WorkloadRequest,
    effective_policy: Mapping[str, Any],
    network_volume: RunPodNetworkVolumeEvidence,
    *,
    gpu_type_id: str,
    verified_at_utc: datetime,
    validity_seconds: int = 120,
) -> RunPodCurrentPricingEvidence:
    """Bind exact GPU price and exact Network Volume datacenter stock into evidence."""

    network_volume.validate_shape()
    checked = _utc(verified_at_utc, "verified_at_utc")
    if isinstance(validity_seconds, bool) or not isinstance(validity_seconds, int) or not 1 <= validity_seconds <= _MAX_EVIDENCE_TTL_SECONDS:
        raise RunPodV2Error("validity_seconds must be between 1 and 300")
    if effective_policy.get("profile") != request.gpu_profile:
        raise RunPodV2Error("effective policy profile does not match workload request")
    if effective_policy.get("gpu_count") != 1:
        raise RunPodV2Error("current RunPod pricing requires exactly one GPU")
    try:
        min_vram_gb = int(effective_policy.get("min_vram_gb", 0))
    except (TypeError, ValueError) as exc:
        raise RunPodV2Error("effective policy min_vram_gb is invalid") from exc
    if min_vram_gb <= 0:
        raise RunPodV2Error("effective policy min_vram_gb must be positive")
    if not isinstance(gpu_type_id, str) or not gpu_type_id.strip() or gpu_type_id != gpu_type_id.strip():
        raise RunPodV2Error("gpu_type_id is invalid")

    gpu_matches = [item for item in gpu_types if isinstance(item, Mapping) and item.get("id") == gpu_type_id]
    if len(gpu_matches) != 1:
        raise RunPodV2Error("current RunPod GPU response must contain exactly one requested GPU type")
    gpu = gpu_matches[0]
    memory = gpu.get("memoryInGb")
    if isinstance(memory, bool) or not isinstance(memory, int) or memory < min_vram_gb:
        raise RunPodV2Error("current RunPod GPU memory does not satisfy selected profile")
    if gpu.get("secureCloud") is not True:
        raise RunPodV2Error("current RunPod GPU is not offered in Secure Cloud")
    price = _positive_decimal(gpu.get("securePrice"), "current RunPod securePrice")

    dc_matches = [item for item in data_centers if isinstance(item, Mapping) and item.get("id") == network_volume.data_center_id]
    if len(dc_matches) != 1:
        raise RunPodV2Error("current RunPod datacenter response must contain the exact Network Volume datacenter once")
    availability = _list(dc_matches[0].get("gpuAvailability"), "RunPod datacenter gpuAvailability")
    stock_matches = [item for item in availability if isinstance(item, Mapping) and item.get("gpuTypeId") == gpu_type_id]
    if len(stock_matches) != 1:
        raise RunPodV2Error("current RunPod datacenter must contain exactly one availability row for requested GPU")
    raw_stock = stock_matches[0].get("stockStatus")
    if not isinstance(raw_stock, str) or raw_stock.strip().lower() != "high":
        raise RunPodV2Error("current RunPod exact datacenter does not have HIGH stock")

    verified = _format_utc(checked)
    valid_until = _format_utc(checked + timedelta(seconds=validity_seconds))
    digest = _evidence_digest(
        gpu_profile=request.gpu_profile,
        gpu_type_id=gpu_type_id,
        data_center_id=network_volume.data_center_id,
        memory_gb=memory,
        hourly_price_usd=price,
        stock_status="HIGH",
        verified_at_utc=verified,
        valid_until_utc=valid_until,
        contract_commit=RUNPOD_PRICING_CONTRACT_COMMIT,
    )
    evidence = RunPodCurrentPricingEvidence(
        gpu_profile=request.gpu_profile,
        gpu_type_id=gpu_type_id,
        data_center_id=network_volume.data_center_id,
        memory_gb=memory,
        hourly_price_usd=price,
        stock_status="HIGH",
        verification_reference=f"runpod-current-pricing:sha256:{digest}",
        verified_at_utc=verified,
        valid_until_utc=valid_until,
    )
    evidence.validate_shape()
    return evidence
