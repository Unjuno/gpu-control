from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re

from .pricing import PricingVerificationError, parse_utc_timestamp
from .workloads import AcceleratorKind, NetworkRequirement, ResultTransport, _json_value


class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class CostClassification(str, Enum):
    LOCAL = "LOCAL"
    FREE = "FREE"
    FREE_QUOTA = "FREE_QUOTA"
    CREDIT_BACKED = "CREDIT_BACKED"
    PAID = "PAID"
    MANUAL_ONLY = "MANUAL_ONLY"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class OverageBehavior(str, Enum):
    STOPS = "STOPS"
    CHARGED = "CHARGED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CostBreakdown:
    """Worst-case USD totals for one bounded run; None means not evidenced."""

    accelerator_usd: Decimal | None = None
    cpu_usd: Decimal | None = None
    memory_usd: Decimal | None = None
    storage_usd: Decimal | None = None
    egress_usd: Decimal | None = None
    other_usd: Decimal | None = None

    def __post_init__(self) -> None:
        for field, value in asdict(self).items():
            if value is None:
                continue
            if (not isinstance(value, Decimal) or not value.is_finite() or value < 0):
                raise ValueError(f"cost component {field} must be a finite nonnegative Decimal or None")

    @property
    def all_components_known(self) -> bool:
        return all(value is not None for value in asdict(self).values())

    @property
    def known_total_usd(self) -> Decimal | None:
        if not self.all_components_known:
            return None
        return sum(asdict(self).values(), start=Decimal("0"))

    @property
    def all_known_zero(self) -> bool:
        total = self.known_total_usd
        return total is not None and total == 0

    def to_dict(self) -> dict[str, str | None]:
        return {field: (None if value is None else format(value, "f"))
                for field, value in asdict(self).items()}


