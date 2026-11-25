"""Provider-side entry point for a pinned MAP-44M training image."""
from pathlib import Path
import re

from map_checkpoint import checkpoint_manifest


def run_map_training(plan, *, source_sha, image_digest, config, corpus_dir,
                     runs_dir: Path, commit_volume, train):
    """Run a previously authorized plan using server-selected data and config."""
    if (plan["commit"] != source_sha or plan["image_digest"] != image_digest
            or plan["repository"] != "unjuno/model-as-a-paper"
            or plan["gpu"] != "L4" or plan["gpu_count"] != 1):
        raise ValueError("training_profile_mismatch")
    run_id = plan["run_id"]
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise ValueError("invalid_run_id")
    seconds = plan["runtime_seconds"]
    budget = plan["max_cost_microusd"]
    hourly_rate = plan["hourly_microusd"]
    if (type(seconds) is not int or not 120 <= seconds <= 3000
            or type(budget) is not int or not 1 <= budget <= 1_000_000
            or type(hourly_rate) is not int or not 1 <= hourly_rate <= 1_000_000_000
            or hourly_rate * (seconds + 600) > budget * 3240):
        raise ValueError("training_budget_invalid")

    result = train(
        config, corpus_dir, runs_dir / run_id, device="cuda", steps=100_000,
        seconds=seconds, budget_usd=budget / 1_000_000,
        hourly_rate=hourly_rate / 1_000_000, on_save=commit_volume,
    )
    if (not isinstance(result, dict) or not str(result.get("device", "")).startswith("cuda")
            or type(result.get("steps")) is not int or result["steps"] < 1):
        raise ValueError("training_gpu_result_invalid")
    return {
        "run_id": run_id, "source_sha": source_sha, "image_digest": image_digest,
        "gpu_used": True, "steps": result["steps"],
        "checkpoint": checkpoint_manifest(runs_dir, run_id),
    }
