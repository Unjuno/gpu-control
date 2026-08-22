from decimal import Decimal

import pytest

from gpu_control.execution import ExecutionGateError, build_approved_execution_plan
from gpu_control.policy import load_policy, validate_against_policy
from gpu_control.source import SourceVerificationResult
from gpu_control.validation import build_request


SHA = "0123456789abcdef0123456789abcdef01234567"


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


def make_policy(request):  # type: ignore[no-untyped-def]
    return validate_against_policy(request, load_policy())


def approve(request, **overrides):  # type: ignore[no-untyped-def]
    arguments = {
        "provider": "runpod",
        "verified_hourly_price_usd": "0.34",
        "container_verified": True,
        "dry_run_succeeded": True,
        "cleanup_guaranteed": True,
        "explicit_human_authorization": True,
        "authorization_reference": "workflow_dispatch:12345",
    }
    arguments.update(overrides)
    return build_approved_execution_plan(request, make_policy(request), make_source(), **arguments)


def test_builds_immutable_plan_only_after_all_gates_pass() -> None:
    request = make_request(max_cost_usd="0.10", runtime=15)

    plan = approve(request)

    assert plan.provider == "runpod"
    assert plan.target_repo == "example/model"
    assert plan.target_sha == SHA
    assert plan.gpu_count == 1
    assert plan.max_runtime_minutes == 15
    assert plan.max_cost_usd == Decimal("0.10")
    assert plan.verified_hourly_price_usd == Decimal("0.34")
    assert plan.worst_case_cost_usd == Decimal("0.09")
    assert plan.explicit_human_authorization is True
    assert plan.cleanup_guaranteed is True


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("container_verified", False, "container verification"),
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
            provider="runpod",
            verified_hourly_price_usd="0.34",
            container_verified=True,
            dry_run_succeeded=True,
            cleanup_guaranteed=True,
            explicit_human_authorization=True,
            authorization_reference="workflow_dispatch:12345",
        )


def test_rounds_worst_case_cost_up_to_avoid_underestimating_spend() -> None:
    request = make_request(max_cost_usd="0.08", runtime=15)

    with pytest.raises(ExecutionGateError, match=r"\$0.09"):
        approve(request)


def test_accepts_worst_case_cost_at_exact_requested_limit() -> None:
    request = make_request(max_cost_usd="0.09", runtime=15)

    plan = approve(request)

    assert plan.worst_case_cost_usd == Decimal("0.09")


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity", "abc"])
def test_rejects_unverified_or_invalid_price(price: str) -> None:
    request = make_request()

    with pytest.raises(ExecutionGateError):
        approve(request, verified_hourly_price_usd=price)


def test_rejects_policy_that_does_not_allow_exactly_one_gpu() -> None:
    request = make_request()
    policy = make_policy(request)
    policy["gpu_count"] = 2

    with pytest.raises(ExecutionGateError, match="exactly one GPU"):
        build_approved_execution_plan(
            request,
            policy,
            make_source(),
            provider="runpod",
            verified_hourly_price_usd="0.34",
            container_verified=True,
            dry_run_succeeded=True,
            cleanup_guaranteed=True,
            explicit_human_authorization=True,
            authorization_reference="workflow_dispatch:12345",
        )
