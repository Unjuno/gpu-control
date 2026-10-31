"""Verify independently issued Gateway-to-RunPod paid authorizations.

This module is a pure trust-boundary check. It neither issues authorization,
creates a RunPod permit, nor performs provider I/O. The Gateway worker must
call it before submission intent and the provider adapter must repeat the
time/revocation checks immediately before allocation.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
from collections.abc import Callable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from gpu_control.execution import ApprovedExecutionPlan, ExecutionGateError

from .contracts import PlanV2, plan_fingerprint
from .registry import candidate_plan_requires_paid_authorization

MAX_AUTHORIZATION_BYTES = 16_384
MAX_AUTHORIZATION_TTL_SECONDS = 900
RUNPOD_PAID_AUTHORIZATION_AUDIENCE = "gpu-control:runpod-paid-execution"
_FIELDS = {
    "schema_version", "issuer", "key_id", "audience", "authorization_id",
    "revocation_id", "run_id", "owner", "actor", "decision_record_id",
    "control_plane_sha", "gateway_plan_fingerprint", "core_plan_fingerprint",
    "provider", "resource_id", "image_digest", "runtime_seconds",
    "max_cost_usd", "authorization_reference", "policy_version", "issued_at",
    "expires_at", "signature",
}
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_ISSUER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_KEY_ID = re.compile(r"^paid:([A-Za-z0-9][A-Za-z0-9_.-]{0,63}):([A-Za-z0-9][A-Za-z0-9_.-]{0,63})$")
_TEXT = re.compile(r"^[^\x00-\x1f\x7f]{1,256}$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{86}$")


class PaidAuthorizationBridgeError(ValueError):
    """A paid authorization is invalid, stale, revoked, or plan-mismatched."""


@dataclass(frozen=True)
class VerifiedPaidAuthorization:
    """Minimal verified claims safe to pass to the worker's admission gate."""

    authorization_id: str
    revocation_id: str
    issuer: str
    run_id: str
    owner: str
    actor: str
    decision_record_id: str
    gateway_plan_fingerprint: str
    core_plan_fingerprint: str
    valid_until: int
    authorization_reference: str


def _canonical(value: object) -> bytes:
    try:
        # The v1 envelope is a flat object. Rejecting nested Python/JSON
        # containers also bounds work before serialization and prevents JSON
        # coercions from changing signed meaning.
        if type(value) is not dict:
            raise PaidAuthorizationBridgeError("authorization must be a JSON object")
        for key, item in value.items():
            if type(key) is not str or len(key) > 64:
                raise PaidAuthorizationBridgeError("authorization field name is invalid")
            if type(item) is str:
                if len(item) > 256:
                    raise PaidAuthorizationBridgeError("authorization text field exceeds the limit")
            elif type(item) is int:
                if item.bit_length() > 64:
                    raise PaidAuthorizationBridgeError("authorization integer exceeds the limit")
            elif item is not None and type(item) is not bool:
                raise PaidAuthorizationBridgeError("authorization fields must be scalar JSON values")
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("ascii")
    except PaidAuthorizationBridgeError:
        raise
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise PaidAuthorizationBridgeError("authorization is not canonical finite JSON") from exc
    if len(encoded) > MAX_AUTHORIZATION_BYTES:
        raise PaidAuthorizationBridgeError("authorization exceeds the size limit")
    return encoded


def _required_text(envelope: Mapping, field: str) -> str:
    value = envelope.get(field)
    if not isinstance(value, str) or not _TEXT.fullmatch(value) or value != value.strip():
        raise PaidAuthorizationBridgeError(f"authorization {field} is invalid")
    return value


def _decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?", value):
        raise PaidAuthorizationBridgeError(f"authorization {field} is invalid")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise PaidAuthorizationBridgeError(f"authorization {field} is invalid") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise PaidAuthorizationBridgeError(f"authorization {field} must be positive")
    return parsed


def _decode_signature(value: object) -> bytes:
    if not isinstance(value, str) or not _SIGNATURE.fullmatch(value):
        raise PaidAuthorizationBridgeError("authorization signature encoding is invalid")
    try:
        decoded = base64.urlsafe_b64decode(value + "==")
    except (ValueError, TypeError) as exc:
        raise PaidAuthorizationBridgeError("authorization signature encoding is invalid") from exc
    if len(decoded) != 64 or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        raise PaidAuthorizationBridgeError("authorization signature encoding is invalid")
    return decoded


