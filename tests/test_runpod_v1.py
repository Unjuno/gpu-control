from __future__ import annotations

from decimal import Decimal
import io
import json
from urllib.error import HTTPError

import pytest

from gpu_control.completion import CompletionChallenge, execution_name_for
from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.providers.runpod_network_volume import RunPodNetworkVolumeEvidence
from gpu_control.providers.runpod_v1 import (
    RUNPOD_V1_BASE_URL,
    RunPodV1HttpClient,
    build_create_pod_payload_v1,
    normalize_v1_inventory,
    normalize_v1_pod,
)
from gpu_control.providers.runpod_v2 import (
    PublishedImageEvidence,
    RunPodCompletionLaunch,
    RunPodV2Error,
)


DIGEST = "sha256:" + "a" * 64
SECRET = bytes(range(32))


def plan() -> ApprovedExecutionPlan:
    value = ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="NVIDIA GeForce RTX 4090",
        target_repo="Unjuno/orbitune",
        target_sha="d" * 40,
        dockerfile_path="workloads/runpod-training-canary/Dockerfile",
        image_digest=DIGEST,
        container_verification_reference="container:1",
        gpu_profile="cheap-24gb",
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.20"),
        verified_hourly_price_usd=Decimal("0.44"),
        pricing_verification_reference="pricing:1",
        pricing_verified_at_utc="2026-08-31T12:00:00Z",
        pricing_valid_until_utc="2026-08-31T12:05:00Z",
        worst_case_cost_usd=Decimal("0.11"),
        authorization_reference="human-auth:1",
    )
    value.validate_shape()
    return value


def image(value: ApprovedExecutionPlan) -> PublishedImageEvidence:
    return PublishedImageEvidence(
        plan_fingerprint=value.fingerprint(),
        image_reference=f"ghcr.io/unjuno/orbitune@{DIGEST}",
        image_digest=DIGEST,
        verification_reference="registry:1",
    )


def completion(value: ApprovedExecutionPlan) -> RunPodCompletionLaunch:
    nonce = "b" * 64
    challenge = CompletionChallenge(
        key_id="paid-runpod-v3",
        nonce=nonce,
        plan_fingerprint=value.fingerprint(),
        execution_name=execution_name_for(value.fingerprint(), nonce),
        source_sha=value.target_sha,
        image_digest=value.image_digest,
    )
    return RunPodCompletionLaunch(challenge=challenge, secret_key=SECRET)


def volume() -> RunPodNetworkVolumeEvidence:
    return RunPodNetworkVolumeEvidence(
        network_volume_id="vol_123",
        data_center_id="US-KS-2",
        verification_reference="runpod-volume:1",
    )


def raw_pod(value: ApprovedExecutionPlan, *, status: str = "RUNNING") -> dict[str, object]:
    launch = completion(value)
    return {
        "id": "pod-123",
        "name": launch.challenge.execution_name,
        "image": image(value).image_reference,
        "costPerHr": "0.44",
        "desiredStatus": status,
        "gpu": {"id": value.provider_resource_id, "count": 1},
        "machine": {
            "secureCloud": True,
            "dataCenterId": "US-KS-2",
        },
        "networkVolume": {
            "id": "vol_123",
            "name": "gpu-control-results",
            "size": 10,
            "dataCenterId": "US-KS-2",
        },
        "volumeMountPath": "/outputs",
    }


def test_v1_create_payload_uses_current_official_field_names_and_trusted_volume() -> None:
    value = plan()
    launch = completion(value)
    payload = build_create_pod_payload_v1(
        value,
        image(value),
        cloud="SECURE",
        disk_gb=20,
        completion=launch,
        network_volume=volume(),
    )

    assert payload == {
        "name": launch.challenge.execution_name,
        "imageName": image(value).image_reference,
        "computeType": "GPU",
        "gpuTypeIds": [value.provider_resource_id],
        "gpuTypePriority": "custom",
        "gpuCount": 1,
        "containerDiskInGb": 20,
        "cloudType": "SECURE",
        "globalNetworking": False,
        "interruptible": False,
        "supportPublicIp": False,
        "ports": [],
        "dockerEntrypoint": [],
        "dockerStartCmd": [],
        "env": launch.provider_environment(value),
        "networkVolumeId": "vol_123",
        "volumeMountPath": "/outputs",
        "dataCenterIds": ["US-KS-2"],
        "dataCenterPriority": "custom",
    }
    assert "image" not in payload
    assert "gpu" not in payload
    assert "disk" not in payload
    assert "cloud" not in payload


def test_network_volume_create_is_forced_to_secure_cloud() -> None:
    value = plan()
    with pytest.raises(RunPodV2Error, match="requires SECURE"):
        build_create_pod_payload_v1(
            value,
            image(value),
            cloud="COMMUNITY",
            network_volume=volume(),
        )


