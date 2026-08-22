from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from .validation import ValidationError, WorkloadRequest


class PolicyError(ValidationError):
    """Raised when a valid request exceeds configured policy."""


def load_policy(path: str | Path) -> dict[str, Any]:
    policy_path = Path(path)
    with policy_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise PolicyError("policy file must contain a mapping")
    return data


def _as_decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # defensive parse of trusted policy file
        raise PolicyError(f"invalid decimal in policy: {field}") from exc
    if not result.is_finite() or result <= 0:
        raise PolicyError(f"policy field {field} must be finite and positive")
    return result


def validate_against_policy(request: WorkloadRequest, policy: dict[str, Any]) -> dict[str, Any]:
    hard_limits = policy.get("hard_limits")
    profiles = policy.get("profiles")
    if not isinstance(hard_limits, dict) or not isinstance(profiles, dict):
        raise PolicyError("policy must define hard_limits and profiles mappings")

    profile = profiles.get(request.gpu_profile)
    if not isinstance(profile, dict):
        raise PolicyError(f"unknown gpu_profile: {request.gpu_profile}")

    hard_gpu_count = int(hard_limits.get("max_gpu_count", 0))
    profile_gpu_count = int(profile.get("max_gpu_count", 0))
    if hard_gpu_count != 1 or profile_gpu_count != 1:
        raise PolicyError("MVP policy requires exactly one allowed GPU")

    hard_runtime = int(hard_limits.get("max_runtime_minutes", 0))
    profile_runtime = int(profile.get("max_runtime_minutes", 0))
    allowed_runtime = min(hard_runtime, profile_runtime)
    if request.max_runtime_minutes > allowed_runtime:
        raise PolicyError(
            f"requested runtime {request.max_runtime_minutes}m exceeds policy limit {allowed_runtime}m"
        )

    hard_cost = _as_decimal(hard_limits.get("max_cost_usd"), "hard_limits.max_cost_usd")
    profile_cost = _as_decimal(profile.get("max_cost_usd"), f"profiles.{request.gpu_profile}.max_cost_usd")
    allowed_cost = min(hard_cost, profile_cost)
    if request.max_cost_usd > allowed_cost:
        raise PolicyError(
            f"requested cost ${request.max_cost_usd} exceeds policy limit ${allowed_cost}"
        )

    min_vram_gb = int(profile.get("min_vram_gb", 0))
    if min_vram_gb <= 0:
        raise PolicyError("profile min_vram_gb must be positive")

    return {
        "profile": request.gpu_profile,
        "min_vram_gb": min_vram_gb,
        "gpu_count": 1,
        "max_runtime_minutes": allowed_runtime,
        "max_cost_usd": str(allowed_cost),
    }
