from pathlib import Path

import pytest
import yaml

from gpu_control.paid_authorization import (
    PaidAuthorizationError,
    PaidExecutionContext,
    authorize_paid_execution,
    load_paid_execution_policy,
)


ROOT = Path(__file__).resolve().parents[1]
OWNER = "Unjuno"
REPOSITORY = "Unjuno/gpu-control"
WORKFLOW_REF = "Unjuno/gpu-control/.github/workflows/paid-runpod.yml@refs/heads/main"


def context(**changes: object) -> PaidExecutionContext:
    values: dict[str, object] = {
        "actor": OWNER,
        "triggering_actor": OWNER,
        "repository": REPOSITORY,
        "repository_owner": OWNER,
        "event_name": "workflow_dispatch",
        "ref": "refs/heads/main",
        "workflow_ref": WORKFLOW_REF,
        "run_id": "123456789",
        "run_attempt": 1,
    }
    values.update(changes)
    return PaidExecutionContext(**values)  # type: ignore[arg-type]


def enabled_policy() -> dict:
    policy = load_paid_execution_policy()
    policy["live_paid_compute_enabled"] = True
    return policy


def test_bundled_and_repository_paid_policies_match() -> None:
    bundled = load_paid_execution_policy()
    repository = yaml.safe_load((ROOT / "policies" / "paid-execution-policy.yaml").read_text(encoding="utf-8"))
    assert bundled == repository


def test_live_paid_compute_is_disabled_by_default() -> None:
    with pytest.raises(PaidAuthorizationError, match="remains disabled"):
        authorize_paid_execution(context())


def test_owner_context_can_be_authorized_only_when_policy_is_explicitly_enabled() -> None:
    evidence = authorize_paid_execution(context(), enabled_policy())

    assert evidence.actor == OWNER
    assert evidence.triggering_actor == OWNER
    assert evidence.environment_name == "paid-runpod"
    assert evidence.concurrency_group == "gpu-control-paid-runpod"
    assert evidence.authorization_reference == (
        "github-actions:Unjuno/gpu-control:run:123456789:attempt:1:actor:Unjuno"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actor", "someone-else"),
        ("triggering_actor", "someone-else"),
        ("repository", "someone/fork"),
        ("repository_owner", "someone"),
        ("event_name", "pull_request"),
        ("event_name", "repository_dispatch"),
        ("event_name", "schedule"),
        ("ref", "refs/heads/feature"),
        ("workflow_ref", "Unjuno/gpu-control/.github/workflows/ci.yml@refs/heads/main"),
    ],
)
def test_non_owner_or_wrong_entrypoint_is_rejected(field: str, value: str) -> None:
    with pytest.raises(PaidAuthorizationError):
        authorize_paid_execution(context(**{field: value}), enabled_policy())


def test_rerun_by_different_triggering_actor_is_rejected_even_if_original_actor_is_owner() -> None:
    with pytest.raises(PaidAuthorizationError, match="triggering_actor"):
        authorize_paid_execution(
            context(actor=OWNER, triggering_actor="write-collaborator", run_attempt=2),
            enabled_policy(),
        )


def test_policy_requires_single_flight_and_authorization_before_queue() -> None:
    policy = enabled_policy()
    policy["concurrency"]["max_in_flight"] = 2
    with pytest.raises(PaidAuthorizationError, match="exactly one"):
        authorize_paid_execution(context(), policy)

    policy = enabled_policy()
    policy["concurrency"]["authorization_before_concurrency"] = False
    with pytest.raises(PaidAuthorizationError, match="before paid concurrency"):
        authorize_paid_execution(context(), policy)


def test_runpod_secret_must_be_environment_scoped() -> None:
    policy = enabled_policy()
    policy["github_environment"]["secret_scope"] = "repository"
    with pytest.raises(PaidAuthorizationError, match="environment-scoped"):
        authorize_paid_execution(context(), policy)
