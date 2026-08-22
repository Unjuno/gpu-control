from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping

from ..execution import ApprovedExecutionPlan
from .runpod_v2 import RunPodV2Error


_TERMINATED = "TERMINATED"


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RunPodV2Error(f"{field} must be timezone-aware UTC")
    normalized = value.astimezone(timezone.utc)
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise RunPodV2Error(f"{field} must be UTC")
    return normalized


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RunPodAccountOccupancyEvidence:
    """Short-lived evidence that the RunPod account has no competing GPU Pod.

    This is intentionally account-scoped, not workflow-scoped. The owner-exclusive
    GitHub gate prevents other actors from entering paid compute; this evidence also
    prevents gpu-control from allocating a new Pod while any non-terminated Pod is
    already present in the credential's RunPod account.
    """

    plan_fingerprint: str
    active_pod_ids: tuple[str, ...]
    checked_at_utc: str
    valid_until_utc: str
    verification_reference: str
    schema_version: int = 1

    def validate_against_plan(self, plan: ApprovedExecutionPlan, *, now_utc: datetime) -> None:
        plan.validate_shape()
        if self.schema_version != 1:
            raise RunPodV2Error("unsupported RunPod occupancy evidence schema_version")
        if self.plan_fingerprint != plan.fingerprint():
            raise RunPodV2Error("RunPod occupancy evidence does not match approved plan fingerprint")
        if self.active_pod_ids:
            raise RunPodV2Error("RunPod account is busy; another non-terminated Pod exists")
        if not self.verification_reference.strip():
            raise RunPodV2Error("RunPod occupancy verification_reference is required")
        try:
            checked = datetime.fromisoformat(self.checked_at_utc.replace("Z", "+00:00"))
            valid_until = datetime.fromisoformat(self.valid_until_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RunPodV2Error("RunPod occupancy timestamps must be ISO 8601") from exc
        checked = _utc(checked, "checked_at_utc")
        valid_until = _utc(valid_until, "valid_until_utc")
        now = _utc(now_utc, "now_utc")
        if valid_until <= checked:
            raise RunPodV2Error("RunPod occupancy validity window is invalid")
        if (valid_until - checked).total_seconds() > 60:
            raise RunPodV2Error("RunPod occupancy evidence may be valid for at most 60 seconds")
        if now < checked:
            raise RunPodV2Error("RunPod occupancy evidence is newer than submission time")
        if now >= valid_until:
            raise RunPodV2Error("RunPod occupancy evidence expired before submission")


def build_account_occupancy_evidence(
    plan: ApprovedExecutionPlan,
    pods: Iterable[Mapping[str, Any]],
    *,
    checked_at_utc: datetime,
    ttl_seconds: int = 30,
) -> RunPodAccountOccupancyEvidence:
    """Normalize a trusted account-level List Pods response into short-lived evidence."""

    plan.validate_shape()
    checked = _utc(checked_at_utc, "checked_at_utc")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 60:
        raise RunPodV2Error("RunPod occupancy ttl_seconds must be between 1 and 60")

    active: list[str] = []
    normalized: list[dict[str, str]] = []
    for pod in pods:
        if not isinstance(pod, Mapping):
            raise RunPodV2Error("RunPod occupancy Pod entry must be an object")
        pod_id = pod.get("id")
        status = pod.get("status")
        if not isinstance(pod_id, str) or not pod_id.strip():
            raise RunPodV2Error("RunPod occupancy Pod id is required")
        if not isinstance(status, str) or not status.strip():
            raise RunPodV2Error("RunPod occupancy Pod status is required")
        pod_id = pod_id.strip()
        status = status.strip().upper()
        normalized.append({"id": pod_id, "status": status})
        if status != _TERMINATED:
            active.append(pod_id)

    normalized.sort(key=lambda item: (item["id"], item["status"]))
    digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    valid_until = checked.timestamp() + ttl_seconds
    until = datetime.fromtimestamp(valid_until, tz=timezone.utc)
    return RunPodAccountOccupancyEvidence(
        plan_fingerprint=plan.fingerprint(),
        active_pod_ids=tuple(sorted(active)),
        checked_at_utc=_iso(checked),
        valid_until_utc=_iso(until),
        verification_reference=f"runpod-account-pods:sha256:{digest}",
    )
