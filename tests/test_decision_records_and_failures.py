from decimal import Decimal
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "policies" / "decision-record-schema.yaml"
FAILURE_CATALOG_PATH = ROOT / "policies" / "failure-catalog.yaml"
DECISION_POLICY_PATH = ROOT / "policies" / "decision-policy.yaml"
STATE_PATH = ROOT / "policies" / "repository-state.yaml"
EXAMPLES_DIR = ROOT / "examples" / "decision-records"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    assert isinstance(value, dict)
    return value


def assert_non_empty_string(value: object) -> None:
    assert isinstance(value, str)
    assert value.strip()


def test_decision_record_schema_is_offline_and_non_authoritative() -> None:
    schema = load_yaml(SCHEMA_PATH)

    assert schema["version"] == 1
    assert schema["name"] == "DecisionRecord"
    assert schema["runtime_enforced"] is False

    example_safety = schema["example_safety"]
    assert example_safety["examples_are_illustrative_only"] is True
    assert example_safety["examples_never_grant_authority"] is True
    assert example_safety["examples_never_prove_current_price_or_availability"] is True
    assert example_safety["examples_never_override_repository_state"] is True
    assert example_safety["examples_must_not_be_copied_as_live_authorization"] is True
    assert example_safety["current_facts_must_be_revalidated"] is True


def test_few_shot_examples_cover_all_action_outcomes_and_validate_shape() -> None:
    schema = load_yaml(SCHEMA_PATH)
    required = set(schema["required_fields"])
    allowed_outcomes = set(schema["fields"]["decision"]["action_outcome_values"])
    allowed_reversibility = set(schema["fields"]["risk"]["reversibility_values"])
    allowed_blast_radius = set(schema["fields"]["risk"]["blast_radius_values"])

    example_paths = sorted(EXAMPLES_DIR.glob("*.yaml"))
    assert len(example_paths) >= 5

    record_ids: set[str] = set()
    outcomes: set[str] = set()

    for path in example_paths:
        record = load_yaml(path)
        assert required.issubset(record)
        assert record["schema_version"] == 1
        assert record["illustrative_only"] is True

        record_id = record["record_id"]
        assert_non_empty_string(record_id)
        assert record_id.startswith("EXAMPLE-DR-")
        assert record_id not in record_ids
        record_ids.add(record_id)

        assert_non_empty_string(record["active_goal"])
        assert_non_empty_string(record["current_question"])
        assert_non_empty_string(record["proposed_action"])
        assert isinstance(record["evidence"], list) and record["evidence"]
        assert isinstance(record["alternatives_considered"], list) and record["alternatives_considered"]
        assert_non_empty_string(record["cheapest_viable_alternative"])
        assert_non_empty_string(record["why_cheaper_alternative_is_insufficient"])
        assert_non_empty_string(record["expected_decision_impact"])

        economic = record["economic"]
        expected_cost = economic["expected_cost_usd"]
        maximum_cost = economic["maximum_justified_cost_usd"]
        assert isinstance(expected_cost, str)
        assert isinstance(maximum_cost, str)
        assert Decimal(expected_cost) >= 0
        assert Decimal(maximum_cost) >= 0
        assert Decimal(expected_cost) <= Decimal(maximum_cost)
        assert economic["budget_is_loss_ceiling"] is True
        assert_non_empty_string(economic["opportunity_cost"])

        risk = record["risk"]
        assert risk["reversibility"] in allowed_reversibility
        assert risk["blast_radius"] in allowed_blast_radius
        assert_non_empty_string(risk["worst_case_downside"])
        assert_non_empty_string(risk["recovery_path"])

        authority = record["authority"]
        assert_non_empty_string(authority["required_authority"])
        assert authority["authority_reference"] is None
        assert authority["current_authority_verified"] is False

        conditions = record["conditions"]
        assert_non_empty_string(conditions["success_condition"])
        assert_non_empty_string(conditions["stop_condition"])
        assert_non_empty_string(conditions["failure_learning_value"])

        decision = record["decision"]
        outcome = decision["action_outcome"]
        assert outcome in allowed_outcomes
        outcomes.add(outcome)
        assert_non_empty_string(decision["rationale"])
        assert_non_empty_string(decision["next_safe_step"])
        assert isinstance(decision["human_checkpoint_required"], bool)

    assert outcomes == allowed_outcomes


