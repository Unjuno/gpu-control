from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.lifecycle import (
    CleanupState,
    JobObservation,
    JobState,
    LifecycleError,
    SubmissionReceipt,
    build_submission_receipt,
    validate_observation,
    validate_observation_transition,
    validate_plan_for_submission,
    validate_receipt_against_plan,
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
    validate_receipt_against_plan(plan, receipt)


def test_receipt_fingerprint_changes_when_provider_job_changes() -> None:
    receipt = make_receipt()
    changed = replace(receipt, provider_job_id="job-456")

    assert receipt.fingerprint() != changed.fingerprint()


def test_submission_receipt_json_round_trip_is_canonical() -> None:
    receipt = make_receipt()

    restored = SubmissionReceipt.from_json(receipt.canonical_json())

    assert restored == receipt
    assert restored.canonical_json() == receipt.canonical_json()
    assert restored.fingerprint() == receipt.fingerprint()
    assert isinstance(restored.max_cost_usd, Decimal)


def test_submission_receipt_rejects_unknown_missing_and_duplicate_fields() -> None:
    receipt = make_receipt()
    payload = receipt.to_dict()

    unknown = dict(payload)
    unknown["unexpected"] = True
    with pytest.raises(LifecycleError, match="unknown fields"):
        SubmissionReceipt.from_json(json.dumps(unknown))

    missing = dict(payload)
    del missing["image_digest"]
    with pytest.raises(LifecycleError, match="missing fields"):
        SubmissionReceipt.from_json(json.dumps(missing))

    duplicate = receipt.canonical_json().replace(
        '"provider":"runpod"',
        '"provider":"runpod","provider":"other"',
    )
    with pytest.raises(LifecycleError, match="duplicate field: provider"):
        SubmissionReceipt.from_json(duplicate)


def test_submission_receipt_requires_decimal_string_not_json_number() -> None:
    payload = make_receipt().to_dict()
    payload["max_cost_usd"] = 0.10

    with pytest.raises(LifecycleError, match="decimal string"):
        SubmissionReceipt.from_json(json.dumps(payload))


def test_rejects_non_utc_submission_time() -> None:
    with pytest.raises(LifecycleError, match="timezone-aware UTC"):
        build_submission_receipt(
            make_plan(),
            provider_job_id="job-123",
            submitted_at_utc=datetime(2026, 8, 22, 16, 0),
        )


def test_submission_rechecks_price_freshness_at_provider_boundary() -> None:
    plan = make_plan()

    validate_plan_for_submission(plan, SUBMITTED_AT)

    with pytest.raises(LifecycleError, match="expired before provider submission"):
        validate_plan_for_submission(
            plan,
            datetime(2026, 8, 22, 16, 5, tzinfo=timezone.utc),
        )

    with pytest.raises(LifecycleError, match="predate pricing verification"):
        validate_plan_for_submission(
            plan,
            datetime(2026, 8, 22, 15, 54, 59, tzinfo=timezone.utc),
        )


def test_submission_rechecks_approval_and_cleanup_flags() -> None:
    for field, message in [
        ("pricing_verified", "verified pricing"),
        ("explicit_human_authorization", "human authorization"),
        ("cleanup_guaranteed", "cleanup guarantee"),
    ]:
        plan = replace(make_plan(), **{field: False})
        with pytest.raises(LifecycleError, match=message):
            validate_plan_for_submission(plan, SUBMITTED_AT)


def test_receipt_must_still_match_approved_plan_after_persistence() -> None:
    plan = make_plan()
    receipt = make_receipt()

    for field, value, message in [
        ("provider_resource_id", "other-offer", "provider_resource_id"),
        ("plan_fingerprint", "sha256:" + "f" * 64, "plan_fingerprint"),
        ("image_digest", "sha256:" + "b" * 64, "image_digest"),
        ("max_runtime_minutes", 10, "runtime limit"),
        ("max_cost_usd", Decimal("0.09"), "cost limit"),
    ]:
        tampered = replace(receipt, **{field: value})
        with pytest.raises(LifecycleError, match=message):
            validate_receipt_against_plan(plan, tampered)


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


def test_job_observation_json_round_trip_is_canonical() -> None:
    observation = make_observation(state=JobState.RUNNING)

    restored = JobObservation.from_json(observation.canonical_json())

    assert restored == observation
    assert restored.canonical_json() == observation.canonical_json()
    assert restored.fingerprint() == observation.fingerprint()


def test_job_observation_rejects_unknown_or_invalid_state() -> None:
    payload = make_observation().to_dict()
    payload["extra"] = "nope"
    with pytest.raises(LifecycleError, match="unknown fields"):
        JobObservation.from_json(json.dumps(payload))

    payload = make_observation().to_dict()
    payload["state"] = "resurrected"
    with pytest.raises(LifecycleError, match="supported JobState"):
        JobObservation.from_json(json.dumps(payload))


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
