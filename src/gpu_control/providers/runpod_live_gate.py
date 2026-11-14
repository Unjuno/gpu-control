"""Hard stop for RunPod while the repository remains in parked mode.

Enabling this module requires a reviewed source change after repository policy,
account, authorization, result transport, and cleanup prerequisites are complete.
Runtime config and caller-supplied booleans must not activate paid allocation.
"""

from datetime import datetime, timezone

from ..execution import ApprovedExecutionPlan
from ..human_authorization import HumanAuthorizationError, LiveExecutionPermit


class RunPodLiveDisabledError(RuntimeError):
    """Raised when code attempts a RunPod operation while live use is parked."""


# Intentionally fixed in source. The checked-in repository state is parked and
# policy booleans alone are not an activation mechanism.
RUNPOD_LIVE_ALLOCATION_ENABLED = False


def require_runpod_live_allocation_enabled() -> None:
    if not RUNPOD_LIVE_ALLOCATION_ENABLED:
        raise RunPodLiveDisabledError("RunPod live calls are disabled while repository mode is parked")


def validate_runpod_create_authorization(
    plan: ApprovedExecutionPlan,
    live_permit: LiveExecutionPermit,
) -> None:
    """Require a current in-process permit for the exact RunPod plan at create."""
    try:
        plan.validate_shape()
        if plan.provider != "runpod":
            raise ValueError("RunPod create requires a runpod approved plan")
        if not isinstance(live_permit, LiveExecutionPermit):
            raise ValueError("RunPod create requires a live execution permit")
        live_permit.validate_for_plan(plan, now_utc=datetime.now(timezone.utc))
    except (HumanAuthorizationError, ValueError) as exc:
        raise ValueError(f"RunPod create authorization is invalid: {exc}") from exc
