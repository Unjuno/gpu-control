from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from ..execution import ApprovedExecutionPlan
from .runpod_occupancy import RunPodAccountOccupancyEvidence, build_account_occupancy_evidence
from .runpod_v2 import RunPodV2HttpClient


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_live_account_occupancy_probe(
    client: RunPodV2HttpClient,
    *,
    clock: Callable[[], datetime] = _utc_now,
    ttl_seconds: int = 30,
) -> Callable[[ApprovedExecutionPlan], RunPodAccountOccupancyEvidence]:
    """Build the production account-wide occupancy probe from RunPod v2 List Pods.

    The returned callable performs one fresh ``GET /v2/pods`` per invocation and
    normalizes the entire authenticated account into short-lived evidence. It does
    not filter by gpu-control Pod name: any non-TERMINATED Pod keeps the account
    busy under the current single-tenant paid policy.
    """

    if not isinstance(client, RunPodV2HttpClient):
        raise TypeError("client must be a RunPodV2HttpClient")
    if not callable(clock):
        raise TypeError("clock must be callable")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 60:
        raise ValueError("ttl_seconds must be between 1 and 60")

    def probe(plan: ApprovedExecutionPlan) -> RunPodAccountOccupancyEvidence:
        payload = client.list_pods()
        pods = payload.get("pods")
        if not isinstance(pods, list):
            raise ValueError("RunPod List Pods response is missing pods")
        return build_account_occupancy_evidence(
            plan,
            pods,
            checked_at_utc=clock(),
            ttl_seconds=ttl_seconds,
        )

    return probe