def verify_paid_authorization(
    envelope: Mapping,
    trusted_keys: Mapping[str, bytes],
    *,
    expected_issuer: str,
    expected_policy_version: str,
    now: int,
    owner: str,
    actor: str,
    decision_record_id: str,
    control_plane_sha: str,
    run_id: str,
    gateway_plan: PlanV2,
    core_plan: ApprovedExecutionPlan,
    is_revoked: Callable[[str, str], bool],
) -> VerifiedPaidAuthorization:
    """Verify signature, revocation, and exact Gateway/core plan identity.

    ``is_revoked(issuer, revocation_id)`` is a required trusted lookup and must
    return a literal bool.
    Lookup errors fail closed. Expected identity values, the trusted key map,
    and revocation lookup must be supplied from server-side trusted state, never
    MCP arguments. The lookup must return current revocation state. This
    function accepts no caller-created permit and does not itself prevent
    replay; durable one-use admission belongs to the worker integration.
    """
    if type(envelope) is not dict or len(envelope) != len(_FIELDS) or set(envelope) != _FIELDS:
        raise PaidAuthorizationBridgeError("authorization fields are invalid")
    _canonical(envelope)
    if type(now) is not int or now < 0:
        raise PaidAuthorizationBridgeError("authorization verification time is invalid")
    if (type(trusted_keys) is not dict or len(trusted_keys) > 16 or
            not callable(is_revoked)):
        raise PaidAuthorizationBridgeError("authorization trust configuration is invalid")
    if not isinstance(gateway_plan, PlanV2) or gateway_plan.selection_binding is None:
        raise PaidAuthorizationBridgeError("candidate-bound Gateway plan is required")
    if not candidate_plan_requires_paid_authorization(gateway_plan):
        raise PaidAuthorizationBridgeError("paid authorization is not valid for a zero-additional-cost plan")
    if not isinstance(core_plan, ApprovedExecutionPlan):
        raise PaidAuthorizationBridgeError("approved RunPod core plan is required")
    cost_evidence = gateway_plan.cost_evidence
    additional_cost = cost_evidence.additional_cost_usd
    observed_at, expires_at = cost_evidence.observed_at, cost_evidence.expires_at
    if (cost_evidence.classification != "PAID" or additional_cost is None or
            additional_cost <= 0 or additional_cost > gateway_plan.max_cost_usd or
            type(observed_at) is not int or type(expires_at) is not int or
            observed_at < 0 or observed_at > now or expires_at <= now or
            expires_at <= observed_at or not isinstance(cost_evidence.reference, str) or
            not cost_evidence.reference.strip()):
        raise PaidAuthorizationBridgeError(
            "Gateway paid cost evidence must be known, within the ceiling, and current")
    try:
        core_plan.validate_shape()
    except ExecutionGateError as exc:
        raise PaidAuthorizationBridgeError("approved RunPod core plan is invalid") from exc
    if core_plan.worst_case_cost_usd > additional_cost:
        raise PaidAuthorizationBridgeError(
            "approved RunPod worst-case cost exceeds the current Gateway cost evidence")

    issuer = _required_text(envelope, "issuer")
    key_id = _required_text(envelope, "key_id")
    if not _ISSUER.fullmatch(issuer) or issuer != expected_issuer:
        raise PaidAuthorizationBridgeError("authorization issuer is not trusted")
    key_match = _KEY_ID.fullmatch(key_id)
    if key_match is None or key_match.group(1) != issuer:
        raise PaidAuthorizationBridgeError("authorization key ID is invalid")
    # The complete, namespaced key ID is the trust-map key. This prevents a key
    # trusted for one authority from being reused under another issuer label.
    key = trusted_keys.get(key_id)
    if not isinstance(key, bytes) or not key or len(key) > 8192:
        raise PaidAuthorizationBridgeError("authorization signing key is not trusted")
    try:
        public_key = serialization.load_pem_public_key(key)
    except (ValueError, TypeError) as exc:
        raise PaidAuthorizationBridgeError("authorization public key is invalid") from exc
    if not isinstance(public_key, Ed25519PublicKey):
        raise PaidAuthorizationBridgeError("authorization public key must be Ed25519")

    unsigned = {name: value for name, value in envelope.items() if name != "signature"}
    signature = _decode_signature(envelope.get("signature"))
    try:
        public_key.verify(signature, _canonical(unsigned))
    except InvalidSignature as exc:
        raise PaidAuthorizationBridgeError("authorization signature verification failed") from exc

    if _required_text(envelope, "audience") != RUNPOD_PAID_AUTHORIZATION_AUDIENCE:
        raise PaidAuthorizationBridgeError("authorization audience does not match")
    if envelope.get("schema_version") != 1 or type(envelope.get("schema_version")) is not int:
        raise PaidAuthorizationBridgeError("authorization schema is unsupported")
    issued, expires = envelope.get("issued_at"), envelope.get("expires_at")
    if (type(issued) is not int or type(expires) is not int or issued < 0 or issued > now or
            expires <= now or expires <= issued or
            expires - issued > MAX_AUTHORIZATION_TTL_SECONDS):
        raise PaidAuthorizationBridgeError("authorization is expired or outside its validity window")

    text_fields = (
        "authorization_id", "revocation_id", "owner", "actor", "decision_record_id",
        "control_plane_sha", "gateway_plan_fingerprint", "core_plan_fingerprint",
        "provider", "resource_id", "image_digest", "max_cost_usd",
        "authorization_reference", "policy_version",
    )
    values = {field: _required_text(envelope, field) for field in text_fields}
    if values["policy_version"] != expected_policy_version:
        raise PaidAuthorizationBridgeError("authorization policy version is not current")
    if (not _RUN_ID.fullmatch(str(envelope.get("run_id", ""))) or
            envelope.get("run_id") != run_id):
        raise PaidAuthorizationBridgeError("authorization run identity does not match")
    if (values["owner"] != owner or values["actor"] != actor or
            values["decision_record_id"] != decision_record_id):
        raise PaidAuthorizationBridgeError("authorization owner or decision identity does not match")
    if not _SHA40.fullmatch(values["control_plane_sha"]) or values["control_plane_sha"] != control_plane_sha:
        raise PaidAuthorizationBridgeError("authorization control-plane identity does not match")
    if (not _SHA64.fullmatch(values["gateway_plan_fingerprint"]) or
            values["gateway_plan_fingerprint"] != plan_fingerprint(gateway_plan)):
        raise PaidAuthorizationBridgeError("authorization Gateway plan fingerprint does not match")
    if (not _SHA64.fullmatch(values["core_plan_fingerprint"]) or
            values["core_plan_fingerprint"] != core_plan.fingerprint().removeprefix("sha256:")):
        raise PaidAuthorizationBridgeError("authorization core plan fingerprint does not match")

    binding = gateway_plan.selection_binding
    if (gateway_plan.provider != "runpod" or values["provider"] != gateway_plan.provider or
            binding.provider != gateway_plan.provider or values["resource_id"] != binding.resource_id or
            not re.fullmatch(r"sha256:[0-9a-f]{64}", values["image_digest"]) or
            values["image_digest"] != gateway_plan.image_digest):
        raise PaidAuthorizationBridgeError("authorization provider, resource, or image does not match")
    requirements = gateway_plan.device_requirement
    profile, gpu_count = requirements.get("gpu_profile"), requirements.get("gpu_count")
    runtime = envelope.get("runtime_seconds")
    if (not isinstance(profile, str) or not profile or type(gpu_count) is not int or gpu_count < 1 or
            type(runtime) is not int or runtime != gateway_plan.runtime_seconds or runtime % 60 != 0 or
            core_plan.gpu_profile != profile or core_plan.gpu_count != gpu_count or
            core_plan.max_runtime_minutes != runtime // 60):
        raise PaidAuthorizationBridgeError("authorization GPU or runtime binding does not match")
    try:
        authorized_cost = _decimal(values["max_cost_usd"], "max_cost_usd")
    except PaidAuthorizationBridgeError:
        raise
    if (values["max_cost_usd"] != format(core_plan.max_cost_usd, "f") or
            authorized_cost != gateway_plan.max_cost_usd or core_plan.max_cost_usd != authorized_cost or
            core_plan.provider != gateway_plan.provider or
            core_plan.provider_resource_id != binding.resource_id or
            core_plan.target_repo != gateway_plan.repository or
            core_plan.target_sha != gateway_plan.source_sha or
            core_plan.image_digest != gateway_plan.image_digest or
            core_plan.authorization_reference != values["authorization_reference"]):
        raise PaidAuthorizationBridgeError("authorization core plan mapping does not match")
    try:
        revoked = is_revoked(issuer, values["revocation_id"])
    except Exception as exc:
        raise PaidAuthorizationBridgeError("authorization revocation status is unavailable") from exc
    if type(revoked) is not bool:
        raise PaidAuthorizationBridgeError("authorization revocation status is invalid")
    if revoked:
        raise PaidAuthorizationBridgeError("authorization has been revoked")

    return VerifiedPaidAuthorization(
        authorization_id=values["authorization_id"], revocation_id=values["revocation_id"],
        issuer=issuer, run_id=run_id,
        owner=owner, actor=actor, decision_record_id=decision_record_id,
        gateway_plan_fingerprint=values["gateway_plan_fingerprint"],
        core_plan_fingerprint=values["core_plan_fingerprint"], valid_until=expires,
        authorization_reference=values["authorization_reference"],
    )
