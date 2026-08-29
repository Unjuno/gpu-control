from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policies" / "runpod-v2-policy.yaml"


def load_policy() -> dict:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    assert isinstance(policy, dict)
    return policy


def test_live_runpod_calls_are_disabled_by_default() -> None:
    policy = load_policy()
    api = policy["api"]

    assert policy["provider"] == "runpod"
    assert api["version"] == "v2-beta"
    assert api["base_url"] == "https://api.runpod.io/v2"
    assert api["authentication"] == "bearer_header"
    assert api["live_calls_enabled"] is False
    assert api["live_adapter_enabled"] is False
    assert api["cli_enabled"] is False
    assert api["workflow_enabled"] is False


def test_current_api_audit_does_not_overstate_production_log_support() -> None:
    audit = load_policy()["api_contract_audit"]

    assert audit["current_official_rest_base_observed"] == "https://api.runpod.io/v2"
    assert audit["current_official_contract_revalidation_required"] is True
    assert audit["implementation_may_not_be_enabled_live_until_revalidated"] is True
    assert audit["live_enablement_by_flag_only_forbidden"] is True
    assert audit["create_env_contract_observed"] is True
    assert audit["list_pods_contract_observed"] is True
    assert audit["list_pods_endpoint"] == "GET /pods"
    assert audit["list_pods_response_envelope"] == "pods"
    assert audit["list_pods_server_side_name_filter_supported"] is False
    assert audit["pod_container_log_sse_status"] == "dev_only_prod_unavailable"
    assert audit["pod_container_log_sse_prod_verified"] is False
    assert audit["pod_container_log_sse_prod_failure"] == "http_422_path_not_found"
    assert audit["pod_container_log_sse_live_collection_allowed"] is False

    upstream_sha = "465872464c4f157a2e87afcd855c60a607954c26"
    assert audit["list_pods_evidence_repository"] == "runpod/runpod-mcp"
    assert audit["list_pods_evidence_commit"] == upstream_sha
    assert audit["list_pods_evidence_path"] == "src/tools/pods.ts"
    assert audit["pod_container_log_sse_evidence_repository"] == "runpod/runpod-mcp"
    assert audit["pod_container_log_sse_evidence_commit"] == upstream_sha
    assert audit["pod_container_log_sse_evidence_path"] == "test.md"
    assert audit["pod_container_log_sse_evidence_section"] == "K — Dev-only tools, currently DISABLED (not registered)"
    assert audit["pod_container_log_sse_evidence_url"] == (
        f"https://github.com/runpod/runpod-mcp/blob/{upstream_sha}/test.md"
    )


def test_submission_is_bound_to_permit_plan_image_gpu_cloud_price_and_reconciliation() -> None:
    submission = load_policy()["submission"]

    assert submission["approved_plan_required"] is True
    assert submission["structured_live_execution_permit_required"] is True
    assert submission["live_permit_plan_fingerprint_must_match"] is True
    assert submission["live_permit_human_authorization_reference_must_match_plan"] is True
    assert submission["live_permit_repository_security_evidence_required"] is True
    assert submission["live_permit_expiry_rechecked_immediately_before_create"] is True
    assert submission["published_image_evidence_required"] is True
    assert submission["catalog_pricing_evidence_required"] is True
    assert submission["image_reference_must_be_digest_pinned"] is True
    assert submission["published_image_must_match_plan_fingerprint"] is True
    assert submission["published_image_digest_must_match_plan"] is True
    assert submission["gpu_type_id_from_verified_pricing"] is True
    assert submission["create_cloud_from_catalog_pricing_evidence"] is True
    assert submission["gpu_count"] == 1
    assert submission["global_networking"] is False
    assert submission["user_ports_forwarded"] is False
    assert submission["user_env_forwarded"] is False
    assert submission["user_mounts_forwarded"] is False
    assert submission["automatic_create_retry"] is False
    assert submission["ambiguous_create_requires_reconciliation"] is True
    assert submission["ambiguous_create_reconciliation_status"] == "implemented_offline_mock_tested"
    assert submission["ambiguous_create_reconciliation_live_verified"] is False
    assert submission["ambiguous_create_reconciliation_requires_per_execution_identity"] is True
    assert submission["ambiguous_create_reconciliation_inventory_endpoint"] == "GET /pods"
    assert submission["ambiguous_create_reconciliation_inventory_max_entries"] == 256
    assert submission["ambiguous_create_reconciliation_inventory_max_ttl_seconds"] == 60
    assert submission["ambiguous_create_zero_match"] == "reject"
    assert submission["ambiguous_create_multiple_match"] == "reject"
    assert submission["ambiguous_create_terminated_only_match"] == "reject"
    assert submission["ambiguous_create_candidate_requires_full_get_revalidation"] is True
    assert submission["post_create_identity_revalidation"] is True
    assert submission["post_create_cloud_revalidation"] is True
    assert submission["post_create_price_must_not_exceed_verified_price"] is True
    assert submission["post_create_validation_failure_terminates_known_pod"] is True
    assert submission["compensating_termination_failure_is_visible"] is True


