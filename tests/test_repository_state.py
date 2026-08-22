from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "policies" / "repository-state.yaml"
PAID = ROOT / "policies" / "paid-execution-policy.yaml"
RUNPOD = ROOT / "policies" / "runpod-v2-policy.yaml"
AGENT = ROOT / "policies" / "agent-policy.yaml"
CONTAINER = ROOT / "policies" / "container-verification-policy.yaml"
WORKFLOWS = ROOT / ".github" / "workflows"


def load(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_repository_is_explicitly_parked() -> None:
    state = load(STATE)
    assert state["version"] == 1
    assert state["mode"] == "parked"
    assert state["reason"] == "no_active_workload"
    parked = state["while_parked"]
    assert all(value is False for value in parked.values())
    assert state["authorization"]["activation_requires_explicit_human_request"] is True


def test_parked_mode_cross_checks_all_live_provider_flags() -> None:
    paid = load(PAID)
    runpod = load(RUNPOD)
    agent = load(AGENT)
    container = load(CONTAINER)

    assert paid["live_paid_compute_enabled"] is False
    assert runpod["api"]["live_calls_enabled"] is False
    assert runpod["api"]["live_adapter_enabled"] is False
    assert runpod["api"]["cli_enabled"] is False
    assert runpod["api"]["workflow_enabled"] is False
    assert runpod["results"]["enabled"] is False
    assert agent["provider_adapter"]["live_implementation_enabled"] is False
    assert container["build"]["generic_execution_enabled"] is False
    assert container["runtime"]["generic_execution_enabled"] is False


def test_parked_mode_has_no_paid_entrypoint_or_provider_secret_access() -> None:
    assert not (WORKFLOWS / "paid-runpod.yml").exists()
    for workflow in WORKFLOWS.glob("*.yml"):
        content = workflow.read_text(encoding="utf-8")
        assert "secrets.RUNPOD_API_KEY" not in content
        assert "environment: paid-runpod" not in content
        assert "pull_request_target:" not in content
        assert "repository_dispatch:" not in content
        assert "schedule:" not in content


def test_parked_mode_activation_prerequisites_remain_explicit() -> None:
    state = load(STATE)
    prerequisites = set(state["activation_prerequisites"])
    assert {
        "active_workload_repository_selected",
        "main_branch_protection_configured",
        "required_ci_checks_enforced",
        "owner_only_paid_environment_configured",
        "environment_scoped_runpod_secret_configured",
        "immutable_published_image_path_available",
        "authenticated_workload_completion_evidence_available",
        "reliable_cleanup_path_available",
    } <= prerequisites
    assert state["resume_rule"]["keep_paid_compute_disabled_until_external_github_gates_are_verified"] is True
