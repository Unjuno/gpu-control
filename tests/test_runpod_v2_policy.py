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
    assert api["cli_enabled"] is False
    assert api["workflow_enabled"] is False


def test_submission_is_bound_to_plan_image_gpu_and_price() -> None:
    submission = load_policy()["submission"]

    assert submission["approved_plan_required"] is True
    assert submission["published_image_evidence_required"] is True
    assert submission["image_reference_must_be_digest_pinned"] is True
    assert submission["published_image_must_match_plan_fingerprint"] is True
    assert submission["published_image_digest_must_match_plan"] is True
    assert submission["gpu_type_id_from_verified_pricing"] is True
    assert submission["gpu_count"] == 1
    assert submission["global_networking"] is False
    assert submission["user_ports_forwarded"] is False
    assert submission["user_env_forwarded"] is False
    assert submission["user_mounts_forwarded"] is False
    assert submission["post_create_identity_revalidation"] is True
    assert submission["post_create_price_must_not_exceed_verified_price"] is True


def test_ambiguous_or_future_provider_states_fail_closed() -> None:
    status = load_policy()["status"]

    assert status["provisioning"] == "submitted"
    assert status["starting"] == "submitted"
    assert status["running"] == "running"
    assert status["error"] == "failed"
    assert status["terminated"] == "cancelled"
    assert status["exited"] == "ambiguous_requires_workload_completion_evidence"
    assert status["unknown"] == "reject"


def test_forbidden_runpod_boundary_failures_are_explicit() -> None:
    forbidden = set(load_policy()["forbidden"])

    assert "live_runpod_call_from_ci" in forbidden
    assert "live_runpod_call_from_public_cli" in forbidden
    assert "arbitrary_api_origin" in forbidden
    assert "api_key_in_query_string" in forbidden
    assert "api_key_in_logs_or_errors" in forbidden
    assert "mutable_tag_only_image" in forbidden
    assert "submit_image_not_bound_to_approved_plan" in forbidden
    assert "unverified_post_create_gpu_identity" in forbidden
    assert "accepting_price_above_verified_price" in forbidden
    assert "treating_exited_as_success_without_completion_evidence" in forbidden
    assert "treating_unknown_provider_status_as_success" in forbidden
