from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.human_authorization import (
    HumanAuthorizationError,
    HumanAuthorizationEvidence,
    authorize_live_plan,
)
from gpu_control.paid_authorization import PaidAuthorizationEvidence


NOW = datetime(2026, 8, 28, 0, 5, tzinfo=timezone.utc)
CONTROL_SHA = "c" * 40
DECISION_ID = "decision-live-canary-1"


def plan() -> ApprovedExecutionPlan:
    value = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="NVIDIA GeForce RTX 4090",
        target_repo="Unjuno/orbitune",
        target_sha="d" * 40,
        dockerfile_path="workloads/runpod-training-canary/Dockerfile",
        image_digest="sha256:" + "a" * 64,
        container_verification_reference="container:1",
        gpu_profile="cheap-24gb",
        gpu_count=1,
        max_runtime_minutes=5,
        max_cost_usd=Decimal("0.05"),
        verified_hourly_price_usd=Decimal("0.44"),
        pricing_verification_reference="pricing:1",
        pricing_verified_at_utc="2026-08-28T00:04:00Z",
        pricing_valid_until_utc="2026-08-28T00:09:00Z",
        worst_case_cost_usd=Decimal("0.04"),
        authorization_reference="human-auth:auth-1",
    )
    value.validate_shape()
    return value


def human(value: ApprovedExecutionPlan) -> HumanAuthorizationEvidence:
    return HumanAuthorizationEvidence(
        authorization_id="auth-1",
        actor="Unjuno",
        decision_record_id=DECISION_ID,
        control_plane_sha=CONTROL_SHA,
        plan_fingerprint=value.fingerprint(),
        target_repo=value.target_repo,
        target_sha=value.target_sha,
        image_digest=value.image_digest,
        provider=value.provider,
        provider_resource_id=value.provider_resource_id,
        gpu_count=1,
        max_runtime_minutes=5,
        max_cost_usd="0.05",
        authorized_at_utc="2026-08-28T00:00:00Z",
        valid_until_utc="2026-08-28T00:10:00Z",
        authorization_reference=value.authorization_reference,
    )


def paid() -> PaidAuthorizationEvidence:
    return PaidAuthorizationEvidence(
        actor="Unjuno",
        triggering_actor="Unjuno",
        repository="Unjuno/gpu-control",
        event_name="workflow_dispatch",
        ref="refs/heads/main",
        workflow_ref="Unjuno/gpu-control/.github/workflows/paid-runpod.yml@refs/heads/main",
        run_id="100",
        run_attempt=1,
        environment_name="paid-runpod",
        concurrency_group="gpu-control-paid-runpod",
        repository_security_reference="github:main-protection:sha256:" + "b" * 64,
        authorization_reference="github-actions:Unjuno/gpu-control:run:100:attempt:1:actor:Unjuno",
    )


def test_exact_current_human_intent_and_paid_identity_issue_live_permit() -> None:
    value = plan()
    permit = authorize_live_plan(
        value,
        human(value),
        paid(),
        expected_control_plane_sha=CONTROL_SHA,
        expected_decision_record_id=DECISION_ID,
        now_utc=NOW,
    )
    assert permit.plan_fingerprint == value.fingerprint()
    assert permit.actor == "Unjuno"
    assert permit.human_authorization_id == "auth-1"
    assert permit.repository_security_reference.startswith("github:main-protection")
    assert permit.valid_until_utc == "2026-08-28T00:10:00Z"
    permit.validate_for_plan(value, now_utc=NOW)


def test_live_permit_cannot_be_reused_after_human_authorization_expiry() -> None:
    value = plan()
    permit = authorize_live_plan(
        value,
        human(value),
        paid(),
        expected_control_plane_sha=CONTROL_SHA,
        expected_decision_record_id=DECISION_ID,
        now_utc=NOW,
    )
    with pytest.raises(HumanAuthorizationError, match="expired before provider submission"):
        permit.validate_for_plan(
            value,
            now_utc=datetime(2026, 8, 28, 0, 10, tzinfo=timezone.utc),
        )


def test_human_authorization_round_trip_is_strict() -> None:
    value = human(plan())
    restored = HumanAuthorizationEvidence.from_dict(value.to_dict())
    assert restored == value
    extra = value.to_dict()
    extra["unexpected"] = True
    with pytest.raises(HumanAuthorizationError, match="fields do not match schema"):
        HumanAuthorizationEvidence.from_dict(extra)


def test_expired_or_future_human_authorization_is_rejected() -> None:
    value = plan()
    expired = replace(human(value), valid_until_utc="2026-08-28T00:04:59Z")
    with pytest.raises(HumanAuthorizationError, match="expired"):
        authorize_live_plan(
            value,
            expired,
            paid(),
            expected_control_plane_sha=CONTROL_SHA,
            expected_decision_record_id=DECISION_ID,
            now_utc=NOW,
        )
    future = replace(
        human(value),
        authorized_at_utc="2026-08-28T00:06:00Z",
        valid_until_utc="2026-08-28T00:10:00Z",
    )
    with pytest.raises(HumanAuthorizationError, match="not valid yet"):
        authorize_live_plan(
            value,
            future,
            paid(),
            expected_control_plane_sha=CONTROL_SHA,
            expected_decision_record_id=DECISION_ID,
            now_utc=NOW,
        )


def test_authorization_ttl_may_not_exceed_fifteen_minutes() -> None:
    value = replace(human(plan()), valid_until_utc="2026-08-28T00:15:01Z")
    with pytest.raises(HumanAuthorizationError, match="15 minutes"):
        value.validate_shape()


def test_plan_change_requires_new_human_authorization() -> None:
    value = plan()
    changed = replace(value, max_runtime_minutes=4, worst_case_cost_usd=Decimal("0.03"))
    changed.validate_shape()
    with pytest.raises(HumanAuthorizationError, match="exact execution plan"):
        authorize_live_plan(
            changed,
            human(value),
            paid(),
            expected_control_plane_sha=CONTROL_SHA,
            expected_decision_record_id=DECISION_ID,
            now_utc=NOW,
        )


def test_control_plane_or_decision_record_replay_is_rejected() -> None:
    value = plan()
    with pytest.raises(HumanAuthorizationError, match="control-plane commit"):
        authorize_live_plan(
            value,
            human(value),
            paid(),
            expected_control_plane_sha="e" * 40,
            expected_decision_record_id=DECISION_ID,
            now_utc=NOW,
        )
    with pytest.raises(HumanAuthorizationError, match="DecisionRecord"):
        authorize_live_plan(
            value,
            human(value),
            paid(),
            expected_control_plane_sha=CONTROL_SHA,
            expected_decision_record_id="other-decision",
            now_utc=NOW,
        )


def test_paid_actor_must_match_current_human_actor() -> None:
    value = plan()
    other = replace(paid(), actor="other", triggering_actor="other")
    with pytest.raises(HumanAuthorizationError, match="authorized actor"):
        authorize_live_plan(
            value,
            human(value),
            other,
            expected_control_plane_sha=CONTROL_SHA,
            expected_decision_record_id=DECISION_ID,
            now_utc=NOW,
        )


def test_bare_owner_identity_without_repository_security_is_not_a_live_permit() -> None:
    value = plan()
    weak_paid = replace(paid(), repository_security_reference="not-live")
    with pytest.raises(HumanAuthorizationError, match="repository security"):
        authorize_live_plan(
            value,
            human(value),
            weak_paid,
            expected_control_plane_sha=CONTROL_SHA,
            expected_decision_record_id=DECISION_ID,
            now_utc=NOW,
        )
