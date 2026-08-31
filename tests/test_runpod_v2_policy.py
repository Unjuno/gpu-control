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


def test_current_api_audit_records_v1_migration_blocker_log_blocker_and_volume_alternative() -> None:
    audit = load_policy()["api_contract_audit"]

    assert audit["implementation_contract"] == "rest_v2_public_beta_offline"
    assert audit["implementation_matches_current_official_rest_contract"] is False
    assert audit["current_official_rest_version_observed"] == "v1"
    assert audit["current_official_rest_base_observed"] == "https://rest.runpod.io/v1"
    assert audit["current_official_openapi_endpoint"] == "GET /openapi.json"
    assert audit["current_official_create_pod_endpoint"] == "POST /pods"
    assert audit["current_official_list_pods_endpoint"] == "GET /pods"
    assert audit["current_official_list_pods_response_shape"] == "array"
    assert audit["current_official_delete_pod_endpoint"] == "DELETE /pods/{id}"
    assert audit["current_official_network_volume_attach_fields_observed"] is True
    assert audit["current_official_network_volume_fields"] == ["networkVolumeId", "volumeMountPath"]
    assert audit["migration_to_current_official_rest_contract_required"] is True
    assert audit["current_official_contract_revalidation_required"] is True
    assert audit["implementation_may_not_be_enabled_live_until_revalidated"] is True
    assert audit["live_enablement_by_flag_only_forbidden"] is True
    assert audit["create_env_contract_observed"] is True
    assert audit["list_pods_contract_observed"] is True
    assert audit["implementation_list_pods_endpoint"] == "GET /pods"
    assert audit["implementation_list_pods_response_envelope"] == "pods"
    assert audit["implementation_list_pods_server_side_name_filter_supported"] is False
    assert audit["pod_container_log_sse_status"] == "dev_only_prod_unavailable"
    assert audit["pod_container_log_sse_prod_verified"] is False
    assert audit["pod_container_log_sse_prod_failure"] == "http_422_path_not_found"
    assert audit["pod_container_log_sse_live_collection_allowed"] is False

    upstream_sha = "465872464c4f157a2e87afcd855c60a607954c26"
    assert audit["legacy_v2_list_pods_evidence_repository"] == "runpod/runpod-mcp"
    assert audit["legacy_v2_list_pods_evidence_commit"] == upstream_sha
    assert audit["legacy_v2_list_pods_evidence_path"] == "src/tools/pods.ts"
    assert audit["pod_container_log_sse_evidence_repository"] == "runpod/runpod-mcp"
    assert audit["pod_container_log_sse_evidence_commit"] == upstream_sha

    assert audit["network_volume_storage_docs_observed"] is True
    assert audit["network_volume_s3_api_observed"] is True
    assert audit["network_volume_docs_repository"] == "runpod/docs"
    assert audit["network_volume_docs_commit"] == "d5b565dc68874e747a5e0476e70b10e8c05c447e"
    assert audit["network_volume_docs_path"] == "storage/network-volumes.mdx"
    assert audit["network_volume_s3_docs_path"] == "storage/s3-api.mdx"
    assert audit["network_volume_attach_contract_repository"] == "runpod/runpodctl"


def test_submission_is_bound_to_permit_plan_image_gpu_cloud_price_volume_and_reconciliation() -> None:
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

    assert submission["trusted_network_volume_required_for_live_canary"] is True
    assert submission["network_volume_must_preexist"] is True
    assert submission["network_volume_auto_create_or_resize"] is False
    assert submission["network_volume_mount_path"] == "/outputs"
    assert submission["network_volume_from_trusted_control_plane_only"] is True
    assert submission["network_volume_s3_supported_datacenter_required"] is True

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


