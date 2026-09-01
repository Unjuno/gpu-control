from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.providers.runpod_current_pricing import (
    RUNPOD_GRAPHQL_URL,
    RUNPOD_PRICING_CONTRACT_COMMIT,
    RunPodPricingGraphQLClient,
    build_current_pricing_evidence,
)
from gpu_control.providers.runpod_network_volume import RunPodNetworkVolumeEvidence
from gpu_control.providers.runpod_v2 import RunPodV2Error
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


def gpu_types() -> list[dict[str, object]]:
    return [
        {
            "id": GPU_ID,
            "displayName": "RTX 4090",
            "memoryInGb": 24,
            "secureCloud": True,
            "communityCloud": True,
            "securePrice": 0.44,
            "communityPrice": 0.34,
        }
    ]


def data_centers(stock: str = "High") -> list[dict[str, object]]:
    return [
        {
            "id": DC,
            "name": "Kansas",
            "location": "US",
            "gpuAvailability": [
                {"gpuTypeId": GPU_ID, "displayName": "RTX 4090", "stockStatus": stock}
            ],
        }
    ]


def evidence():  # type: ignore[no-untyped-def]
    return build_current_pricing_evidence(
        gpu_types(),
        data_centers(),
        request(),
        policy(),
        volume(),
        gpu_type_id=GPU_ID,
        verified_at_utc=NOW,
        validity_seconds=120,
    )


def approved_plan(value):  # type: ignore[no-untyped-def]
    legacy = value.to_catalog_evidence()
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
    legacy.validate_against_plan(plan)
    return plan


def test_current_pricing_binds_secure_price_and_exact_volume_datacenter_stock() -> None:
    value = evidence()
    assert value.gpu_type_id == GPU_ID
    assert value.data_center_id == DC
    assert value.memory_gb == 24
    assert value.hourly_price_usd == Decimal("0.44")
    assert value.stock_status == "HIGH"
    assert value.contract_commit == RUNPOD_PRICING_CONTRACT_COMMIT
    assert value.verification_reference.startswith("runpod-current-pricing:sha256:")

    plan = approved_plan(value)
    value.validate_against_plan(plan, network_volume=volume(), now_utc=NOW)


def test_current_pricing_rejects_low_stock_wrong_dc_and_tampering() -> None:
    with pytest.raises(RunPodV2Error, match="does not have HIGH stock"):
        build_current_pricing_evidence(
            gpu_types(), data_centers("Low"), request(), policy(), volume(),
            gpu_type_id=GPU_ID, verified_at_utc=NOW,
        )

    value = evidence()
    plan = approved_plan(value)
    wrong_volume = volume("US-WA-1")
    with pytest.raises(RunPodV2Error, match="datacenter does not match"):
        value.validate_against_plan(plan, network_volume=wrong_volume, now_utc=NOW)

    with pytest.raises(RunPodV2Error, match="verification_reference"):
        replace(value, hourly_price_usd=Decimal("0.45")).validate_shape()


def test_current_pricing_rejects_expired_evidence() -> None:
    value = evidence()
    plan = approved_plan(value)
    with pytest.raises(RunPodV2Error, match="expired"):
        value.validate_against_plan(
            plan,
            network_volume=volume(),
            now_utc=datetime(2026, 9, 1, 9, 2, tzinfo=timezone.utc),
        )


class Response:
    def __init__(self, payload: object) -> None:
        self.status = 200
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *args):  # type: ignore[no-untyped-def]
        return False

    def read(self) -> bytes:
        return self._payload


def test_pricing_client_uses_fixed_graphql_origin_bearer_header_and_exact_queries() -> None:
    seen = []

    def opener(http_request, timeout):  # type: ignore[no-untyped-def]
        seen.append((http_request, timeout))
        body = json.loads(http_request.data.decode("utf-8"))
        query = body["query"]
        if "gpuTypes" in query:
            return Response({"data": {"gpuTypes": gpu_types()}})
        if "dataCenters" in query:
            return Response({"data": {"dataCenters": data_centers()}})
        raise AssertionError(query)

    client = RunPodPricingGraphQLClient("secret-token", opener=opener)
    assert client.gpu_types() == gpu_types()
    assert client.data_centers() == data_centers()
    assert len(seen) == 2
    for http_request, timeout in seen:
        assert http_request.full_url == RUNPOD_GRAPHQL_URL
        assert http_request.method == "POST"
        assert http_request.get_header("Authorization") == "Bearer secret-token"
        assert timeout == 10.0
        assert b"secret-token" not in http_request.data


def test_pricing_client_fails_closed_on_graphql_errors() -> None:
    def opener(http_request, timeout):  # type: ignore[no-untyped-def]
        return Response({"data": {"gpuTypes": []}, "errors": [{"message": "denied"}]})

    with pytest.raises(RunPodV2Error, match="contained errors"):
        RunPodPricingGraphQLClient("secret-token", opener=opener).gpu_types()
