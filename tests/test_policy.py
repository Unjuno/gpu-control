from decimal import Decimal

import pytest

from gpu_control.policy import PolicyError, load_policy, validate_against_policy
from gpu_control.validation import WorkloadRequest


SHA = "0123456789abcdef0123456789abcdef01234567"


def request(*, profile: str = "cheap-24gb", runtime: int = 15, cost: str = "0.20") -> WorkloadRequest:
    return WorkloadRequest(
        target_repo="example/model",
        target_sha=SHA,
        dockerfile_path="Dockerfile",
        gpu_profile=profile,
        max_runtime_minutes=runtime,
        max_cost_usd=Decimal(cost),
    )


def test_accepts_request_within_profile_limits() -> None:
    policy = load_policy()
    effective = validate_against_policy(request(), policy)
    assert effective["gpu_count"] == 1
    assert effective["min_vram_gb"] == 24


def test_rejects_unknown_profile() -> None:
    policy = load_policy()
    with pytest.raises(PolicyError, match="unknown gpu_profile"):
        validate_against_policy(request(profile="h100-8x"), policy)


def test_rejects_runtime_above_profile_limit() -> None:
    policy = load_policy()
    with pytest.raises(PolicyError, match="runtime"):
        validate_against_policy(request(runtime=31), policy)


def test_rejects_cost_above_profile_limit() -> None:
    policy = load_policy()
    with pytest.raises(PolicyError, match="cost"):
        validate_against_policy(request(cost="0.31"), policy)


def test_fail_closed_if_gpu_count_policy_is_not_one() -> None:
    policy = load_policy()
    policy["profiles"]["cheap-24gb"]["max_gpu_count"] = 2
    with pytest.raises(PolicyError, match="exactly one"):
        validate_against_policy(request(), policy)
