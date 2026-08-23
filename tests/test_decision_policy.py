from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DECISION_POLICY_PATH = ROOT / "policies" / "decision-policy.yaml"
AGENT_POLICY_PATH = ROOT / "policies" / "agent-policy.yaml"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    assert isinstance(value, dict)
    return value


def test_decision_policy_preserves_goal_when_one_action_is_denied() -> None:
    policy = load_yaml(DECISION_POLICY_PATH)

    assert policy["principle"] == "goal_preserving_restraint"
    assert policy["mission"]["action_denial_does_not_equal_goal_failure"] is True
    assert policy["mission"]["safe_progress_preferred_over_unnecessary_stop"] is True

    denied = policy["when_action_is_not_approved"]
    assert denied["preserve_active_goal_if_not_achieved"] is True
    assert denied["report_specific_reason"] is True
    assert denied["propose_cheapest_safe_next_step"] is True
    assert denied["prefer_local_or_read_only_progress"] is True
    assert denied["escalate_to_human_if_no_safe_autonomous_step"] is True
    assert denied["do_not_mark_goal_failed_solely_because_action_was_denied"] is True


def test_action_outcomes_degrade_scope_before_denial() -> None:
    policy = load_yaml(DECISION_POLICY_PATH)
    assert policy["action_outcomes"]["order"] == [
        "continue",
        "reduce_scope",
        "safer_alternative",
        "human_checkpoint",
        "deny_action",
    ]


def test_escalation_requires_new_information_not_failure_or_remaining_budget() -> None:
    policy = load_yaml(DECISION_POLICY_PATH)
    escalation = policy["escalation_rules"]
    progressive = policy["progressive_experimentation"]

    assert escalation["uncertainty_must_not_increase_action_scope"] is True
    assert escalation["previous_stage_success_does_not_authorize_next_stage"] is True
    assert escalation["previous_failure_does_not_justify_more_spend"] is True
    assert escalation["remaining_budget_is_not_a_reason_to_spend"] is True
    assert escalation["provider_availability_is_not_a_reason_to_allocate"] is True

    assert progressive["use_smallest_experiment_that_can_change_the_next_decision"] is True
    assert progressive["require_success_condition_before_execution"] is True
    assert progressive["require_stop_condition_before_execution"] is True
    assert progressive["require_failure_information_value_before_paid_execution"] is True
    assert progressive["stop_when_current_question_is_answered"] is True
    assert progressive["expansion_requires_new_information_from_prior_stage"] is True


def test_hard_stop_is_last_resort_and_not_normal_control_flow() -> None:
    policy = load_yaml(DECISION_POLICY_PATH)
    hard_stop = policy["hard_stop"]

    assert hard_stop["is_last_resort"] is True
    assert set(hard_stop["applies_when"]) == {
        "explicit_human_cancellation",
        "no_safe_or_authorized_path_remains",
        "objective_is_no_longer_valid",
        "required_action_has_unacceptable_irreversible_downside",
    }
    assert hard_stop["after_hard_stop"]["preserve_audit_reason"] is True
    assert hard_stop["after_hard_stop"]["report_what_would_be_required_to_resume_when_applicable"] is True


def test_paid_decision_record_is_about_value_not_only_budget() -> None:
    policy = load_yaml(DECISION_POLICY_PATH)
    required = set(policy["decision_record"]["required_before_paid_compute"])

    assert required == {
        "active_goal",
        "current_question",
        "cheapest_viable_alternative",
        "why_cheaper_alternative_is_insufficient",
        "expected_decision_impact",
        "maximum_justified_cost",
        "success_condition",
        "stop_condition",
        "failure_learning_value",
        "worst_case_downside",
    }
    assert policy["decision_record"]["budget_is_loss_ceiling_not_spending_target"] is True


def test_agent_policy_integrates_decision_gate_before_paid_compute() -> None:
    policy = load_yaml(AGENT_POLICY_PATH)
    stages = policy["stages"]
    decision_stage = next(stage for stage in stages if stage["id"] == "decision_gate")
    paid_stage = next(stage for stage in stages if stage["id"] == "paid_gpu_runpod")

    assert decision_stage["required"] is True
    assert decision_stage["order"] < paid_stage["order"]
    assert policy["decision_governance"]["policy"] == "policies/decision-policy.yaml"
    assert policy["decision_governance"]["action_denial_does_not_equal_goal_failure"] is True
    assert policy["decision_governance"]["safe_progress_preferred_over_unnecessary_stop"] is True
    assert policy["decision_governance"]["hard_stop_is_last_resort"] is True

    paid_requirements = set(policy["paid_compute"]["requires"])
    assert "active_goal" in paid_requirements
    assert "current_decision_rationale" in paid_requirements
    assert "cheapest_viable_alternative_considered" in paid_requirements
    assert "expected_decision_impact" in paid_requirements
    assert "explicit_success_condition" in paid_requirements
    assert "explicit_stop_condition" in paid_requirements
    assert "failure_learning_value" in paid_requirements
    assert "maximum_justified_cost" in paid_requirements


def test_agent_policy_forbids_both_reckless_escalation_and_needless_paralysis() -> None:
    forbidden = set(load_yaml(AGENT_POLICY_PATH)["forbidden"])

    assert "paid_compute_without_current_decision_rationale" in forbidden
    assert "open_ended_experiment_without_stop_condition" in forbidden
    assert "spending_remaining_budget_without_new_rationale" in forbidden
    assert "escalating_scope_after_failure_without_new_evidence" in forbidden
    assert "assuming_previous_stage_authorizes_next_stage" in forbidden
    assert "treating_action_denial_as_goal_failure" in forbidden
    assert "unnecessary_hard_stop_when_safe_progress_exists" in forbidden


def test_decision_governance_context_is_present() -> None:
    assert (ROOT / "docs" / "DECISION_GOVERNANCE.md").is_file()
    assert (ROOT / "policies" / "decision-policy.yaml").is_file()

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "goal-preserving restraint" in agents
    assert "Rejecting one action is not the same as abandoning the goal" in agents
