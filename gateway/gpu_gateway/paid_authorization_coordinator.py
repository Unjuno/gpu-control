"""Internal verification and persistence seam for RunPod paid authorization.

This module has no HTTP/MCP or Worker registration. A future authorization
issuer must be independently deployed and reviewed before any caller is added.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Mapping

from gpu_control.execution import ApprovedExecutionPlan

from .contracts import PlanV2, plan_fingerprint
from .paid_authorization_bridge import (
    PaidAuthorizationBridgeError,
    VerifiedPaidAuthorization,
    verify_paid_authorization,
)


class PaidAuthorizationCoordinatorError(ValueError):
    """Trusted context or signed authorization is missing or invalid."""


@dataclass(frozen=True)
class PaidAuthorizationContext:
    """Exact current identity resolved from server-owned run/decision state."""

    approval_id: str
    actor: str
    decision_record_id: str
    control_plane_sha: str
    gateway_plan: PlanV2
    core_plan: ApprovedExecutionPlan


class PaidAuthorizationCoordinator:
    """Verify before Store writes and reverify after Store reads.

    ``resolve_context`` must load the exact current run approval and immutable
    decision/core-plan context from trusted server state. Never implement it
    from MCP parameters, browser form fields, or provider output. ``clock`` and
    ``is_revoked`` must also be server-owned. This coordinator intentionally
    cannot mint a permit or submit a provider job.
    """

    def __init__(
        self,
        *,
        store,
        resolve_context: Callable[[str, str], PaidAuthorizationContext | None],
        trusted_keys: Mapping[str, bytes],
        expected_issuer: str,
        expected_policy_version: str,
        is_revoked: Callable[[str, str], bool],
        clock: Callable[[], int],
    ):
        if (not callable(resolve_context) or not callable(is_revoked) or
                not callable(clock) or not isinstance(expected_issuer, str) or
                not expected_issuer or not isinstance(expected_policy_version, str) or
                not expected_policy_version or type(trusted_keys) is not dict):
            raise ValueError("paid authorization coordinator configuration is invalid")
        if not callable(getattr(store, "persist_verified_paid_authorization", None)) or not callable(
                getattr(store, "read_paid_authorization", None)):
            raise ValueError("paid authorization coordinator Store contract is invalid")
        self.store = store
        self.resolve_context = resolve_context
        self.trusted_keys = dict(trusted_keys)
        self.expected_issuer = expected_issuer
        self.expected_policy_version = expected_policy_version
        self.is_revoked = is_revoked
        self.clock = clock

    def _now(self) -> int:
        value = self.clock()
        if type(value) is not int or value < 0:
            raise PaidAuthorizationCoordinatorError("trusted authorization clock is invalid")
        return value

    def _context(self, run_id: str, owner: str) -> PaidAuthorizationContext:
        if (not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None or
                not isinstance(owner, str) or not owner or len(owner) > 128):
            raise PaidAuthorizationCoordinatorError("paid authorization identity is invalid")
        try:
            context = self.resolve_context(run_id, owner)
        except Exception as exc:
            raise PaidAuthorizationCoordinatorError("trusted authorization context is unavailable") from exc
        if (type(context) is not PaidAuthorizationContext or
                not isinstance(context.gateway_plan, PlanV2) or
                not isinstance(context.core_plan, ApprovedExecutionPlan) or
                not isinstance(context.actor, str) or not context.actor or
                not isinstance(context.decision_record_id, str) or not context.decision_record_id or
                not isinstance(context.control_plane_sha, str) or not context.control_plane_sha):
            raise PaidAuthorizationCoordinatorError("trusted authorization context is invalid")
        return context

    def _verify(self, *, envelope: dict, run_id: str, owner: str,
                context: PaidAuthorizationContext) -> VerifiedPaidAuthorization:
        try:
            return verify_paid_authorization(
                envelope, self.trusted_keys,
                expected_issuer=self.expected_issuer,
                expected_policy_version=self.expected_policy_version,
                now=self._now(), owner=owner, actor=context.actor,
                decision_record_id=context.decision_record_id,
                expected_approval_id=context.approval_id,
                control_plane_sha=context.control_plane_sha, run_id=run_id,
                gateway_plan=context.gateway_plan, core_plan=context.core_plan,
                is_revoked=self.is_revoked,
            )
        except PaidAuthorizationBridgeError as exc:
            raise PaidAuthorizationCoordinatorError(str(exc)) from exc

    def persist(self, *, run_id: str, owner: str, envelope: dict) -> dict:
        """Persist a verified exact-plan envelope; return non-secret identity only."""
        context = self._context(run_id, owner)
        verified = self._verify(envelope=envelope, run_id=run_id, owner=owner,
                                context=context)
        try:
            saved = self.store.persist_verified_paid_authorization(
                run_id=run_id, owner=owner,
                plan_fingerprint=plan_fingerprint(context.gateway_plan),
                approval_id=context.approval_id, envelope=envelope,
                verified=verified, now=self.clock,
            )
        except Exception as exc:
            raise PaidAuthorizationCoordinatorError(
                "paid authorization could not be persisted") from exc
        if saved is not True:
            raise PaidAuthorizationCoordinatorError(
                "current run approval changed before authorization persistence")
        # Re-read through the same owner/plan/approval lock and verify again so
        # callers never receive even metadata for an envelope whose revocation,
        # approval, or validity changed during the write.
        current = self.reload_verified(run_id=run_id, owner=owner)
        if current is None or current.authorization_id != verified.authorization_id:
            raise PaidAuthorizationCoordinatorError(
                "paid authorization changed during persistence")
        return {
            "authorization_id": current.authorization_id,
            "approval_id": current.approval_id,
            "issuer": current.issuer,
        }

    def reload_verified(self, *, run_id: str, owner: str) -> VerifiedPaidAuthorization | None:
        """Reload and reverify current approval, issuer signature, and revocation."""
        context = self._context(run_id, owner)
        try:
            stored = self.store.read_paid_authorization(
                run_id=run_id, owner=owner,
                plan_fingerprint=plan_fingerprint(context.gateway_plan),
                approval_id=context.approval_id, now=self.clock,
            )
        except Exception as exc:
            raise PaidAuthorizationCoordinatorError(
                "paid authorization could not be reloaded") from exc
        if stored is None:
            return None
        verified = self._verify(
            envelope=stored["envelope"], run_id=run_id, owner=owner,
            context=context,
        )
        if (verified.authorization_id != stored["authorization_id"] or
                verified.issuer != stored["issuer"]):
            raise PaidAuthorizationCoordinatorError(
                "stored paid authorization identity changed")
        return verified
