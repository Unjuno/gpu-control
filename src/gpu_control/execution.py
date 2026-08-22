from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from typing import Any, Mapping

from .container import ContainerVerificationResult
from .pricing import PricingVerificationError, PricingVerificationResult
from .source import SourceVerificationResult
from .validation import WorkloadRequest


class ExecutionGateError(ValueError):
    """Raised when a request is not ready to cross the paid-compute boundary."""


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

    return ApprovedExecutionPlan(
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
