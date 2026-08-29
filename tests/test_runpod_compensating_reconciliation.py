from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.providers.runpod_adapter import RunPodV2Adapter, RunPodV2AdapterError
from gpu_control.providers.runpod_occupancy import build_account_occupancy_evidence
from gpu_control.providers.runpod_pricing import RunPodCatalogPricingEvidence
from gpu_control.providers.runpod_reconciliation import build_pod_inventory_evidence
from gpu_control.providers.runpod_v2 import PublishedImageEvidence, RunPodV2Error


NOW = datetime(2026, 8, 28, 1, 30, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def pricing() -> RunPodCatalogPricingEvidence:
    return RunPodCatalogPricingEvidence(
        gpu_profile="cheap-24gb",
        gpu_type_id="NVIDIA GeForce RTX 4090",
        cloud="SECURE",
        memory_gb=24,
        hourly_price_usd=Decimal("0.44"),
        availability="HIGH",
        verification_reference="runpod-v2-catalog:sha256:" + "c" * 64,
        verified_at_utc="2026-08-28T01:29:00Z",
        valid_until_utc="2026-08-28T01:34:00Z",
    )


def plan() -> ApprovedExecutionPlan:
    catalog = pricing()
    value = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id=catalog.gpu_type_id,
        target_repo="example/model",
        target_sha="0123456789abcdef0123456789abcdef01234567",
        dockerfile_path="Dockerfile",
        image_digest=DIGEST,
        container_verification_reference="actions-run:100/container",
        gpu_profile=catalog.gpu_profile,
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.20"),
        verified_hourly_price_usd=catalog.hourly_price_usd,
        pricing_verification_reference=catalog.verification_reference,
        pricing_verified_at_utc=catalog.verified_at_utc,
        pricing_valid_until_utc=catalog.valid_until_utc,
        worst_case_cost_usd=Decimal("0.11"),
        authorization_reference="workflow_dispatch:100",
    )
    value.validate_shape()
    return value


def image(value: ApprovedExecutionPlan) -> PublishedImageEvidence:
    return PublishedImageEvidence(
        plan_fingerprint=value.fingerprint(),
        image_reference=f"ghcr.io/example/model@{DIGEST}",
        image_digest=DIGEST,
        verification_reference="registry-publish:100",
    )


def invalid_create_response(value: ApprovedExecutionPlan) -> dict[str, object]:
    return {
        "id": "pod-123",
        "image": image(value).image_reference,
        "gpu": {"id": value.provider_resource_id, "count": 1},
        "cloud": "SECURE",
        "cost": 0.45,
        "status": "PROVISIONING",
    }


class Client:
    def __init__(self, value: ApprovedExecutionPlan) -> None:
        self.value = value
        self.create_calls = 0
        self.terminate_calls: list[str] = []

    def create_pod(self, payload):  # type: ignore[no-untyped-def]
        self.create_calls += 1
        return invalid_create_response(self.value)

    def terminate_pod(self, pod_id):  # type: ignore[no-untyped-def]
        self.terminate_calls.append(pod_id)
        raise RunPodV2Error("RunPod API could not be reached")

    def get_pod(self, pod_id):  # type: ignore[no-untyped-def]
        raise AssertionError("not used")


class Occupancy:
    def __init__(self, value: ApprovedExecutionPlan) -> None:
        self.value = value
        self.calls = 0

    def __call__(self, value: ApprovedExecutionPlan):  # type: ignore[no-untyped-def]
        self.calls += 1
        return build_account_occupancy_evidence(
            value,
            [],
            checked_at_utc=NOW,
            ttl_seconds=60,
        )


class Inventory:
    def __init__(self, value: ApprovedExecutionPlan, pods: list[dict[str, object]]) -> None:
        self.value = value
        self.pods = pods
        self.calls = 0

    def __call__(self, value: ApprovedExecutionPlan):  # type: ignore[no-untyped-def]
        self.calls += 1
        return build_pod_inventory_evidence(
            value,
            {"pods": self.pods},
            checked_at_utc=NOW,
            ttl_seconds=60,
        )


def adapter_with_inventory(pods: list[dict[str, object]]):  # type: ignore[no-untyped-def]
    value = plan()
    client = Client(value)
    occupancy = Occupancy(value)
    inventory = Inventory(value, pods)
    adapter = RunPodV2Adapter(
        client=client,  # type: ignore[arg-type]
        approved_plan=value,
        published_image=image(value),
        catalog_pricing=pricing(),
        occupancy_probe=occupancy,
        inventory_probe=inventory,
        clock=lambda: NOW + timedelta(seconds=1),
    )
    return value, client, inventory, adapter


def test_invalid_create_still_fails_when_compensating_release_is_reconciled_absent() -> None:
    value, client, inventory, adapter = adapter_with_inventory([])

    with pytest.raises(RunPodV2AdapterError, match="release was reconciled"):
        adapter.submit(value)

    assert client.create_calls == 1
    assert client.terminate_calls == ["pod-123"]
    assert inventory.calls == 1


def test_invalid_create_still_fails_when_compensating_release_is_reconciled_terminated() -> None:
    value, client, inventory, adapter = adapter_with_inventory(
        [{"id": "pod-123", "name": "invalid-created-pod", "status": "TERMINATED"}]
    )

    with pytest.raises(RunPodV2AdapterError, match="release was reconciled"):
        adapter.submit(value)

    assert client.terminate_calls == ["pod-123"]
    assert inventory.calls == 1


def test_invalid_create_reports_unreleased_when_compensating_pod_remains_active() -> None:
    value, client, inventory, adapter = adapter_with_inventory(
        [{"id": "pod-123", "name": "invalid-created-pod", "status": "RUNNING"}]
    )

    with pytest.raises(RunPodV2AdapterError, match="could not be proven released"):
        adapter.submit(value)

    assert client.terminate_calls == ["pod-123"]
    assert inventory.calls == 1
