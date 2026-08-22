from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gpu_control.execution import ApprovedExecutionPlan
from gpu_control.providers.runpod_pricing import (
    RunPodCatalogPricingEvidence,
    build_catalog_pricing_evidence,
    build_priced_create_pod_payload,
    validate_created_pod_with_pricing,
)
from gpu_control.providers.runpod_v2 import PublishedImageEvidence, RunPodV2Error
from gpu_control.validation import build_request


DIGEST = "sha256:" + "a" * 64
VERIFIED_AT = datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc)


def catalog(**overrides):  # type: ignore[no-untyped-def]
    gpu = {
        "id": "NVIDIA GeForce RTX 4090",
        "name": "RTX 4090",
        "memory": 24,
        "secure": True,
        "community": True,
        "price": {"secure": 0.44, "community": 0.31},
        "maxCount": {"secure": 8, "community": 4},
        "availability": "HIGH",
        "dataCenters": [{"id": "US-KS-2", "availability": "HIGH"}],
    }
    gpu.update(overrides)
    return {"gpus": [gpu]}


def request_and_policy():  # type: ignore[no-untyped-def]
    request = build_request(
        target_repo="example/model",
        target_sha="0123456789abcdef0123456789abcdef01234567",
        dockerfile_path="Dockerfile",
        gpu_profile="cheap-24gb",
        max_runtime_minutes=15,
        max_cost_usd="0.20",
    )
    policy = {
        "profile": "cheap-24gb",
        "min_vram_gb": 24,
        "gpu_count": 1,
        "max_runtime_minutes": 30,
        "max_cost_usd": "0.30",
    }
    return request, policy


def build_evidence(cloud: str = "SECURE") -> RunPodCatalogPricingEvidence:
    request, policy = request_and_policy()
    return build_catalog_pricing_evidence(
        catalog(),
        request,
        policy,
        gpu_type_id="NVIDIA GeForce RTX 4090",
        cloud=cloud,
        verified_at_utc=VERIFIED_AT,
        validity_seconds=120,
    )


def make_plan(evidence: RunPodCatalogPricingEvidence | None = None, **overrides) -> ApprovedExecutionPlan:  # type: ignore[no-untyped-def]
    evidence = evidence or build_evidence()
    values = {
        "provider": "runpod",
        "provider_resource_id": evidence.gpu_type_id,
        "target_repo": "example/model",
        "target_sha": "0123456789abcdef0123456789abcdef01234567",
        "dockerfile_path": "Dockerfile",
        "image_digest": DIGEST,
        "container_verification_reference": "actions-run:100/container",
        "gpu_profile": evidence.gpu_profile,
        "gpu_count": 1,
        "max_runtime_minutes": 15,
        "max_cost_usd": Decimal("0.20"),
        "verified_hourly_price_usd": evidence.hourly_price_usd,
        "pricing_verification_reference": evidence.verification_reference,
        "pricing_verified_at_utc": evidence.verified_at_utc,
        "pricing_valid_until_utc": evidence.valid_until_utc,
        "worst_case_cost_usd": Decimal("0.11") if evidence.hourly_price_usd == Decimal("0.44") else Decimal("0.08"),
        "authorization_reference": "workflow_dispatch:100",
    }
    values.update(overrides)
    plan = ApprovedExecutionPlan(**values)
    plan.validate_shape()
    return plan


def image_for(plan: ApprovedExecutionPlan) -> PublishedImageEvidence:
    return PublishedImageEvidence(
        plan_fingerprint=plan.fingerprint(),
        image_reference=f"ghcr.io/example/model@{DIGEST}",
        image_digest=DIGEST,
        verification_reference="registry-publish:100",
    )


