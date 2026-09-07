from __future__ import annotations

from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from .validation import ValidationError, WorkloadRequest


class PolicyError(ValidationError):
    """Raised when a valid request exceeds configured policy."""


class _PolicyLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys instead of silently overriding safety limits."""


def _unique_mapping(loader: _PolicyLoader, node: yaml.MappingNode) -> dict[str, Any]:
    loader.flatten_mapping(node)
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise PolicyError("policy mapping keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_PolicyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _parse_policy(text: str) -> dict[str, Any]:
    if len(text) > 262144:
        raise PolicyError("policy file exceeds the 256 Ki-character limit")
    try:
        data = yaml.load(text, Loader=_PolicyLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        raise PolicyError("policy file contains invalid YAML") from exc
    if not isinstance(data, dict):
        raise PolicyError("policy file must contain a mapping")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise PolicyError("policy version must be integer 1")
    return data


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    """Load a policy file, or the policy bundled with gpu-control when omitted."""
    if path is None:
        resource = files("gpu_control").joinpath("default_policy.yaml")
        with resource.open("r", encoding="utf-8") as handle:
            return _parse_policy(handle.read(262145))

    policy_path = Path(path)
    with policy_path.open("r", encoding="utf-8") as handle:
        return _parse_policy(handle.read(262145))


def _positive_integer(value: Any, field: str) -> int:
    if type(value) is not int or value < 1:
        raise PolicyError(f"policy field {field} must be a positive integer")
    return value


def _as_decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise PolicyError(f"invalid decimal in policy: {field}")
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

    hard_gpu_count = _positive_integer(hard_limits.get("max_gpu_count"), "hard_limits.max_gpu_count")
    profile_gpu_count = _positive_integer(profile.get("max_gpu_count"), "profile.max_gpu_count")
    if hard_gpu_count != 1 or profile_gpu_count != 1:
        raise PolicyError("MVP policy requires exactly one allowed GPU")

    hard_runtime = _positive_integer(hard_limits.get("max_runtime_minutes"), "hard_limits.max_runtime_minutes")
    profile_runtime = _positive_integer(profile.get("max_runtime_minutes"), "profile.max_runtime_minutes")
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

    min_vram_gb = _positive_integer(profile.get("min_vram_gb"), "profile.min_vram_gb")

    return {
        "profile": request.gpu_profile,
        "min_vram_gb": min_vram_gb,
        "gpu_count": 1,
        "max_runtime_minutes": allowed_runtime,
        "max_cost_usd": str(allowed_cost),
    }
