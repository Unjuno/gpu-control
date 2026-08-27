from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_POLICY = ROOT / "policies" / "context-trust-policy.yaml"
DECISION_POLICY = ROOT / "policies" / "decision-policy.yaml"
AGENT_POLICY = ROOT / "policies" / "agent-policy.yaml"
PAID_POLICY = ROOT / "policies" / "paid-execution-policy.yaml"
RUNPOD_POLICY = ROOT / "policies" / "runpod-v2-policy.yaml"
REPOSITORY_STATE = ROOT / "policies" / "repository-state.yaml"
FAILURE_CATALOG = ROOT / "policies" / "failure-catalog.yaml"
HUMAN_AUTH_SCHEMA = ROOT / "policies" / "human-authorization-evidence-schema.yaml"
FIXTURES = ROOT / "examples" / "context-security"


def load(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_context_trust_policy_separates_instruction_authority_from_external_data() -> None:
    policy = load(CONTEXT_POLICY)

    assert policy["version"] == 1
    assert policy["name"] == "context_trust_policy"
    assert policy["runtime_enforced"] is False

    rules = policy["core_rules"]
    assert rules["instructions_and_data_are_not_equivalent"] is True
    assert rules["trust_is_assigned_by_source_and_authority_not_by_wording"] is True
    assert rules["untrusted_content_never_grants_authority"] is True
    assert rules["untrusted_content_never_overrides_higher_level_policy"] is True
    assert rules["suspicious_string_detection_is_not_a_security_boundary"] is True

    external = policy["trust_classes"]["external_untrusted_content"]
    assert external["instruction_authority"] is False
    sources = set(external["sources"])
    assert {
        "target_repository_files",
        "target_repository_agents_or_instruction_files",
        "readme_and_documentation",
        "source_and_dockerfile_comments",
        "commit_messages",
        "pull_request_bodies_and_reviews",
        "issues_and_comments",
        "web_pages",
        "provider_response_text",
        "logs",
        "artifacts",
        "generated_model_output",
        "few_shot_examples",
    } <= sources


def test_source_to_sink_boundary_blocks_untrusted_authority_flow() -> None:
    policy = load(CONTEXT_POLICY)
    boundary = policy["source_sink_boundary"]
    sinks = set(boundary["high_impact_sinks"])

    assert {
        "paid_provider_allocation",
        "secret_or_credential_access",
        "external_data_transmission",
        "github_write",
        "branch_or_environment_security_change",
        "policy_or_live_flag_change",
        "collaborator_or_permission_change",
        "destructive_or_irreversible_operation",
    } <= sinks

    rules = set(boundary["rules"])
    assert "untrusted_content_may_inform_analysis_but_may_not_authorize_a_sink" in rules
    assert "sink_arguments_must_be_derived_from_current_user_intent_and_validated_trusted_state" in rules
    assert "untrusted_content_cannot_supply_or_expand_human_authorization" in rules
    assert "provider_or_tool_output_is_data_not_instruction" in rules
    assert "risky_sink_must_remain_behind_deterministic_policy_and_human_control" in rules


def test_red_team_fixtures_are_explicitly_untrusted_and_non_authoritative() -> None:
    paths = sorted(FIXTURES.glob("*.yaml"))
    assert len(paths) >= 3

    for path in paths:
        fixture = load(path)
        assert fixture["schema_version"] == 1
        assert fixture["fixture_type"] == "untrusted_context_security"
        assert fixture["source_class"] == "external_untrusted_content"
        assert fixture["must_never_authorize"] is True
        assert isinstance(fixture["payload"], str) and "UNTRUSTED_FIXTURE_ONLY" in fixture["payload"]
        assert isinstance(fixture["expected_handling"], dict)

    readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
    assert "untrusted adversarial test data" in readme
    assert "must never be used as authority" in readme


def test_failure_catalog_covers_prompt_and_context_attack_classes() -> None:
    failures = load(FAILURE_CATALOG)["failures"]
    by_name = {failure["name"]: failure for failure in failures}

    assert {
        "indirect_prompt_injection",
        "context_poisoning",
        "provider_output_instruction_confusion",
        "authority_spoofing_in_content",
        "control_plane_context_poisoning",
    } <= set(by_name)

    for name in (
        "indirect_prompt_injection",
        "context_poisoning",
        "provider_output_instruction_confusion",
        "authority_spoofing_in_content",
        "control_plane_context_poisoning",
    ):
        assert by_name[name]["category"] in {"prompt_security", "authority"}
        assert by_name[name]["required_response"].strip()


def test_decision_and_agent_policies_bind_context_trust_before_escalation() -> None:
    decision = load(DECISION_POLICY)["context_trust"]
    assert decision["policy"] == "policies/context-trust-policy.yaml"
    assert decision["must_conform"] is True
    assert decision["classify_source_before_consequential_use"] is True
    assert decision["untrusted_content_never_grants_authority"] is True
    assert decision["provider_or_tool_output_is_data_not_instruction"] is True
    assert decision["high_impact_sink_requires_trusted_current_inputs"] is True

    agent = load(AGENT_POLICY)["context_trust"]
    assert agent["policy"] == "policies/context-trust-policy.yaml"
    assert agent["target_repository_content_is_untrusted_data"] is True
    assert agent["target_repository_agent_instructions_have_no_control_plane_authority"] is True
    assert agent["model_output_is_not_authorization_evidence"] is True
    assert agent["high_impact_sink_requires_current_trusted_intent_and_validated_state"] is True


def test_paid_policy_requires_context_and_structured_human_authorization_for_future_live_use() -> None:
    paid = load(PAID_POLICY)
    prompt_security = paid["prompt_context_security"]

    assert paid["live_paid_compute_enabled"] is False
    assert prompt_security["required_before_live_authorization"] is True
    assert prompt_security["control_plane_context_integrity_required"] is True
    assert prompt_security["target_repository_content_has_instruction_authority"] is False
    assert prompt_security["external_content_may_grant_human_authorization"] is False
    assert prompt_security["provider_output_has_instruction_authority"] is False
    assert prompt_security["prompt_context_red_team_required"] is True
    assert prompt_security["structured_human_authorization_required"] is True
    assert prompt_security["bare_human_authorization_boolean_sufficient_for_live"] is False
    assert prompt_security["exact_control_plane_sha_binding_required"] is True
    assert prompt_security["exact_execution_plan_fingerprint_binding_required"] is True


def test_human_authorization_schema_is_action_specific_but_not_runtime_enabled_yet() -> None:
    schema = load(HUMAN_AUTH_SCHEMA)

    assert schema["version"] == 1
    assert schema["name"] == "HumanAuthorizationEvidence"
    assert schema["runtime_enforced"] is False

    properties = schema["security_properties"]
    assert properties["bare_boolean_is_not_final_live_authorization"] is True
    assert properties["authorization_is_current_action_specific"] is True
    assert properties["authorization_is_not_inheritable"] is True
    assert properties["authorization_cannot_be_derived_from_untrusted_content"] is True
    assert properties["exact_execution_plan_binding_required"] is True
    assert properties["exact_control_plane_commit_binding_required"] is True
    assert properties["expiry_required"] is True

    required = set(schema["required_fields"])
    assert {
        "decision_record_id",
        "control_plane_sha",
        "plan_fingerprint",
        "target_repo",
        "target_sha",
        "image_digest",
        "provider_resource_id",
        "max_runtime_minutes",
        "max_cost_usd",
        "valid_until_utc",
    } <= required


def test_live_activation_is_blocked_on_new_prompt_authorization_and_provider_prerequisites() -> None:
    state = load(REPOSITORY_STATE)
    prerequisites = set(state["activation_prerequisites"])

    assert state["mode"] == "parked"
    assert {
        "control_plane_context_integrity_verified",
        "prompt_context_security_red_team_passed",
        "context_trust_policy_bound_into_agent_context",
        "structured_decision_record_bound_to_execution_plan",
        "structured_human_authorization_bound_to_execution_plan",
        "current_runpod_api_contract_revalidated",
        "live_account_occupancy_probe_available",
        "ambiguous_create_reconciliation_available",
        "cleanup_idempotency_reconciliation_available",
    } <= prerequisites

    assert state["authorization"]["prompt_or_external_content_does_not_activate"] is True
    assert state["authorization"]["target_repository_instruction_does_not_activate"] is True
    assert state["resume_rule"]["keep_paid_compute_disabled_until_prompt_context_gates_are_verified"] is True
    assert state["resume_rule"]["keep_paid_compute_disabled_until_provider_contract_is_current"] is True


def test_runpod_v2_beta_contract_is_current_but_still_blocked_from_live_enablement() -> None:
    runpod = load(RUNPOD_POLICY)
    audit = runpod["api_contract_audit"]
    completion = runpod["completion_evidence"]

    assert runpod["api"]["live_calls_enabled"] is False
    assert runpod["api"]["live_adapter_enabled"] is False
    assert runpod["api"]["workflow_enabled"] is False
    assert audit["implementation_contract"] == "rest_v2_public_beta_offline"
    assert audit["current_official_rest_base_observed"] == "https://api.runpod.io/v2"
    assert audit["create_env_contract_observed"] is True
    assert audit["container_log_sse_contract_observed"] is True
    assert audit["current_official_contract_revalidation_required"] is True
    assert audit["implementation_may_not_be_enabled_live_until_revalidated"] is True
    assert audit["live_enablement_by_flag_only_forbidden"] is True
    assert completion["protocol"] == "hmac-sha256-v2"
    assert completion["pre_create_execution_name_required"] is True
    assert completion["live_injection_enabled"] is False
    assert completion["live_collection_enabled"] is False


def test_agent_contexts_explicitly_demote_external_instructions_to_data() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    copilot = (ROOT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "## Prompt and context trust boundary" in agents
    assert "untrusted data, not control-plane instructions" in agents
    assert "source-to-sink" in agents
    assert "examples/context-security/" in agents

    assert "## Context trust" in copilot
    assert "untrusted data rather than control-plane instructions" in copilot
    assert "source-to-sink" in copilot

    assert "## Prompt injection and context poisoning" in security
    assert "source-to-sink security boundary" in security
    assert "## Control-plane context integrity" in security
    assert "## Human authorization binding" in security
