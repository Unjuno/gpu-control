from __future__ import annotations

from dataclasses import asdict, dataclass, fields
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

    @classmethod
    def from_dict(cls, value: object) -> "CostBreakdown":
        names = set(cls.__dataclass_fields__)
        if not isinstance(value, dict) or set(value) != names:
            raise ValueError("cost breakdown fields are invalid")
        parsed = {}
        for name, amount in value.items():
            if amount is None:
                parsed[name] = None
            elif not isinstance(amount, str):
                raise ValueError(f"cost component {name} must be a decimal string or null")
            else:
                try:
                    parsed[name] = Decimal(amount)
                except Exception as exc:
                    raise ValueError(f"cost component {name} is invalid") from exc
        return cls(**parsed)


def _require_text(value: object, field: str) -> str:
    if (not isinstance(value, str) or not value or value != value.strip() or
            any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError(f"{field} must be nonempty canonical text")
    return value


def _optional_positive_int(value: int | None, field: str) -> None:
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError(f"{field} must be a positive integer or None")


@dataclass(frozen=True)
class QuotaEvidence:
    """Current usage headroom and eligible credit balance for bounded work."""

    remaining_usage_usd: Decimal
    remaining_credits_usd: Decimal
    covered_components: tuple[str, ...]
    evidence_reference: str
    observed_at_utc: str
    valid_until_utc: str

    def __post_init__(self) -> None:
        for field, value in (("remaining_usage_usd", self.remaining_usage_usd),
                             ("remaining_credits_usd", self.remaining_credits_usd)):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError(f"{field} must be a finite nonnegative Decimal")
        known_components = set(CostBreakdown.__dataclass_fields__)
        if (not isinstance(self.covered_components, tuple) or not self.covered_components or
                any(not isinstance(item, str) for item in self.covered_components) or
                len(set(self.covered_components)) != len(self.covered_components) or
                any(item not in known_components for item in self.covered_components)):
            raise ValueError("covered_components must be a nonempty tuple of unique cost component names")
        _require_text(self.evidence_reference, "credit evidence_reference")
        try:
            observed = parse_utc_timestamp(self.observed_at_utc, "credit observed_at_utc")
            valid_until = parse_utc_timestamp(self.valid_until_utc, "credit valid_until_utc")
        except PricingVerificationError as exc:
            raise ValueError(str(exc)) from exc
        if valid_until <= observed:
            raise ValueError("credit valid_until_utc must be after observed_at_utc")

    def is_current(self, now_utc: str) -> bool:
        try:
            now = parse_utc_timestamp(now_utc, "credit now_utc")
            observed = parse_utc_timestamp(self.observed_at_utc, "credit observed_at_utc")
            valid_until = parse_utc_timestamp(self.valid_until_utc, "credit valid_until_utc")
        except PricingVerificationError as exc:
            raise ValueError(str(exc)) from exc
        return observed <= now < valid_until

    def covered_cost_usd(self, costs: CostBreakdown) -> Decimal | None:
        components = asdict(costs)
        values = [components[name] for name in self.covered_components]
        if any(value is None for value in values):
            return None
        return sum(values, start=Decimal("0"))

    def to_dict(self) -> dict[str, object]:
        return {
            "remaining_usage_usd": format(self.remaining_usage_usd, "f"),
            "remaining_credits_usd": format(self.remaining_credits_usd, "f"),
            "covered_components": list(self.covered_components),
            "evidence_reference": self.evidence_reference,
            "observed_at_utc": self.observed_at_utc,
            "valid_until_utc": self.valid_until_utc,
        }

    @classmethod
    def from_dict(cls, value: object) -> "QuotaEvidence":
        expected = {"remaining_usage_usd", "remaining_credits_usd", "covered_components",
                    "evidence_reference", "observed_at_utc", "valid_until_utc"}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("quota evidence fields are invalid")
        if (not isinstance(value["remaining_usage_usd"], str) or
                not isinstance(value["remaining_credits_usd"], str) or
                not isinstance(value["covered_components"], list)):
            raise ValueError("quota evidence values are invalid")
        try:
            usage = Decimal(value["remaining_usage_usd"])
            credits = Decimal(value["remaining_credits_usd"])
        except Exception as exc:
            raise ValueError("quota evidence monetary values are invalid") from exc
        return cls(
            remaining_usage_usd=usage,
            remaining_credits_usd=credits,
            covered_components=tuple(value["covered_components"]),
            evidence_reference=value["evidence_reference"],
            observed_at_utc=value["observed_at_utc"],
            valid_until_utc=value["valid_until_utc"],
        )


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
    quota_evidence: QuotaEvidence | None = None
    supported_runtime_requirements: tuple[str, ...] | None = None
    estimated_queue_wait_seconds: int | None = None

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
        if self.quota_evidence is not None and not isinstance(self.quota_evidence, QuotaEvidence):
            raise ValueError("quota_evidence must be QuotaEvidence or None")
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
        if self.supported_runtime_requirements is not None:
            values = self.supported_runtime_requirements
            if (not isinstance(values, tuple) or
                    any(not isinstance(item, str) or not item or item != item.strip() or
                        any(ord(char) < 32 or ord(char) == 127 for char in item)
                        for item in values) or len(set(values)) != len(values)):
                raise ValueError("supported_runtime_requirements must be unique canonical strings or None")
        if (self.estimated_queue_wait_seconds is not None and
                (type(self.estimated_queue_wait_seconds) is not int or
                 self.estimated_queue_wait_seconds < 0)):
            raise ValueError("estimated_queue_wait_seconds must be a nonnegative integer or None")

    @property
    def zero_additional_cost_proven(self) -> bool:
        return (self.cost_classification in {CostClassification.LOCAL, CostClassification.FREE,
                                             CostClassification.FREE_QUOTA,
                                             CostClassification.CREDIT_BACKED} and
                self.costs.all_known_zero and self.hard_spend_cap_enforced is True and
                self.overage_behavior in {OverageBehavior.STOPS, OverageBehavior.NOT_APPLICABLE})

    def zero_additional_cost_proven_at(self, now_utc: str) -> bool:
        if self.zero_additional_cost_proven:
            return True
        if (self.cost_classification is not CostClassification.CREDIT_BACKED or
                self.hard_spend_cap_enforced is not True or
                self.overage_behavior is not OverageBehavior.STOPS or
                self.quota_evidence is None or not self.quota_evidence.is_current(now_utc)):
            return False
        total = self.costs.known_total_usd
        covered = self.quota_evidence.covered_cost_usd(self.costs)
        return (total is not None and covered is not None and covered == total and
                self.quota_evidence.remaining_credits_usd >= covered and
                self.quota_evidence.remaining_usage_usd >= total)

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
        payload["quota_evidence"] = (None if self.quota_evidence is None else
                                      self.quota_evidence.to_dict())
        return _json_value(payload)

    @classmethod
    def from_dict(cls, value: object) -> "CapabilityEvidence":
        """Rebuild selector evidence from a strict canonical JSON object."""
        names = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != names:
            raise ValueError("capability evidence fields are invalid")
        def optional_tuple(name: str):
            item = value[name]
            if item is None:
                return None
            if not isinstance(item, list):
                raise ValueError(f"{name} must be an array or null")
            return tuple(item)

        def optional_decimal(name: str):
            item = value[name]
            if item is None:
                return None
            if not isinstance(item, str):
                raise ValueError(f"{name} must be a decimal string or null")
            try:
                return Decimal(item)
            except Exception as exc:
                raise ValueError(f"{name} is invalid") from exc

        quota = value["quota_evidence"]
        runtime = optional_tuple("supported_runtime_requirements")
        return cls(
            provider=value["provider"],
            resource_id=value["resource_id"],
            availability=Availability(value["availability"]),
            cost_classification=CostClassification(value["cost_classification"]),
            costs=CostBreakdown.from_dict(value["costs"]),
            hard_spend_cap_enforced=value["hard_spend_cap_enforced"],
            overage_behavior=OverageBehavior(value["overage_behavior"]),
            evidence_reference=value["evidence_reference"],
            evidence_source=value["evidence_source"],
            observed_at_utc=value["observed_at_utc"],
            valid_until_utc=value["valid_until_utc"],
            supported_operating_systems=optional_tuple("supported_operating_systems"),
            supported_architectures=optional_tuple("supported_architectures"),
            accelerator_kind=(None if value["accelerator_kind"] is None else
                              AcceleratorKind(value["accelerator_kind"])),
            gpu_profiles=optional_tuple("gpu_profiles"),
            max_gpu_count=value["max_gpu_count"],
            max_vram_mib=value["max_vram_mib"],
            max_cpu_cores=optional_decimal("max_cpu_cores"),
            max_memory_mib=value["max_memory_mib"],
            max_runtime_seconds=value["max_runtime_seconds"],
            max_result_bytes=value["max_result_bytes"],
            network_modes_supported=(None if value["network_modes_supported"] is None else
                                     tuple(NetworkRequirement(item) for item in
                                           value["network_modes_supported"])),
            result_transports=(None if value["result_transports"] is None else
                               tuple(ResultTransport(item) for item in value["result_transports"])),
            cancellation_supported=value["cancellation_supported"],
            cleanup_proof_supported=value["cleanup_proof_supported"],
            quota_evidence=None if quota is None else QuotaEvidence.from_dict(quota),
            supported_runtime_requirements=runtime,
            estimated_queue_wait_seconds=value["estimated_queue_wait_seconds"],
        )

    def fingerprint(self) -> str:
        canonical = json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
