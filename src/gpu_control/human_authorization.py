from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping

from .execution import ApprovedExecutionPlan, ExecutionGateError
from .paid_authorization import PaidAuthorizationEvidence


_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROVIDER_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_MAX_AUTHORIZATION_TTL_SECONDS = 900
_FIELDS = {
    "schema_version",
    "authorization_id",
    "actor",
    "decision_record_id",
    "control_plane_sha",
    "plan_fingerprint",
    "target_repo",
    "target_sha",
    "image_digest",
    "provider",
    "provider_resource_id",
    "gpu_count",
    "max_runtime_minutes",
    "max_cost_usd",
    "authorized_at_utc",
    "valid_until_utc",
    "authorization_reference",
}


class HumanAuthorizationError(ValueError):
    """Raised when explicit human intent does not bind the exact live action."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HumanAuthorizationError(f"{field} is required")
    if value != value.strip():
        raise HumanAuthorizationError(f"{field} must not contain surrounding whitespace")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise HumanAuthorizationError(f"{field} must not contain control characters")
    return value


def _utc(value: object, field: str) -> datetime:
    text = _text(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HumanAuthorizationError(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise HumanAuthorizationError(f"{field} must be timezone-aware UTC")
    return parsed


def _require_now_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise HumanAuthorizationError("now_utc must be timezone-aware UTC")
    return value


def _cost(value: object) -> Decimal:
    text = _text(value, "max_cost_usd")
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise HumanAuthorizationError("max_cost_usd must be a decimal string") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise HumanAuthorizationError("max_cost_usd must be finite and positive")
    return parsed


@dataclass(frozen=True)
class HumanAuthorizationEvidence:
    authorization_id: str
    actor: str
    decision_record_id: str
    control_plane_sha: str
    plan_fingerprint: str
    target_repo: str
    target_sha: str
    image_digest: str
    provider: str
    provider_resource_id: str
    gpu_count: int
    max_runtime_minutes: int
    max_cost_usd: str
    authorized_at_utc: str
    valid_until_utc: str
    authorization_reference: str
    schema_version: int = 1

    def validate_shape(self) -> tuple[datetime, datetime, Decimal]:
        if self.schema_version != 1:
            raise HumanAuthorizationError("unsupported human authorization schema_version")
        _text(self.authorization_id, "authorization_id")
        _text(self.actor, "actor")
        _text(self.decision_record_id, "decision_record_id")
        if not _SHA40_RE.fullmatch(self.control_plane_sha):
            raise HumanAuthorizationError("control_plane_sha must be a lowercase 40-character commit SHA")
        if not _SHA256_RE.fullmatch(self.plan_fingerprint):
            raise HumanAuthorizationError("plan_fingerprint must be a lowercase sha256 fingerprint")
        if not _REPO_RE.fullmatch(self.target_repo):
            raise HumanAuthorizationError("target_repo must be a canonical owner/repository name")
        if not _SHA40_RE.fullmatch(self.target_sha):
            raise HumanAuthorizationError("target_sha must be a lowercase 40-character commit SHA")
        if not _SHA256_RE.fullmatch(self.image_digest):
            raise HumanAuthorizationError("image_digest must be a lowercase sha256 digest")
        if not _PROVIDER_RE.fullmatch(self.provider):
            raise HumanAuthorizationError("provider must be a canonical lowercase provider identifier")
        _text(self.provider_resource_id, "provider_resource_id")
        if isinstance(self.gpu_count, bool) or not isinstance(self.gpu_count, int) or self.gpu_count != 1:
            raise HumanAuthorizationError("gpu_count must be exactly one")
        if (
            isinstance(self.max_runtime_minutes, bool)
            or not isinstance(self.max_runtime_minutes, int)
            or self.max_runtime_minutes <= 0
        ):
            raise HumanAuthorizationError("max_runtime_minutes must be a positive integer")
        cost = _cost(self.max_cost_usd)
        authorized = _utc(self.authorized_at_utc, "authorized_at_utc")
        valid_until = _utc(self.valid_until_utc, "valid_until_utc")
        if valid_until <= authorized:
            raise HumanAuthorizationError("valid_until_utc must be after authorized_at_utc")
        if (valid_until - authorized).total_seconds() > _MAX_AUTHORIZATION_TTL_SECONDS:
            raise HumanAuthorizationError("human authorization validity may not exceed 15 minutes")
        _text(self.authorization_reference, "authorization_reference")
        return authorized, valid_until, cost

    def validate_for_live_plan(
        self,
        plan: ApprovedExecutionPlan,
        *,
        expected_actor: str,
        expected_control_plane_sha: str,
        expected_decision_record_id: str,
        now_utc: datetime,
    ) -> None:
        try:
            plan.validate_shape()
        except ExecutionGateError as exc:
            raise HumanAuthorizationError(str(exc)) from exc
        authorized, valid_until, authorized_cost = self.validate_shape()
        now = _require_now_utc(now_utc)
        if now < authorized:
            raise HumanAuthorizationError("human authorization is not valid yet")
        if now >= valid_until:
            raise HumanAuthorizationError("human authorization expired before live submission")
        if self.actor != _text(expected_actor, "expected_actor"):
            raise HumanAuthorizationError("human authorization actor does not match current authorized actor")
        if self.control_plane_sha != expected_control_plane_sha or not _SHA40_RE.fullmatch(expected_control_plane_sha):
            raise HumanAuthorizationError("human authorization is not bound to the running control-plane commit")
        if self.decision_record_id != _text(expected_decision_record_id, "expected_decision_record_id"):
            raise HumanAuthorizationError("human authorization is not bound to the current DecisionRecord")
        if self.plan_fingerprint != plan.fingerprint():
            raise HumanAuthorizationError("human authorization is not bound to the exact execution plan")

        exact = {
            "target_repo": (self.target_repo, plan.target_repo),
            "target_sha": (self.target_sha, plan.target_sha),
            "image_digest": (self.image_digest, plan.image_digest),
            "provider": (self.provider, plan.provider),
            "provider_resource_id": (self.provider_resource_id, plan.provider_resource_id),
            "gpu_count": (self.gpu_count, plan.gpu_count),
            "authorization_reference": (self.authorization_reference, plan.authorization_reference),
        }
        for field, (actual, expected) in exact.items():
            if actual != expected:
                raise HumanAuthorizationError(f"human authorization {field} does not match execution plan")
        if plan.max_runtime_minutes > self.max_runtime_minutes:
            raise HumanAuthorizationError("execution plan runtime exceeds human-authorized bound")
        if plan.max_cost_usd > authorized_cost:
            raise HumanAuthorizationError("execution plan cost exceeds human-authorized bound")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "authorization_id": self.authorization_id,
            "actor": self.actor,
            "decision_record_id": self.decision_record_id,
            "control_plane_sha": self.control_plane_sha,
            "plan_fingerprint": self.plan_fingerprint,
            "target_repo": self.target_repo,
            "target_sha": self.target_sha,
            "image_digest": self.image_digest,
            "provider": self.provider,
            "provider_resource_id": self.provider_resource_id,
            "gpu_count": self.gpu_count,
            "max_runtime_minutes": self.max_runtime_minutes,
            "max_cost_usd": self.max_cost_usd,
            "authorized_at_utc": self.authorized_at_utc,
            "valid_until_utc": self.valid_until_utc,
            "authorization_reference": self.authorization_reference,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HumanAuthorizationEvidence":
        if not isinstance(payload, Mapping) or set(payload) != _FIELDS:
            raise HumanAuthorizationError("human authorization evidence fields do not match schema")
        value = cls(**payload)  # type: ignore[arg-type]
        value.validate_shape()
        return value


@dataclass(frozen=True)
class LiveExecutionPermit:
    plan_fingerprint: str
    actor: str
    decision_record_id: str
    human_authorization_id: str
    human_authorization_reference: str
    paid_authorization_reference: str
    repository_security_reference: str
    control_plane_sha: str
    valid_until_utc: str

    def validate_for_plan(self, plan: ApprovedExecutionPlan, *, now_utc: datetime) -> None:
        try:
            plan.validate_shape()
        except ExecutionGateError as exc:
            raise HumanAuthorizationError(str(exc)) from exc
        if not _SHA256_RE.fullmatch(self.plan_fingerprint):
            raise HumanAuthorizationError("live execution permit plan_fingerprint is invalid")
        if self.plan_fingerprint != plan.fingerprint():
            raise HumanAuthorizationError("live execution permit does not match the exact execution plan")
        _text(self.actor, "live execution permit actor")
        _text(self.decision_record_id, "live execution permit decision_record_id")
        _text(self.human_authorization_id, "live execution permit human_authorization_id")
        if self.human_authorization_reference != plan.authorization_reference:
            raise HumanAuthorizationError("live execution permit human authorization reference does not match plan")
        _text(self.paid_authorization_reference, "live execution permit paid_authorization_reference")
        repository_reference = _text(
            self.repository_security_reference,
            "live execution permit repository_security_reference",
        )
        if repository_reference == "not-live":
            raise HumanAuthorizationError("live execution permit requires repository security evidence")
        if not _SHA40_RE.fullmatch(self.control_plane_sha):
            raise HumanAuthorizationError("live execution permit control_plane_sha is invalid")
        valid_until = _utc(self.valid_until_utc, "live execution permit valid_until_utc")
        now = _require_now_utc(now_utc)
        if now >= valid_until:
            raise HumanAuthorizationError("live execution permit expired before provider submission")


def authorize_live_plan(
    plan: ApprovedExecutionPlan,
    human: HumanAuthorizationEvidence,
    paid: PaidAuthorizationEvidence,
    *,
    expected_control_plane_sha: str,
    expected_decision_record_id: str,
    now_utc: datetime,
) -> LiveExecutionPermit:
    """Bind GitHub identity authorization and current human intent to one plan."""

    human.validate_for_live_plan(
        plan,
        expected_actor=paid.actor,
        expected_control_plane_sha=expected_control_plane_sha,
        expected_decision_record_id=expected_decision_record_id,
        now_utc=now_utc,
    )
    if paid.actor != paid.triggering_actor:
        raise HumanAuthorizationError("paid authorization actor and triggering actor must match")
    if not paid.repository_security_reference or paid.repository_security_reference == "not-live":
        raise HumanAuthorizationError("live execution requires repository security evidence")
    permit = LiveExecutionPermit(
        plan_fingerprint=plan.fingerprint(),
        actor=paid.actor,
        decision_record_id=human.decision_record_id,
        human_authorization_id=human.authorization_id,
        human_authorization_reference=human.authorization_reference,
        paid_authorization_reference=paid.authorization_reference,
        repository_security_reference=paid.repository_security_reference,
        control_plane_sha=human.control_plane_sha,
        valid_until_utc=human.valid_until_utc,
    )
    permit.validate_for_plan(plan, now_utc=now_utc)
    return permit
