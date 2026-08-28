from pathlib import Path

import yaml


STATE = Path(__file__).resolve().parents[1] / "policies" / "repository-state.yaml"


def test_vlab16_local_gpu_validation_is_selected_without_enabling_runpod() -> None:
    state = yaml.safe_load(STATE.read_text(encoding="utf-8"))
    local = state["local_validation"]

    assert state["mode"] == "parked"
    assert local == {
        "selected": True,
        "execution_target": "local",
        "host_label": "VLab16",
        "expected_gpu_name_substring": "RTX 3080",
        "repository": "Unjuno/orbitune",
        "candidate_pr": 14,
        "candidate_source_sha": "d94846a6e115ab08e4fb7eb0fff975ef8183f4f6",
        "merge_required_before_canonical_run": True,
        "dockerfile_path": "workloads/local-gpu-canary/Dockerfile",
        "launcher_path": "workloads/local-gpu-canary/run-local.sh",
        "workload_id": "orbitune-local-gpu-canary-v1",
        "steps": 250,
        "batch_size": 4,
        "sequence_length": 256,
        "training_tokens": 256000,
        "provider_cost_usd": 0,
        "runpod_required": False,
        "runpod_credentials_required": False,
        "state": "pending_orbitune_merge_and_local_execution",
    }

    parked = state["while_parked"]
    assert parked["live_paid_compute_allowed"] is False
    assert parked["runpod_live_calls_allowed"] is False
    assert parked["runpod_live_adapter_allowed"] is False
    assert parked["runpod_workflow_allowed"] is False