def test_catalog_row_becomes_short_lived_structured_pricing_evidence() -> None:
    evidence = build_evidence()
    result = evidence.to_pricing_result()

    assert evidence.cloud == "SECURE"
    assert evidence.memory_gb == 24
    assert evidence.hourly_price_usd == Decimal("0.44")
    assert evidence.availability == "HIGH"
    assert evidence.verification_reference.startswith("runpod-v2-catalog:sha256:")
    assert evidence.verified_at_utc == "2026-08-22T16:00:00Z"
    assert evidence.valid_until_utc == "2026-08-22T16:02:00Z"

    assert result.provider == "runpod"
    assert result.gpu_profile == "cheap-24gb"
    assert result.provider_resource_id == "NVIDIA GeForce RTX 4090"
    assert result.hourly_price_usd == Decimal("0.44")
    assert result.price_verified is True
    assert result.availability_verified is True


def test_cloud_is_part_of_price_identity() -> None:
    secure = build_evidence("SECURE")
    community = build_evidence("COMMUNITY")

    assert secure.hourly_price_usd == Decimal("0.44")
    assert community.hourly_price_usd == Decimal("0.31")
    assert secure.verification_reference != community.verification_reference


def test_catalog_evidence_fails_closed_on_vram_capacity_and_availability() -> None:
    request, policy = request_and_policy()

    with pytest.raises(RunPodV2Error, match="memory"):
        build_catalog_pricing_evidence(
            catalog(memory=16), request, policy,
            gpu_type_id="NVIDIA GeForce RTX 4090", cloud="SECURE", verified_at_utc=VERIFIED_AT,
        )

    with pytest.raises(RunPodV2Error, match="HIGH catalog availability"):
        build_catalog_pricing_evidence(
            catalog(availability="LOW"), request, policy,
            gpu_type_id="NVIDIA GeForce RTX 4090", cloud="SECURE", verified_at_utc=VERIFIED_AT,
        )

    with pytest.raises(RunPodV2Error, match="no one-GPU capacity"):
        build_catalog_pricing_evidence(
            catalog(maxCount={"secure": 0, "community": 4}), request, policy,
            gpu_type_id="NVIDIA GeForce RTX 4090", cloud="SECURE", verified_at_utc=VERIFIED_AT,
        )

    with pytest.raises(RunPodV2Error, match="no HIGH-availability data center"):
        build_catalog_pricing_evidence(
            catalog(dataCenters=[{"id": "US-KS-2", "availability": "LOW"}]), request, policy,
            gpu_type_id="NVIDIA GeForce RTX 4090", cloud="SECURE", verified_at_utc=VERIFIED_AT,
        )


def test_pricing_ttl_is_bounded_to_five_minutes() -> None:
    request, policy = request_and_policy()

    with pytest.raises(RunPodV2Error, match="between 1 and 300"):
        build_catalog_pricing_evidence(
            catalog(), request, policy,
            gpu_type_id="NVIDIA GeForce RTX 4090", cloud="SECURE", verified_at_utc=VERIFIED_AT,
            validity_seconds=301,
        )


def test_create_payload_cloud_must_come_from_same_catalog_evidence_as_plan() -> None:
    evidence = build_evidence("SECURE")
    plan = make_plan(evidence)
    payload = build_priced_create_pod_payload(plan, image_for(plan), evidence)

    assert payload["cloud"] == "SECURE"
    assert payload["gpu"] == {"id": evidence.gpu_type_id, "count": 1}

    community = build_evidence("COMMUNITY")
    with pytest.raises(RunPodV2Error, match="price does not match"):
        build_priced_create_pod_payload(plan, image_for(plan), community)


def test_create_response_cloud_is_revalidated() -> None:
    evidence = build_evidence("SECURE")
    plan = make_plan(evidence)
    image = image_for(plan)
    pod = {
        "id": "pod-123",
        "image": image.image_reference,
        "gpu": {"id": evidence.gpu_type_id, "count": 1},
        "cloud": "SECURE",
        "cost": 0.44,
        "status": "PROVISIONING",
    }

    assert validate_created_pod_with_pricing(plan, image, evidence, pod) == "pod-123"

    wrong_cloud = dict(pod, cloud="COMMUNITY")
    with pytest.raises(RunPodV2Error, match="cloud does not match"):
        validate_created_pod_with_pricing(plan, image, evidence, wrong_cloud)
