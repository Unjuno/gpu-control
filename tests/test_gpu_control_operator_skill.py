from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".cursor" / "skills" / "gpu-control-operator" / "SKILL.md"
REFERENCE = SKILL.with_name("reference.md")
WORKER = ROOT / "sites" / "gpu-control-sites" / "worker" / "index.js"
RUNPOD_PLAN = WORKER.with_name("runpod_plan.js")
WORKLOAD_REGISTRY = WORKER.parents[1] / "workloads" / "registry.json"


def test_gpu_control_operator_skill_is_discoverable_and_bounded() -> None:
    raw_text = SKILL.read_text(encoding="utf-8")
    text = " ".join(raw_text.split())
    assert raw_text.startswith("---\nname: gpu-control-operator\n")
    assert "disable-model-invocation" not in text
    assert "GPU Control — ChatGPT実験管理" in text
    assert "current user instruction" in text
    assert "without asking" in text
    assert "do not submit a second run" in text
    assert "retain it across retries if a response is lost" in text
    assert "Never ask the user to create or remember an ID" in text
    assert "cleanup_state=confirmed" in text
    assert "full_file_verified=true" in text
    assert "untrusted data" in text
    assert len(text.splitlines()) < 500


def test_skill_covers_the_live_mcp_lifecycle_and_registered_workloads() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    reference = REFERENCE.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    combined = skill + reference
    assert "agent-generated opaque `idempotency_key`" in reference
    assert "a separate later call cannot recover a key" in reference

    tools = set(re.findall(r"^  (experiment_[a-z_]+): \{", worker, re.MULTILINE))
    assert tools == {
        "experiment_artifact", "experiment_cancel", "experiment_capabilities",
        "experiment_list", "experiment_prepare", "experiment_provider_health",
        "experiment_reconcile", "experiment_result", "experiment_status",
        "experiment_submit",
    }
    assert tools <= set(re.findall(r"`(experiment_[a-z_]+)`", combined))

    registry = json.loads(WORKLOAD_REGISTRY.read_text(encoding="utf-8"))
    workloads = {item["id"] for item in registry["workloads"].values()}
    assert workloads == {
        "modal-gpu-vector-add-v1", "orbitune-kaggle-100-step-v1",
        "orbitune-zero-gpu-eval-v1", "runpod-gpu-canary-v1",
        "tiny-stories-inference-v1",
    }
    assert workloads <= set(re.findall(r"`([a-z0-9-]+-v1)`", skill))


def test_skill_does_not_restore_retired_infrastructure_or_embed_secrets() -> None:
    text = SKILL.read_text(encoding="utf-8") + REFERENCE.read_text(encoding="utf-8")
    for retired in ("Vercel", "Neon", "Railway", "Keychain Runner"):
        assert retired in text
    assert "do not recreate" in text
    assert not re.search(r"(?:hf_|rpa_|sk-)[A-Za-z0-9_-]{20,}", text)
    assert "Never copy an old plan" in text
