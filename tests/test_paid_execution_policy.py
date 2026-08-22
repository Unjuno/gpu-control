from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "policies" / "paid-execution-policy.yaml"
WORKFLOWS = ROOT / ".github" / "workflows"


def policy() -> dict:
    value = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_paid_compute_stays_disabled_until_owner_environment_is_configured() -> None:
    value = policy()
    assert value["live_paid_compute_enabled"] is False
    identity = value["github_identity"]
    assert identity["repository"] == "Unjuno/gpu-control"
    assert identity["repository_owner"] == "Unjuno"
    assert identity["authorized_actor"] == "Unjuno"
    assert identity["authorized_triggering_actor"] == "Unjuno"
    assert identity["event_name"] == "workflow_dispatch"
    assert identity["ref"] == "refs/heads/main"
    assert identity["require_actor_and_triggering_actor_match"] is True
    assert identity["reject_rerun_by_different_triggering_actor"] is True


def test_no_paid_workflow_or_provider_secret_reference_exists_while_live_is_disabled() -> None:
    assert not (WORKFLOWS / "paid-runpod.yml").exists()
    for workflow in WORKFLOWS.glob("*.yml"):
        content = workflow.read_text(encoding="utf-8")
        assert "RUNPOD_API_KEY" not in content
        assert "environment: paid-runpod" not in content


def test_paid_secret_is_environment_only_and_owner_reviewed() -> None:
    environment = policy()["github_environment"]
    assert environment["name"] == "paid-runpod"
    assert environment["required_reviewer"] == "Unjuno"
    assert environment["prevent_self_review"] is False
    assert environment["protected_branch_only"] is True
    assert environment["secret_scope"] == "environment_only"
    assert environment["secret_names"] == ["RUNPOD_API_KEY"]


def test_paid_queue_is_single_flight_and_owner_gate_precedes_queue() -> None:
    concurrency = policy()["concurrency"]
    assert concurrency["group"] == "gpu-control-paid-runpod"
    assert concurrency["max_in_flight"] == 1
    assert concurrency["cancel_in_progress"] is False
    assert concurrency["authorization_before_concurrency"] is True
    assert concurrency["unauthorized_runs_must_not_enter_paid_queue"] is True


def test_provider_account_must_be_exclusive_before_submit() -> None:
    occupancy = policy()["provider_occupancy"]
    assert occupancy["require_zero_active_gpu_pods_before_submit"] is True
    assert occupancy["recheck_immediately_before_create"] is True
    assert occupancy["fail_closed_on_list_error"] is True
    assert occupancy["fail_closed_on_unknown_pod_state"] is True
    assert occupancy["ambiguous_create_requires_reconciliation"] is True


def test_public_or_non_owner_paid_entrypoints_are_explicitly_forbidden() -> None:
    forbidden = set(policy()["forbidden"])
    required = {
        "paid_compute_from_pull_request",
        "paid_compute_from_fork",
        "paid_compute_from_issue",
        "paid_compute_from_issue_comment",
        "paid_compute_from_repository_dispatch",
        "paid_compute_from_schedule",
        "paid_compute_from_non_main_ref",
        "paid_compute_from_non_owner_actor",
        "paid_compute_from_non_owner_triggering_actor",
        "repository_level_runpod_secret",
        "organization_level_runpod_secret",
        "unauthorized_run_entering_paid_concurrency_group",
        "more_than_one_paid_gpu_job_in_flight",
        "create_without_provider_occupancy_check",
        "create_while_other_gpu_pod_is_active",
    }
    assert required <= forbidden
