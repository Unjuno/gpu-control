"""Provider-side entry point for a pinned MAP-44M training image."""
from pathlib import Path
import re
import time

from map_checkpoint import checkpoint_manifest


def validate_map_plan(plan, *, source_sha, image_digest, hourly_microusd, quote_expires_at):
    """Check the exact reviewed profile against trusted provider settings."""
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
    now = int(time.time())
    if (type(quote_expires_at) is not int or not now < quote_expires_at <= now + 3600
            or plan["quote_expires_at"] != quote_expires_at
            or hourly_rate != hourly_microusd):
        raise ValueError("training_quote_invalid")
    if (type(seconds) is not int or not 120 <= seconds <= 3000
            or type(budget) is not int or not 1 <= budget <= 1_000_000
            or type(hourly_rate) is not int or not 1 <= hourly_rate <= 1_000_000_000
            or hourly_rate * (seconds + 600) > budget * 3240):
        raise ValueError("training_budget_invalid")

    return run_id, seconds, budget, hourly_rate


def run_map_training(plan, *, source_sha, image_digest, hourly_microusd, quote_expires_at,
                     config, corpus_dir, runs_dir: Path, commit_volume, train):
    """Run a previously authorized plan using server-selected data and config."""
    run_id, seconds, budget, hourly_rate = validate_map_plan(
        plan, source_sha=source_sha, image_digest=image_digest,
        hourly_microusd=hourly_microusd, quote_expires_at=quote_expires_at,
    )
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
