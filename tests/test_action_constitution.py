from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION_DOCUMENT = ROOT / "ACTION_CONSTITUTION.md"
CONSTITUTION_POLICY = ROOT / "policies" / "action-constitution.yaml"
DECISION_POLICY = ROOT / "policies" / "decision-policy.yaml"
AGENT_POLICY = ROOT / "policies" / "agent-policy.yaml"
REPOSITORY_STATE = ROOT / "policies" / "repository-state.yaml"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    assert isinstance(value, dict)
    return value


def test_action_constitution_is_normative_and_provider_neutral() -> None:
    policy = load_yaml(CONSTITUTION_POLICY)

    assert policy["name"] == "action_constitution"
    assert policy["status"] == "normative"
    assert policy["scope"] == "all_agent_actions"
    assert policy["provider_neutral"] is True

    document = CONSTITUTION_DOCUMENT.read_text(encoding="utf-8")
    assert "RunPod" not in document
    assert "RUNPOD_API_KEY" not in document
    assert "GitHub Actions" not in document


def test_constitution_has_complete_behavioral_articles() -> None:
    policy = load_yaml(CONSTITUTION_POLICY)
    article_ids = {article["id"] for article in policy["articles"]}

    assert article_ids == {
        "human_sovereignty",
        "goal_fidelity",
        "least_necessary_action",
        "evidence_before_escalation",
        "progressive_escalation_and_learning",
        "reversibility_blast_radius_and_recoverability",
        "economic_rationality_and_opportunity_cost",
        "meaningful_oversight_and_auditability",
        "graceful_restraint_and_recovery",
    }


def test_constitution_does_not_override_hard_boundaries_or_abandon_goal() -> None:
    policy = load_yaml(CONSTITUTION_POLICY)
    hierarchy = policy["hierarchy"]

    assert hierarchy["hard_safety_security_legal_and_external_authorization_are_non_bypassable"] is True
    assert hierarchy["human_principal_controls_active_objective"] is True
    assert hierarchy["constitution_governs_behavioral_tradeoffs"] is True
    assert hierarchy["repository_state_and_decision_policies_may_be_more_restrictive"] is True
    assert hierarchy["lower_policies_may_not_weaken_higher_level_hard_boundaries"] is True
    assert hierarchy["action_denial_must_not_imply_mission_abandonment_when_safe_progress_exists"] is True

    specialization = policy["specialization"]
    assert specialization["lower_policy_may_be_more_restrictive_for_concrete_risk"] is True
    assert specialization["lower_policy_may_not_grant_missing_authority"] is True
    assert specialization["lower_policy_may_not_turn_denied_action_into_goal_abandonment_without_reason"] is True


def test_constitution_conflict_order_balances_control_safety_and_progress() -> None:
    order = load_yaml(CONSTITUTION_POLICY)["conflict_resolution"]["order"]

    assert order == [
        "preserve_human_control",
        "prevent_unacceptable_irreversible_harm_or_unauthorized_action",
        "preserve_active_objective",
        "prefer_smaller_reversible_evidence_producing_progress",
        "maximize_useful_information_or_outcome_per_cost_and_risk",
        "stop_only_when_no_acceptable_path_remains",
    ]


def test_economic_article_avoids_both_waste_and_false_economy() -> None:
    policy = load_yaml(CONSTITUTION_POLICY)
    article = next(
        article
        for article in policy["articles"]
        if article["id"] == "economic_rationality_and_opportunity_cost"
    )
    requirements = set(article["requires"])

    assert "budget_is_loss_ceiling_not_spending_target" in requirements
    assert "remaining_budget_is_not_reason_to_spend" in requirements
    assert "prior_spend_is_not_reason_for_more_spend" in requirements
    assert "scarce_resource_occupancy_is_opportunity_cost" in requirements
    assert "optimize_useful_value_relative_to_cost_and_risk" in requirements
    assert "pure_cost_minimization_must_not_defeat_objective_or_required_quality" in requirements


def test_progressive_escalation_rejects_sunk_cost_and_automatic_scope_growth() -> None:
    policy = load_yaml(CONSTITUTION_POLICY)
    article = next(
        article
        for article in policy["articles"]
        if article["id"] == "progressive_escalation_and_learning"
    )
    requirements = set(article["requires"])

    assert "previous_success_does_not_authorize_next_stage" in requirements
    assert "previous_failure_does_not_justify_greater_scope_or_spend" in requirements
    assert "each_higher_impact_stage_requires_current_rationale" in requirements
    assert "early_low_cost_observations_should_be_able_to_stop_later_work" in requirements
    assert "sunk_cost_does_not_justify_continuation" in requirements


def test_decision_and_agent_policies_are_bound_to_constitution() -> None:
    decision = load_yaml(DECISION_POLICY)["constitution"]
    agent = load_yaml(AGENT_POLICY)["constitution"]

    assert decision["document"] == "ACTION_CONSTITUTION.md"
    assert decision["machine_policy"] == "policies/action-constitution.yaml"
    assert decision["must_conform"] is True
    assert decision["hard_boundaries_are_non_bypassable"] is True
    assert decision["denied_action_does_not_abandon_goal_when_safe_progress_exists"] is True

    assert agent["document"] == "ACTION_CONSTITUTION.md"
    assert agent["machine_policy"] == "policies/action-constitution.yaml"
    assert agent["normative"] is True
    assert agent["applies_before_decision_policy"] is True
    assert agent["hard_safety_security_and_external_authorization_are_non_bypassable"] is True
    assert agent["lower_policies_may_not_grant_missing_authority"] is True
    assert agent["lower_policies_may_not_abandon_active_goal_only_because_one_action_is_denied"] is True


def test_agent_contexts_read_constitution_before_execution_policy() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    copilot = (ROOT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Read and follow `ACTION_CONSTITUTION.md`" in agents
    assert "Read the constitution first" in agents
    assert "ACTION_CONSTITUTION.md" in copilot
    assert "highest-level behavioral norm" in copilot
    assert "## Action constitution" in readme
    assert "policies/action-constitution.yaml" in readme


def test_constitution_change_does_not_activate_parked_repository() -> None:
    state = load_yaml(REPOSITORY_STATE)

    assert state["mode"] == "parked"
    while_parked = state["while_parked"]
    assert while_parked["paid_workflow_allowed"] is False
    assert while_parked["provider_secret_reference_allowed"] is False
    assert while_parked["live_paid_compute_allowed"] is False
    assert while_parked["runpod_live_calls_allowed"] is False
    assert while_parked["generic_external_container_execution_allowed"] is False