def test_v1_pod_normalization_revalidates_machine_price_and_volume_identity() -> None:
    value = plan()
    normalized = normalize_v1_pod(
        raw_pod(value),
        require_machine=True,
        expected_network_volume=volume(),
    )

    assert normalized == {
        "id": "pod-123",
        "name": completion(value).challenge.execution_name,
        "image": image(value).image_reference,
        "gpu": {"id": value.provider_resource_id, "count": 1},
        "cost": Decimal("0.44"),
        "status": "RUNNING",
        "cloud": "SECURE",
        "dataCenterId": "US-KS-2",
        "networkVolumeId": "vol_123",
        "networkVolumeDataCenterId": "US-KS-2",
        "volumeMountPath": "/outputs",
    }

    wrong_volume = raw_pod(value)
    wrong_volume["networkVolume"] = {
        "id": "other",
        "name": "wrong",
        "size": 10,
        "dataCenterId": "US-KS-2",
    }
    with pytest.raises(RunPodV2Error, match="volume id mismatch"):
        normalize_v1_pod(wrong_volume, require_machine=True, expected_network_volume=volume())


def test_v1_inventory_requires_array_unique_ids_and_known_statuses() -> None:
    payload = [
        {"id": "pod-a", "name": "a", "desiredStatus": "RUNNING"},
        {"id": "pod-b", "name": "b", "desiredStatus": "EXITED"},
        {"id": "pod-c", "name": "c", "desiredStatus": "TERMINATED"},
    ]
    assert normalize_v1_inventory(payload) == {
        "pods": [
            {"id": "pod-a", "name": "a", "status": "RUNNING"},
            {"id": "pod-b", "name": "b", "status": "EXITED"},
            {"id": "pod-c", "name": "c", "status": "TERMINATED"},
        ]
    }
    with pytest.raises(RunPodV2Error, match="JSON array"):
        normalize_v1_inventory({"pods": []})
    with pytest.raises(RunPodV2Error, match="duplicate"):
        normalize_v1_inventory(
            [
                {"id": "pod-a", "name": "a", "desiredStatus": "RUNNING"},
                {"id": "pod-a", "name": "b", "desiredStatus": "RUNNING"},
            ]
        )
    with pytest.raises(RunPodV2Error, match="unknown"):
        normalize_v1_inventory([{"id": "pod-a", "name": "a", "desiredStatus": "PROVISIONING"}])


class FakeResponse:
    def __init__(self, status: int, payload: object | None = None) -> None:
        self.status = status
        self._raw = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def read(self) -> bytes:
        return self._raw


def test_v1_http_client_uses_fixed_origin_array_list_and_delete_204() -> None:
    value = plan()
    calls = []
    responses = iter(
        [
            FakeResponse(200, [{"id": "pod-123", "name": "x", "desiredStatus": "RUNNING"}]),
            FakeResponse(201, raw_pod(value)),
            FakeResponse(200, raw_pod(value, status="EXITED")),
            FakeResponse(204),
        ]
    )

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        calls.append((request, timeout))
        return next(responses)

    client = RunPodV1HttpClient("secret-token", network_volume=volume(), timeout=3.0, opener=opener)
    assert client.list_pods()["pods"][0]["status"] == "RUNNING"
    created = client.create_pod({"name": "test", "networkVolumeId": "vol_123", "volumeMountPath": "/outputs"})
    assert created["id"] == "pod-123"
    assert created["status"] == "RUNNING"
    assert created["cloud"] == "SECURE"
    observed = client.get_pod("pod-123")
    assert observed["status"] == "EXITED"
    assert observed["networkVolumeId"] == "vol_123"
    client.terminate_pod("pod-123")

    assert [request.full_url for request, _ in calls] == [
        f"{RUNPOD_V1_BASE_URL}/pods",
        f"{RUNPOD_V1_BASE_URL}/pods",
        f"{RUNPOD_V1_BASE_URL}/pods/pod-123?includeMachine=true&includeNetworkVolume=true",
        f"{RUNPOD_V1_BASE_URL}/pods/pod-123",
    ]
    assert [request.get_method() for request, _ in calls] == ["GET", "POST", "GET", "DELETE"]
    assert all(timeout == 3.0 for _, timeout in calls)
    assert all(request.get_header("Authorization") == "Bearer secret-token" for request, _ in calls)


def test_v1_http_errors_do_not_leak_api_key() -> None:
    body = io.BytesIO(json.dumps({"message": "access denied"}).encode("utf-8"))

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        raise HTTPError(request.full_url, 403, "Forbidden", {}, body)

    client = RunPodV1HttpClient("super-secret-api-key", opener=opener)
    with pytest.raises(RunPodV2Error) as exc_info:
        client.get_pod("pod-123")

    message = str(exc_info.value)
    assert "HTTP 403" in message
    assert "access denied" in message
    assert "super-secret-api-key" not in message


def test_v1_bad_pod_identifier_is_rejected_before_network() -> None:
    calls = 0

    def opener(request, timeout):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise AssertionError("network should not be reached")

    client = RunPodV1HttpClient("secret", opener=opener)
    with pytest.raises(RunPodV2Error, match="whitespace"):
        client.get_pod("pod 123")
    assert calls == 0
