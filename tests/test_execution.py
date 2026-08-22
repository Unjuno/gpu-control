from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

import pytest

from gpu_control.container import ContainerVerificationResult
from gpu_control.execution import ExecutionGateError, build_approved_execution_plan
from gpu_control.policy import load_policy, validate_against_policy
from gpu_control.pricing import PricingVerificationResult
from gpu_control.source import SourceVerificationResult
from gpu_control.validation import build_request


SHA = "0123456789abcdef0123456789abcdef01234567"
IMAGE_DIGEST = "sha256:" + "a" * 64
DECISION_TIME = datetime(2026, 8, 22, 16, 5, tzinfo=timezone.utc)


def make_request(*, max_cost_usd: str = "0.10", runtime: int = 15):
    return build_request(
        target_repo="example/model",
        target_sha=SHA,
        dockerfile_path="Dockerfile",
        gpu_profile="cheap-24gb",
        max_runtime_minutes=runtime,
        max_cost_usd=max_cost_usd,
    )


def make_source():
    return SourceVerificationResult(
        repository="example/model",
        commit_sha=SHA,
        dockerfile_path="Dockerfile",
        repository_public=True,
        commit_verified=True,
        dockerfile_verified=True,
    )


def make_container(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "repository": "example/model",
        "commit_sha": SHA,
        "dockerfile_path": "Dockerfile",
        "image_digest": IMAGE_DIGEST,
        "verification_reference": "actions-run:98765/container-verification",
        "build_isolated": True,
        "runtime_isolated": True,
        "smoke_test_passed": True,
        "output_contract_verified": True,
        "credentials_absent": True,
        "network_policy_enforced": True,
        "resource_limits_enforced": True,
    }
    values.update(overrides)
    return ContainerVerificationResult(**values)


def make_pricing(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "provider": "runpod",
        "gpu_profile": "cheap-24gb",
        "provider_resource_id": "synthetic-offer-3090",
        "hourly_price_usd": Decimal("0.34"),
        "verification_reference": "pricing-check:synthetic-123",
        "verified_at_utc": "2026-08-22T16:00:00Z",
        "valid_until_utc": "2026-08-22T16:15:00Z",
        "price_verified": True,
        "availability_verified": True,
    }
    values.update(overrides)
    return PricingVerificationResult(**values)


def make_policy(request):  # type: ignore[no-untyped-def]
    return validate_against_policy(request, load_policy())


def approve(request, **overrides):  # type: ignore[no-untyped-def]
    container = overrides.pop("container", make_container())
    pricing = overrides.pop("pricing", make_pricing())
    arguments = {
        "dry_run_succeeded": True,
        "cleanup_guaranteed": True,
        "explicit_human_authorization": True,
        "authorization_reference": "workflow_dispatch:12345",
        "decision_time_utc": DECISION_TIME,
    }
    arguments.update(overrides)
    return build_approved_execution_plan(
        request,
        make_policy(request),
        make_source(),
        container,
        pricing,
        **arguments,
    )


def test_builds_immutable_plan_only_after_all_gates_pass() -> None:
    request = make_request(max_cost_usd="0.10", runtime=15)

    plan = approve(request)

    assert plan.provider == "runpod"
    assert plan.provider_resource_id == "synthetic-offer-3090"
    assert plan.target_repo == "example/model"
    assert plan.target_sha == SHA
    assert plan.image_digest == IMAGE_DIGEST
    assert plan.container_verification_reference == "actions-run:98765/container-verification"
    assert plan.gpu_count == 1
    assert plan.max_runtime_minutes == 15
    assert plan.max_cost_usd == Decimal("0.10")
    assert plan.verified_hourly_price_usd == Decimal("0.34")
    assert plan.pricing_verification_reference == "pricing-check:synthetic-123"
    assert plan.pricing_verified_at_utc == "2026-08-22T16:00:00Z"
    assert plan.pricing_valid_until_utc == "2026-08-22T16:15:00Z"
    assert plan.worst_case_cost_usd == Decimal("0.09")
    assert plan.container_verified is True
    assert plan.pricing_verified is True
    assert plan.explicit_human_authorization is True
    assert plan.cleanup_guaranteed is True
    assert plan.schema_version == 1


def test_plan_serialization_is_canonical_and_json_compatible() -> None:
    plan = approve(make_request())

    payload = plan.to_dict()
    canonical = plan.canonical_json()

    assert payload["schema_version"] == 1
    assert payload["max_cost_usd"] == "0.10"
    assert payload["verified_hourly_price_usd"] == "0.34"
    assert payload["worst_case_cost_usd"] == "0.09"
    assert json.loads(canonical) == payload
    assert canonical == json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def test_plan_fingerprint_is_stable_content_identity_not_authorization() -> None:
    plan = approve(make_request())
    canonical = plan.canonical_json()
    expected = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    assert plan.fingerprint() == expected
    assert plan.fingerprint() == plan.fingerprint()

    changed = replace(plan, pricing_verification_reference="pricing-check:other")
    assert changed.fingerprint() != plan.fingerprint()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dry_run_succeeded", False, "dry-run"),
        ("cleanup_guaranteed", False, "cleanup"),
        ("explicit_human_authorization", False, "human authorization"),
        ("authorization_reference", "", "authorization_reference"),
    ],
)
def test_rejects_missing_paid_compute_precondition(field: str, value: object, message: str) -> None:
    request = make_request()

    with pytest.raises(ExecutionGateError, match=message):
        approve(request, **{field: value})


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("build_isolated", "isolated container build"),
        ("runtime_isolated", "isolated container runtime"),
        ("smoke_test_passed", "container smoke test"),
        ("output_contract_verified", "container output contract"),
        ("credentials_absent", "container credential isolation"),
        ("network_policy_enforced", "container network policy"),
        ("resource_limits_enforced", "container resource limits"),
    ],
)
def test_rejects_partial_container_verification(field: str, message: str) -> None:
    request = make_request()
    container = replace(make_container(), **{field: False})

    with pytest.raises(ExecutionGateError, match=message):
        approve(request, container=container)


