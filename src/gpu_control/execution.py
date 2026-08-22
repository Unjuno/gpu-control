from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Mapping

from .source import SourceVerificationResult
from .validation import WorkloadRequest


class ExecutionGateError(ValueError):
    """Raised when a request is not ready to cross the paid-compute boundary."""


@dataclass(frozen=True)
class ApprovedExecutionPlan:
    """Immutable provider input produced only after all paid-compute gates pass."""

    provider: str
    target_repo: str
    target_sha: str
    dockerfile_path: str
    gpu_profile: str
    gpu_count: int
    max_runtime_minutes: int
    max_cost_usd: Decimal
    verified_hourly_price_usd: Decimal
    worst_case_cost_usd: Decimal
    authorization_reference: str
    source_verified: bool = True
    container_verified: bool = True
    dry_run_succeeded: bool = True
    cleanup_guaranteed: bool = True
    explicit_human_authorization: bool = True


def _positive_decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ExecutionGateError(f"{field} must be a decimal number") from exc
    if not result.is_finite() or result <= 0:
        raise ExecutionGateError(f"{field} must be finite and positive")
    return result


def _validate_source_identity(request: WorkloadRequest, source: SourceVerificationResult) -> None:
    if not (source.repository_public and source.commit_verified and source.dockerfile_verified):
        raise ExecutionGateError("source verification is incomplete")
    if source.repository != request.target_repo:
        raise ExecutionGateError("verified repository does not match the workload request")
    if source.commit_sha != request.target_sha:
        raise ExecutionGateError("verified commit does not match the workload request")
    if source.dockerfile_path != request.dockerfile_path:
        raise ExecutionGateError("verified Dockerfile does not match the workload request")


def build_approved_execution_plan(
    request: WorkloadRequest,
    effective_policy: Mapping[str, Any],
    source: SourceVerificationResult,
    *,
    provider: str,
    verified_hourly_price_usd: str | Decimal,
    container_verified: bool,
    dry_run_succeeded: bool,
    cleanup_guaranteed: bool,
    explicit_human_authorization: bool,
    authorization_reference: str,
) -> ApprovedExecutionPlan:
    """Create immutable provider input only when every paid-compute gate passes.

    This function is intentionally provider-agnostic and performs no provider call.
    A future provider adapter should accept an ApprovedExecutionPlan rather than a
    raw WorkloadRequest.
    """

    _validate_source_identity(request, source)

    if not container_verified:
        raise ExecutionGateError("container verification must pass before paid compute")
    if not dry_run_succeeded:
        raise ExecutionGateError("a successful dry-run is required before paid compute")
    if not cleanup_guaranteed:
        raise ExecutionGateError("provider cleanup must be guaranteed before paid compute")
    if not explicit_human_authorization:
        raise ExecutionGateError("explicit human authorization is required for paid compute")
    if not authorization_reference or not authorization_reference.strip():
        raise ExecutionGateError("authorization_reference is required for paid compute")
    if not provider or not provider.strip():
        raise ExecutionGateError("provider must be explicitly identified")

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

    allowed_cost = _positive_decimal(effective_policy.get("max_cost_usd"), "effective policy max_cost_usd")
    if request.max_cost_usd > allowed_cost:
        raise ExecutionGateError("requested cost exceeds the effective policy")

    hourly_price = _positive_decimal(verified_hourly_price_usd, "verified_hourly_price_usd")
    raw_worst_case = hourly_price * Decimal(request.max_runtime_minutes) / Decimal(60)
    worst_case_cost = raw_worst_case.quantize(Decimal("0.01"), rounding=ROUND_CEILING)

    if worst_case_cost > request.max_cost_usd:
        raise ExecutionGateError(
            f"worst-case provider cost ${worst_case_cost} exceeds requested limit ${request.max_cost_usd}"
        )

    return ApprovedExecutionPlan(
        provider=provider.strip(),
        target_repo=request.target_repo,
        target_sha=request.target_sha,
        dockerfile_path=request.dockerfile_path,
        gpu_profile=request.gpu_profile,
        gpu_count=gpu_count,
        max_runtime_minutes=request.max_runtime_minutes,
        max_cost_usd=request.max_cost_usd,
        verified_hourly_price_usd=hourly_price,
        worst_case_cost_usd=worst_case_cost,
        authorization_reference=authorization_reference.strip(),
    )
