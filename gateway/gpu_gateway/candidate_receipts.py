"""Authenticated evidence binding a GPU result to its approved candidate.

This verifier defines the gateway side of the receipt contract. It does not
claim any provider implements or emits this format; an adapter must also
cross-check its live provider object through ``validate_candidate_observation``.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .contracts import PlanV2, plan_fingerprint

MAX_RECEIPT_BYTES = 16_384
MAX_RECEIPT_TTL_SECONDS = 300
_FIELDS = {"schema_version", "signer", "key_id", "provider", "issued_at", "expires_at", "payload", "signature"}
_PAYLOAD_FIELDS = {
    "run_id", "plan_fingerprint", "source_sha", "image_digest", "resource_id",
    "provider_execution_id", "device_id", "device_model", "gpu_used", "exit_code",
    "result_sha256", "evidence_source", "provider_object_sha256",
}


class CandidateReceiptError(ValueError):
    """A candidate receipt is malformed, stale, untrusted, or mismatched."""


def _canonical(value: object) -> bytes:
    try:
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise CandidateReceiptError("receipt is not canonical finite JSON") from exc
    if len(raw) > MAX_RECEIPT_BYTES:
        raise CandidateReceiptError("receipt exceeds size limit")
    return raw


def candidate_result_digest(result: Mapping) -> str:
    """Hash provider-produced result claims before gateway-added metadata."""
    if not isinstance(result, Mapping):
        raise CandidateReceiptError("result must be an object")
    claims = {key: result.get(key) for key in
              ("device", "gpu_used", "exit_code", "metrics", "checksum")}
    return hashlib.sha256(_canonical(claims)).hexdigest()


def _validate_projection_json(value: object, ancestors: set[int] | None = None) -> None:
    """Reject Python-only containers and coercible object keys before hashing."""
    if value is None or type(value) in {str, bool, int, float}:
        return
    if type(value) not in {dict, list}:
        raise CandidateReceiptError("provider object projection must contain only JSON values")
    ancestors = set() if ancestors is None else ancestors
    identity = id(value)
    if identity in ancestors:
        raise CandidateReceiptError("provider object projection must not contain cycles")
    ancestors.add(identity)
    try:
        if type(value) is dict:
            for key, item in value.items():
                if type(key) is not str:
                    raise CandidateReceiptError("provider object projection keys must be strings")
                _validate_projection_json(item, ancestors)
        else:
            for item in value:
                _validate_projection_json(item, ancestors)
    finally:
        ancestors.remove(identity)


def sign_adapter_candidate_receipt(
    *, private_key: Ed25519PrivateKey, key_id: str, issued_at: int,
    expires_at: int, now: int, plan: PlanV2, fingerprint: str, run_id: str,
    result: Mapping, provider_execution_id: str, device_id: str,
    evidence_source: str, provider_object_projection: Mapping,
) -> dict:
    """Sign claims after trusted adapter code authenticates the provider object.

    ``provider_object_projection`` must be a bounded, normalized projection
    from an authenticated provider API call. This helper hashes and signs it;
    it does not authenticate the response. The key must be operator-held,
    distinct from provider-observation keys, and unavailable to workloads.
    """
    if not isinstance(private_key, Ed25519PrivateKey):
        raise CandidateReceiptError("adapter receipt key must be Ed25519")
    if not isinstance(plan, PlanV2) or plan.selection_binding is None:
        raise CandidateReceiptError("candidate-bound plan is required")
    if fingerprint != plan_fingerprint(plan):
        raise CandidateReceiptError("plan fingerprint does not match candidate plan")
    if type(provider_object_projection) is not dict:
        raise CandidateReceiptError("provider object projection must be a JSON object")
    try:
        _validate_projection_json(provider_object_projection)
    except RecursionError as exc:
        raise CandidateReceiptError("provider object projection is too deeply nested") from exc
    projection_digest = hashlib.sha256(_canonical(provider_object_projection)).hexdigest()
    payload = {
        "run_id": run_id,
        "plan_fingerprint": fingerprint,
        "source_sha": plan.source_sha,
        "image_digest": plan.image_digest,
        "resource_id": plan.selection_binding.resource_id,
        "provider_execution_id": provider_execution_id,
        "device_id": device_id,
        "device_model": result.get("device") if isinstance(result, Mapping) else None,
        "gpu_used": result.get("gpu_used") if isinstance(result, Mapping) else None,
        "exit_code": result.get("exit_code") if isinstance(result, Mapping) else None,
        "result_sha256": candidate_result_digest(result),
        "evidence_source": evidence_source,
        "provider_object_sha256": projection_digest,
    }
    unsigned = {
        "schema_version": 1,
        "signer": "gateway_adapter",
        "key_id": key_id,
        "provider": plan.provider,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "payload": payload,
    }
    signature = base64.urlsafe_b64encode(private_key.sign(_canonical(unsigned)))
    receipt = unsigned | {"signature": signature.rstrip(b"=").decode("ascii")}
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # Reuse the verifier as the single source of envelope, timestamp, identity,
    # and success-claim rules; reject invalid receipts before returning them.
    verify_candidate_receipt(
        receipt, {key_id: public_key}, now=now, plan=plan,
        fingerprint=fingerprint, run_id=run_id, result=result,
    )
    return receipt


def verify_candidate_receipt(receipt: Mapping, trusted_keys: Mapping[str, bytes], *,
                             now: int, plan: PlanV2, fingerprint: str,
                             run_id: str, result: Mapping,
                             require_current: bool = True) -> dict:
    """Verify signer scope, freshness, candidate identity, and result claims.

    ``provider`` means a provider-signed receipt. ``gateway_adapter`` means a
    trusted adapter signed its authenticated provider API observation; the
    adapter must independently compare the live provider object before it can
    return true from ``validate_candidate_observation``.
    """
    if not isinstance(receipt, Mapping) or set(receipt) != _FIELDS:
        raise CandidateReceiptError("receipt fields are invalid")
    encoded = _canonical(receipt)
    if not isinstance(trusted_keys, Mapping) or type(now) is not int or now < 0:
        raise CandidateReceiptError("receipt trust configuration is invalid")
    unsigned = {key: value for key, value in receipt.items() if key != "signature"}
    key_id = receipt["key_id"]
    signer = receipt["signer"]
    signature_text = receipt["signature"]
    if not isinstance(signer, str) or signer not in {"provider", "gateway_adapter"}:
        raise CandidateReceiptError("receipt signer type is invalid")
    key_prefix = "provider" if signer == "provider" else "adapter"
    if (not isinstance(key_id, str) or
            not re.fullmatch(r"(?:provider|adapter):[a-z][a-z0-9_-]{0,31}:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", key_id) or
            not key_id.startswith(key_prefix + ":" + str(receipt["provider"]) + ":")):
        raise CandidateReceiptError("receipt key ID is invalid")
    if not isinstance(signature_text, str) or not re.fullmatch(r"[A-Za-z0-9_-]{86}", signature_text):
        raise CandidateReceiptError("receipt signature encoding is invalid")
    issued, expires = receipt["issued_at"], receipt["expires_at"]
    if (type(issued) is not int or type(expires) is not int or issued > now or
            require_current and expires <= now or expires <= issued or
            expires - issued > MAX_RECEIPT_TTL_SECONDS):
        raise CandidateReceiptError("receipt is stale or outside its validity window")
    if receipt["schema_version"] != 1 or type(receipt["schema_version"]) is not int:
        raise CandidateReceiptError("receipt schema is unsupported")
    provider = receipt["provider"]
    if provider != plan.provider:
        raise CandidateReceiptError("receipt provider does not match plan")
    payload = receipt["payload"]
    if not isinstance(payload, Mapping) or set(payload) != _PAYLOAD_FIELDS:
        raise CandidateReceiptError("receipt payload fields are invalid")
    binding = plan.selection_binding
    if binding is None:
        raise CandidateReceiptError("candidate-bound plan is required")
    expected = {
        "run_id": run_id,
        "plan_fingerprint": fingerprint,
        "source_sha": plan.source_sha,
        "image_digest": plan.image_digest,
        "resource_id": binding.resource_id,
        "gpu_used": True,
        "exit_code": 0,
        "result_sha256": candidate_result_digest(result),
        "device_model": result.get("device"),
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise CandidateReceiptError("receipt identity or result does not match plan")
    for field in ("run_id", "plan_fingerprint", "source_sha", "image_digest", "result_sha256"):
        if not isinstance(payload[field], str):
            raise CandidateReceiptError("receipt digest or identity is invalid")
    for field in ("provider_execution_id", "device_id", "device_model"):
        value = payload[field]
        if (not isinstance(value, str) or not value or value != value.strip() or len(value) > 256 or
                any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise CandidateReceiptError("receipt execution or device identity is invalid")
    source = payload["evidence_source"]
    snapshot_digest = payload["provider_object_sha256"]
    if (not isinstance(source, str) or not source.startswith(provider + ".") or
            len(source) > 128 or any(ord(char) < 33 or ord(char) == 127 for char in source) or
            not isinstance(snapshot_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", snapshot_digest)):
        raise CandidateReceiptError("receipt provider evidence source is invalid")
    if type(payload["gpu_used"]) is not bool or type(payload["exit_code"]) is not int:
        raise CandidateReceiptError("receipt result claim types are invalid")
    public_pem = trusted_keys.get(key_id)
    if not isinstance(public_pem, bytes):
        raise CandidateReceiptError("receipt signing key is not trusted")
    try:
        public_key = serialization.load_pem_public_key(public_pem)
        signature = base64.urlsafe_b64decode(signature_text + "==")
    except (TypeError, ValueError, base64.binascii.Error) as exc:
        raise CandidateReceiptError("receipt public key or signature is invalid") from exc
    if not isinstance(public_key, Ed25519PublicKey) or len(signature) != 64:
        raise CandidateReceiptError("receipt must use a trusted Ed25519 key")
    try:
        public_key.verify(signature, _canonical(unsigned))
    except InvalidSignature as exc:
        raise CandidateReceiptError("receipt signature verification failed") from exc
    # Keep the serialized envelope bounded and prove that the complete value
    # is finite JSON, even though the signature covers only the unsigned form.
    if not encoded:
        raise CandidateReceiptError("receipt is empty")
    return dict(receipt)