def test_rejects_source_identity_mismatch() -> None:
    request = make_request()
    source = make_source()
    mismatched = SourceVerificationResult(
        repository=source.repository,
        commit_sha="f" * 40,
        dockerfile_path=source.dockerfile_path,
        repository_public=True,
        commit_verified=True,
        dockerfile_verified=True,
    )

    with pytest.raises(ExecutionGateError, match="verified commit"):
        build_approved_execution_plan(
            request,
            make_policy(request),
            mismatched,
            make_container(),
            make_pricing(),
            dry_run_succeeded=True,
            cleanup_guaranteed=True,
            explicit_human_authorization=True,
            authorization_reference="workflow_dispatch:12345",
            decision_time_utc=DECISION_TIME,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("repository", "example/other", "container repository identity"),
        ("commit_sha", "f" * 40, "container commit identity"),
        ("dockerfile_path", "containers/Dockerfile", "container Dockerfile identity"),
    ],
)
def test_rejects_container_identity_mismatch(field: str, value: str, message: str) -> None:
    request = make_request()
    container = replace(make_container(), **{field: value})

    with pytest.raises(ExecutionGateError, match=message):
        approve(request, container=container)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("image_digest", "latest", "image_digest"),
        ("image_digest", "sha256:" + "A" * 64, "image_digest"),
        ("verification_reference", "", "verification_reference"),
    ],
)
def test_rejects_malformed_container_evidence(field: str, value: str, message: str) -> None:
    request = make_request()
    container = replace(make_container(), **{field: value})

    with pytest.raises(ExecutionGateError, match=message):
        approve(request, container=container)


@pytest.mark.parametrize(
    ("pricing", "message"),
    [
        (make_pricing(gpu_profile="large-vram"), "pricing gpu_profile"),
        (make_pricing(price_verified=False), "price verification"),
        (make_pricing(availability_verified=False), "availability"),
        (make_pricing(provider_resource_id=""), "provider_resource_id"),
        (make_pricing(verification_reference=""), "pricing verification_reference"),
        (make_pricing(hourly_price_usd=Decimal("0")), "hourly_price_usd"),
        (make_pricing(hourly_price_usd=Decimal("NaN")), "hourly_price_usd"),
        (make_pricing(valid_until_utc="2026-08-22T16:00:00Z"), "valid_until_utc"),
    ],
)
def test_rejects_invalid_pricing_evidence(pricing: PricingVerificationResult, message: str) -> None:
    with pytest.raises(ExecutionGateError, match=message):
        approve(make_request(), pricing=pricing)


def test_rejects_expired_pricing_evidence() -> None:
    pricing = make_pricing(valid_until_utc="2026-08-22T16:05:00Z")

    with pytest.raises(ExecutionGateError, match="expired"):
        approve(make_request(), pricing=pricing)


def test_rejects_pricing_evidence_from_future_relative_to_decision() -> None:
    pricing = make_pricing(verified_at_utc="2026-08-22T16:06:00Z", valid_until_utc="2026-08-22T16:20:00Z")

    with pytest.raises(ExecutionGateError, match="newer than"):
        approve(make_request(), pricing=pricing)


def test_rejects_non_utc_decision_time() -> None:
    decision_time = datetime(2026, 8, 22, 16, 5)

    with pytest.raises(ExecutionGateError, match="timezone-aware UTC"):
        approve(make_request(), decision_time_utc=decision_time)


def test_rounds_worst_case_cost_up_to_avoid_underestimating_spend() -> None:
    request = make_request(max_cost_usd="0.08", runtime=15)

    with pytest.raises(ExecutionGateError, match=r"\$0.09"):
        approve(request)


def test_accepts_worst_case_cost_at_exact_requested_limit() -> None:
    request = make_request(max_cost_usd="0.09", runtime=15)

    plan = approve(request)

    assert plan.worst_case_cost_usd == Decimal("0.09")


def test_rejects_policy_that_does_not_allow_exactly_one_gpu() -> None:
    request = make_request()
    policy = make_policy(request)
    policy["gpu_count"] = 2

    with pytest.raises(ExecutionGateError, match="exactly one GPU"):
        build_approved_execution_plan(
            request,
            policy,
            make_source(),
            make_container(),
            make_pricing(),
            dry_run_succeeded=True,
            cleanup_guaranteed=True,
            explicit_human_authorization=True,
            authorization_reference="workflow_dispatch:12345",
            decision_time_utc=DECISION_TIME,
        )
