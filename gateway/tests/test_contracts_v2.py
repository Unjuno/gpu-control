from decimal import Decimal

import pytest
from pydantic import ValidationError

from gpu_gateway.contracts import (
    CandidateBinding,
    PlanV2,
    ResultV2,
    plan_fingerprint,
    plan_payload,
    validate_candidate_gpu_success,
    validate_result_binding,
)


def _plan():
    return PlanV2(
        schema_version=2,
        repository="Unjuno/orbitune",
        source_sha="a" * 40,
        workload="cpu-smoke-v1",
        workload_manifest_digest="b" * 64,
        image_digest="sha256:" + "c" * 64,
        parameters={"iterations": 3},
        provider="local_cpu",
        device_requirement={"kind": "cpu", "gpu_required": False},
        runtime_seconds=30,
        max_cost_usd=Decimal("0"),
        cost_evidence={
            "classification": "LOCAL", "additional_cost_usd": Decimal("0"),
            "reference": "operator-local-cpu-policy-v1", "observed_at": 100,
            "expires_at": 200,
        },
        authorization_policy_version="local-cpu-v1",
    )


def _result(plan, fingerprint):
    return ResultV2(
        schema_version=2, run_id="d" * 32, source_sha=plan.source_sha,
        plan_fingerprint=fingerprint, provider="local_cpu", image_digest=plan.image_digest,
        simulation=False,
        gpu_used=False, device="cpu", exit_code=0, started_at=110,
        finished_at=111, runtime_seconds=1.0, metrics={"checksum": 42},
        artifacts=[], known_cost_usd=Decimal("0"), cost_classification="LOCAL",
        cleanup_state="complete",
    )


def test_v2_plan_fingerprint_and_result_identity_are_stable():
    plan = _plan()
    fingerprint = plan_fingerprint(plan)
    assert fingerprint == plan_fingerprint(_plan())
    result = _result(plan, fingerprint)
    validate_result_binding(plan, fingerprint, result)


def test_plan_v2_round_trips_through_json_storage():
    plan = _plan()
    restored = PlanV2.model_validate_json(plan.model_dump_json())
    assert restored == plan
    assert plan_fingerprint(restored) == plan_fingerprint(plan)


def test_selection_binding_is_persisted_and_changes_the_approved_plan_fingerprint():
    base = _plan()
    binding = CandidateBinding(
        workload_fingerprint="sha256:" + "d" * 64,
        provider="modal",
        resource_id="gpu-a10-nyc-01",
        evidence_fingerprint="sha256:" + "e" * 64,
    )
    approved = base.model_copy(update={
        "provider": "modal",
        "selection_binding": binding,
    })
    restored = PlanV2.model_validate_json(approved.model_dump_json())

    assert restored.selection_binding == binding
    assert plan_fingerprint(restored) != plan_fingerprint(base)
    assert plan_fingerprint(restored.model_copy(update={
        "selection_binding": binding.model_copy(update={"evidence_fingerprint": "sha256:" + "f" * 64})
    })) != plan_fingerprint(restored)


def test_selection_binding_requires_provider_match_and_strict_fields():
    with pytest.raises(ValidationError):
        CandidateBinding(
            workload_fingerprint="sha256:" + "d" * 64,
            provider="Modal",
            resource_id="gpu-a10-nyc-01",
            evidence_fingerprint="sha256:" + "e" * 64,
        )
    with pytest.raises(ValidationError):
        CandidateBinding(
            workload_fingerprint="sha256:" + "d" * 64,
            provider="modal",
            resource_id="gpu-a10-nyc-01",
            evidence_fingerprint="sha256:" + "e" * 64,
            quota_remaining="999",
        )

    data = _plan().model_dump()
    data["selection_binding"] = {
        "workload_fingerprint": "sha256:" + "d" * 64,
        "provider": "modal",
        "resource_id": "gpu-a10-nyc-01",
        "evidence_fingerprint": "sha256:" + "e" * 64,
    }
    with pytest.raises(ValidationError, match="provider does not match"):
        PlanV2.model_validate(data)