def test_completion_v3_and_volume_transport_are_implemented_but_not_live_verified() -> None:
    policy = load_policy()
    completion = policy["completion_evidence"]
    transport = policy["network_volume_results"]
    results = policy["results"]

    assert completion["protocol"] == "hmac-sha256-v3"
    assert completion["legacy_v2_compatibility_status"] == "temporary_offline_migration_only"
    assert completion["provider_job_id_binding"] == "submission_receipt_and_provider_specific_collection_transport"
    assert completion["max_marker_bytes"] == 16384
    assert completion["offline_marker_authentication_allowed"] is True
    assert "process_exit_code" in completion["binds"]
    assert completion["completion_marker"] == "GPU_CONTROL_COMPLETION_JSON_V3:"
    assert completion["production_collection_transport_status"] == (
        "network_volume_s3_implemented_offline_mock_tested"
    )
    assert completion["production_collection_transport_live_verified"] is False
    assert completion["live_injection_enabled"] is False
    assert completion["live_collection_enabled"] is False

    assert transport["implementation_status"] == "implemented_offline_mock_tested"
    assert transport["live_verified"] is False
    assert transport["live_enabled"] is False
    assert transport["secure_cloud_required"] is True
    assert transport["mount_path"] == "/outputs"
    assert transport["persistent_after_pod_termination"] is True
    assert transport["object_keys"] == ["result.json", "completion-v3.json"]
    assert transport["max_object_bytes"] == 16384
    assert transport["fixed_runpod_s3_origin_required"] is True
    assert transport["s3_endpoint_derived_from_datacenter"] is True
    assert transport["s3_credentials_separate_from_runpod_api_key"] is True
    assert transport["s3_credentials_forwarded_to_workload"] is False
    assert transport["auto_create_or_resize_volume"] is False
    assert "US-KS-2" in transport["supported_datacenters"]

    assert results["enabled"] is False
    assert results["requires_authenticated_workload_completion_evidence"] is True
    assert results["production_transport_must_be_currently_supported"] is True
    assert results["network_volume_s3_transport_implemented"] is True
    assert results["network_volume_s3_live_verified"] is False
    assert results["durable_after_pod_cleanup"] is True


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
    assert status["exited"] == "authenticated_v3_network_volume_evidence_required"
    assert status["unknown"] == "reject"
    assert policy["results"]["enabled"] is False


def test_forbidden_runpod_boundary_failures_are_explicit() -> None:
    forbidden = set(load_policy()["forbidden"])

    required = {
        "live_runpod_call_from_ci",
        "live_runpod_call_from_public_cli",
        "live_adapter_from_public_cli",
        "live_enablement_without_current_official_api_contract_revalidation",
        "live_enablement_while_provider_adapter_targets_legacy_v2_beta",
        "live_enablement_by_policy_flag_only",
        "create_without_structured_live_execution_permit",
        "create_with_expired_live_execution_permit",
        "create_with_live_permit_for_different_plan",
        "arbitrary_api_origin",
        "api_key_in_query_string",
        "api_key_in_logs_or_errors",
        "mutable_tag_only_image",
        "submit_image_not_bound_to_approved_plan",
        "submission_cloud_not_bound_to_pricing_evidence",
        "stale_catalog_pricing_evidence",
        "catalog_gpu_below_profile_vram",
        "catalog_gpu_without_one_gpu_capacity",
        "automatic_retry_after_ambiguous_create",
        "ambiguous_create_without_reconciliation",
        "ambiguous_create_reconciliation_without_per_execution_identity",
        "accepting_zero_or_multiple_ambiguous_create_matches",
        "accepting_reconciled_candidate_without_full_identity_revalidation",
        "unverified_post_create_gpu_identity",
        "create_response_cloud_mismatch",
        "accepting_price_above_verified_price",
        "leaving_known_invalid_created_pod_running",
        "hiding_compensating_termination_failure",
        "treating_exited_as_success_without_completion_evidence",
        "treating_exited_as_success_without_v3_signed_exit_code",
        "treating_unknown_provider_status_as_success",
        "collecting_results_without_authenticated_completion_evidence",
        "collecting_live_results_through_unavailable_prod_pod_log_sse",
        "treating_dev_only_provider_operation_as_production_contract",
        "arbitrary_network_volume_id_from_workload",
        "user_controlled_volume_mount_path",
        "network_volume_auto_create_or_resize_in_paid_workflow",
        "runpod_s3_credentials_forwarded_to_workload",
        "runpod_s3_secret_in_logs_or_errors",
        "unbounded_s3_result_read",
        "s3_endpoint_not_derived_from_supported_datacenter",
        "treating_cleanup_404_as_success_without_reconciliation_policy",
        "treating_active_pod_as_cleanup_success_after_terminate_error",
    }
    assert required <= forbidden
