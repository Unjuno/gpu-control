from decimal import Decimal

import pytest

from gpu_control.validation import ValidationError, build_request


VALID_SHA = "0123456789abcdef0123456789abcdef01234567"


def test_build_request_accepts_valid_public_workload() -> None:
    request = build_request(
        target_repo="example/model-a",
        target_sha=VALID_SHA,
        dockerfile_path="containers/Dockerfile",
        gpu_profile="cheap-24gb",
        max_runtime_minutes="15",
        max_cost_usd="0.20",
    )
    assert request.target_repo == "example/model-a"
    assert request.target_sha == VALID_SHA
    assert request.max_runtime_minutes == 15
    assert request.max_cost_usd == Decimal("0.20")


@pytest.mark.parametrize(
    "target_repo",
    [
        "example",
        "example/model;curl",
        "example/model $(id)",
        "https://github.com/example/model",
        "../example/model",
    ],
)
def test_rejects_malformed_repository(target_repo: str) -> None:
    with pytest.raises(ValidationError):
        build_request(
            target_repo=target_repo,
            target_sha=VALID_SHA,
            dockerfile_path="Dockerfile",
            gpu_profile="cheap-24gb",
            max_runtime_minutes=15,
            max_cost_usd="0.20",
        )


@pytest.mark.parametrize("target_sha", ["main", "abc123", "g" * 40, VALID_SHA + "0"])
def test_requires_full_commit_sha(target_sha: str) -> None:
    with pytest.raises(ValidationError):
        build_request(
            target_repo="example/model",
            target_sha=target_sha,
            dockerfile_path="Dockerfile",
            gpu_profile="cheap-24gb",
            max_runtime_minutes=15,
            max_cost_usd="0.20",
        )


@pytest.mark.parametrize(
    "dockerfile_path",
    ["../Dockerfile", "/tmp/Dockerfile", "containers/../Dockerfile", "..", "foo\\Dockerfile"],
)
def test_rejects_path_traversal_and_absolute_paths(dockerfile_path: str) -> None:
    with pytest.raises(ValidationError):
        build_request(
            target_repo="example/model",
            target_sha=VALID_SHA,
            dockerfile_path=dockerfile_path,
            gpu_profile="cheap-24gb",
            max_runtime_minutes=15,
            max_cost_usd="0.20",
        )


@pytest.mark.parametrize("runtime", [0, -1, "abc"])
def test_rejects_invalid_runtime(runtime: object) -> None:
    with pytest.raises(ValidationError):
        build_request(
            target_repo="example/model",
            target_sha=VALID_SHA,
            dockerfile_path="Dockerfile",
            gpu_profile="cheap-24gb",
            max_runtime_minutes=runtime,  # type: ignore[arg-type]
            max_cost_usd="0.20",
        )


@pytest.mark.parametrize("cost", ["0", "-0.1", "NaN", "Infinity", "abc"])
def test_rejects_invalid_cost(cost: str) -> None:
    with pytest.raises(ValidationError):
        build_request(
            target_repo="example/model",
            target_sha=VALID_SHA,
            dockerfile_path="Dockerfile",
            gpu_profile="cheap-24gb",
            max_runtime_minutes=15,
            max_cost_usd=cost,
        )
