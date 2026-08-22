from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from ..execution import ApprovedExecutionPlan, ExecutionGateError
from ..lifecycle import (
    CleanupState,
    JobObservation,
    JobState,
    LifecycleError,
    SubmissionReceipt,
    build_submission_receipt,
    validate_observation,
    validate_observation_transition,
    validate_plan_for_submission,
)
from ..results import ResultManifest, ResultPolicy, build_result_manifest
from .base import (
    ProviderAdapter,
    ProviderCleanupSnapshot,
    ProviderResultSnapshot,
    ProviderStatusSnapshot,
    ProviderSubmission,
)


_PROVIDER_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


class ProviderContractError(ValueError):
    """Raised when a provider adapter violates the control-plane contract."""


@dataclass(frozen=True)
class SubmittedJob:
    """Trusted lifecycle state produced after one validated provider submission."""

    receipt: SubmissionReceipt
    initial_observation: JobObservation


def _format_utc(value: datetime, field: str) -> str:
    if not isinstance(value, datetime):
        raise ProviderContractError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ProviderContractError(f"{field} must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_text(value: object, field: str, *, max_length: int = 512) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderContractError(f"{field} is required")
    if value != value.strip():
        raise ProviderContractError(f"{field} must not contain surrounding whitespace")
    if len(value) > max_length:
        raise ProviderContractError(f"{field} exceeds maximum length {max_length}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProviderContractError(f"{field} must not contain control characters")
    return value


def _adapter_provider(adapter: ProviderAdapter) -> str:
    try:
        provider = adapter.provider_name
    except Exception as exc:
        raise ProviderContractError("provider adapter must expose provider_name") from exc
    provider = _require_text(provider, "provider adapter name", max_length=64)
    if not _PROVIDER_RE.fullmatch(provider):
        raise ProviderContractError("provider adapter name must be a canonical lowercase identifier")
    return provider


def _require_provider_match(adapter: ProviderAdapter, provider: str) -> str:
    adapter_provider = _adapter_provider(adapter)
    if adapter_provider != provider:
        raise ProviderContractError(
            f"provider adapter {adapter_provider!r} does not match lifecycle provider {provider!r}"
        )
    return adapter_provider


def _require_job_id(value: object) -> str:
    return _require_text(value, "provider_job_id", max_length=512)


def submit_approved_plan(
    adapter: ProviderAdapter,
    plan: ApprovedExecutionPlan,
    *,
    expected_plan_fingerprint: str,
    submitted_at_utc: datetime,
) -> SubmittedJob:
    """Cross the provider allocation boundary exactly once after all local gates pass.

    This wrapper must be used by future billable adapters. It validates the restored
    approved plan against a trusted expected fingerprint and re-checks pricing
    freshness before invoking ``adapter.submit``.
    """

    try:
        plan.validate_shape()
        plan.validate_expected_fingerprint(expected_plan_fingerprint)
        validate_plan_for_submission(plan, submitted_at_utc)
    except (ExecutionGateError, LifecycleError) as exc:
        raise ProviderContractError(str(exc)) from exc

    provider = _require_provider_match(adapter, plan.provider)
    response = adapter.submit(plan)
    if not isinstance(response, ProviderSubmission):
        raise ProviderContractError("provider submit must return ProviderSubmission")
    provider_job_id = _require_job_id(response.provider_job_id)

    try:
        receipt = build_submission_receipt(
            plan,
            provider_job_id=provider_job_id,
            submitted_at_utc=submitted_at_utc,
        )
        initial = JobObservation(
            provider=provider,
            provider_job_id=provider_job_id,
            plan_fingerprint=receipt.plan_fingerprint,
            state=JobState.SUBMITTED,
            cleanup_state=CleanupState.NOT_STARTED,
            observed_at_utc=_format_utc(submitted_at_utc, "submitted_at_utc"),
            status_reference=f"{provider}:submitted:{provider_job_id}",
        )
        validate_observation(receipt, initial)
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc

    return SubmittedJob(receipt=receipt, initial_observation=initial)


def observe_provider_job(
    adapter: ProviderAdapter,
    receipt: SubmissionReceipt,
    *,
    observed_at_utc: datetime,
    previous_observation: JobObservation | None = None,
) -> JobObservation:
    """Translate one untrusted provider status response into correlated lifecycle state."""

    _require_provider_match(adapter, receipt.provider)
    try:
        receipt.validate_shape()
        if previous_observation is not None:
            validate_observation(receipt, previous_observation)
            if previous_observation.cleanup_state is not CleanupState.NOT_STARTED:
                raise LifecycleError("provider status observation is forbidden after cleanup has started")
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc

    response = adapter.observe(receipt)
    if not isinstance(response, ProviderStatusSnapshot):
        raise ProviderContractError("provider observe must return ProviderStatusSnapshot")
    provider_job_id = _require_job_id(response.provider_job_id)
    if provider_job_id != receipt.provider_job_id:
        raise ProviderContractError("provider status job id does not match submission receipt")
    if not isinstance(response.state, JobState):
        raise ProviderContractError("provider status state must be a JobState")
    status_reference = _require_text(response.status_reference, "provider status reference")

    observation = JobObservation(
        provider=receipt.provider,
        provider_job_id=receipt.provider_job_id,
        plan_fingerprint=receipt.plan_fingerprint,
        state=response.state,
        cleanup_state=CleanupState.NOT_STARTED,
        observed_at_utc=_format_utc(observed_at_utc, "observed_at_utc"),
        status_reference=status_reference,
    )
    try:
        validate_observation(receipt, observation)
        if previous_observation is not None:
            validate_observation_transition(previous_observation, observation)
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc
    return observation


def cleanup_provider_job(
    adapter: ProviderAdapter,
    receipt: SubmissionReceipt,
    terminal_observation: JobObservation,
    *,
    observed_at_utc: datetime,
) -> JobObservation:
    """Run one bounded cleanup operation and record its correlated lifecycle state."""

    _require_provider_match(adapter, receipt.provider)
    try:
        receipt.validate_shape()
        validate_observation(receipt, terminal_observation)
        if not terminal_observation.terminal:
            raise LifecycleError("provider cleanup requires a terminal job observation")
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc

    response = adapter.cleanup(receipt, terminal_observation)
    if not isinstance(response, ProviderCleanupSnapshot):
        raise ProviderContractError("provider cleanup must return ProviderCleanupSnapshot")
    provider_job_id = _require_job_id(response.provider_job_id)
    if provider_job_id != receipt.provider_job_id:
        raise ProviderContractError("provider cleanup job id does not match submission receipt")
    if not isinstance(response.cleanup_state, CleanupState):
        raise ProviderContractError("provider cleanup_state must be a CleanupState")
    if response.cleanup_state is CleanupState.NOT_STARTED:
        raise ProviderContractError("provider cleanup response cannot return not_started")
    cleanup_reference = _require_text(response.cleanup_reference, "provider cleanup reference")

    current = JobObservation(
        provider=receipt.provider,
        provider_job_id=receipt.provider_job_id,
        plan_fingerprint=receipt.plan_fingerprint,
        state=terminal_observation.state,
        cleanup_state=response.cleanup_state,
        observed_at_utc=_format_utc(observed_at_utc, "observed_at_utc"),
        status_reference=cleanup_reference,
    )
    try:
        validate_observation(receipt, current)
        validate_observation_transition(terminal_observation, current)
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc
    return current


def collect_provider_results(
    adapter: ProviderAdapter,
    receipt: SubmissionReceipt,
    final_observation: JobObservation,
    *,
    collected_at_utc: datetime,
    policy: ResultPolicy | None = None,
) -> ResultManifest:
    """Translate provider result metadata only after terminal cleanup has completed."""

    _require_provider_match(adapter, receipt.provider)
    try:
        receipt.validate_shape()
        validate_observation(receipt, final_observation)
        if not final_observation.finalized:
            raise LifecycleError("provider result collection requires finalized lifecycle state")
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc

    response = adapter.collect_results(receipt, final_observation)
    if not isinstance(response, ProviderResultSnapshot):
        raise ProviderContractError("provider collect_results must return ProviderResultSnapshot")
    provider_job_id = _require_job_id(response.provider_job_id)
    if provider_job_id != receipt.provider_job_id:
        raise ProviderContractError("provider result job id does not match submission receipt")
    if not isinstance(response.artifacts, tuple):
        raise ProviderContractError("provider result artifacts must be a tuple")

    return build_result_manifest(
        receipt,
        final_observation,
        artifacts=response.artifacts,
        log_bytes_retained=response.log_bytes_retained,
        logs_truncated=response.logs_truncated,
        collected_at_utc=collected_at_utc,
        policy=policy,
    )
