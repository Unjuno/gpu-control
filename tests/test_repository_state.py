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


def test_repository_is_explicitly_parked_with_active_workload_recorded() -> None:
    state = load(STATE)
    assert state["version"] == 1
    assert state["mode"] == "parked"
    assert state["reason"] == "activation_prerequisites_incomplete"
    workload = state["active_workload"]
    assert workload["repository"] == "Unjuno/orbitune"
    assert workload["source_sha"] == "38594057d1b118a7acf6c843e39d7d8a25571316"
    assert workload["dockerfile_path"] == "workloads/runpod-training-canary/Dockerfile"
    assert workload["workload_id"] == "orbitune-runpod-training-canary-v1"
    assert workload["training_tokens"] == 512000
    assert workload["source_ci"] == {
        "evidence_scope": "exact_main_sha",
        "full_pytest": "passed",
        "full_pytest_run_id": 33117645383,
        "runpod_canary_smoke": "passed",
        "runpod_canary_smoke_run_id": 33117645387,
        "authenticated_completion_envelope": "passed",
        "completion_protocol": "gpu-control-hmac-sha256-v2",
    }
    assert workload["immutable_image"] == {"published": False, "digest": None}
    assert workload["completion_evidence"] == {
        "workload_protocol": "gpu-control-hmac-sha256-v2",
        "workload_signer_boundary": "root_signer_uid_0_training_uid_10001",
        "workload_protocol_status": "implemented_and_smoke_tested",
        "control_plane_verifier": "implemented_offline",
        "production_collection_transport": "blocked_pending_supported_provider_transport",
        "production_pod_log_sse": "unavailable_http_422_path_not_found",
        "live_secret_injection": False,
        "live_result_collection": False,
    }
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
    assert runpod["completion_evidence"]["implementation_status"] == "pre_create_identity_and_env_contract_offline"
    assert runpod["completion_evidence"]["protocol"] == "hmac-sha256-v2"
    assert runpod["completion_evidence"]["production_collection_transport_status"] == "blocked_pending_supported_provider_transport"
    assert runpod["completion_evidence"]["live_injection_enabled"] is False
    assert runpod["completion_evidence"]["live_collection_enabled"] is False
    assert runpod["api_contract_audit"]["pod_container_log_sse_prod_verified"] is False
    assert runpod["api_contract_audit"]["pod_container_log_sse_live_collection_allowed"] is False
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
        "supported_production_completion_transport_available",
        "live_completion_result_collection_verified",
        "reliable_cleanup_path_available",
    } <= prerequisites
    assert state["resume_rule"]["keep_paid_compute_disabled_until_external_github_gates_are_verified"] is True