def test_cleanup_reconciliation_is_offline_only_and_fail_closed() -> None:
    cleanup = load_policy()["cleanup"]

    assert cleanup["terminate_endpoint"] == "DELETE /pods/{id}"
    assert cleanup["terminate_is_irreversible"] is True
    assert cleanup["cleanup_failure_visible"] is True
    assert cleanup["idempotent_already_absent_reconciliation_required_before_live"] is True
    assert cleanup["idempotent_reconciliation_status"] == "implemented_offline_mock_tested"
    assert cleanup["idempotent_reconciliation_live_verified"] is False
    assert cleanup["reconciliation_inventory_endpoint"] == "GET /pods"
    assert cleanup["reconciliation_accept_absent_exact_pod"] is True
    assert cleanup["reconciliation_accept_explicit_terminated_exact_pod"] is True
    assert cleanup["reconciliation_reject_active_exact_pod"] is True
    assert cleanup["reconciliation_invalid_inventory_is_failure"] is True


def test_completion_offline_verification_does_not_imply_live_collection() -> None:
    policy = load_policy()
    completion = policy["completion_evidence"]
    results = policy["results"]

    assert completion["protocol"] == "hmac-sha256-v2"
    assert completion["provider_job_id_binding"] == "submission_receipt_and_provider_specific_collection_transport"
    assert completion["max_marker_bytes"] == 16384
    assert completion["offline_marker_authentication_allowed"] is True
    assert completion["production_collection_transport_status"] == "blocked_pending_supported_provider_transport"
    assert completion["live_injection_enabled"] is False
    assert completion["live_collection_enabled"] is False
    assert results["enabled"] is False
    assert results["requires_authenticated_workload_completion_evidence"] is True
    assert results["production_transport_must_be_currently_supported"] is True


def test_catalog_evidence_is_short_lived_and_capacity_checked() -> None:
    catalog = load_policy()["catalog"]

    assert catalog["endpoint"] == "GET /catalog/gpus"
    assert catalog["include_availability"] is True
    assert catalog["product"] == "POD"
    assert catalog["gpu_count"] == 1
    assert catalog["evidence_max_ttl_seconds"] == 300
    assert catalog["required_availability"] == "HIGH"
    assert catalog["require_high_availability_datacenter"] is True
    assert catalog["require_profile_min_vram"] is True
    assert catalog["require_cloud_price"] is True
    assert catalog["require_cloud_capacity"] is True


def test_ambiguous_or_future_provider_states_fail_closed() -> None:
    policy = load_policy()
    status = policy["status"]

    assert status["provisioning"] == "submitted"
    assert status["starting"] == "submitted"
    assert status["running"] == "running"
    assert status["error"] == "failed"
    assert status["terminated"] == "cancelled"
    assert status["exited"] == "ambiguous_requires_workload_completion_evidence"
    assert status["unknown"] == "reject"
    assert policy["results"]["enabled"] is False


def test_forbidden_runpod_boundary_failures_are_explicit() -> None:
    forbidden = set(load_policy()["forbidden"])

    assert "live_runpod_call_from_ci" in forbidden
    assert "live_runpod_call_from_public_cli" in forbidden
    assert "live_adapter_from_public_cli" in forbidden
    assert "live_enablement_without_current_official_api_contract_revalidation" in forbidden
    assert "live_enablement_by_policy_flag_only" in forbidden
    assert "create_without_structured_live_execution_permit" in forbidden
    assert "create_with_expired_live_execution_permit" in forbidden
    assert "create_with_live_permit_for_different_plan" in forbidden
    assert "arbitrary_api_origin" in forbidden
    assert "api_key_in_query_string" in forbidden
    assert "api_key_in_logs_or_errors" in forbidden
    assert "mutable_tag_only_image" in forbidden
    assert "submit_image_not_bound_to_approved_plan" in forbidden
    assert "submission_cloud_not_bound_to_pricing_evidence" in forbidden
    assert "stale_catalog_pricing_evidence" in forbidden
    assert "catalog_gpu_below_profile_vram" in forbidden
    assert "catalog_gpu_without_one_gpu_capacity" in forbidden
    assert "automatic_retry_after_ambiguous_create" in forbidden
    assert "ambiguous_create_without_reconciliation" in forbidden
    assert "ambiguous_create_reconciliation_without_per_execution_identity" in forbidden
    assert "accepting_zero_or_multiple_ambiguous_create_matches" in forbidden
    assert "accepting_reconciled_candidate_without_full_identity_revalidation" in forbidden
    assert "unverified_post_create_gpu_identity" in forbidden
    assert "create_response_cloud_mismatch" in forbidden
    assert "accepting_price_above_verified_price" in forbidden
    assert "leaving_known_invalid_created_pod_running" in forbidden
    assert "hiding_compensating_termination_failure" in forbidden
    assert "treating_exited_as_success_without_completion_evidence" in forbidden
    assert "treating_unknown_provider_status_as_success" in forbidden
    assert "collecting_results_without_authenticated_completion_evidence" in forbidden
    assert "collecting_live_results_through_unavailable_prod_pod_log_sse" in forbidden
    assert "treating_dev_only_provider_operation_as_production_contract" in forbidden
    assert "treating_cleanup_404_as_success_without_reconciliation_policy" in forbidden
    assert "treating_active_pod_as_cleanup_success_after_terminate_error" in forbidden
