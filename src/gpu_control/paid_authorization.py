from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

import yaml


class PaidAuthorizationError(ValueError):
    """Raised when a GitHub Actions context is not allowed to reach paid compute."""


@dataclass(frozen=True)
class PaidExecutionContext:
    actor: str
    triggering_actor: str
    repository: str
    repository_owner: str
    event_name: str
    ref: str
    workflow_ref: str
    run_id: str
    run_attempt: int


@dataclass(frozen=True)
class PaidAuthorizationEvidence:
    actor: str
    triggering_actor: str
    repository: str
    event_name: str
    ref: str
    workflow_ref: str
    run_id: str
    run_attempt: int
    environment_name: str
    concurrency_group: str
    authorization_reference: str


def load_paid_execution_policy(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        text = resources.files("gpu_control").joinpath("default_paid_execution_policy.yaml").read_text(encoding="utf-8")
        payload = yaml.safe_load(text)
    else:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise PaidAuthorizationError("paid execution policy must be a mapping")
    return payload


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PaidAuthorizationError(f"{field} is required")
    if value != value.strip():
        raise PaidAuthorizationError(f"{field} must not contain surrounding whitespace")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise PaidAuthorizationError(f"{field} must not contain control characters")
    return value


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PaidAuthorizationError(f"{field} must be a mapping")
    return value


def authorize_paid_execution(
    context: PaidExecutionContext,
    policy: Mapping[str, Any] | None = None,
    *,
    require_live_enabled: bool = True,
) -> PaidAuthorizationEvidence:
    """Authorize the one GitHub identity allowed to approach the paid boundary.

    This gate deliberately validates both ``actor`` and ``triggering_actor``. GitHub
    re-runs retain the privileges of the original actor, so checking only ``actor``
    would allow another write-capable user to re-run an owner's historical paid run.

    The function does not grant access to any secret and does not replace the
    protected GitHub Environment. It is an independent fail-closed code gate that
    must run before a paid job enters its global concurrency group.
    """

    policy = policy or load_paid_execution_policy()
    if policy.get("version") != 1:
        raise PaidAuthorizationError("unsupported paid execution policy version")
    if require_live_enabled and policy.get("live_paid_compute_enabled") is not True:
        raise PaidAuthorizationError("live paid compute remains disabled by policy")

    identity = _mapping(policy.get("github_identity"), "github_identity")
    environment = _mapping(policy.get("github_environment"), "github_environment")
    concurrency = _mapping(policy.get("concurrency"), "concurrency")

    actor = _text(context.actor, "actor")
    triggering_actor = _text(context.triggering_actor, "triggering_actor")
    repository = _text(context.repository, "repository")
    repository_owner = _text(context.repository_owner, "repository_owner")
    event_name = _text(context.event_name, "event_name")
    ref = _text(context.ref, "ref")
    workflow_ref = _text(context.workflow_ref, "workflow_ref")
    run_id = _text(context.run_id, "run_id")
    if not run_id.isdecimal() or int(run_id) <= 0:
        raise PaidAuthorizationError("run_id must be a positive GitHub Actions run id")
    if isinstance(context.run_attempt, bool) or not isinstance(context.run_attempt, int) or context.run_attempt < 1:
        raise PaidAuthorizationError("run_attempt must be a positive integer")

    expected_repository = _text(identity.get("repository"), "policy repository")
    expected_owner = _text(identity.get("repository_owner"), "policy repository_owner")
    expected_actor = _text(identity.get("authorized_actor"), "policy authorized_actor")
    expected_triggering_actor = _text(
        identity.get("authorized_triggering_actor"), "policy authorized_triggering_actor"
    )
    expected_event = _text(identity.get("event_name"), "policy event_name")
    expected_ref = _text(identity.get("ref"), "policy ref")
    expected_workflow_path = _text(identity.get("workflow_path"), "policy workflow_path")

    checks = {
        "repository": (repository, expected_repository),
        "repository_owner": (repository_owner, expected_owner),
        "actor": (actor, expected_actor),
        "triggering_actor": (triggering_actor, expected_triggering_actor),
        "event_name": (event_name, expected_event),
        "ref": (ref, expected_ref),
    }
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise PaidAuthorizationError(f"{label} is not authorized for paid compute")

    if identity.get("require_actor_and_triggering_actor_match") is not True:
        raise PaidAuthorizationError("paid policy must require actor/triggering_actor equality")
    if actor != triggering_actor:
        raise PaidAuthorizationError("paid workflow re-run by a different triggering actor is forbidden")

    expected_workflow_ref = f"{expected_repository}/{expected_workflow_path}@{expected_ref}"
    if workflow_ref != expected_workflow_ref:
        raise PaidAuthorizationError("workflow_ref is not the owner-only paid workflow on main")

    environment_name = _text(environment.get("name"), "paid environment name")
    required_reviewer = _text(environment.get("required_reviewer"), "paid environment required_reviewer")
    if required_reviewer != expected_actor:
        raise PaidAuthorizationError("paid environment reviewer must be the authorized actor")
    if environment.get("secret_scope") != "environment_only":
        raise PaidAuthorizationError("paid provider secret must be environment-scoped")
    secrets = environment.get("secret_names")
    if not isinstance(secrets, list) or secrets != ["RUNPOD_API_KEY"]:
        raise PaidAuthorizationError("paid environment must expose only the expected RunPod secret name")

    group = _text(concurrency.get("group"), "paid concurrency group")
    if concurrency.get("max_in_flight") != 1:
        raise PaidAuthorizationError("paid concurrency must allow exactly one in-flight job")
    if concurrency.get("cancel_in_progress") is not False:
        raise PaidAuthorizationError("paid concurrency must not cancel an already-running GPU job")
    if concurrency.get("authorization_before_concurrency") is not True:
        raise PaidAuthorizationError("authorization must run before paid concurrency admission")
    if concurrency.get("unauthorized_runs_must_not_enter_paid_queue") is not True:
        raise PaidAuthorizationError("unauthorized runs must not enter the paid queue")

    reference = f"github-actions:{repository}:run:{run_id}:attempt:{context.run_attempt}:actor:{actor}"
    return PaidAuthorizationEvidence(
        actor=actor,
        triggering_actor=triggering_actor,
        repository=repository,
        event_name=event_name,
        ref=ref,
        workflow_ref=workflow_ref,
        run_id=run_id,
        run_attempt=context.run_attempt,
        environment_name=environment_name,
        concurrency_group=group,
        authorization_reference=reference,
    )
