"""Policy decisions for the narrowly preauthorized local CPU lane."""

from dataclasses import dataclass
import hashlib
import json
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    approval_required: bool
    blocking_reason: str | None
    policy_digest: str
    valid_until: int | None


def evaluate_admission(plan, policy, now: int) -> AdmissionDecision:
    try:
        canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        policy_digest = hashlib.sha256(canonical).hexdigest()
        version = policy["version"]
        valid_until = policy["valid_until"]
        enabled = policy["enabled"]
        workloads = policy["workloads"]
        max_runtime = policy["max_runtime_seconds"]
        max_cost = Decimal(policy["max_cost_usd"])
        profiles = policy["allowed_profiles"]
        valid_policy = (
            isinstance(version, str) and bool(version) and type(valid_until) is int and
            type(enabled) is bool and isinstance(workloads, list) and
            all(isinstance(item, str) for item in workloads) and type(max_runtime) is int and
            isinstance(profiles, list) and all(isinstance(item, str) for item in profiles) and
            max_cost.is_finite() and max_cost >= 0
        )
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return AdmissionDecision(False, True, "INVALID_POLICY", "", None)

    if not valid_policy:
        return AdmissionDecision(False, True, "INVALID_POLICY", policy_digest, None)

    blocker = None
    if not enabled:
        blocker = "POLICY_DISABLED"
    elif valid_until <= now:
        blocker = "POLICY_EXPIRED"
    elif version != plan.authorization_policy_version:
        blocker = "POLICY_VERSION_MISMATCH"
    elif plan.provider != "local_cpu":
        blocker = "PROVIDER_NOT_LOCAL_CPU"
    elif plan.device_requirement.get("requires_gpu") is not False or plan.device_requirement.get("kind") != "cpu":
        blocker = "GPU_NOT_ALLOWED"
    elif plan.workload not in workloads:
        blocker = "WORKLOAD_NOT_ALLOWLISTED"
    elif plan.device_requirement.get("profile") not in profiles:
        blocker = "PROFILE_NOT_ALLOWED"
    elif plan.runtime_seconds > max_runtime:
        blocker = "RUNTIME_LIMIT"
    elif max_cost != 0 or plan.max_cost_usd != 0:
        blocker = "NONZERO_COST_CAP"
    else:
        evidence = plan.cost_evidence
        if (evidence.classification != "LOCAL" or evidence.additional_cost_usd != 0 or
                not evidence.reference or type(evidence.observed_at) is not int or
                evidence.observed_at > now or type(evidence.expires_at) is not int or
                evidence.expires_at <= now):
            blocker = "COST_NOT_VERIFIED_FREE"

    return AdmissionDecision(blocker is None, False if blocker is None else True,
                             blocker, policy_digest, valid_until)
