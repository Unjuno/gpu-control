from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import (
    CleanupState,
    JobObservation,
    JobState,
    LifecycleError,
    build_submission_receipt,
    validate_observation,
    validate_observation_transition,
)


PLAN_SHA = "0123456789abcdef0123456789abcdef01234567"
IMAGE_DIGEST = "sha256:" + "a" * 64
SUBMITTED_AT = datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc)


def make_plan() -> ApprovedExecutionPlan:
    return ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="synthetic-offer-3090",
        target_repo="example/model",
        target_sha=PLAN_SHA,
        dockerfile_path="Dockerfile",
        image_digest=IMAGE_DIGEST,
        container_verification_reference="actions-run:100/container",
        gpu_profile="cheap-24gb",
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.10"),
        verified_hourly_price_usd=Decimal("0.34"),
        pricing_verification_reference="pricing-check:100",
        pricing_verified_at_utc="2026-08-22T15:55:00Z",
        pricing_valid_until_utc="2026-08-22T16:05:00Z",
        worst_case_cost_usd=Decimal("0.09"),
        authorization_reference="workflow_dispatch:100",
    )


def make_receipt():  # type: ignore[no-untyped-def]
    return build_submission_receipt(
        make_plan(),
        provider_job_id="job-123",
        submitted_at_utc=SUBMITTED_AT,
    )


def make_observation(
    *,
    state: JobState = JobState.SUBMITTED,
    cleanup_state: CleanupState = CleanupState.NOT_STARTED,
    observed_at_utc: str = "2026-08-22T16:00:01Z",
    **overrides,
):  # type: ignore[no-untyped-def]
    receipt = make_receipt()
    values = {
        "provider": receipt.provider,
        "provider_job_id": receipt.provider_job_id,
        "plan_fingerprint": receipt.plan_fingerprint,
        "state": state,
        "cleanup_state": cleanup_state,
        "observed_at_utc": observed_at_utc,
        "status_reference": "provider-status:job-123",
    }
    values.update(overrides)
    return JobObservation(**values)


def test_submission_receipt_is_bound_to_approved_plan() -> None:
    plan = make_plan()
    receipt = build_submission_receipt(
        plan,
        provider_job_id="job-123",
        submitted_at_utc=SUBMITTED_AT,
    )

    assert receipt.provider == plan.provider
    assert receipt.provider_resource_id == plan.provider_resource_id
    assert receipt.plan_fingerprint == plan.fingerprint()
    assert receipt.image_digest == plan.image_digest
    assert receipt.max_runtime_minutes == plan.max_runtime_minutes
    assert receipt.max_cost_usd == plan.max_cost_usd
    assert receipt.submitted_at_utc == "2026-08-22T16:00:00Z"
    assert receipt.fingerprint().startswith("sha256:")
    assert receipt.fingerprint() == receipt.fingerprint()


def test_receipt_fingerprint_changes_when_provider_job_changes() -> None:
    receipt = make_receipt()
    changed = replace(receipt, provider_job_id="job-456")

    assert receipt.fingerprint() != changed.fingerprint()


def test_rejects_non_utc_submission_time() -> None:
    with pytest.raises(LifecycleError, match="timezone-aware UTC"):
        build_submission_receipt(
            make_plan(),
            provider_job_id="job-123",
            submitted_at_utc=datetime(2026, 8, 22, 16, 0),
        )


def test_observation_must_match_submission_identity() -> None:
    receipt = make_receipt()

    for field, value, message in [
        ("provider", "other", "provider"),
        ("provider_job_id", "job-other", "provider_job_id"),
        ("plan_fingerprint", "sha256:" + "f" * 64, "plan_fingerprint"),
    ]:
        observation = replace(make_observation(), **{field: value})
        with pytest.raises(LifecycleError, match=message):
            validate_observation(receipt, observation)


def test_observation_cannot_predate_submission() -> None:
    observation = make_observation(observed_at_utc="2026-08-22T15:59:59Z")

    with pytest.raises(LifecycleError, match="predate"):
        validate_observation(make_receipt(), observation)