def _require_text(value: object, field: str) -> str:
    if (not isinstance(value, str) or not value or value != value.strip() or
            any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError(f"{field} must be nonempty canonical text")
    return value


def _optional_positive_int(value: int | None, field: str) -> None:
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError(f"{field} must be a positive integer or None")


@dataclass(frozen=True)
class CapabilityEvidence:
    """Time-bounded provider capability and cost evidence, never an authorization."""

    provider: str
    resource_id: str | None
    availability: Availability
    cost_classification: CostClassification
    costs: CostBreakdown
    hard_spend_cap_enforced: bool | None
    overage_behavior: OverageBehavior
    evidence_reference: str
    evidence_source: str
    observed_at_utc: str
    valid_until_utc: str
    supported_operating_systems: tuple[str, ...] | None
    supported_architectures: tuple[str, ...] | None
    accelerator_kind: AcceleratorKind | None
    gpu_profiles: tuple[str, ...] | None
    max_gpu_count: int | None
    max_vram_mib: int | None
    max_cpu_cores: Decimal | None
    max_memory_mib: int | None
    max_runtime_seconds: int | None
    max_result_bytes: int | None
    network_modes_supported: tuple[NetworkRequirement, ...] | None
    result_transports: tuple[ResultTransport, ...] | None
    cancellation_supported: bool | None
    cleanup_proof_supported: bool | None

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", self.provider):
            raise ValueError("provider must be a canonical lowercase identifier")
        if self.resource_id is not None:
            _require_text(self.resource_id, "resource_id")
        if not isinstance(self.availability, Availability):
            raise ValueError("availability is unsupported")
        if not isinstance(self.cost_classification, CostClassification):
            raise ValueError("cost_classification is unsupported")
        if not isinstance(self.costs, CostBreakdown):
            raise ValueError("costs must be a CostBreakdown")
        if self.availability is Availability.AVAILABLE and self.resource_id is None:
            raise ValueError("available capability requires resource_id")
        if self.hard_spend_cap_enforced is not None and type(self.hard_spend_cap_enforced) is not bool:
            raise ValueError("hard_spend_cap_enforced must be boolean or None")
        if not isinstance(self.overage_behavior, OverageBehavior):
            raise ValueError("overage_behavior is unsupported")
        _require_text(self.evidence_reference, "evidence_reference")
        _require_text(self.evidence_source, "evidence_source")
        try:
            observed = parse_utc_timestamp(self.observed_at_utc, "observed_at_utc")
            valid_until = parse_utc_timestamp(self.valid_until_utc, "valid_until_utc")
        except PricingVerificationError as exc:
            raise ValueError(str(exc)) from exc
        if valid_until <= observed:
            raise ValueError("valid_until_utc must be after observed_at_utc")
        if (self.supported_operating_systems is not None and
                not isinstance(self.supported_operating_systems, tuple)):
            raise ValueError("supported_operating_systems must be a tuple or None")
        if (self.supported_architectures is not None and
                not isinstance(self.supported_architectures, tuple)):
            raise ValueError("supported_architectures must be a tuple or None")
        for field, values in (("supported_operating_systems", self.supported_operating_systems),
                              ("supported_architectures", self.supported_architectures),
                              ("gpu_profiles", self.gpu_profiles)):
            if values is None:
                continue
            if not isinstance(values, tuple):
                raise ValueError(f"{field} must be a tuple or None")
            if any(not isinstance(value, str) or not value or value != value.strip() for value in values):
                raise ValueError(f"{field} contains invalid text")
        if self.accelerator_kind is not None and not isinstance(self.accelerator_kind, AcceleratorKind):
            raise ValueError("accelerator_kind is unsupported")
        for field, value in (("max_gpu_count", self.max_gpu_count),
                             ("max_vram_mib", self.max_vram_mib),
                             ("max_memory_mib", self.max_memory_mib),
                             ("max_runtime_seconds", self.max_runtime_seconds),
                             ("max_result_bytes", self.max_result_bytes)):
            _optional_positive_int(value, field)
        if self.max_cpu_cores is not None and (
                not isinstance(self.max_cpu_cores, Decimal) or
                not self.max_cpu_cores.is_finite() or self.max_cpu_cores <= 0):
            raise ValueError("max_cpu_cores must be a finite positive Decimal or None")
        if (self.network_modes_supported is not None and
                (not isinstance(self.network_modes_supported, tuple) or
                 any(not isinstance(item, NetworkRequirement)
                     for item in self.network_modes_supported))):
            raise ValueError("network_modes_supported must contain supported NetworkRequirement values or None")
        for field, value in (("cancellation_supported", self.cancellation_supported),
                             ("cleanup_proof_supported", self.cleanup_proof_supported)):
            if value is not None and type(value) is not bool:
                raise ValueError(f"{field} must be boolean or None")
        if self.result_transports is not None:
            if (not isinstance(self.result_transports, tuple) or
                    any(not isinstance(item, ResultTransport) for item in self.result_transports)):
                raise ValueError("result_transports must contain supported ResultTransport values or None")

    @property
    def zero_additional_cost_proven(self) -> bool:
        return (self.cost_classification in {CostClassification.LOCAL, CostClassification.FREE,
                                             CostClassification.FREE_QUOTA} and
                self.costs.all_known_zero and self.hard_spend_cap_enforced is True and
                self.overage_behavior in {OverageBehavior.STOPS, OverageBehavior.NOT_APPLICABLE})

    def is_current(self, now_utc: str) -> bool:
        try:
            now = parse_utc_timestamp(now_utc, "now_utc")
            observed = parse_utc_timestamp(self.observed_at_utc, "observed_at_utc")
            valid_until = parse_utc_timestamp(self.valid_until_utc, "valid_until_utc")
        except PricingVerificationError as exc:
            raise ValueError(str(exc)) from exc
        return observed <= now < valid_until

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["costs"] = self.costs.to_dict()
        return _json_value(payload)

    def fingerprint(self) -> str:
        canonical = json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
