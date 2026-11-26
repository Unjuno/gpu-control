"""Provider-side entry point for a pinned MAP-44M training image."""
import json
from pathlib import Path
import re
import time

from map_checkpoint import checkpoint_manifest


MAX_PRICING_AGE_SECONDS = 30 * 24 * 60 * 60
MAX_TRAINING_BUDGET_MICROUSD = 250_000
MAX_TRAINING_RUNTIME_SECONDS = 120
CHECKPOINT_FINALIZATION_SECONDS = 45


def validate_map_plan(plan, *, source_sha, image_digest, hourly_microusd, quote_expires_at):
    """Check the exact reviewed profile against trusted provider settings."""
    if not isinstance(plan, dict):
        raise ValueError("training_plan_invalid")
    if (plan["commit"] != source_sha or plan["image_digest"] != image_digest
            or plan["repository"] != "unjuno/model-as-a-paper"
            or plan["gpu"] != "L4" or plan["gpu_count"] != 1
            or plan.get("provider") != "modal"
            or plan.get("provider_resource_id") != "gpu-control-map-training/train_map"):
        raise ValueError("training_profile_mismatch")
    dataset, run_name, steps = plan.get("dataset"), plan.get("run_name"), plan.get("steps")
    if (not isinstance(dataset, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", dataset) is None
            or not isinstance(run_name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_name) is None
            or type(steps) is not int or not 1 <= steps <= 100000):
        raise ValueError("training_parameters_invalid")
    run_id = plan["run_id"]
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise ValueError("invalid_run_id")
    seconds = plan["runtime_seconds"]
    budget = plan["max_cost_microusd"]
    hourly_rate = plan["hourly_microusd"]
    now = int(time.time())
    if (type(quote_expires_at) is not int or not now < quote_expires_at <= now + MAX_PRICING_AGE_SECONDS
            or plan["quote_expires_at"] != quote_expires_at
            or hourly_rate != hourly_microusd):
        raise ValueError("training_quote_invalid")
    if (type(seconds) is not int or seconds != MAX_TRAINING_RUNTIME_SECONDS
            or type(budget) is not int or not 1 <= budget <= MAX_TRAINING_BUDGET_MICROUSD
            or type(hourly_rate) is not int or not 1 <= hourly_rate <= 1_000_000_000
            or hourly_rate * (seconds + 600) > budget * 3240):
        raise ValueError("training_budget_invalid")

    return run_id, seconds, budget, hourly_rate, dataset, run_name, steps


def run_map_training(plan, *, source_sha, image_digest, hourly_microusd, quote_expires_at,
                     config, corpus_dir, runs_dir: Path, commit_volume, train):
    """Run a previously authorized plan using server-selected data and config."""
    run_id, seconds, budget, hourly_rate, dataset, run_name, steps = validate_map_plan(
        plan, source_sha=source_sha, image_digest=image_digest,
        hourly_microusd=hourly_microusd, quote_expires_at=quote_expires_at,
    )
    corpus_root = Path(corpus_dir).resolve(strict=True)
    dataset_path = (corpus_root / dataset).resolve(strict=True)
    if dataset_path.parent != corpus_root or not dataset_path.is_dir():
        raise ValueError("training_dataset_unavailable")
    run_dir = Path(runs_dir) / run_id
    metadata_path = Path(runs_dir) / f"{run_id}.gpu-control-run.json"
    if run_dir.exists() or metadata_path.exists():
        raise ValueError("training_run_directory_exists")
    metadata_path.write_text(
        json.dumps({"run_id": run_id, "run_name": run_name,
                    "dataset": dataset, "steps_limit": steps},
                   sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    commit_volume()
    result = train(
        config, dataset_path, run_dir, device="cuda", steps=steps,
        seconds=seconds - CHECKPOINT_FINALIZATION_SECONDS, budget_usd=budget / 1_000_000,
        hourly_rate=hourly_rate / 1_000_000, on_save=commit_volume,
    )
    if (not isinstance(result, dict) or not str(result.get("device", "")).startswith("cuda")
            or type(result.get("steps")) is not int or not 1 <= result["steps"] <= steps):
        raise ValueError("training_gpu_result_invalid")
    commit_volume()
    return {
        "run_id": run_id, "source_sha": source_sha, "image_digest": image_digest,
        "gpu_used": True, "steps": result["steps"], "dataset": dataset, "run_name": run_name,
        "checkpoint": checkpoint_manifest(runs_dir, run_id),
    }
