from custom_training_tool_args import uses_custom_training_lane


def test_owner_selected_plan_recovers_journal_less_status_cancel_and_artifact_calls():
    plan = {"execution_kind": "owner_selected_python"}
    for tool in ("training_status", "training_cancel", "training_checkpoint", "training_artifact"):
        assert uses_custom_training_lane(tool, {"approved_plan": plan}, None)


def test_submit_routes_from_plan_and_existing_submission_remains_authoritative():
    assert uses_custom_training_lane("training_submit", {"plan": {"execution_kind": "owner_selected_python"}}, None)
    assert uses_custom_training_lane("training_status", {}, {"run_id": "owner-run"})


def test_registered_workload_does_not_enter_custom_lane():
    assert not uses_custom_training_lane("training_status", {
        "approved_plan": {"execution_kind": "map_training"}}, None)
    assert not uses_custom_training_lane("training_submit", {
        "plan": {"execution_kind": "map_training"}}, None)
