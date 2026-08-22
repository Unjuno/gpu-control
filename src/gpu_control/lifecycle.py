from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re

from .execution import ApprovedExecutionPlan


_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class LifecycleError(ValueError):
    """Raised when asynchronous provider lifecycle state is inconsistent."""


class JobState(str, Enum):
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class CleanupState(str, Enum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


_TERMINAL_JOB_STATES = {
    JobState.SUCCEEDED,
    JobState.FAILED,
    JobState.CANCELLED,
    JobState.TIMED_OUT,
}

_ALLOWED_JOB_TRANSITIONS = {
    JobState.SUBMITTED: {
        JobState.SUBMITTED,
        JobState.RUNNING,
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.CANCELLED,
        JobState.TIMED_OUT,
    },
    JobState.RUNNING: {
        JobState.RUNNING,
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.CANCELLED,
        JobState.TIMED_OUT,
    },
    JobState.SUCCEEDED: {JobState.SUCCEEDED},
    JobState.FAILED: {JobState.FAILED},
    JobState.CANCELLED: {JobState.CANCELLED},
    JobState.TIMED_OUT: {JobState.TIMED_OUT},
}

_ALLOWED_CLEANUP_TRANSITIONS = {
    CleanupState.NOT_STARTED: {
        CleanupState.NOT_STARTED,
        CleanupState.PENDING,
        CleanupState.COMPLETED,
        CleanupState.FAILED,
    },
    CleanupState.PENDING: {
        CleanupState.PENDING,
        CleanupState.COMPLETED,
        CleanupState.FAILED,
    },
    CleanupState.COMPLETED: {CleanupState.COMPLETED},
    CleanupState.FAILED: {
        CleanupState.FAILED,
        CleanupState.PENDING,
        CleanupState.COMPLETED,
    },
}


def _parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise LifecycleError(f"{field} is required")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise LifecycleError(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise LifecycleError(f"{field} must be timezone-aware UTC")
    return parsed


def _format_utc(value: datetime, field: str) -> str:
    if not isinstance(value, datetime):
        raise LifecycleError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise LifecycleError(f"{field} must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_identity(provider: str, provider_job_id: str, plan_fingerprint: str) -> None:
    if not isinstance(provider, str) or not provider.strip():
        raise LifecycleError("provider is required")
    if not isinstance(provider_job_id, str) or not provider_job_id.strip():
        raise LifecycleError("provider_job_id is required")
    if not isinstance(plan_fingerprint, str) or not _FINGERPRINT_RE.fullmatch(plan_fingerprint):
        raise LifecycleError("plan_fingerprint must be a lowercase sha256 fingerprint")


@dataclass(frozen=True)
class SubmissionReceipt:
    """Persisted handoff created immediately after a provider accepts a job."""

    provider: str
    provider_resource_id: str
    provider_job_id: str
    plan_fingerprint: str
    submitted_at_utc: str
    max_runtime_minutes: int
    max_cost_usd: Decimal
    image_digest: str
    schema_version: int = 1

    def validate_shape(self) -> datetime:
        if self.schema_version != 1:
            raise LifecycleError("unsupported submission receipt schema_version")
        _validate_identity(self.provider, self.provider_job_id, self.plan_fingerprint)
        if not isinstance(self.provider_resource_id, str) or not self.provider_resource_id.strip():
            raise LifecycleError("provider_resource_id is required")
        if isinstance(self.max_runtime_minutes, bool) or not isinstance(self.max_runtime_minutes, int) or self.max_runtime_minutes <= 0:
            raise LifecycleError("max_runtime_minutes must be a positive integer")
        if not isinstance(self.max_cost_usd, Decimal) or not self.max_cost_usd.is_finite() or self.max_cost_usd <= 0:
            raise LifecycleError("max_cost_usd must be a finite positive Decimal")
        if not isinstance(self.image_digest, str) or not _FINGERPRINT_RE.fullmatch(self.image_digest):
            raise LifecycleError("image_digest must be a lowercase sha256 digest")
        return _parse_utc(self.submitted_at_utc, "submitted_at_utc")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["max_cost_usd"] = format(self.max_cost_usd, "f")
        return payload

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


@dataclass(frozen=True)
class JobObservation:
    """One provider-state observation correlated to a persisted submission receipt."""

    provider: str
    provider_job_id: str
    plan_fingerprint: str
    state: JobState
    cleanup_state: CleanupState
    observed_at_utc: str
    status_reference: str
    schema_version: int = 1

    def validate_shape(self) -> datetime:
        if self.schema_version != 1:
            raise LifecycleError("unsupported job observation schema_version")
        _validate_identity(self.provider, self.provider_job_id, self.plan_fingerprint)
        if not isinstance(self.state, JobState):
            raise LifecycleError("state must be a JobState")
        if not isinstance(self.cleanup_state, CleanupState):
            raise LifecycleError("cleanup_state must be a CleanupState")
        if not isinstance(self.status_reference, str) or not self.status_reference.strip():
            raise LifecycleError("status_reference is required")
        if self.state not in _TERMINAL_JOB_STATES and self.cleanup_state is not CleanupState.NOT_STARTED:
            raise LifecycleError("cleanup cannot begin before the provider job is terminal")
        return _parse_utc(self.observed_at_utc, "observed_at_utc")

    @property
    def terminal(self) -> bool:
        return self.state in _TERMINAL_JOB_STATES

    @property
    def finalized(self) -> bool:
        return self.terminal and self.cleanup_state is CleanupState.COMPLETED


def build_submission_receipt(
    plan: ApprovedExecutionPlan,
    *,
    provider_job_id: str,
    submitted_at_utc: datetime,
) -> SubmissionReceipt:
    normalized_job_id = provider_job_id.strip() if isinstance(provider_job_id, str) else provider_job_id
    receipt = SubmissionReceipt(
        provider=plan.provider,
        provider_resource_id=plan.provider_resource_id,
        provider_job_id=normalized_job_id,  # type: ignore[arg-type]
        plan_fingerprint=plan.fingerprint(),
        submitted_at_utc=_format_utc(submitted_at_utc, "submitted_at_utc"),
        max_runtime_minutes=plan.max_runtime_minutes,
        max_cost_usd=plan.max_cost_usd,
        image_digest=plan.image_digest,
    )
    receipt.validate_shape()
    return receipt


def validate_observation(receipt: SubmissionReceipt, observation: JobObservation) -> None:
    submitted_at = receipt.validate_shape()
    observed_at = observation.validate_shape()

    if observation.provider != receipt.provider:
        raise LifecycleError("observation provider does not match submission receipt")
    if observation.provider_job_id != receipt.provider_job_id:
        raise LifecycleError("observation provider_job_id does not match submission receipt")
    if observation.plan_fingerprint != receipt.plan_fingerprint:
        raise LifecycleError("observation plan_fingerprint does not match submission receipt")
    if observed_at < submitted_at:
        raise LifecycleError("observation cannot predate submission")


def validate_observation_transition(previous: JobObservation, current: JobObservation) -> None:
    previous_at = previous.validate_shape()
    current_at = current.validate_shape()

    if current.provider != previous.provider:
        raise LifecycleError("provider changed between observations")
    if current.provider_job_id != previous.provider_job_id:
        raise LifecycleError("provider_job_id changed between observations")
    if current.plan_fingerprint != previous.plan_fingerprint:
        raise LifecycleError("plan_fingerprint changed between observations")
    if current_at < previous_at:
        raise LifecycleError("observation time moved backwards")
    if current.state not in _ALLOWED_JOB_TRANSITIONS[previous.state]:
        raise LifecycleError(f"illegal job-state transition: {previous.state.value} -> {current.state.value}")
    if current.cleanup_state not in _ALLOWED_CLEANUP_TRANSITIONS[previous.cleanup_state]:
        raise LifecycleError(
            f"illegal cleanup-state transition: {previous.cleanup_state.value} -> {current.cleanup_state.value}"
        )
