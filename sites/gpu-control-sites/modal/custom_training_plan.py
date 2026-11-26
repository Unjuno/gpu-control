"""Validate a custom GPU plan against trusted, independently configured rates.

Signature/owner binding and the atomic monthly reservation are separate caller
responsibilities. A plan is not executable merely because it passes this check.
"""
import re
import time


def validate_custom_plan(plan, *, image_id, hourly_microusd, quote_expires_at, gpu, now=None):
    keys = {"run_id", "registration_id", "execution_spec_id", "repository", "commit", "command",
            "image_id", "gpu", "gpu_count", "runtime_seconds", "max_cost_microusd",
            "hourly_microusd", "quote_expires_at"}
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
    command = plan["command"]
    if (not isinstance(command, list) or not 1 <= len(command) <= 32 or
            any(not isinstance(arg, str) or not arg or len(arg) > 1024 or "\x00" in arg for arg in command)):
        raise ValueError("invalid_command")
    if (not isinstance(image_id, str) or re.fullmatch(r"im-[A-Za-z0-9]{8,128}", image_id) is None or
            plan["image_id"] != image_id or gpu not in {"L4", "T4"} or plan["gpu"] != gpu or
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
    if (type(runtime) is not int or not 120 <= runtime <= 3000 or
            type(budget) is not int or not 1 <= budget <= 1_000_000 or
            hourly_microusd * (runtime + 600) > budget * 3240):
        raise ValueError("training_budget_invalid")
