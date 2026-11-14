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
    assert workload["source_sha"] == "fc131174a9b529a9825f54fccf1a7df4c63c9a1a"
    assert workload["dockerfile_path"] == "workloads/runpod-training-canary/Dockerfile"
    assert workload["workload_id"] == "orbitune-runpod-training-canary-v1"
    assert workload["training_tokens"] == 512000
    assert workload["source_ci"] == {
        "evidence_scope": "exact_main_sha",
        "full_pytest": "passed",
        "full_pytest_run_id": 33313993621,
        "runpod_canary_smoke": "passed",
        "runpod_canary_smoke_run_id": 33313993623,
        "authenticated_completion_envelope": "passed",
        "completion_protocol": "gpu-control-hmac-sha256-v3",
    }
    assert workload["immutable_image"] == {
        "published": True,
        "digest": "sha256:489348337940c858f83ab056769a5c843ed8f778b906e7e16a8120581b0dd08e",
    }
    assert workload["completion_evidence"] == {
        "workload_protocol": "gpu-control-hmac-sha256-v3",
        "legacy_v2_compatibility": "temporary_migration_only",
        "workload_signer_boundary": "root_signer_uid_0_training_uid_10001",
        "workload_protocol_status": "implemented_and_smoke_tested",
        "signed_process_exit_code": True,
        "control_plane_verifier": "implemented_offline",
        "production_collection_transport": "network_volume_s3_implemented_offline_mock_tested",
        "production_collection_transport_live_verified": False,
        "production_pod_log_sse": "officially_documented_not_live_verified",
        "live_secret_injection": False,
        "live_result_collection": False,
    }
    parked = state["while_parked"]
    assert all(value is False for value in parked.values())
    cpu = state["modal_cpu_smoke_exception"]
    assert cpu["allowed_while_parked"] is True
    assert cpu["purpose"] == "one_authenticated_registered_cpu_inference"
    assert cpu["provider"] == "modal"
    assert cpu["environment"] == "main"
    assert cpu["workload"] == {
        "repository": "Unjuno/gpu-control",
        "source_sha": "3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288",
        "workload_id": "tiny-stories-inference-v1",
        "image_digest": "sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541",
    }
    bounds = cpu["execution_bounds"]
    assert bounds["max_runs_per_authorization"] == 1
    assert bounds["max_runtime_seconds"] == 30
    assert bounds["max_cpu_cores"] == 1
    assert bounds["max_memory_mib"] == 512
    assert bounds["gpu_allowed"] is False
    assert bounds["network_egress"] == "blocked"
    assert bounds["automatic_retry_after_ambiguous_submit"] is False
    assert bounds["require_confirmed_cleanup_before_next_run"] is True
    assert bounds["per_run_cost_ceiling_usd"] == "0.01"
    assert bounds["cost_is_usage_billed"] is True
    assert bounds["credit_eligibility_is_not_zero_cost"] is True
    assert cpu["account_guard"]["require_current_modal_workspace_usage_limit_usd_at_most"] == "1.00"
    assert cpu["authorization"]["explicit_current_human_request_required"] is True
    assert cpu["authorization"]["exact_plan_fingerprint_required"] is True
    assert cpu["credentials"]["maximum_deploy_token_lifetime_minutes"] == 60
    assert cpu["credentials"]["deploy_command_must_target_environment"] == "main"
    assert cpu["credentials"]["revoke_deploy_token_immediately_after_deploy"] is True
    assert cpu["credentials"]["credentials_exposed_to_sandbox"] is False
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
    assert runpod["completion_evidence"]["implementation_status"] == (
        "disabled_awaiting_controller_owned_completion_protocol"
    )
    assert runpod["completion_evidence"]["security_status"] == "workload_signing_secret_not_sent_fail_closed"
    assert runpod["completion_evidence"]["root_owned_signer_redesign_required"] is True
    assert runpod["completion_evidence"]["protocol"] == "hmac-sha256-v3"
    assert runpod["completion_evidence"]["production_collection_transport_status"] == (
        "network_volume_s3_implemented_offline_mock_tested"
    )
    assert runpod["completion_evidence"]["production_collection_transport_live_verified"] is False
    assert runpod["completion_evidence"]["live_injection_enabled"] is False
    assert runpod["completion_evidence"]["live_collection_enabled"] is False
    assert runpod["network_volume_results"]["live_verified"] is False
    assert runpod["network_volume_results"]["live_enabled"] is False
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
        assert "secrets.RUNPOD_S3_SECRET_ACCESS_KEY" not in content
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
        "paid_environment_required_reviewers_configured",
        "paid_environment_prevent_self_review_enabled",
        "paid_environment_deployment_branch_policy_restricted",
        "environment_scoped_runpod_secret_configured",
        "environment_scoped_runpod_s3_secrets_configured",
        "immutable_published_image_path_available",
        "preexisting_runpod_network_volume_available",
        "network_volume_in_s3_supported_datacenter",
        "authenticated_workload_completion_evidence_available",
        "supported_production_completion_transport_available",
        "live_completion_result_collection_verified",
        "reliable_cleanup_path_available",
    } <= prerequisites
    assert state["resume_rule"]["keep_paid_compute_disabled_until_external_github_gates_are_verified"] is True
