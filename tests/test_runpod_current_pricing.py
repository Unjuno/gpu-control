from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.providers.runpod_current_pricing import (
    RUNPOD_PRICING_CONTRACT_REVISION,
    RunPodPricingCatalogClient,
    build_current_pricing_evidence,
)
from gpu_control.providers.runpod_network_volume import RunPodNetworkVolumeEvidence
from gpu_control.providers.runpod_v2 import RUNPOD_V2_BASE_URL, RunPodV2Error
from gpu_control.validation import WorkloadRequest


NOW = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
GPU_ID = "NVIDIA GeForce RTX 4090"
DC = "US-KS-2"


def request() -> WorkloadRequest:
    return WorkloadRequest(
        target_repo="Unjuno/orbitune",
        target_sha="d" * 40,
        dockerfile_path="workloads/runpod-training-canary/Dockerfile",
        gpu_profile="cheap-24gb",
        max_runtime_minutes=30,
        max_cost_usd=Decimal("0.30"),
    )


def policy() -> dict[str, object]:
    return {"profile": "cheap-24gb", "gpu_count": 1, "min_vram_gb": 24}


def volume(data_center_id: str = DC) -> RunPodNetworkVolumeEvidence:
    return RunPodNetworkVolumeEvidence(
        network_volume_id="volume-123",
        data_center_id=data_center_id,
        verification_reference="runpod-volume:test",
    )


def catalog(stock: str = "HIGH") -> dict[str, object]:
    return {
        "gpus": [
            {
                "id": GPU_ID,
                "name": "RTX 4090",
                "memory": 24,
                "secure": True,
                "community": True,
                "price": {"secure": 0.44, "community": 0.34},
                "maxCount": {"secure": 8, "community": 4},
                "availability": stock,
                "dataCenters": [{"id": DC, "name": "US Kansas 2", "availability": stock}],
            }
        ]
    }


def evidence():  # type: ignore[no-untyped-def]
    return build_current_pricing_evidence(
        catalog(), request(), policy(), volume(),
        gpu_type_id=GPU_ID, verified_at_utc=NOW, validity_seconds=120,
    )


def approved_plan(value):  # type: ignore[no-untyped-def]
    catalog_evidence = value.to_catalog_evidence()
    plan = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id=value.gpu_type_id,
        target_repo="Unjuno/orbitune",
        target_sha="d" * 40,
        dockerfile_path="workloads/runpod-training-canary/Dockerfile",
        image_digest="sha256:" + "a" * 64,
        container_verification_reference="container:test",
        gpu_profile=value.gpu_profile,
        gpu_count=1,
        max_runtime_minutes=30,
        max_cost_usd=Decimal("0.30"),
        verified_hourly_price_usd=value.hourly_price_usd,
        pricing_verification_reference=value.verification_reference,
        pricing_verified_at_utc=value.verified_at_utc,
        pricing_valid_until_utc=value.valid_until_utc,
        worst_case_cost_usd=Decimal("0.22"),
        authorization_reference="human-auth:test",
    )
    plan.validate_shape()
    catalog_evidence.validate_against_plan(plan)
    return plan


def test_current_pricing_binds_secure_price_and_exact_volume_datacenter_stock() -> None:
    value = evidence()
    assert value.gpu_type_id == GPU_ID
    assert value.data_center_id == DC
    assert value.memory_gb == 24
    assert value.hourly_price_usd == Decimal("0.44")
    assert value.stock_status == "HIGH"
    assert value.contract_revision == RUNPOD_PRICING_CONTRACT_REVISION
    assert value.verification_reference.startswith("runpod-v2-catalog-pricing:sha256:")

    value.validate_against_plan(approved_plan(value), network_volume=volume(), now_utc=NOW)


def test_current_pricing_rejects_low_stock_wrong_dc_and_tampering() -> None:
    with pytest.raises(RunPodV2Error, match="does not have HIGH stock"):
        build_current_pricing_evidence(
            catalog("LOW"), request(), policy(), volume(), gpu_type_id=GPU_ID, verified_at_utc=NOW,
        )

    value = evidence()
    plan = approved_plan(value)
    with pytest.raises(RunPodV2Error, match="datacenter does not match"):
        value.validate_against_plan(plan, network_volume=volume("US-WA-1"), now_utc=NOW)
    with pytest.raises(RunPodV2Error, match="verification_reference"):
        replace(value, hourly_price_usd=Decimal("0.45")).validate_shape()


def test_current_pricing_rejects_missing_exact_datacenter_and_capacity() -> None:
    missing_dc = catalog()
    missing_dc["gpus"][0]["dataCenters"] = []  # type: ignore[index]
    with pytest.raises(RunPodV2Error, match="exact Network Volume datacenter"):
        build_current_pricing_evidence(missing_dc, request(), policy(), volume(), gpu_type_id=GPU_ID, verified_at_utc=NOW)

    no_capacity = catalog()
    no_capacity["gpus"][0]["maxCount"]["secure"] = 0  # type: ignore[index]
    with pytest.raises(RunPodV2Error, match="no one-GPU Secure Cloud capacity"):
        build_current_pricing_evidence(no_capacity, request(), policy(), volume(), gpu_type_id=GPU_ID, verified_at_utc=NOW)


def test_current_pricing_rejects_expired_evidence() -> None:
    value = evidence()
    with pytest.raises(RunPodV2Error, match="expired"):
        value.validate_against_plan(
            approved_plan(value), network_volume=volume(),
            now_utc=datetime(2026, 9, 1, 9, 2, tzinfo=timezone.utc),
        )


class Response:
    def __init__(self, payload: object) -> None:
        import json

        self.status = 200
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *args):  # type: ignore[no-untyped-def]
        return False

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]


def test_pricing_client_uses_fixed_v2_catalog_and_bearer_header() -> None:
    seen = []

    def opener(http_request, timeout):  # type: ignore[no-untyped-def]
        seen.append((http_request, timeout))
        return Response(catalog())

    client = RunPodPricingCatalogClient("secret-token", opener=opener)
    assert client.catalog() == catalog()
    assert len(seen) == 1
    http_request, timeout = seen[0]
    assert http_request.full_url == (
        f"{RUNPOD_V2_BASE_URL}/catalog/gpus?include=AVAILABILITY&product=POD&count=1&cloud=SECURE"
    )
    assert http_request.method == "GET"
    assert http_request.data is None
    assert http_request.get_header("Authorization") == "Bearer secret-token"
    assert timeout == 10.0


def test_pricing_client_fails_closed_on_malformed_v2_catalog() -> None:
    def opener(http_request, timeout):  # type: ignore[no-untyped-def]
        return Response({"items": []})

    with pytest.raises(RunPodV2Error, match="missing gpus"):
        RunPodPricingCatalogClient("secret-token", opener=opener).catalog()
