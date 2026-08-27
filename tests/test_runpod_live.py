from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.providers.runpod_live import build_live_account_occupancy_probe
from gpu_control.providers.runpod_v2 import RunPodV2HttpClient


NOW = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def plan() -> ApprovedExecutionPlan:
    value = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="NVIDIA GeForce RTX 4090",
        target_repo="Unjuno/orbitune",
        target_sha="8c19af0e7d091a1ead928cecfdeecf177f7e32f8",
        dockerfile_path="workloads/runpod-training-canary/Dockerfile",
        image_digest=DIGEST,
        container_verification_reference="actions-run:1/container",
        gpu_profile="cheap-24gb",
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.20"),
        verified_hourly_price_usd=Decimal("0.44"),
        pricing_verification_reference="runpod-v2-catalog:sha256:" + "b" * 64,
        pricing_verified_at_utc="2026-08-27T23:59:00Z",
        pricing_valid_until_utc="2026-08-28T00:04:00Z",
        worst_case_cost_usd=Decimal("0.11"),
        authorization_reference="human-auth:test",
    )
    value.validate_shape()
    return value


class FakeClient(RunPodV2HttpClient):
    def __init__(self, pods: list[dict[str, str]]) -> None:
        self.pods = pods
        self.calls = 0

    def list_pods(self):  # type: ignore[no-untyped-def]
        self.calls += 1
        return {"pods": self.pods}


def test_live_probe_uses_fresh_account_wide_list_pods() -> None:
    value = plan()
    client = FakeClient([])
    probe = build_live_account_occupancy_probe(client, clock=lambda: NOW, ttl_seconds=30)

    first = probe(value)
    assert first.active_pod_ids == ()
    first.validate_before_create(value, now_utc=NOW)

    client.pods = [{"id": "other-pod", "status": "RUNNING"}]
    second = probe(value)
    assert second.active_pod_ids == ("other-pod",)
    assert client.calls == 2


def test_live_probe_treats_exited_and_error_as_busy_until_terminated() -> None:
    value = plan()
    client = FakeClient(
        [
            {"id": "exited", "status": "EXITED"},
            {"id": "error", "status": "ERROR"},
            {"id": "gone", "status": "TERMINATED"},
        ]
    )
    evidence = build_live_account_occupancy_probe(client, clock=lambda: NOW)(value)
    assert evidence.active_pod_ids == ("error", "exited")
