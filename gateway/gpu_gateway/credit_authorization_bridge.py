"""Verify a signed, run-specific decision to consume provider credits.

This is an offline trust-boundary check only. It creates no authorization,
does no provider I/O, and is not wired into worker admission. Account credit is
not consent, and this envelope does not prove the provider will honor caps.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from collections.abc import Callable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from gpu_control.capabilities import (
    CapabilityEvidence, CostBreakdown, CostClassification, OverageBehavior,
)

from .contracts import PlanV2, plan_fingerprint

MAX_CREDIT_AUTHORIZATION_BYTES = 16_384
MAX_CREDIT_AUTHORIZATION_TTL_SECONDS = 900
CREDIT_AUTHORIZATION_AUDIENCE = "gpu-control:provider-credit-execution"
_FIELDS = frozenset({
    "schema_version", "issuer", "key_id", "audience", "authorization_id",
    "revocation_id", "run_id", "owner", "actor", "decision_record_id",
    "control_plane_sha", "gateway_plan_fingerprint", "provider",
    "resource_id", "image_digest", "runtime_seconds", "max_gross_credit_debit_usd",
    "max_out_of_pocket_usd", "quota_evidence_fingerprint", "authorization_reference",
    "policy_version", "issued_at", "expires_at", "signature",
})
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_ISSUER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_KEY_ID = re.compile(r"^credit:([A-Za-z0-9][A-Za-z0-9_.-]{0,63}):([A-Za-z0-9][A-Za-z0-9_.-]{0,63})$")
_TEXT = re.compile(r"^[^\x00-\x1f\x7f]{1,256}$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")
_MONEY = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")


class CreditAuthorizationError(ValueError):
    """Credit-consumption authorization is invalid or does not match the plan."""


@dataclass(frozen=True)
class VerifiedCreditAuthorization:
    authorization_id: str
    revocation_id: str
    issuer: str
    run_id: str
    owner: str
    actor: str
    decision_record_id: str
    gateway_plan_fingerprint: str
    quota_evidence_fingerprint: str
    valid_until: int
    max_gross_credit_debit_usd: Decimal


def _canonical(value: object) -> bytes:
    if type(value) is not dict:
        raise CreditAuthorizationError("authorization must be a JSON object")
    for key, item in value.items():
        if type(key) is not str or len(key) > 64:
            raise CreditAuthorizationError("authorization field name is invalid")
        if type(item) is str and len(item) > 256:
            raise CreditAuthorizationError("authorization text field exceeds the limit")
        if type(item) not in (str, int, bool) and item is not None:
            raise CreditAuthorizationError("authorization fields must be scalar JSON values")
        if type(item) is int and item.bit_length() > 64:
            raise CreditAuthorizationError("authorization integer exceeds the limit")
    try:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise CreditAuthorizationError("authorization is not canonical finite JSON") from exc
    if len(encoded) > MAX_CREDIT_AUTHORIZATION_BYTES:
        raise CreditAuthorizationError("authorization exceeds the size limit")
    return encoded


def _text(envelope: Mapping, field: str) -> str:
    value = envelope.get(field)
    if not isinstance(value, str) or not _TEXT.fullmatch(value) or value != value.strip():
        raise CreditAuthorizationError(f"authorization {field} is invalid")
    return value


def _money(envelope: Mapping, field: str) -> Decimal:
    value = envelope.get(field)
    if not isinstance(value, str) or not _MONEY.fullmatch(value):
        raise CreditAuthorizationError(f"authorization {field} is invalid")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise CreditAuthorizationError(f"authorization {field} is invalid") from exc
    if not amount.is_finite() or amount < 0:
        raise CreditAuthorizationError(f"authorization {field} is invalid")
    return amount


def _decode_signature(value: object) -> bytes:
    if not isinstance(value, str) or not _SIGNATURE.fullmatch(value):
        raise CreditAuthorizationError("authorization signature encoding is invalid")
    try:
        decoded = base64.urlsafe_b64decode(value + "==")
    except (ValueError, TypeError) as exc:
        raise CreditAuthorizationError("authorization signature encoding is invalid") from exc
    if len(decoded) != 64 or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        raise CreditAuthorizationError("authorization signature encoding is invalid")
    return decoded


def verify_credit_authorization(
    envelope: Mapping,
    trusted_keys: Mapping[str, bytes],
    *, expected_issuer: str, expected_policy_version: str, now: int,
    owner: str, actor: str, decision_record_id: str, control_plane_sha: str,
    run_id: str, gateway_plan: PlanV2, capability_evidence: CapabilityEvidence,
    is_revoked: Callable[[str, str], bool],
) -> VerifiedCreditAuthorization:
    """Verify owner decision against exact current plan, quota and credit costs.

    Caller-owned values and current evidence must come from trusted server-side
    state. The required revocation lookup fails closed. Replay prevention and
    provider-side revalidation require later durable integration.
    """
    if type(envelope) is not dict or set(envelope) != _FIELDS:
        raise CreditAuthorizationError("authorization fields are invalid")
    _canonical(envelope)
    if type(now) is not int or now < 0:
        raise CreditAuthorizationError("authorization verification time is invalid")
    if type(trusted_keys) is not dict or len(trusted_keys) > 16 or not callable(is_revoked):
        raise CreditAuthorizationError("authorization trust configuration is invalid")
    if not isinstance(gateway_plan, PlanV2) or gateway_plan.selection_binding is None:
        raise CreditAuthorizationError("candidate-bound Gateway plan is required")
    if (gateway_plan.cost_evidence.classification != "CREDIT_BACKED" or
            gateway_plan.cost_evidence.additional_cost_usd is None or
            gateway_plan.cost_evidence.additional_cost_usd <= 0):
        raise CreditAuthorizationError("credit authorization requires positive CREDIT_BACKED plan cost")
    now_utc = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
    if (not isinstance(capability_evidence, CapabilityEvidence) or
            capability_evidence.provider != gateway_plan.provider or
            capability_evidence.resource_id != gateway_plan.selection_binding.resource_id or
            capability_evidence.cost_classification is not CostClassification.CREDIT_BACKED or
            capability_evidence.hard_spend_cap_enforced is not True or
            capability_evidence.overage_behavior is not OverageBehavior.STOPS or
            not capability_evidence.is_current(now_utc) or
            capability_evidence.quota_evidence is None or
            not capability_evidence.quota_evidence.is_current(now_utc)):
        raise CreditAuthorizationError("current provider quota and hard-stop evidence is required")
    quota = capability_evidence.quota_evidence
    gross = capability_evidence.costs.known_total_usd
    covered = quota.covered_cost_usd(capability_evidence.costs)
    all_components = set(CostBreakdown.__dataclass_fields__)
    if (gross is None or gross <= 0 or covered != gross or
            set(quota.covered_components) != all_components or
            quota.remaining_usage_usd < gross or quota.remaining_credits_usd < gross or
            capability_evidence.fingerprint() != gateway_plan.selection_binding.evidence_fingerprint or
            gross > gateway_plan.max_cost_usd or
            gateway_plan.cost_evidence.additional_cost_usd != gross or
            gateway_plan.cost_evidence.reference != capability_evidence.evidence_reference):
        raise CreditAuthorizationError("current quota evidence does not cover the exact plan")

    issuer = _text(envelope, "issuer")
    key_id = _text(envelope, "key_id")
    match = _KEY_ID.fullmatch(key_id)
    if not _ISSUER.fullmatch(issuer) or issuer != expected_issuer or match is None or match.group(1) != issuer:
        raise CreditAuthorizationError("authorization issuer or key scope is not trusted")
    key_pem = trusted_keys.get(key_id)
    if not isinstance(key_pem, bytes) or not key_pem or len(key_pem) > 8192:
        raise CreditAuthorizationError("authorization signing key is not trusted")
    try:
        public_key = serialization.load_pem_public_key(key_pem)
    except (ValueError, TypeError) as exc:
        raise CreditAuthorizationError("authorization public key is invalid") from exc
    if not isinstance(public_key, Ed25519PublicKey):
        raise CreditAuthorizationError("authorization public key must be Ed25519")
    unsigned = {key: value for key, value in envelope.items() if key != "signature"}
    try:
        public_key.verify(_decode_signature(envelope.get("signature")), _canonical(unsigned))
    except InvalidSignature as exc:
        raise CreditAuthorizationError("authorization signature verification failed") from exc

    if (_text(envelope, "audience") != CREDIT_AUTHORIZATION_AUDIENCE or
            type(envelope.get("schema_version")) is not int or envelope["schema_version"] != 1):
        raise CreditAuthorizationError("authorization audience or schema is invalid")
    issued, expires = envelope.get("issued_at"), envelope.get("expires_at")
    if (type(issued) is not int or type(expires) is not int or issued < 0 or issued > now or
            expires <= now or expires <= issued or
            expires - issued > MAX_CREDIT_AUTHORIZATION_TTL_SECONDS):
        raise CreditAuthorizationError("authorization is expired or outside its validity window")
    values = {field: _text(envelope, field) for field in (
        "authorization_id", "revocation_id", "owner", "actor", "decision_record_id",
        "control_plane_sha", "gateway_plan_fingerprint", "provider", "resource_id",
        "image_digest", "quota_evidence_fingerprint", "authorization_reference", "policy_version",
    )}
    if (values["policy_version"] != expected_policy_version or values["owner"] != owner or
            values["actor"] != actor or values["decision_record_id"] != decision_record_id or
            not _SHA40.fullmatch(values["control_plane_sha"]) or values["control_plane_sha"] != control_plane_sha or
            not _RUN_ID.fullmatch(str(envelope.get("run_id", ""))) or envelope.get("run_id") != run_id):
        raise CreditAuthorizationError("authorization identity or policy does not match")
    binding = gateway_plan.selection_binding
    if (values["gateway_plan_fingerprint"] != plan_fingerprint(gateway_plan) or
            values["provider"] != gateway_plan.provider or values["resource_id"] != binding.resource_id or
            values["image_digest"] != gateway_plan.image_digest or
            values["quota_evidence_fingerprint"] != capability_evidence.fingerprint() or
            not _SHA64.fullmatch(values["gateway_plan_fingerprint"]) or
            not re.fullmatch(r"sha256:[0-9a-f]{64}", values["quota_evidence_fingerprint"]) or
            not re.fullmatch(r"sha256:[0-9a-f]{64}", values["image_digest"])):
        raise CreditAuthorizationError("authorization does not match the exact plan or quota evidence")
    runtime = envelope.get("runtime_seconds")
    debit = _money(envelope, "max_gross_credit_debit_usd")
    out_of_pocket = _money(envelope, "max_out_of_pocket_usd")
    if (type(runtime) is not int or runtime != gateway_plan.runtime_seconds or
            debit <= 0 or debit != gross or out_of_pocket != 0 or debit < gross):
        raise CreditAuthorizationError("authorization credit debit or out-of-pocket limit is invalid")
    try:
        revoked = is_revoked(issuer, values["revocation_id"])
    except Exception as exc:
        raise CreditAuthorizationError("authorization revocation status is unavailable") from exc
    if type(revoked) is not bool:
        raise CreditAuthorizationError("authorization revocation status is invalid")
    if revoked:
        raise CreditAuthorizationError("authorization has been revoked")
    return VerifiedCreditAuthorization(
        authorization_id=values["authorization_id"], revocation_id=values["revocation_id"],
        issuer=issuer, run_id=run_id, owner=owner, actor=actor,
        decision_record_id=decision_record_id,
        gateway_plan_fingerprint=values["gateway_plan_fingerprint"],
        quota_evidence_fingerprint=values["quota_evidence_fingerprint"],
        valid_until=expires, max_gross_credit_debit_usd=debit,
    )