def test_legacy_plan_without_selection_binding_keeps_its_canonical_fingerprint():
    import hashlib
    import json

    legacy_payload = _plan().model_dump(mode="json")
    legacy_payload.pop("selection_binding", None)
    canonical = json.dumps(legacy_payload, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode()
    expected = hashlib.sha256(canonical).hexdigest()

    legacy_plan = PlanV2.model_validate_json(json.dumps(legacy_payload))
    assert plan_fingerprint(legacy_plan) == expected
    assert plan_payload(legacy_plan) == legacy_payload


def test_result_v2_preserves_smoke_checks_and_checksum():
    plan = _plan()
    result = _result(plan, plan_fingerprint(plan)).model_dump()
    result["checks"] = ["iterations_completed", "checksum_verified"]
    result["checksum"] = "d" * 64
    validated = ResultV2.model_validate(result)
    assert validated.checks == result["checks"]
    assert validated.checksum == result["checksum"]


def test_result_checks_are_bounded_ascii_tokens():
    plan = _plan()
    result = _result(plan, plan_fingerprint(plan)).model_dump()
    result["checks"] = ["x" * 65]
    with pytest.raises(ValidationError):
        ResultV2.model_validate(result)


def test_candidate_gpu_success_requires_device_and_resource_verification():
    plan = _plan()
    result = _result(plan, plan_fingerprint(plan))
    with pytest.raises(ValueError, match="verified GPU and cleanup evidence"):
        validate_candidate_gpu_success(result)

    verified = result.model_copy(update={
        "gpu_used": True,
        "device": "NVIDIA A10",
        "checks": ["candidate_resource_verified", "device_identity_verified"],
    })
    validate_candidate_gpu_success(verified)
    unclean = verified.model_copy(update={"cleanup_state": "unknown"})
    with pytest.raises(ValueError, match="cleanup evidence"):
        validate_candidate_gpu_success(unclean)


@pytest.mark.parametrize("field,value", [
    ("source_sha", "A" * 40),
    ("max_cost_usd", Decimal("NaN")),
    ("max_cost_usd", Decimal("-0.01")),
    ("schema_version", 1),
])
def test_plan_rejects_noncanonical_or_invalid_identity(field, value):
    data = _plan().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        PlanV2.model_validate(data)


@pytest.mark.parametrize("metrics", [{"loss": float("nan")}, {"loss": True}, {"日本語": 1}])
def test_result_rejects_nonfinite_boolean_or_non_ascii_metrics(metrics):
    plan = _plan()
    fingerprint = plan_fingerprint(plan)
    data = _result(plan, fingerprint).model_dump()
    data["metrics"] = metrics
    with pytest.raises(ValidationError):
        ResultV2.model_validate(data)


def test_result_cannot_claim_different_source_or_fingerprint():
    plan = _plan()
    fingerprint = plan_fingerprint(plan)
    result = _result(plan, fingerprint).model_copy(update={"source_sha": "e" * 40})
    with pytest.raises(ValueError, match="does not match"):
        validate_result_binding(plan, fingerprint, result)
    result = _result(plan, "f" * 64)
    with pytest.raises(ValueError, match="does not match"):
        validate_result_binding(plan, fingerprint, result)
    result = _result(plan, fingerprint).model_copy(update={"image_digest": "sha256:" + "e" * 64})
    with pytest.raises(ValueError, match="does not match"):
        validate_result_binding(plan, fingerprint, result)
    result = _result(plan, fingerprint).model_copy(update={"image_digest": None})
    with pytest.raises(ValueError, match="does not match"):
        validate_result_binding(plan, fingerprint, result)


def test_result_provider_and_image_are_bound_for_non_cpu_plans():
    plan = _plan().model_copy(update={"provider": "modal"})
    fingerprint = plan_fingerprint(plan)
    result = _result(plan, fingerprint).model_copy(update={"provider": "modal"})
    validate_result_binding(plan, fingerprint, result)

    for changes in (
        {"provider": "runpod"},
        {"image_digest": "sha256:" + "e" * 64},
        {"image_digest": None},
    ):
        mismatched = result.model_copy(update=changes)
        with pytest.raises(ValueError, match="does not match"):
            validate_result_binding(plan, fingerprint, mismatched)


def test_unknown_result_fields_are_rejected():
    plan = _plan()
    fingerprint = plan_fingerprint(plan)
    data = _result(plan, fingerprint).model_dump()
    data["provider_secret"] = "must-not-be-serialized"
    with pytest.raises(ValidationError):
        ResultV2.model_validate(data)
