from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable, Iterable, Mapping

from ..execution import ApprovedExecutionPlan
from .runpod_v2 import RunPodV2Error, RunPodV2HttpClient


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RunPodAccountOccupancyEvidence:
    """Short-lived account-wide Pod occupancy evidence.

    Only TERMINATED Pods are considered released. EXITED, ERROR, provisioning,
    running, and unknown/future states remain busy until they are explicitly
    terminated. This is intentionally stricter than a workload-success model.
    """

    plan_fingerprint: str
    active_pod_ids: tuple[str, ...]
    checked_at_utc: str
    valid_until_utc: str
    verification_reference: str
    schema_version: int = 1

    def _validate_common(self, plan: ApprovedExecutionPlan, *, now_utc: datetime) -> None:
        plan.validate_shape()
        if self.schema_version != 1:
            raise RunPodV2Error("unsupported RunPod occupancy evidence schema_version")
        if self.plan_fingerprint != plan.fingerprint():
            raise RunPodV2Error("RunPod occupancy evidence does not match approved plan fingerprint")
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

    def validate_before_create(self, plan: ApprovedExecutionPlan, *, now_utc: datetime) -> None:
        self._validate_common(plan, now_utc=now_utc)
        if self.active_pod_ids:
            raise RunPodV2Error("RunPod account is busy; another non-terminated Pod exists")

    def validate_after_create(
        self,
        plan: ApprovedExecutionPlan,
        *,
        expected_pod_id: str,
        now_utc: datetime,
    ) -> None:
        self._validate_common(plan, now_utc=now_utc)
        if not isinstance(expected_pod_id, str) or not expected_pod_id.strip():
            raise RunPodV2Error("expected created Pod id is required")
        if self.active_pod_ids != (expected_pod_id.strip(),):
            raise RunPodV2Error(
                "RunPod account exclusivity was lost after create; expected only the newly created Pod"
            )


def build_account_occupancy_evidence(
    plan: ApprovedExecutionPlan,
    pods: Iterable[Mapping[str, Any]],
    *,
    checked_at_utc: datetime,
    ttl_seconds: int = 30,
) -> RunPodAccountOccupancyEvidence:
    """Normalize an account-level List Pods response into short-lived evidence."""

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
    until = datetime.fromtimestamp(checked.timestamp() + ttl_seconds, tz=timezone.utc)
    return RunPodAccountOccupancyEvidence(
        plan_fingerprint=plan.fingerprint(),
        active_pod_ids=tuple(sorted(active)),
        checked_at_utc=_iso(checked),
        valid_until_utc=_iso(until),
        verification_reference=f"runpod-account-pods:sha256:{digest}",
    )


@dataclass(frozen=True)
class RunPodV2AccountOccupancyProbe:
    """Read the authenticated account-wide v2 Pod list and normalize it."""

    client: RunPodV2HttpClient
    clock: Callable[[], datetime] = _utc_now
    ttl_seconds: int = 30

    def __post_init__(self) -> None:
        if not callable(self.clock):
            raise RunPodV2Error("RunPod occupancy probe clock must be callable")
        if isinstance(self.ttl_seconds, bool) or not isinstance(self.ttl_seconds, int) or not 1 <= self.ttl_seconds <= 60:
            raise RunPodV2Error("RunPod occupancy probe ttl_seconds must be between 1 and 60")

    def __call__(self, plan: ApprovedExecutionPlan) -> RunPodAccountOccupancyEvidence:
        payload = self.client.list_pods()
        pods = payload.get("pods")
        if not isinstance(pods, list):
            raise RunPodV2Error("RunPod List Pods response is missing pods")
        return build_account_occupancy_evidence(
            plan,
            pods,
            checked_at_utc=self.clock(),
            ttl_seconds=self.ttl_seconds,
        )