def test_few_shot_examples_do_not_embed_secret_or_live_authority_evidence() -> None:
    forbidden_fragments = (
        "secrets.runpod_api_key",
        "${{ secrets.",
        "authorization_reference:",
    )

    for path in sorted(EXAMPLES_DIR.glob("*.yaml")):
        text = path.read_text(encoding="utf-8").lower()
        for fragment in forbidden_fragments:
            assert fragment not in text


def test_failure_catalog_has_stable_unique_ids_and_constitutional_responses() -> None:
    catalog = load_yaml(FAILURE_CATALOG_PATH)
    failures = catalog["failures"]

    assert len(failures) >= 15
    ids = [failure["id"] for failure in failures]
    assert len(ids) == len(set(ids))
    assert ids == [f"F{index:03d}" for index in range(1, len(ids) + 1)]

    valid_articles = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"}
    for failure in failures:
        assert_non_empty_string(failure["name"])
        assert_non_empty_string(failure["category"])
        assert_non_empty_string(failure["pattern"])
        assert isinstance(failure["signals"], list) and failure["signals"]
        assert set(failure["constitutional_articles"]).issubset(valid_articles)
        assert failure["constitutional_articles"]
        assert_non_empty_string(failure["required_response"])

    names = {failure["name"] for failure in failures}
    assert {
        "goal_drift",
        "sunk_cost_escalation",
        "authorization_inheritance",
        "defensive_paralysis",
        "resource_hoarding",
        "cleanup_blindness",
        "example_laundering",
        "scope_laundering",
        "failure_without_learning",
    }.issubset(names)


def test_failure_catalog_preserves_goal_and_does_not_create_authority() -> None:
    rules = load_yaml(FAILURE_CATALOG_PATH)["catalog_rules"]

    assert rules["failures_are_patterns_not_permissions"] is True
    assert rules["detection_signal_is_not_proof"] is True
    assert rules["response_should_preserve_goal_when_safe"] is True
    assert rules["hard_stop_is_last_resort"] is True
    assert rules["current_repository_state_must_be_rechecked"] is True
    assert rules["examples_and_prior_incidents_never_grant_authority"] is True


def test_decision_policy_binds_schema_examples_and_failure_catalog_without_runtime_activation() -> None:
    policy = load_yaml(DECISION_POLICY_PATH)["decision_record"]

    assert policy["schema"] == "policies/decision-record-schema.yaml"
    assert policy["documentation"] == "docs/DECISION_RECORD.md"
    assert policy["examples_directory"] == "examples/decision-records"
    assert policy["failure_catalog"] == "policies/failure-catalog.yaml"
    assert policy["runtime_binding_enabled"] is False
    assert policy["illustrative_examples_never_grant_authority"] is True
    assert policy["illustrative_examples_never_prove_current_external_state"] is True
    assert policy["current_facts_must_be_revalidated"] is True
    assert policy["consult_failure_catalog_before_consequential_escalation"] is True


def test_agent_context_teaches_safe_few_shot_usage() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    copilot = (ROOT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")

    for text in (agents, copilot):
        assert "policies/decision-record-schema.yaml" in text
        assert "policies/failure-catalog.yaml" in text
        assert "examples/decision-records/" in text
        assert "example" in text.lower()
        assert "authority" in text.lower()
        assert "revalid" in text.lower()

    assert "example_laundering" in agents
    assert "example laundering" in copilot


def test_runtime_execution_gate_is_not_implicitly_bound_to_decision_record() -> None:
    execution = (ROOT / "src" / "gpu_control" / "execution.py").read_text(encoding="utf-8")
    assert "DecisionRecord" not in execution
    assert "decision-record-schema" not in execution


def test_repository_remains_parked_after_decision_context_additions() -> None:
    state = load_yaml(STATE_PATH)
    assert state["mode"] == "parked"
    assert state["while_parked"]["live_paid_compute_allowed"] is False
    assert state["while_parked"]["provider_secret_reference_allowed"] is False
    assert state["while_parked"]["runpod_live_calls_allowed"] is False
