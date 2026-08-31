from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policies" / "runpod-rest-v1-policy.yaml"


def load_policy() -> dict:
    value = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_current_v1_transport_contract_is_offline_only() -> None:
    policy = load_policy()
    api = policy["api"]
    migration = policy["migration"]

    assert policy["provider"] == "runpod"
    assert policy["contract"] == "rest_v1_current_official"
    assert policy["status"] == "transport_layer_implemented_offline_mock_tested"
    assert api["base_url"] == "https://rest.runpod.io/v1"
    assert api["authentication"] == "bearer_header"
    assert api["openapi_endpoint"] == "GET /openapi.json"
    assert api["live_calls_enabled"] is False
    assert api["adapter_migrated"] is False
    assert api["workflow_enabled"] is False

    assert migration["current_v1_http_client_implemented"] is True
    assert migration["current_v1_payload_builder_implemented"] is True
    assert migration["current_v1_response_normalizer_implemented"] is True
    assert migration["current_v1_list_array_normalizer_implemented"] is True
    assert migration["current_v1_fixed_origin_tests_implemented"] is True
    assert migration["provider_adapter_migration_pending"] is True
    assert migration["current_pricing_catalog_revalidation_pending"] is True
    assert migration["live_provider_verification_pending"] is True


def test_v1_pod_contract_matches_current_field_shapes() -> None:
    policy = load_policy()
    endpoints = policy["pod_endpoints"]
    listing = policy["list_pods"]
    create = policy["create"]
    response = policy["response_normalization"]

    assert endpoints == {
        "create": "POST /pods",
        "list": "GET /pods",
        "get": "GET /pods/{id}",
        "delete": "DELETE /pods/{id}",
        "delete_success_status": 204,
    }
    assert listing["response_shape"] == "array"
    assert listing["allowed_statuses"] == ["RUNNING", "EXITED", "TERMINATED"]
    assert listing["status_field"] == "desiredStatus"
    assert listing["duplicate_ids_rejected"] is True
    assert listing["unknown_status_rejected"] is True

    assert create["image_field"] == "imageName"
    assert create["gpu_type_field"] == "gpuTypeIds"
    assert create["gpu_count_field"] == "gpuCount"
    assert create["disk_field"] == "containerDiskInGb"
    assert create["cloud_field"] == "cloudType"
    assert create["network_volume_id_field"] == "networkVolumeId"
    assert create["network_volume_mount_field"] == "volumeMountPath"
    assert create["global_networking"] is False
    assert create["interruptible"] is False
    assert create["support_public_ip"] is False

    assert response["status_source"] == "desiredStatus"
    assert response["hourly_cost_source"] == "costPerHr"
    assert response["cloud_source"] == "machine.secureCloud"
    assert response["network_volume_source"] == "networkVolume"
    assert response["machine_evidence_required_for_adapter_identity_validation"] is True


def test_v1_forbidden_boundaries_fail_closed() -> None:
    forbidden = set(load_policy()["forbidden"])
    assert {
        "live_calls_before_adapter_migration",
        "live_calls_before_current_pricing_revalidation",
        "arbitrary_api_origin",
        "api_key_in_query_string",
        "api_key_in_logs_or_errors",
        "accepting_non_array_list_pods_response",
        "accepting_unknown_desired_status",
        "accepting_duplicate_pod_ids",
        "accepting_unvalidated_machine_cloud_identity",
        "accepting_unvalidated_network_volume_identity",
        "forwarding_untrusted_user_environment",
        "forwarding_untrusted_user_ports",
        "forwarding_untrusted_user_volume_configuration",
    } <= forbidden
