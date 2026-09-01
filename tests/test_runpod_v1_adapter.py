from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.human_authorization import LiveExecutionPermit
from gpu_control.providers.controller import submit_approved_plan
from gpu_control.providers.runpod_pricing import RunPodCatalogPricingEvidence
from gpu_control.providers.runpod_v1_adapter import (
    RunPodV1Adapter,
    RunPodV1InventoryProbe,
    RunPodV1OccupancyProbe,
)
from gpu_control.providers.runpod_v2 import PublishedImageEvidence


NOW = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def pricing() -> RunPodCatalogPricingEvidence:
    return RunPodCatalogPricingEvidence(
        gpu_profile="cheap-24gb",
        gpu_type_id="NVIDIA GeForce RTX 4090",
        cloud="SECURE",
        memory_gb=24,
        hourly_price_usd=Decimal("0.44"),
        availability="HIGH",
        verification_reference="runpod-current-pricing:sha256:" + "c" * 64,
        verified_at_utc="2026-09-01T08:59:00Z",
        valid_until_utc="2026-09-01T09:04:00Z",
    )


def plan() -> ApprovedExecutionPlan:
    evidence = pricing()
    value = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id=evidence.gpu_type_id,
        target_repo="Unjuno/orbitune",
        target_sha="d" * 40,
        dockerfile_path="workloads/runpod-training-canary/Dockerfile",
        image_digest=DIGEST,
        container_verification_reference="container:test",
        gpu_profile=evidence.gpu_profile,
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.20"),
        verified_hourly_price_usd=evidence.hourly_price_usd,
        pricing_verification_reference=evidence.verification_reference,
        pricing_verified_at_utc=evidence.verified_at_utc,
        pricing_valid_until_utc=evidence.valid_until_utc,
        worst_case_cost_usd=Decimal("0.11"),
        authorization_reference="human-auth:test",
    )
    value.validate_shape()
    return value


def image(value: ApprovedExecutionPlan) -> PublishedImageEvidence:
    return PublishedImageEvidence(
        plan_fingerprint=value.fingerprint(),
        image_reference=f"ghcr.io/unjuno/orbitune@{DIGEST}",
        image_digest=DIGEST,
        verification_reference="registry:test",
    )


def permit(value: ApprovedExecutionPlan) -> LiveExecutionPermit:
    return LiveExecutionPermit(
        plan_fingerprint=value.fingerprint(),
        actor="Unjuno",
        decision_record_id="decision-test",
        human_authorization_id="auth-test",
        human_authorization_reference=value.authorization_reference,
        paid_authorization_reference="github-actions:test",
        repository_security_reference="github:main-protection:sha256:" + "b" * 64,
        control_plane_sha="c" * 40,
        valid_until_utc="2026-09-01T09:10:00Z",
    )


class FakeV1Client:
    def __init__(self, value: ApprovedExecutionPlan) -> None:
        self.value = value
        self.create_payloads: list[dict[str, object]] = []
        self.list_responses = [
            {"pods": []},
            {"pods": [{"id": "pod-123", "name": "gpu-control-test", "status": "RUNNING"}]},
        ]

    def list_pods(self):  # type: ignore[no-untyped-def]
        return self.list_responses.pop(0)

    def create_pod(self, payload):  # type: ignore[no-untyped-def]
        self.create_payloads.append(dict(payload))
        return {
            "id": "pod-123",
            "name": payload["name"],
            "image": image(self.value).image_reference,
            "gpu": {"id": self.value.provider_resource_id, "count": 1},
            "cloud": "SECURE",
            "cost": Decimal("0.44"),
            "status": "RUNNING",
        }

    def get_pod(self, pod_id):  # type: ignore[no-untyped-def]
        assert pod_id == "pod-123"
        return {
            "id": "pod-123",
            "name": "gpu-control-test",
            "image": image(self.value).image_reference,
            "gpu": {"id": self.value.provider_resource_id, "count": 1},
            "cloud": "SECURE",
            "cost": Decimal("0.44"),
            "status": "RUNNING",
        }

    def terminate_pod(self, pod_id):  # type: ignore[no-untyped-def]
        assert pod_id == "pod-123"


def test_current_v1_adapter_builds_only_current_create_fields() -> None:
    value = plan()
    client = FakeV1Client(value)
    clock = lambda: NOW + timedelta(seconds=1)
    adapter = RunPodV1Adapter(
        client=client,  # type: ignore[arg-type]
        approved_plan=value,
        published_image=image(value),
        catalog_pricing=pricing(),
        occupancy_probe=RunPodV1OccupancyProbe(client=client, clock=clock),  # type: ignore[arg-type]
        inventory_probe=RunPodV1InventoryProbe(client=client, clock=clock),  # type: ignore[arg-type]
        live_permit=permit(value),
        clock=clock,
    )

    submitted = submit_approved_plan(
        adapter,
        value,
        expected_plan_fingerprint=value.fingerprint(),
        submitted_at_utc=NOW,
    )

    assert submitted.receipt.provider_job_id == "pod-123"
    assert len(client.create_payloads) == 1
    payload = client.create_payloads[0]
    assert payload["imageName"] == image(value).image_reference
    assert payload["gpuTypeIds"] == [value.provider_resource_id]
    assert payload["gpuCount"] == 1
    assert payload["containerDiskInGb"] == 20
    assert payload["cloudType"] == "SECURE"
    assert payload["globalNetworking"] is False
    assert payload["interruptible"] is False
    assert payload["supportPublicIp"] is False
    assert payload["ports"] == []
    assert "image" not in payload
    assert "gpu" not in payload
    assert "disk" not in payload
    assert "cloud" not in payload


def test_v1_list_pods_probes_preserve_fail_closed_occupancy_and_inventory() -> None:
    value = plan()
    client = FakeV1Client(value)
    occupancy = RunPodV1OccupancyProbe(client=client, clock=lambda: NOW)  # type: ignore[arg-type]
    first = occupancy(value)
    first.validate_before_create(value, now_utc=NOW)

    inventory = RunPodV1InventoryProbe(client=client, clock=lambda: NOW)  # type: ignore[arg-type]
    second = inventory(value)
    second.validate_against_plan(value, now_utc=NOW)
    assert len(second.pods) == 1
    assert second.pods[0].provider_job_id == "pod-123"
    assert second.pods[0].status == "RUNNING"
