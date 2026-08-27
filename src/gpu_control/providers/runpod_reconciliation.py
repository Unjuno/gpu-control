from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

from ..completion import CompletionChallenge, CompletionEvidenceError
from ..execution import ApprovedExecutionPlan
from .runpod_v2 import RunPodV2Error


_MAX_INVENTORY_ENTRIES = 256
_MAX_EVIDENCE_TTL_SECONDS = 60
_TERMINATED = "TERMINATED"


@dataclass(frozen=True)
class RunPodPodInventoryEntry:
    """Minimal Pod identity needed for create/cleanup reconciliation."""

    provider_job_id: str
    name: str
    status: str

    def to_dict(self) -> dict[str, str]:
        return {
            "provider_job_id": self.provider_job_id,
            "name": self.name,
            "status": self.status,
        }


@dataclass(frozen=True)
class RunPodPodInventoryEvidence:
    """Short-lived account-wide Pod inventory derived from one v2 List Pods response."""

    plan_fingerprint: str
    pods: tuple[RunPodPodInventoryEntry, ...]
    checked_at_utc: str
    valid_until_utc: str
    verification_reference: str
    schema_version: int = 1

    def validate_against_plan(self, plan: ApprovedExecutionPlan, *, now_utc: datetime) -> None:
        plan.validate_shape()
        if self.schema_version != 1:
            raise RunPodV2Error("unsupported RunPod inventory evidence schema_version")
        if self.plan_fingerprint != plan.fingerprint():
            raise RunPodV2Error("RunPod inventory evidence does not match approved plan fingerprint")
        if not isinstance(self.pods, tuple):
            raise RunPodV2Error("RunPod inventory pods must be a tuple")
        if len(self.pods) > _MAX_INVENTORY_ENTRIES:
            raise RunPodV2Error("RunPod inventory exceeds bounded Pod count")
        seen_ids: set[str] = set()
        for entry in self.pods:
            if not isinstance(entry, RunPodPodInventoryEntry):
                raise RunPodV2Error("RunPod inventory contains an invalid entry")
            if entry.provider_job_id in seen_ids:
                raise RunPodV2Error("RunPod inventory contains duplicate Pod ids")
            seen_ids.add(entry.provider_job_id)
        if not isinstance(self.verification_reference, str) or not self.verification_reference.strip():
            raise RunPodV2Error("RunPod inventory verification_reference is required")
        checked = _parse_utc(self.checked_at_utc, "checked_at_utc")
        valid_until = _parse_utc(self.valid_until_utc, "valid_until_utc")
        now = _require_utc(now_utc, "now_utc")
        if valid_until <= checked:
            raise RunPodV2Error("RunPod inventory validity window is invalid")
        if valid_until - checked > timedelta(seconds=_MAX_EVIDENCE_TTL_SECONDS):
            raise RunPodV2Error("RunPod inventory evidence may be valid for at most 60 seconds")
        if now < checked:
            raise RunPodV2Error("RunPod inventory evidence is newer than reconciliation time")
        if now >= valid_until:
            raise RunPodV2Error("RunPod inventory evidence expired before reconciliation")


