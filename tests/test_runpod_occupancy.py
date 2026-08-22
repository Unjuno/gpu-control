from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.providers.runpod_occupancy import build_account_occupancy_evidence
from gpu_control.providers.runpod_v2 import RunPodV2Error


NOW = datetime(2026, 8, 23, 1, 0, 0, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def plan() -> ApprovedExecutionPlan:
    value = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="NVIDIA GeForce RTX 4090",
        target_repo="example/model",
        target_sha="0123456789abcdef0123456789abcdef01234567",
        dockerfile_path="Dockerfile",
        image_digest=DIGEST,
        container_verification_reference="actions-run:100/container",
        gpu_profile="cheap-24gb",
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.20"),
        verified_hourly_price_usd=Decimal("0.44"),
        pricing_verification_reference="runpod-v2-catalog:sha256:" + "c" * 64,
        pricing_verified_at_utc="2026-08-23T00:59:00Z",
        pricing_valid_until_utc="2026-08-23T01:03:00Z",
        worst_case_cost_usd=Decimal("0.11"),
        authorization_reference="github-actions:Unjuno/gpu-control:run:100:attempt:1:actor:Unjuno",
    )
    value.validate_shape()
    return value


def test_empty_account_is_valid_for_short_window() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(value, [], checked_at_utc=NOW, ttl_seconds=30)
    evidence.validate_against_plan(value, now_utc=NOW + timedelta(seconds=1))
    assert evidence.active_pod_ids == ()


@pytest.mark.parametrize("status", ["PROVISIONING", "STARTING", "RUNNING", "ERROR", "EXITED", "STOPPING"])
def test_any_non_terminated_pod_makes_account_busy(status: str) -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(
        value,
        [{"id": "other-pod", "status": status}],
        checked_at_utc=NOW,
    )
    with pytest.raises(RunPodV2Error, match="account is busy"):
        evidence.validate_against_plan(value, now_utc=NOW + timedelta(seconds=1))


def test_terminated_pods_do_not_block_new_owner_job() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(
        value,
        [{"id": "old-pod", "status": "TERMINATED"}],
        checked_at_utc=NOW,
    )
    evidence.validate_against_plan(value, now_utc=NOW + timedelta(seconds=1))


def test_expired_occupancy_evidence_fails_closed() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(value, [], checked_at_utc=NOW, ttl_seconds=5)
    with pytest.raises(RunPodV2Error, match="expired"):
        evidence.validate_against_plan(value, now_utc=NOW + timedelta(seconds=5))


def test_occupancy_evidence_is_bound_to_exact_plan() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(value, [], checked_at_utc=NOW)
    changed = ApprovedExecutionPlan.from_dict({**value.to_dict(), "authorization_reference": "other"})
    with pytest.raises(RunPodV2Error, match="fingerprint"):
        evidence.validate_against_plan(changed, now_utc=NOW + timedelta(seconds=1))