def test_cleanup_cannot_begin_before_terminal_job_state() -> None:
    observation = make_observation(
        state=JobState.RUNNING,
        cleanup_state=CleanupState.PENDING,
    )

    with pytest.raises(LifecycleError, match="cleanup cannot begin"):
        observation.validate_shape()


def test_valid_async_state_sequence_can_finalize() -> None:
    submitted = make_observation(
        state=JobState.SUBMITTED,
        observed_at_utc="2026-08-22T16:00:01Z",
    )
    running = make_observation(
        state=JobState.RUNNING,
        observed_at_utc="2026-08-22T16:00:10Z",
    )
    succeeded_cleanup_pending = make_observation(
        state=JobState.SUCCEEDED,
        cleanup_state=CleanupState.PENDING,
        observed_at_utc="2026-08-22T16:01:00Z",
    )
    finalized = make_observation(
        state=JobState.SUCCEEDED,
        cleanup_state=CleanupState.COMPLETED,
        observed_at_utc="2026-08-22T16:01:05Z",
    )

    validate_observation_transition(submitted, running)
    validate_observation_transition(running, succeeded_cleanup_pending)
    validate_observation_transition(succeeded_cleanup_pending, finalized)

    assert submitted.terminal is False
    assert succeeded_cleanup_pending.terminal is True
    assert succeeded_cleanup_pending.finalized is False
    assert finalized.finalized is True


@pytest.mark.parametrize(
    ("previous_state", "current_state"),
    [
        (JobState.SUCCEEDED, JobState.RUNNING),
        (JobState.SUCCEEDED, JobState.FAILED),
        (JobState.FAILED, JobState.RUNNING),
        (JobState.CANCELLED, JobState.SUCCEEDED),
        (JobState.TIMED_OUT, JobState.RUNNING),
    ],
)
def test_terminal_job_state_cannot_regress_or_change(
    previous_state: JobState,
    current_state: JobState,
) -> None:
    previous = make_observation(
        state=previous_state,
        cleanup_state=CleanupState.NOT_STARTED,
        observed_at_utc="2026-08-22T16:01:00Z",
    )
    current = make_observation(
        state=current_state,
        cleanup_state=CleanupState.NOT_STARTED,
        observed_at_utc="2026-08-22T16:01:01Z",
    )

    with pytest.raises(LifecycleError, match="illegal job-state transition"):
        validate_observation_transition(previous, current)


def test_observation_time_cannot_move_backwards() -> None:
    previous = make_observation(observed_at_utc="2026-08-22T16:01:00Z")
    current = make_observation(observed_at_utc="2026-08-22T16:00:59Z")

    with pytest.raises(LifecycleError, match="time moved backwards"):
        validate_observation_transition(previous, current)


def test_completed_cleanup_cannot_regress() -> None:
    previous = make_observation(
        state=JobState.SUCCEEDED,
        cleanup_state=CleanupState.COMPLETED,
        observed_at_utc="2026-08-22T16:01:00Z",
    )
    current = make_observation(
        state=JobState.SUCCEEDED,
        cleanup_state=CleanupState.FAILED,
        observed_at_utc="2026-08-22T16:01:01Z",
    )

    with pytest.raises(LifecycleError, match="illegal cleanup-state transition"):
        validate_observation_transition(previous, current)


def test_failed_cleanup_can_be_retried_and_complete() -> None:
    failed = make_observation(
        state=JobState.FAILED,
        cleanup_state=CleanupState.FAILED,
        observed_at_utc="2026-08-22T16:01:00Z",
    )
    retrying = make_observation(
        state=JobState.FAILED,
        cleanup_state=CleanupState.PENDING,
        observed_at_utc="2026-08-22T16:01:01Z",
    )
    completed = make_observation(
        state=JobState.FAILED,
        cleanup_state=CleanupState.COMPLETED,
        observed_at_utc="2026-08-22T16:01:02Z",
    )

    validate_observation_transition(failed, retrying)
    validate_observation_transition(retrying, completed)
    assert completed.finalized is True
