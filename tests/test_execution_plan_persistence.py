from dataclasses import replace
from decimal import Decimal
import json

import pytest

from gpu_control.execution import ApprovedExecutionPlan, ExecutionGateError


SHA = "0123456789abcdef0123456789abcdef01234567"
IMAGE_DIGEST = "sha256:" + "a" * 64


def make_plan() -> ApprovedExecutionPlan:
    return ApprovedExecutionPlan(
        provider="runpod",
        provider_resource_id="synthetic-offer-3090",
        target_repo="example/model",
        target_sha=SHA,
        dockerfile_path="Dockerfile",
        image_digest=IMAGE_DIGEST,
        container_verification_reference="actions-run:100/container",
        gpu_profile="cheap-24gb",
        gpu_count=1,
        max_runtime_minutes=15,
        max_cost_usd=Decimal("0.10"),
        verified_hourly_price_usd=Decimal("0.34"),
        pricing_verification_reference="pricing-check:100",
        pricing_verified_at_utc="2026-08-22T15:55:00Z",
        pricing_valid_until_utc="2026-08-22T16:05:00Z",
        worst_case_cost_usd=Decimal("0.09"),
        authorization_reference="workflow_dispatch:100",
    )


def test_approved_plan_json_round_trip_with_expected_fingerprint() -> None:
    plan = make_plan()
    plan.validate_shape()

    restored = ApprovedExecutionPlan.from_json(
        plan.canonical_json(),
        expected_fingerprint=plan.fingerprint(),
    )

    assert restored == plan
    assert restored.canonical_json() == plan.canonical_json()
    assert restored.fingerprint() == plan.fingerprint()


def test_expected_fingerprint_is_required_to_match_trusted_identity() -> None:
    plan = make_plan()

    with pytest.raises(ExecutionGateError, match="does not match expected fingerprint"):
        ApprovedExecutionPlan.from_json(
            plan.canonical_json(),
            expected_fingerprint="sha256:" + "f" * 64,
        )

    with pytest.raises(ExecutionGateError, match="expected plan fingerprint"):
        plan.validate_expected_fingerprint("not-a-fingerprint")


def test_plan_parser_rejects_unknown_missing_and_duplicate_fields() -> None:
    plan = make_plan()
    payload = plan.to_dict()

    unknown = dict(payload)
    unknown["unexpected"] = True
    with pytest.raises(ExecutionGateError, match="unknown fields"):
        ApprovedExecutionPlan.from_json(json.dumps(unknown))

    missing = dict(payload)
    del missing["image_digest"]
    with pytest.raises(ExecutionGateError, match="missing fields"):
        ApprovedExecutionPlan.from_json(json.dumps(missing))

    duplicate = plan.canonical_json().replace(
        '"provider":"runpod"',
        '"provider":"runpod","provider":"other"',
    )
    with pytest.raises(ExecutionGateError, match="duplicate field: provider"):
        ApprovedExecutionPlan.from_json(duplicate)


def test_money_fields_must_be_decimal_strings_not_json_numbers() -> None:
    for field in ("max_cost_usd", "verified_hourly_price_usd", "worst_case_cost_usd"):
        payload = make_plan().to_dict()
        payload[field] = 0.1
        with pytest.raises(ExecutionGateError, match="decimal string"):
            ApprovedExecutionPlan.from_json(json.dumps(payload))


def test_plan_requires_canonical_source_and_image_identity() -> None:
    cases = [
        ("target_repo", "bad repo", "owner/repository"),
        ("target_sha", "A" * 40, "lowercase canonical"),
        ("dockerfile_path", "a//Dockerfile", "not canonical"),
        ("gpu_profile", "Cheap GPU", "unsupported characters"),
        ("image_digest", "sha256:" + "A" * 64, "image_digest"),
    ]

    for field, value, message in cases:
        plan = replace(make_plan(), **{field: value})
        with pytest.raises(ExecutionGateError, match=message):
            plan.validate_shape()


def test_plan_rejects_false_or_non_boolean_gate_evidence() -> None:
    for field in (
        "source_verified",
        "container_verified",
        "pricing_verified",
        "dry_run_succeeded",
        "cleanup_guaranteed",
        "explicit_human_authorization",
    ):
        plan = replace(make_plan(), **{field: False})
        with pytest.raises(ExecutionGateError, match=field):
            plan.validate_shape()

    payload = make_plan().to_dict()
    payload["source_verified"] = 1
    with pytest.raises(ExecutionGateError, match="source_verified must be a boolean"):
        ApprovedExecutionPlan.from_json(json.dumps(payload))


def test_plan_recomputes_worst_case_cost_instead_of_trusting_serialized_value() -> None:
    plan = replace(make_plan(), worst_case_cost_usd=Decimal("0.08"))

    with pytest.raises(ExecutionGateError, match="does not match verified price and runtime"):
        plan.validate_shape()


def test_plan_rejects_cost_above_requested_ceiling() -> None:
    plan = replace(
        make_plan(),
        max_cost_usd=Decimal("0.08"),
        worst_case_cost_usd=Decimal("0.09"),
    )

    with pytest.raises(ExecutionGateError, match="exceeds max_cost_usd"):
        plan.validate_shape()


def test_plan_requires_valid_pricing_window() -> None:
    plan = replace(
        make_plan(),
        pricing_verified_at_utc="2026-08-22T16:05:00Z",
        pricing_valid_until_utc="2026-08-22T16:05:00Z",
    )
    with pytest.raises(ExecutionGateError, match="must be after"):
        plan.validate_shape()

    non_utc = replace(make_plan(), pricing_verified_at_utc="2026-08-22T15:55:00")
    with pytest.raises(ExecutionGateError, match="timezone-aware UTC"):
        non_utc.validate_shape()


def test_plan_requires_exactly_one_gpu_and_positive_runtime() -> None:
    for field, value, message in [
        ("gpu_count", 2, "exactly one GPU"),
        ("gpu_count", True, "exactly one GPU"),
        ("max_runtime_minutes", 0, "positive integer"),
        ("max_runtime_minutes", True, "positive integer"),
    ]:
        plan = replace(make_plan(), **{field: value})
        with pytest.raises(ExecutionGateError, match=message):
            plan.validate_shape()
