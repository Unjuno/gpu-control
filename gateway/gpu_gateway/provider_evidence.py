"""Authenticated, bounded envelopes for worker-collected provider observations.

The API may share a database writer credential with the worker. Therefore a
database row plus a content hash is not enough to prove worker provenance.
This module signs the canonical envelope in the worker and verifies it against
an API-pinned public-key set. It performs no provider or database I/O.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


MAX_OBSERVATION_TTL_SECONDS = 300
MAX_ENVELOPE_BYTES = 1_048_576
_PROVIDER = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_FIELDS = frozenset({
    "schema_version", "key_id", "provider", "source", "source_revision",
    "version", "observed_at", "expires_at", "payload_sha256", "payload",
    "signature",
})


class ProviderEvidenceError(ValueError):
    """Provider observation envelope is malformed, stale, or unauthenticated."""


def _canonical(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ProviderEvidenceError("observation is not canonical finite JSON") from exc
    if len(encoded) > MAX_ENVELOPE_BYTES:
        raise ProviderEvidenceError("observation envelope exceeds size limit")
    return encoded


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: object) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{86}", value):
        raise ProviderEvidenceError("observation signature encoding is invalid")
    try:
        decoded = base64.urlsafe_b64decode(value + "==")
    except (ValueError, base64.binascii.Error) as exc:
        raise ProviderEvidenceError("observation signature encoding is invalid") from exc
    if len(decoded) != 64:
        raise ProviderEvidenceError("observation signature length is invalid")
    return decoded


def _timestamp(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ProviderEvidenceError(f"{field} must be a nonnegative integer timestamp")
    return value


def build_signed_observation(
    *,
    provider: str,
    source: str,
    source_revision: str,
    version: int,
    observed_at: int,
    expires_at: int,
    payload: Mapping[str, Any],
    key_id: str,
    private_key_pem: bytes,
) -> dict[str, Any]:
    """Create a canonical Ed25519-signed observation envelope in the worker."""
    if not isinstance(provider, str) or not _PROVIDER.fullmatch(provider):
        raise ProviderEvidenceError("provider identifier is invalid")
    if not isinstance(source, str) or not _IDENTIFIER.fullmatch(source):
        raise ProviderEvidenceError("source identifier is invalid")
    if not isinstance(source_revision, str) or not _IDENTIFIER.fullmatch(source_revision):
        raise ProviderEvidenceError("source revision is invalid")
    if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
        raise ProviderEvidenceError("signing key ID is invalid")
    if type(version) is not int or version < 1:
        raise ProviderEvidenceError("observation version must be a positive integer")
    checked = _timestamp(observed_at, "observed_at")
    expiry = _timestamp(expires_at, "expires_at")
    if expiry <= checked or expiry - checked > MAX_OBSERVATION_TTL_SECONDS:
        raise ProviderEvidenceError("observation validity window is invalid")
    if not isinstance(payload, Mapping):
        raise ProviderEvidenceError("observation payload must be an object")
    payload_bytes = _canonical(payload)
    unsigned: dict[str, Any] = {
        "schema_version": 1,
        "key_id": key_id,
        "provider": provider,
        "source": source,
        "source_revision": source_revision,
        "version": version,
        "observed_at": checked,
        "expires_at": expiry,
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "payload": dict(payload),
    }
    signing_bytes = _canonical(unsigned)
    try:
        key = serialization.load_pem_private_key(private_key_pem, password=None)
    except (TypeError, ValueError) as exc:
        raise ProviderEvidenceError("worker signing key is invalid") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ProviderEvidenceError("worker signing key must be Ed25519")
    envelope = unsigned | {"signature": _b64url_encode(key.sign(signing_bytes))}
    _canonical(envelope)
    return envelope


def verify_signed_observation(
    envelope: Mapping[str, Any],
    trusted_public_keys: Mapping[str, bytes],
    *,
    now: int,
    minimum_version: int | None = None,
) -> dict[str, Any]:
    """Verify canonical shape, payload digest, freshness, key, and signature."""
    if not isinstance(envelope, Mapping) or set(envelope) != _FIELDS:
        raise ProviderEvidenceError("observation envelope fields are invalid")
    serialized = _canonical(envelope)
    if not isinstance(trusted_public_keys, Mapping):
        raise ProviderEvidenceError("trusted public keys must be a mapping")
    if type(now) is not int or now < 0:
        raise ProviderEvidenceError("now must be a nonnegative integer timestamp")
    if envelope["schema_version"] != 1 or type(envelope["schema_version"]) is not int:
        raise ProviderEvidenceError("observation schema version is unsupported")
    key_id = envelope["key_id"]
    provider = envelope["provider"]
    source = envelope["source"]
    revision = envelope["source_revision"]
    if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
        raise ProviderEvidenceError("signing key ID is invalid")
    if not isinstance(provider, str) or not _PROVIDER.fullmatch(provider):
        raise ProviderEvidenceError("provider identifier is invalid")
    if not isinstance(source, str) or not _IDENTIFIER.fullmatch(source):
        raise ProviderEvidenceError("source identifier is invalid")
    if not isinstance(revision, str) or not _IDENTIFIER.fullmatch(revision):
        raise ProviderEvidenceError("source revision is invalid")
    version = envelope["version"]
    if type(version) is not int or version < 1:
        raise ProviderEvidenceError("observation version must be a positive integer")
    if minimum_version is not None and (
        type(minimum_version) is not int or version <= minimum_version
    ):
        raise ProviderEvidenceError("observation version is stale or replayed")
    observed = _timestamp(envelope["observed_at"], "observed_at")
    expiry = _timestamp(envelope["expires_at"], "expires_at")
    if observed > now or expiry <= now or expiry <= observed:
        raise ProviderEvidenceError("observation is not current")
    if expiry - observed > MAX_OBSERVATION_TTL_SECONDS:
        raise ProviderEvidenceError("observation validity window exceeds limit")
    payload = envelope["payload"]
    if not isinstance(payload, Mapping):
        raise ProviderEvidenceError("observation payload must be an object")
    payload_digest = envelope["payload_sha256"]
    if not isinstance(payload_digest, str) or not _SHA256.fullmatch(payload_digest):
        raise ProviderEvidenceError("observation payload digest is invalid")
    if hashlib.sha256(_canonical(payload)).hexdigest() != payload_digest:
        raise ProviderEvidenceError("observation payload digest mismatch")
    public_pem = trusted_public_keys.get(key_id)
    if not isinstance(public_pem, bytes):
        raise ProviderEvidenceError("observation signing key is not trusted")
    try:
        public_key = serialization.load_pem_public_key(public_pem)
    except (TypeError, ValueError) as exc:
        raise ProviderEvidenceError("trusted public key is invalid") from exc
    if not isinstance(public_key, Ed25519PublicKey):
        raise ProviderEvidenceError("trusted public key must be Ed25519")
    unsigned = {key: value for key, value in envelope.items() if key != "signature"}
    try:
        public_key.verify(_b64url_decode(envelope["signature"]), _canonical(unsigned))
    except InvalidSignature as exc:
        raise ProviderEvidenceError("observation signature verification failed") from exc
    return dict(envelope)
