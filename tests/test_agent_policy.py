from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policies" / "agent-policy.yaml"


def load_agent_policy() -> dict:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    assert isinstance(policy, dict)
    return policy


def test_paid_compute_is_denied_by_default() -> None:
    policy = load_agent_policy()
    assert policy["default_mode"] == "local_first"
    assert policy["paid_compute_default"] == "denied"


def test_runpod_is_final_escalation_stage() -> None:
    policy = load_agent_policy()
    stages = policy["stages"]
    paid_stage = next(stage for stage in stages if stage["id"] == "paid_gpu_runpod")
    assert paid_stage["final_stage"] is True
    assert paid_stage["order"] == max(stage["order"] for stage in stages)
    assert policy["paid_compute"]["provider"] == "runpod"


def test_paid_compute_requires_explicit_human_request_and_bounds() -> None:
    policy = load_agent_policy()
    requirements = set(policy["paid_compute"]["requires"])
    assert "explicit_human_request" in requirements
    assert "immutable_commit_sha" in requirements
    assert "structured_container_verification_evidence" in requirements
    assert "immutable_image_digest" in requirements
    assert "successful_dry_run" in requirements
    assert "structured_pricing_verification_evidence" in requirements
    assert "verified_provider_price" in requirements
    assert "verified_provider_resource_availability" in requirements
    assert "provider_resource_id" in requirements
    assert "unexpired_pricing_evidence" in requirements
    assert "pricing_freshness_rechecked_immediately_before_submission" in requirements
    assert "explicit_runtime_limit" in requirements
    assert "explicit_cost_limit" in requirements
    assert "cleanup_plan" in requirements
    assert "approved_execution_plan" in requirements
    assert policy["paid_compute"]["defaults"]["gpu_count"] == 1
    assert policy["paid_compute"]["defaults"]["execution_model"] == "asynchronous_submit_collect"
    assert policy["paid_compute"]["provider_adapter_input"] == "approved_execution_plan"


def test_async_state_is_strict_and_not_trusted_on_parse_alone() -> None:
    async_policy = load_agent_policy()["async_execution"]
    persisted = async_policy["persisted_state"]
    submit = async_policy["submit_stage"]
    collection = async_policy["collection_stage"]

    assert persisted["schema_version_required"] is True
    assert persisted["strict_known_fields_only"] is True
    assert persisted["reject_duplicate_json_keys"] is True
    assert persisted["reject_unknown_fields"] is True
    assert persisted["reject_missing_fields"] is True
    assert persisted["money_encoding"] == "decimal_string"
    assert persisted["parse_success_is_not_trust"] is True

    assert submit["revalidate_pricing_freshness_immediately_before_submit"] is True
    assert submit["persist_submission_receipt_before_exit"] is True
    assert submit["restored_receipt_must_match_approved_plan"] is True
    assert submit["wait_for_gpu_workload_completion"] is False

    assert collection["restored_observations_must_pass_strict_schema_validation"] is True
    assert collection["reject_identity_changes"] is True
    assert collection["enforce_monotonic_job_state"] is True
    assert collection["enforce_monotonic_cleanup_state"] is True


def test_repository_context_files_exist() -> None:
    required = [
        ROOT / "AGENTS.md",
        ROOT / "SECURITY.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "docs" / "OPERATING_MODEL.md",
        ROOT / "docs" / "CONTAINER_VERIFICATION.md",
        ROOT / "docs" / "ASYNC_EXECUTION.md",
        ROOT / "docs" / "PRICING_VERIFICATION.md",
        ROOT / ".github" / "copilot-instructions.md",
        ROOT / "policies" / "agent-policy.yaml",
        ROOT / "policies" / "gpu-policy.yaml",
        ROOT / "policies" / "container-verification-policy.yaml",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert missing == []


def test_forbidden_policy_blocks_common_agent_escalation_failures() -> None:
    policy = load_agent_policy()
    forbidden = set(policy["forbidden"])
    assert "arbitrary_remote_shell_interface" in forbidden
    assert "paid_compute_from_untrusted_events" in forbidden
    assert "silent_cost_or_runtime_escalation" in forbidden
    assert "long_lived_actions_polling" in forbidden
    assert "provider_allocation_without_explicit_authorization" in forbidden
    assert "provider_adapter_accepting_raw_workload_request" in forbidden
    assert "paid_gate_accepting_bare_container_boolean" in forbidden
    assert "paid_gate_accepting_bare_price_scalar" in forbidden
    assert "submit_stage_waiting_for_long_running_gpu_completion" in forbidden
    assert "provider_submission_with_expired_pricing_evidence" in forbidden
    assert "collection_without_submission_receipt_correlation" in forbidden
    assert "trusting_persisted_state_only_because_it_parsed" in forbidden
