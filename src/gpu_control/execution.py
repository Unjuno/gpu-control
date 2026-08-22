from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import re
from typing import Any, Mapping

from .container import ContainerVerificationResult
from .pricing import PricingVerificationError, PricingVerificationResult
from .source import SourceVerificationResult
from .validation import (
    ValidationError,
    WorkloadRequest,
    parse_cost,
    validate_profile,
    validate_relative_path,
    validate_repo,
    validate_sha,
)


_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROVIDER_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_PLAN_KEYS = {
    "provider",
    "provider_resource_id",
    "target_repo",
    "target_sha",
    "dockerfile_path",
    "image_digest",
    "container_verification_reference",
    "gpu_profile",
    "gpu_count",
    "max_runtime_minutes",
    "max_cost_usd",
    "verified_hourly_price_usd",
    "pricing_verification_reference",
    "pricing_verified_at_utc",
    "pricing_valid_until_utc",
    "worst_case_cost_usd",
    "authorization_reference",
    "source_verified",
    "container_verified",
    "pricing_verified",
    "dry_run_succeeded",
    "cleanup_guaranteed",
    "explicit_human_authorization",
    "schema_version",
}


class ExecutionGateError(ValueError):
    """Raised when a request is not ready to cross the paid-compute boundary."""


def _require_text(value: object, field: str, *, max_length: int = 512) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionGateError(f"{field} is required")
    if value != value.strip():
        raise ExecutionGateError(f"{field} must not contain surrounding whitespace")
    if len(value) > max_length:
        raise ExecutionGateError(f"{field} exceeds maximum length {max_length}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ExecutionGateError(f"{field} must not contain control characters")
    return value


def _parse_utc(value: object, field: str) -> datetime:
    text = _require_text(value, field, max_length=64)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ExecutionGateError(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ExecutionGateError(f"{field} must be timezone-aware UTC")
    return parsed


def _parse_decimal_string(value: object, field: str) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionGateError(f"{field} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ExecutionGateError(f"{field} must be a decimal string") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ExecutionGateError(f"{field} must be finite and positive")
    return parsed


def _require_exact_keys(payload: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(payload)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ExecutionGateError(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ExecutionGateError(f"{label} contains unknown fields: {', '.join(sorted(unknown))}")


def _load_json_object(value: str, label: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionGateError(f"{label} JSON is required")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ExecutionGateError(f"{label} contains duplicate field: {key}")
            result[key] = item
        return result

    try:
        payload = json.loads(value, object_pairs_hook=reject_duplicates)
    except ExecutionGateError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise ExecutionGateError(f"{label} must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ExecutionGateError(f"{label} must be a JSON object")
    return payload


@dataclass(frozen=True)
class ApprovedExecutionPlan:
    """Immutable provider input produced only after all paid-compute gates pass."""

    provider: str
    provider_resource_id: str
    target_repo: str
    target_sha: str
    dockerfile_path: str
    image_digest: str
    container_verification_reference: str
    gpu_profile: str
    gpu_count: int
    max_runtime_minutes: int
    max_cost_usd: Decimal
    verified_hourly_price_usd: Decimal
    pricing_verification_reference: str
    pricing_verified_at_utc: str
    pricing_valid_until_utc: str
    worst_case_cost_usd: Decimal
    authorization_reference: str
    source_verified: bool = True
    container_verified: bool = True
    pricing_verified: bool = True
    dry_run_succeeded: bool = True
    cleanup_guaranteed: bool = True
    explicit_human_authorization: bool = True
    schema_version: int = 1

    def validate_shape(self) -> None:
        if self.schema_version != 1:
            raise ExecutionGateError("unsupported approved execution plan schema_version")
        if not isinstance(self.provider, str) or not _PROVIDER_RE.fullmatch(self.provider):
            raise ExecutionGateError("provider must be a lowercase provider identifier")
        _require_text(self.provider_resource_id, "provider_resource_id")

        try:
            if validate_repo(self.target_repo) != self.target_repo:
                raise ExecutionGateError("target_repo is not canonical")
            if validate_sha(self.target_sha) != self.target_sha:
                raise ExecutionGateError("target_sha must be lowercase canonical hexadecimal")
            if validate_relative_path(self.dockerfile_path) != self.dockerfile_path:
                raise ExecutionGateError("dockerfile_path is not canonical")
            if validate_profile(self.gpu_profile) != self.gpu_profile:
                raise ExecutionGateError("gpu_profile is not canonical")
        except ValidationError as exc:
            raise ExecutionGateError(str(exc)) from exc

        if not isinstance(self.image_digest, str) or not _FINGERPRINT_RE.fullmatch(self.image_digest):
            raise ExecutionGateError("image_digest must be a lowercase sha256 digest")
        _require_text(self.container_verification_reference, "container_verification_reference")
        _require_text(self.pricing_verification_reference, "pricing_verification_reference")
        _require_text(self.authorization_reference, "authorization_reference")

        if isinstance(self.gpu_count, bool) or not isinstance(self.gpu_count, int) or self.gpu_count != 1:
            raise ExecutionGateError("approved execution plan requires exactly one GPU")
        if (
            isinstance(self.max_runtime_minutes, bool)
            or not isinstance(self.max_runtime_minutes, int)
            or self.max_runtime_minutes <= 0
        ):
            raise ExecutionGateError("max_runtime_minutes must be a positive integer")

        decimal_fields = {
            "max_cost_usd": self.max_cost_usd,
            "verified_hourly_price_usd": self.verified_hourly_price_usd,
            "worst_case_cost_usd": self.worst_case_cost_usd,
        }
        for field, value in decimal_fields.items():
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ExecutionGateError(f"{field} must be a finite positive Decimal")

        try:
            if parse_cost(self.max_cost_usd) != self.max_cost_usd:
                raise ExecutionGateError("max_cost_usd must use canonical two-decimal USD precision")
        except ValidationError as exc:
            raise ExecutionGateError(str(exc)) from exc

        expected_worst_case = (
            self.verified_hourly_price_usd * Decimal(self.max_runtime_minutes) / Decimal(60)
        ).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        if self.worst_case_cost_usd != expected_worst_case:
            raise ExecutionGateError("worst_case_cost_usd does not match verified price and runtime")
        if self.worst_case_cost_usd > self.max_cost_usd:
            raise ExecutionGateError("worst_case_cost_usd exceeds max_cost_usd")

        verified_at = _parse_utc(self.pricing_verified_at_utc, "pricing_verified_at_utc")
        valid_until = _parse_utc(self.pricing_valid_until_utc, "pricing_valid_until_utc")
        if valid_until <= verified_at:
            raise ExecutionGateError("pricing_valid_until_utc must be after pricing_verified_at_utc")

        gate_fields = {
            "source_verified": self.source_verified,
            "container_verified": self.container_verified,
            "pricing_verified": self.pricing_verified,
            "dry_run_succeeded": self.dry_run_succeeded,
            "cleanup_guaranteed": self.cleanup_guaranteed,
            "explicit_human_authorization": self.explicit_human_authorization,
        }
        for field, value in gate_fields.items():
            if value is not True:
                raise ExecutionGateError(f"{field} must be true in an approved execution plan")

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-compatible representation of the approved plan."""
        payload = asdict(self)
        for field in ("max_cost_usd", "verified_hourly_price_usd", "worst_case_cost_usd"):
            payload[field] = format(payload[field], "f")
        return payload

    def canonical_json(self) -> str:
        """Serialize the plan deterministically for cross-stage identity."""
        return json.dumps(
            self.to_dict(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )

    def fingerprint(self) -> str:
        """Return a content fingerprint for correlation, not authorization.

        The fingerprint detects plan changes and gives asynchronous stages a stable
        identifier. It is not a signature and does not authenticate the caller.
        """
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def validate_expected_fingerprint(self, expected_fingerprint: str) -> None:
        if not isinstance(expected_fingerprint, str) or not _FINGERPRINT_RE.fullmatch(expected_fingerprint):
            raise ExecutionGateError("expected plan fingerprint must be a lowercase sha256 fingerprint")
        if self.fingerprint() != expected_fingerprint:
            raise ExecutionGateError("approved execution plan fingerprint does not match expected fingerprint")

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        expected_fingerprint: str | None = None,
    ) -> ApprovedExecutionPlan:
        if not isinstance(payload, Mapping):
            raise ExecutionGateError("approved execution plan must be an object")
        _require_exact_keys(payload, _PLAN_KEYS, "approved execution plan")

        schema_version = payload["schema_version"]
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
            raise ExecutionGateError("unsupported approved execution plan schema_version")

        int_fields: dict[str, int] = {}
        for field in ("gpu_count", "max_runtime_minutes"):
            value = payload[field]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ExecutionGateError(f"{field} must be an integer")
            int_fields[field] = value

        bool_fields: dict[str, bool] = {}
        for field in (
            "source_verified",
            "container_verified",
            "pricing_verified",
            "dry_run_succeeded",
            "cleanup_guaranteed",
            "explicit_human_authorization",
        ):
            value = payload[field]
            if not isinstance(value, bool):
                raise ExecutionGateError(f"{field} must be a boolean")
            bool_fields[field] = value

        plan = cls(
            provider=payload["provider"],  # type: ignore[arg-type]
            provider_resource_id=payload["provider_resource_id"],  # type: ignore[arg-type]
            target_repo=payload["target_repo"],  # type: ignore[arg-type]
            target_sha=payload["target_sha"],  # type: ignore[arg-type]
            dockerfile_path=payload["dockerfile_path"],  # type: ignore[arg-type]
            image_digest=payload["image_digest"],  # type: ignore[arg-type]
            container_verification_reference=payload["container_verification_reference"],  # type: ignore[arg-type]
            gpu_profile=payload["gpu_profile"],  # type: ignore[arg-type]
            gpu_count=int_fields["gpu_count"],
            max_runtime_minutes=int_fields["max_runtime_minutes"],
            max_cost_usd=_parse_decimal_string(payload["max_cost_usd"], "max_cost_usd"),
            verified_hourly_price_usd=_parse_decimal_string(
                payload["verified_hourly_price_usd"], "verified_hourly_price_usd"
            ),
            pricing_verification_reference=payload["pricing_verification_reference"],  # type: ignore[arg-type]
            pricing_verified_at_utc=payload["pricing_verified_at_utc"],  # type: ignore[arg-type]
            pricing_valid_until_utc=payload["pricing_valid_until_utc"],  # type: ignore[arg-type]
            worst_case_cost_usd=_parse_decimal_string(payload["worst_case_cost_usd"], "worst_case_cost_usd"),
            authorization_reference=payload["authorization_reference"],  # type: ignore[arg-type]
            source_verified=bool_fields["source_verified"],
            container_verified=bool_fields["container_verified"],
            pricing_verified=bool_fields["pricing_verified"],
            dry_run_succeeded=bool_fields["dry_run_succeeded"],
            cleanup_guaranteed=bool_fields["cleanup_guaranteed"],
            explicit_human_authorization=bool_fields["explicit_human_authorization"],
            schema_version=schema_version,
        )
        plan.validate_shape()
        if expected_fingerprint is not None:
            plan.validate_expected_fingerprint(expected_fingerprint)
        return plan

    @classmethod
    def from_json(
        cls,
        value: str,
        *,
        expected_fingerprint: str | None = None,
    ) -> ApprovedExecutionPlan:
        return cls.from_dict(
            _load_json_object(value, "approved execution plan"),
            expected_fingerprint=expected_fingerprint,
        )


def _validate_source_identity(request: WorkloadRequest, source: SourceVerificationResult) -> None:
    if not (source.repository_public and source.commit_verified and source.dockerfile_verified):
        raise ExecutionGateError("source verification is incomplete")
    if source.repository != request.target_repo:
        raise ExecutionGateError("verified repository does not match the workload request")
    if source.commit_sha != request.target_sha:
        raise ExecutionGateError("verified commit does not match the workload request")
    if source.dockerfile_path != request.dockerfile_path:
        raise ExecutionGateError("verified Dockerfile does not match the workload request")


def _validate_container_evidence(
    request: WorkloadRequest,
    source: SourceVerificationResult,
    container: ContainerVerificationResult,
) -> None:
    try:
        container.validate_shape()
    except ValueError as exc:
        raise ExecutionGateError(str(exc)) from exc

    if container.repository != request.target_repo or container.repository != source.repository:
        raise ExecutionGateError("container repository identity does not match verified source")
    if container.commit_sha != request.target_sha or container.commit_sha != source.commit_sha:
        raise ExecutionGateError("container commit identity does not match verified source")
    if container.dockerfile_path != request.dockerfile_path or container.dockerfile_path != source.dockerfile_path:
        raise ExecutionGateError("container Dockerfile identity does not match verified source")

    checks = {
        "isolated container build": container.build_isolated,
        "isolated container runtime": container.runtime_isolated,
        "container smoke test": container.smoke_test_passed,
        "container output contract": container.output_contract_verified,
        "container credential isolation": container.credentials_absent,
        "container network policy": container.network_policy_enforced,
        "container resource limits": container.resource_limits_enforced,
    }
    for label, passed in checks.items():
        if not passed:
            raise ExecutionGateError(f"{label} must pass before paid compute")


def _validate_decision_time(value: datetime | None) -> datetime:
    decision_time = value or datetime.now(timezone.utc)
    if decision_time.tzinfo is None or decision_time.utcoffset() != timezone.utc.utcoffset(decision_time):
        raise ExecutionGateError("decision_time_utc must be timezone-aware UTC")
    return decision_time


def _validate_pricing_evidence(
    request: WorkloadRequest,
    pricing: PricingVerificationResult,
    *,
    decision_time_utc: datetime | None,
) -> Decimal:
    try:
        verified_at, valid_until = pricing.validate_shape()
    except PricingVerificationError as exc:
        raise ExecutionGateError(str(exc)) from exc

    if pricing.provider.strip().lower() == "":
        raise ExecutionGateError("pricing provider is required")
    if pricing.gpu_profile != request.gpu_profile:
        raise ExecutionGateError("pricing gpu_profile does not match the workload request")
    if not pricing.price_verified:
        raise ExecutionGateError("provider price verification must pass before paid compute")
    if not pricing.availability_verified:
        raise ExecutionGateError("provider resource availability must be verified before paid compute")

    decision_time = _validate_decision_time(decision_time_utc)
    if decision_time < verified_at:
        raise ExecutionGateError("pricing evidence cannot be newer than the approval decision")
    if decision_time >= valid_until:
        raise ExecutionGateError("pricing evidence expired before the approval decision")

    return pricing.hourly_price_usd


def build_approved_execution_plan(
    request: WorkloadRequest,
    effective_policy: Mapping[str, Any],
    source: SourceVerificationResult,
    container: ContainerVerificationResult,
    pricing: PricingVerificationResult,
    *,
    dry_run_succeeded: bool,
    cleanup_guaranteed: bool,
    explicit_human_authorization: bool,
    authorization_reference: str,
    decision_time_utc: datetime | None = None,
) -> ApprovedExecutionPlan:
    """Create immutable provider input only when every paid-compute gate passes.

    This function is intentionally provider-agnostic and performs no provider call.
    A future provider adapter should accept an ApprovedExecutionPlan rather than a
    raw WorkloadRequest.
    """

    _validate_source_identity(request, source)
    _validate_container_evidence(request, source, container)
    hourly_price = _validate_pricing_evidence(
        request,
        pricing,
        decision_time_utc=decision_time_utc,
    )

    if not dry_run_succeeded:
        raise ExecutionGateError("a successful dry-run is required before paid compute")
    if not cleanup_guaranteed:
        raise ExecutionGateError("provider cleanup must be guaranteed before paid compute")
    if not explicit_human_authorization:
        raise ExecutionGateError("explicit human authorization is required for paid compute")
    if not authorization_reference or not authorization_reference.strip():
        raise ExecutionGateError("authorization_reference is required for paid compute")

    if effective_policy.get("profile") != request.gpu_profile:
        raise ExecutionGateError("effective policy profile does not match the request")

    try:
        gpu_count = int(effective_policy.get("gpu_count", 0))
        allowed_runtime = int(effective_policy.get("max_runtime_minutes", 0))
    except (TypeError, ValueError) as exc:
        raise ExecutionGateError("effective policy contains invalid numeric limits") from exc

    if gpu_count != 1:
        raise ExecutionGateError("paid MVP requires exactly one GPU")
    if request.max_runtime_minutes > allowed_runtime:
        raise ExecutionGateError("requested runtime exceeds the effective policy")

    try:
        allowed_cost = Decimal(str(effective_policy.get("max_cost_usd")))
    except Exception as exc:
        raise ExecutionGateError("effective policy max_cost_usd must be a decimal number") from exc
    if not allowed_cost.is_finite() or allowed_cost <= 0:
        raise ExecutionGateError("effective policy max_cost_usd must be finite and positive")
    if request.max_cost_usd > allowed_cost:
        raise ExecutionGateError("requested cost exceeds the effective policy")

    raw_worst_case = hourly_price * Decimal(request.max_runtime_minutes) / Decimal(60)
    worst_case_cost = raw_worst_case.quantize(Decimal("0.01"), rounding=ROUND_CEILING)

    if worst_case_cost > request.max_cost_usd:
        raise ExecutionGateError(
            f"worst-case provider cost ${worst_case_cost} exceeds requested limit ${request.max_cost_usd}"
        )

    plan = ApprovedExecutionPlan(
        provider=pricing.provider.strip(),
        provider_resource_id=pricing.provider_resource_id.strip(),
        target_repo=request.target_repo,
        target_sha=request.target_sha,
        dockerfile_path=request.dockerfile_path,
        image_digest=container.image_digest,
        container_verification_reference=container.verification_reference.strip(),
        gpu_profile=request.gpu_profile,
        gpu_count=gpu_count,
        max_runtime_minutes=request.max_runtime_minutes,
        max_cost_usd=request.max_cost_usd,
        verified_hourly_price_usd=hourly_price,
        pricing_verification_reference=pricing.verification_reference.strip(),
        pricing_verified_at_utc=pricing.verified_at_utc.strip(),
        pricing_valid_until_utc=pricing.valid_until_utc.strip(),
        worst_case_cost_usd=worst_case_cost,
        authorization_reference=authorization_reference.strip(),
    )
    plan.validate_shape()
    return plan
