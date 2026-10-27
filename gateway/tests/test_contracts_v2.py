from decimal import Decimal

import pytest
from pydantic import ValidationError

from gpu_gateway.contracts import PlanV2, ResultV2, plan_fingerprint, validate_result_binding


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
        plan_fingerprint=fingerprint, provider="local_cpu", simulation=False,
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


def test_unknown_result_fields_are_rejected():
    plan = _plan()
    fingerprint = plan_fingerprint(plan)
    data = _result(plan, fingerprint).model_dump()
    data["provider_secret"] = "must-not-be-serialized"
    with pytest.raises(ValidationError):
        ResultV2.model_validate(data)
