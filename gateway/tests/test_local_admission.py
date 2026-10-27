from decimal import Decimal

from gpu_gateway.admission import evaluate_admission
from gpu_gateway.contracts import CostEvidence, PlanV2


def plan(**overrides):
    value = {
        "schema_version": 2,
        "repository": "Unjuno/gpu-control",
        "source_sha": "a" * 40,
        "workload": "cpu-smoke-v1",
        "workload_manifest_digest": "b" * 64,
        "image_digest": "sha256:" + "c" * 64,
        "parameters": {},
        "provider": "local_cpu",
        "device_requirement": {"kind": "cpu", "requires_gpu": False, "profile": "smoke"},
        "runtime_seconds": 20,
        "max_cost_usd": Decimal("0"),
        "cost_evidence": CostEvidence(
            classification="LOCAL", additional_cost_usd=Decimal("0"),
            reference="operator-confirmed-no-provider-charge", observed_at=100,
            expires_at=200,
        ),
        "authorization_policy_version": "local-cpu-v1",
    }
    value.update(overrides)
    return PlanV2.model_validate(value)


def policy(**overrides):
    value = {
        "version": "local-cpu-v1",
        "enabled": True,
        "valid_until": 180,
        "workloads": ["cpu-smoke-v1"],
        "max_runtime_seconds": 30,
        "max_cost_usd": "0.00",
        "allowed_profiles": ["smoke"],
    }
    value.update(overrides)
    return value


def test_zero_cap_local_cpu_only():
    decision = evaluate_admission(plan(), policy(), now=120)
    assert decision.allowed is True
    assert decision.approval_required is False
    assert decision.blocking_reason is None
    assert decision.valid_until == 180


def test_paid_provider_cannot_reuse_zero_cost_local_policy():
    paid = plan(provider="modal", cost_evidence=CostEvidence(
        classification="FREE", additional_cost_usd=Decimal("0"), reference="free",
        observed_at=100, expires_at=200))
    decision = evaluate_admission(paid, policy(), now=120)
    assert decision.allowed is False
    assert decision.blocking_reason == "PROVIDER_NOT_LOCAL_CPU"


def test_policy_revocation_and_expiry_block_admission():
    assert evaluate_admission(plan(), policy(enabled=False), now=120).blocking_reason == "POLICY_DISABLED"
    assert evaluate_admission(plan(), policy(), now=181).blocking_reason == "POLICY_EXPIRED"


def test_gpu_and_non_smoke_profiles_are_not_preapproved():
    gpu = plan(device_requirement={"kind": "gpu", "requires_gpu": True, "profile": "smoke"})
    high_impact = plan(device_requirement={"kind": "cpu", "requires_gpu": False, "profile": "training"})
    assert evaluate_admission(gpu, policy(), now=120).blocking_reason == "GPU_NOT_ALLOWED"
    assert evaluate_admission(high_impact, policy(), now=120).blocking_reason == "PROFILE_NOT_ALLOWED"


def test_cost_and_workload_must_match_explicit_free_policy():
    charged = plan(max_cost_usd=Decimal("0.01"))
    assert evaluate_admission(charged, policy(), now=120).blocking_reason == "NONZERO_COST_CAP"
    unknown_cost = plan(cost_evidence=CostEvidence(
        classification="UNKNOWN", additional_cost_usd=None, reference="", observed_at=None, expires_at=None))
    assert evaluate_admission(unknown_cost, policy(), now=120).blocking_reason == "COST_NOT_VERIFIED_FREE"
    other_workload = plan(workload="arbitrary")
    assert evaluate_admission(other_workload, policy(), now=120).blocking_reason == "WORKLOAD_NOT_ALLOWLISTED"


def test_admission_binds_policy_version_and_runtime_ceiling():
    mismatched = plan(authorization_policy_version="local-cpu-v0")
    too_long = plan(runtime_seconds=31)
    assert evaluate_admission(mismatched, policy(), now=120).blocking_reason == "POLICY_VERSION_MISMATCH"
    assert evaluate_admission(too_long, policy(), now=120).blocking_reason == "RUNTIME_LIMIT"


def test_malformed_policy_fails_closed():
    decision = evaluate_admission(plan(), {"enabled": True}, now=120)
    assert decision.allowed is False
    assert decision.blocking_reason == "INVALID_POLICY"
