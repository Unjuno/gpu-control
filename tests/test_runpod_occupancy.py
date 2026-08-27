from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.providers.runpod_occupancy import (
    RunPodV2AccountOccupancyProbe,
    build_account_occupancy_evidence,
)
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


def test_empty_account_is_valid_before_create_for_short_window() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(value, [], checked_at_utc=NOW, ttl_seconds=30)
    evidence.validate_before_create(value, now_utc=NOW + timedelta(seconds=1))
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
        evidence.validate_before_create(value, now_utc=NOW + timedelta(seconds=1))


def test_terminated_pods_do_not_block_new_owner_job() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(
        value,
        [{"id": "old-pod", "status": "TERMINATED"}],
        checked_at_utc=NOW,
    )
    evidence.validate_before_create(value, now_utc=NOW + timedelta(seconds=1))


def test_post_create_requires_exactly_new_pod_and_nothing_else() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(
        value,
        [{"id": "pod-123", "status": "PROVISIONING"}],
        checked_at_utc=NOW,
    )
    evidence.validate_after_create(
        value,
        expected_pod_id="pod-123",
        now_utc=NOW + timedelta(seconds=1),
    )

    raced = build_account_occupancy_evidence(
        value,
        [
            {"id": "pod-123", "status": "PROVISIONING"},
            {"id": "other-pod", "status": "RUNNING"},
        ],
        checked_at_utc=NOW,
    )
    with pytest.raises(RunPodV2Error, match="exclusivity was lost"):
        raced.validate_after_create(
            value,
            expected_pod_id="pod-123",
            now_utc=NOW + timedelta(seconds=1),
        )


def test_expired_occupancy_evidence_fails_closed() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(value, [], checked_at_utc=NOW, ttl_seconds=5)
    with pytest.raises(RunPodV2Error, match="expired"):
        evidence.validate_before_create(value, now_utc=NOW + timedelta(seconds=5))


def test_occupancy_evidence_is_bound_to_exact_plan() -> None:
    value = plan()
    evidence = build_account_occupancy_evidence(value, [], checked_at_utc=NOW)
    changed = ApprovedExecutionPlan.from_dict({**value.to_dict(), "authorization_reference": "other"})
    with pytest.raises(RunPodV2Error, match="fingerprint"):
        evidence.validate_before_create(changed, now_utc=NOW + timedelta(seconds=1))


class FakeListPodsClient:
    def __init__(self, pods: list[dict[str, str]]) -> None:
        self.pods = pods
        self.calls = 0

    def list_pods(self):  # type: ignore[no-untyped-def]
        self.calls += 1
        return {"pods": self.pods}


def test_live_occupancy_probe_reads_account_list_and_binds_evidence() -> None:
    value = plan()
    client = FakeListPodsClient([{"id": "old", "status": "TERMINATED"}])
    probe = RunPodV2AccountOccupancyProbe(
        client=client,  # type: ignore[arg-type]
        clock=lambda: NOW,
        ttl_seconds=30,
    )
    evidence = probe(value)
    assert client.calls == 1
    assert evidence.active_pod_ids == ()
    evidence.validate_before_create(value, now_utc=NOW + timedelta(seconds=1))


def test_live_occupancy_probe_fails_closed_on_invalid_list_shape() -> None:
    class BadClient:
        def list_pods(self):  # type: ignore[no-untyped-def]
            return {"pods": "not-a-list"}

    probe = RunPodV2AccountOccupancyProbe(
        client=BadClient(),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    with pytest.raises(RunPodV2Error, match="missing pods"):
        probe(plan())