def _require_utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RunPodV2Error(f"{field} must be timezone-aware UTC")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise RunPodV2Error(f"{field} must be UTC")
    return value.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return _require_utc(value, "checked_at_utc").isoformat().replace("+00:00", "Z")


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise RunPodV2Error(f"{field} must be a non-empty trimmed timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RunPodV2Error(f"{field} must be an ISO 8601 timestamp") from exc
    return _require_utc(parsed, field)


def _require_text(value: object, field: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RunPodV2Error(f"{field} is required")
    if value != value.strip():
        raise RunPodV2Error(f"{field} must not contain surrounding whitespace")
    if len(value) > max_length:
        raise RunPodV2Error(f"{field} exceeds maximum length {max_length}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise RunPodV2Error(f"{field} must not contain control characters")
    return value


def build_pod_inventory_evidence(
    plan: ApprovedExecutionPlan,
    list_response: Mapping[str, Any],
    *,
    checked_at_utc: datetime,
    ttl_seconds: int = 30,
) -> RunPodPodInventoryEvidence:
    """Normalize the official v2 ``GET /pods`` envelope into bounded evidence.

    The pinned RunPod v2 contract returns ``{"pods": [...]}`` and exposes no
    server-side list filters. Reconciliation therefore receives the complete
    account list and applies exact identity matching locally.
    """

    plan.validate_shape()
    checked = _require_utc(checked_at_utc, "checked_at_utc")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 60:
        raise RunPodV2Error("RunPod inventory ttl_seconds must be between 1 and 60")
    if not isinstance(list_response, Mapping):
        raise RunPodV2Error("RunPod List Pods response must be a JSON object")
    raw_pods = list_response.get("pods")
    if not isinstance(raw_pods, list):
        raise RunPodV2Error("RunPod List Pods response is missing pods")
    if len(raw_pods) > _MAX_INVENTORY_ENTRIES:
        raise RunPodV2Error("RunPod List Pods response exceeds bounded Pod count")

    entries: list[RunPodPodInventoryEntry] = []
    seen_ids: set[str] = set()
    for raw in raw_pods:
        if not isinstance(raw, Mapping):
            raise RunPodV2Error("RunPod List Pods entry must be a JSON object")
        pod_id = _require_text(raw.get("id"), "RunPod List Pods id", max_length=512)
        if pod_id in seen_ids:
            raise RunPodV2Error("RunPod List Pods response contains duplicate Pod ids")
        seen_ids.add(pod_id)
        name = _require_text(raw.get("name"), "RunPod List Pods name", max_length=256)
        status = _require_text(raw.get("status"), "RunPod List Pods status", max_length=64).upper()
        entries.append(RunPodPodInventoryEntry(provider_job_id=pod_id, name=name, status=status))

    entries.sort(key=lambda item: (item.provider_job_id, item.name, item.status))
    normalized = [entry.to_dict() for entry in entries]
    digest = hashlib.sha256(
        json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    valid_until = checked + timedelta(seconds=ttl_seconds)
    evidence = RunPodPodInventoryEvidence(
        plan_fingerprint=plan.fingerprint(),
        pods=tuple(entries),
        checked_at_utc=_format_utc(checked),
        valid_until_utc=_format_utc(valid_until),
        verification_reference=f"runpod-v2-pods:sha256:{digest}",
    )
    evidence.validate_against_plan(plan, now_utc=checked)
    return evidence


def reconcile_ambiguous_create(
    evidence: RunPodPodInventoryEvidence,
    plan: ApprovedExecutionPlan,
    challenge: CompletionChallenge,
    *,
    now_utc: datetime,
) -> str:
    """Recover exactly one Pod created under one pre-create execution identity."""

    evidence.validate_against_plan(plan, now_utc=now_utc)
    try:
        challenge.validate_shape()
    except CompletionEvidenceError as exc:
        raise RunPodV2Error(str(exc)) from exc
    if challenge.plan_fingerprint != plan.fingerprint():
        raise RunPodV2Error("RunPod reconciliation challenge does not match approved plan")
    if challenge.source_sha != plan.target_sha:
        raise RunPodV2Error("RunPod reconciliation challenge source_sha does not match approved plan")
    if challenge.image_digest != plan.image_digest:
        raise RunPodV2Error("RunPod reconciliation challenge image_digest does not match approved plan")

    matches = [entry for entry in evidence.pods if entry.name == challenge.execution_name]
    if not matches:
        raise RunPodV2Error("ambiguous RunPod create has no exact execution-name match")
    if len(matches) != 1:
        raise RunPodV2Error("ambiguous RunPod create has multiple exact execution-name matches")
    match = matches[0]
    if match.status == _TERMINATED:
        raise RunPodV2Error("ambiguous RunPod create matched only an already terminated Pod")
    return match.provider_job_id


def cleanup_reconciled(
    evidence: RunPodPodInventoryEvidence,
    plan: ApprovedExecutionPlan,
    provider_job_id: str,
    *,
    now_utc: datetime,
) -> bool:
    """Return true only when an ambiguously terminated Pod is absent or TERMINATED."""

    evidence.validate_against_plan(plan, now_utc=now_utc)
    pod_id = _require_text(provider_job_id, "provider_job_id", max_length=512)
    matches = [entry for entry in evidence.pods if entry.provider_job_id == pod_id]
    if not matches:
        return True
    if len(matches) != 1:
        raise RunPodV2Error("RunPod inventory contains ambiguous cleanup identity")
    return matches[0].status == _TERMINATED
