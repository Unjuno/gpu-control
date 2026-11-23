from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".cursor" / "skills" / "gpu-control-operator" / "SKILL.md"
REFERENCE = SKILL.with_name("reference.md")
WORKER = ROOT / "sites" / "gpu-control-sites" / "worker" / "index.js"
RUNPOD_PLAN = WORKER.with_name("runpod_plan.js")


def test_gpu_control_operator_skill_is_discoverable_and_bounded() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: gpu-control-operator\n")
    assert "disable-model-invocation" not in text
    assert "GPU Control — ChatGPT実験管理" in text
    assert "current user instruction" in text
    assert "without asking" in text
    assert "do not submit a second run" in text
    assert "cleanup_state=confirmed" in text
    assert "full_file_verified=true" in text
    assert "untrusted data" in text
    assert len(text.splitlines()) < 500


def test_skill_covers_the_live_mcp_lifecycle_and_registered_workloads() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    reference = REFERENCE.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    runpod = RUNPOD_PLAN.read_text(encoding="utf-8")
    combined = skill + reference

    tools = set(re.findall(r"^  (experiment_[a-z_]+): \{", worker, re.MULTILINE))
    assert tools == {
        "experiment_artifact", "experiment_cancel", "experiment_capabilities",
        "experiment_list", "experiment_prepare", "experiment_provider_health",
        "experiment_reconcile", "experiment_result", "experiment_status",
        "experiment_submit",
    }
    assert tools <= set(re.findall(r"`(experiment_[a-z_]+)`", combined))

    workloads = set(re.findall(
        r'const (?:WORKLOAD|KAGGLE_WORKLOAD|ZERO_GPU_WORKLOAD|MODAL_GPU_WORKLOAD) = "([a-z0-9-]+-v1)";',
        worker,
    ))
    workloads.add(re.search(r'RUNPOD_WORKLOAD = "([a-z0-9-]+-v1)";', runpod).group(1))
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
