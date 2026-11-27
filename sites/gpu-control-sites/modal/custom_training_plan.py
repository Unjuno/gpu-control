"""Validate a custom GPU plan against trusted, independently configured rates.

Signature/owner binding and the atomic monthly reservation are separate caller
responsibilities. A plan is not executable merely because it passes this check.
"""
import re
import time


def validate_custom_command(command):
    """Allow only the manifest-derived Python entrypoint form."""
    if not isinstance(command, list) or len(command) != 2:
        raise ValueError("invalid_command")
    entrypoint = command[1]
    if (command[0] != "python" or not isinstance(entrypoint, str) or len(entrypoint) > 240 or
            not entrypoint.endswith(".py") or entrypoint.startswith("/") or
            any(not part or part in (".", "..") or re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None
                for part in entrypoint.split("/"))):
        raise ValueError("invalid_command")
    return entrypoint


def validate_custom_plan(plan, *, image_id, hourly_microusd, quote_expires_at, gpu,
                         manifest, lock_sha256, staging_hourly_microusd, max_runtime_seconds,
                         max_cost_ceiling_microusd, monthly_microusd, control_plane_sha, now=None):
    keys = {"execution_kind", "run_id", "registration_id", "execution_spec_id", "repository", "commit", "command",
            "manifest", "manifest_sha256", "lock_sha256", "dependencies_lock", "image_id", "image_digest",
            "provider", "provider_resource_id", "gpu", "gpu_count",
            "runtime_seconds", "max_cost_microusd", "hourly_microusd", "quote_expires_at",
            "estimated_cost_microusd", "monthly_budget_microusd", "task", "control_plane_sha",
            "staging_hourly_microusd", "staging_runtime_seconds", "staging_cpu_cores", "staging_memory_mib"}
    if not isinstance(plan, dict) or set(plan) != keys:
        raise ValueError("invalid_plan")
    for key in ("run_id", "registration_id", "execution_spec_id"):
        if not isinstance(plan[key], str) or re.fullmatch(r"[a-f0-9]{32}", plan[key]) is None:
            raise ValueError("invalid_plan")
    if (not isinstance(plan["commit"], str) or re.fullmatch(r"[a-f0-9]{40}", plan["commit"]) is None or
            not isinstance(plan["repository"], str) or
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", plan["repository"]) is None or
            plan["repository"].split("/")[1] in (".", "..")):
        raise ValueError("invalid_source")
    if (not isinstance(control_plane_sha, str) or re.fullmatch(r"[0-9a-f]{40}", control_plane_sha) is None or
            plan.get("control_plane_sha") != control_plane_sha):
        raise ValueError("training_control_plane_mismatch")
    command = plan["command"]
    # The public execution contract chooses a repository-relative Python entry
    # point. Do not let an agent or caller replace it with shell, an interpreter
    # flag, or an arbitrary command vector.
    validate_custom_command(command)
    if (plan["execution_kind"] != "owner_selected_python" or not isinstance(manifest, dict) or
            set(manifest) != {"dependencies_lock", "entrypoint", "gpu_profiles", "outputs",
                              "python_version", "schema_version", "task"} or
            plan["manifest"] != manifest or
            manifest.get("schema_version") != 1 or manifest.get("task") not in {"train", "evaluate"} or
            manifest.get("python_version") not in {"3.11", "3.12"} or
            not isinstance(manifest.get("gpu_profiles"), list) or
            any(profile not in {"T4", "L4"} for profile in manifest["gpu_profiles"]) or
            not isinstance(manifest.get("outputs"), list) or len(manifest["outputs"]) > 16 or
            not isinstance(plan["manifest_sha256"], str) or
            re.fullmatch(r"[0-9a-f]{64}", plan["manifest_sha256"]) is None or
            not isinstance(lock_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", lock_sha256) is None or
            plan["lock_sha256"] != lock_sha256 or
            not isinstance(plan["dependencies_lock"], str) or
            plan["dependencies_lock"] != manifest.get("dependencies_lock") or
            command != ["python", manifest.get("entrypoint")] or
            plan["gpu"] not in manifest.get("gpu_profiles", []) or plan["task"] != manifest["task"]):
        raise ValueError("training_manifest_mismatch")
    if (not isinstance(image_id, str) or re.fullmatch(r"im-[A-Za-z0-9]{8,128}", image_id) is None or
            plan["image_id"] != image_id or plan["image_digest"] != image_id or
            plan["provider"] != "modal" or
            plan["provider_resource_id"] != "gpu-control-provider-adapter/owner_training" or
            gpu not in {"L4", "T4"} or plan["gpu"] != gpu or
            type(plan["gpu_count"]) is not int or plan["gpu_count"] != 1):
        raise ValueError("training_profile_mismatch")
    now = int(time.time()) if now is None else now
    if (type(hourly_microusd) is not int or not 1 <= hourly_microusd <= 1_000_000_000 or
            type(quote_expires_at) is not int or not now < quote_expires_at <= now + 30 * 86400 or
            type(plan["hourly_microusd"]) is not int or plan["hourly_microusd"] != hourly_microusd or
            type(plan["quote_expires_at"]) is not int or plan["quote_expires_at"] != quote_expires_at):
        raise ValueError("training_quote_invalid")
    runtime, budget = plan["runtime_seconds"], plan["max_cost_microusd"]
    # Rate must cover all Sandbox components, not just the GPU. Reserve ten
    # percent margin and 600 seconds for startup, matching the worker's gate.
    if (type(max_runtime_seconds) is not int or not 120 <= max_runtime_seconds <= 3000 or
            type(max_cost_ceiling_microusd) is not int or not 1 <= max_cost_ceiling_microusd <= 1_000_000 or
            type(monthly_microusd) is not int or not 1 <= monthly_microusd <= 30_000_000 or
            type(staging_hourly_microusd) is not int or not 1 <= staging_hourly_microusd <= 1_000_000_000 or
            type(runtime) is not int or not 120 <= runtime <= min(3000, max_runtime_seconds) or
            type(budget) is not int or not 1 <= budget <= min(1_000_000, max_cost_ceiling_microusd) or
            type(plan.get("monthly_budget_microusd")) is not int or plan["monthly_budget_microusd"] != monthly_microusd or
            plan.get("staging_hourly_microusd") != staging_hourly_microusd or
            plan.get("staging_runtime_seconds") != 300 or plan.get("staging_cpu_cores") != 1 or
            plan.get("staging_memory_mib") != 1024 or
            plan.get("task") not in {"train", "evaluate"} or
            type(plan.get("estimated_cost_microusd")) is not int or
            plan["estimated_cost_microusd"] !=
              (hourly_microusd * (runtime + 300) + staging_hourly_microusd * 300 + 3239) // 3240 or
            plan["estimated_cost_microusd"] > budget or
            hourly_microusd * (runtime + 300) + staging_hourly_microusd * 300 > budget * 3240):
        raise ValueError("training_budget_invalid")
