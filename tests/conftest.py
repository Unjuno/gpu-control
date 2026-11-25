from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from gpu_control.human_authorization import HumanAuthorizationEvidence, authorize_live_plan
from gpu_control.paid_authorization import PaidAuthorizationEvidence
from gpu_control.providers import runpod_live_gate


_RUNPOD_OFFLINE_ADAPTER_TESTS = {
    "test_runpod_adapter",
    "test_runpod_compensating_reconciliation",
    "test_runpod_reconciliation",
    "test_runpod_v1",
    "test_runpod_v1_adapter",
    "test_runpod_v2",
}


@pytest.fixture(autouse=True)
def enable_mock_runpod_adapter_only(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Permit mock-only adapter tests to exercise code behind the parked gate."""
    if request.module.__name__.rsplit(".", 1)[-1] in _RUNPOD_OFFLINE_ADAPTER_TESTS:
        monkeypatch.setattr(runpod_live_gate, "RUNPOD_LIVE_ALLOCATION_ENABLED", True)


def issue_live_permit_for_plan(plan, *, valid_until_utc: str | None = None):  # type: ignore[no-untyped-def]
    """Build a real in-process permit from the authorization factory for unit fixtures."""
    end = (
        datetime.fromisoformat(valid_until_utc.replace("Z", "+00:00"))
        if valid_until_utc is not None
        else datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    start = end - timedelta(minutes=5)
    now = end - timedelta(seconds=1)
    human = HumanAuthorizationEvidence(
        authorization_id="test-human-auth",
        actor="test-owner",
        decision_record_id="test-decision",
        control_plane_sha="c" * 40,
        plan_fingerprint=plan.fingerprint(),
        target_repo=plan.target_repo,
        target_sha=plan.target_sha,
        image_digest=plan.image_digest,
        provider=plan.provider,
        provider_resource_id=plan.provider_resource_id,
        gpu_count=plan.gpu_count,
        max_runtime_minutes=plan.max_runtime_minutes,
        max_cost_usd=format(plan.max_cost_usd, "f"),
        authorized_at_utc=start.isoformat().replace("+00:00", "Z"),
        valid_until_utc=end.isoformat().replace("+00:00", "Z"),
        authorization_reference=plan.authorization_reference,
    )
    paid = PaidAuthorizationEvidence(
        actor="test-owner",
        triggering_actor="test-owner",
        repository="Unjuno/gpu-control",
        event_name="workflow_dispatch",
        ref="refs/heads/main",
        workflow_ref="Unjuno/gpu-control/.github/workflows/paid-runpod.yml@refs/heads/main",
        run_id="1",
        run_attempt=1,
        environment_name="paid-runpod",
        concurrency_group="gpu-control-paid-runpod",
        repository_security_reference="test-repository-security",
        authorization_reference="test-paid-auth",
    )
    return authorize_live_plan(
        plan,
        human,
        paid,
        expected_control_plane_sha="c" * 40,
        expected_decision_record_id="test-decision",
        now_utc=now,
    )
