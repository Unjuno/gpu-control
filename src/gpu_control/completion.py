from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import secrets
from typing import Any, Mapping


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
_KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class CompletionEvidenceError(ValueError):
    """Raised when workload-completion evidence is malformed or unauthenticated."""


def _require_nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompletionEvidenceError(f"{field} is required")
    return value.strip()


def _require_sha256(value: object, field: str) -> str:
    normalized = _require_nonempty(value, field)
    if not _SHA256_RE.fullmatch(normalized):
        raise CompletionEvidenceError(f"{field} must be a lowercase sha256 digest")
    return normalized


def _canonical_payload(
    *,
    key_id: str,
    nonce: str,
    plan_fingerprint: str,
    provider_job_id: str,
    source_sha: str,
    image_digest: str,
    result_sha256: str,
) -> bytes:
    payload = {
        "image_digest": image_digest,
        "key_id": key_id,
        "nonce": nonce,
        "plan_fingerprint": plan_fingerprint,
        "provider_job_id": provider_job_id,
        "result_sha256": result_sha256,
        "source_sha": source_sha,
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class CompletionChallenge:
    """Public, persisted correlation data for one approved workload execution.

    The HMAC key is deliberately absent. It must be supplied from a protected
    control-plane secret at issue/verify time and must never be serialized into
    durable lifecycle JSON.
    """

    key_id: str
    nonce: str
    plan_fingerprint: str
    provider_job_id: str
    source_sha: str
    image_digest: str
    schema_version: int = 1

    def validate_shape(self) -> None:
        if self.schema_version != 1:
            raise CompletionEvidenceError("unsupported completion challenge schema_version")
        if not isinstance(self.key_id, str) or not _KEY_ID_RE.fullmatch(self.key_id):
            raise CompletionEvidenceError("key_id is invalid")
        if not isinstance(self.nonce, str) or not _HEX_64_RE.fullmatch(self.nonce):
            raise CompletionEvidenceError("nonce must be 32 random bytes encoded as lowercase hex")
        _require_sha256(self.plan_fingerprint, "plan_fingerprint")
        _require_nonempty(self.provider_job_id, "provider_job_id")
        if not isinstance(self.source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", self.source_sha):
            raise CompletionEvidenceError("source_sha must be a lowercase 40-character commit SHA")
        _require_sha256(self.image_digest, "image_digest")

    def to_dict(self) -> dict[str, object]:
        self.validate_shape()
        return {
            "key_id": self.key_id,
            "nonce": self.nonce,
            "plan_fingerprint": self.plan_fingerprint,
            "provider_job_id": self.provider_job_id,
            "source_sha": self.source_sha,
            "image_digest": self.image_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def create(
        cls,
        *,
        key_id: str,
        plan_fingerprint: str,
        provider_job_id: str,
        source_sha: str,
        image_digest: str,
    ) -> "CompletionChallenge":
        value = cls(
            key_id=key_id,
            nonce=secrets.token_hex(32),
            plan_fingerprint=plan_fingerprint,
            provider_job_id=provider_job_id,
            source_sha=source_sha,
            image_digest=image_digest,
        )
        value.validate_shape()
        return value


@dataclass(frozen=True)
class CompletionEvidence:
    """Authenticated statement that the approved workload finalized result bytes."""

    key_id: str
    nonce: str
    plan_fingerprint: str
    provider_job_id: str
    source_sha: str
    image_digest: str
    result_sha256: str
    mac_sha256: str
    schema_version: int = 1

    def validate_shape(self) -> None:
        if self.schema_version != 1:
            raise CompletionEvidenceError("unsupported completion evidence schema_version")
        if not isinstance(self.key_id, str) or not _KEY_ID_RE.fullmatch(self.key_id):
            raise CompletionEvidenceError("key_id is invalid")
        if not isinstance(self.nonce, str) or not _HEX_64_RE.fullmatch(self.nonce):
            raise CompletionEvidenceError("nonce is invalid")
        _require_sha256(self.plan_fingerprint, "plan_fingerprint")
        _require_nonempty(self.provider_job_id, "provider_job_id")
        if not isinstance(self.source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", self.source_sha):
            raise CompletionEvidenceError("source_sha must be a lowercase 40-character commit SHA")
        _require_sha256(self.image_digest, "image_digest")
        _require_sha256(self.result_sha256, "result_sha256")
        if not isinstance(self.mac_sha256, str) or not _HEX_64_RE.fullmatch(self.mac_sha256):
            raise CompletionEvidenceError("mac_sha256 must be lowercase HMAC-SHA256 hex")

    def to_dict(self) -> dict[str, object]:
        self.validate_shape()
        return {
            "key_id": self.key_id,
            "nonce": self.nonce,
            "plan_fingerprint": self.plan_fingerprint,
            "provider_job_id": self.provider_job_id,
            "source_sha": self.source_sha,
            "image_digest": self.image_digest,
            "result_sha256": self.result_sha256,
            "mac_sha256": self.mac_sha256,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionEvidence":
        expected = {
            "key_id", "nonce", "plan_fingerprint", "provider_job_id", "source_sha",
            "image_digest", "result_sha256", "mac_sha256", "schema_version",
        }
        if set(payload) != expected:
            raise CompletionEvidenceError("completion evidence fields do not match schema")
        value = cls(
            key_id=payload["key_id"],  # type: ignore[arg-type]
            nonce=payload["nonce"],  # type: ignore[arg-type]
            plan_fingerprint=payload["plan_fingerprint"],  # type: ignore[arg-type]
            provider_job_id=payload["provider_job_id"],  # type: ignore[arg-type]
            source_sha=payload["source_sha"],  # type: ignore[arg-type]
            image_digest=payload["image_digest"],  # type: ignore[arg-type]
            result_sha256=payload["result_sha256"],  # type: ignore[arg-type]
            mac_sha256=payload["mac_sha256"],  # type: ignore[arg-type]
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
        )
        value.validate_shape()
        return value


def sign_completion(
    challenge: CompletionChallenge,
    *,
    result_sha256: str,
    secret_key: bytes,
) -> CompletionEvidence:
    challenge.validate_shape()
    result_digest = _require_sha256(result_sha256, "result_sha256")
    if not isinstance(secret_key, bytes) or len(secret_key) < 32:
        raise CompletionEvidenceError("completion secret key must contain at least 32 bytes")
    message = _canonical_payload(
        key_id=challenge.key_id,
        nonce=challenge.nonce,
        plan_fingerprint=challenge.plan_fingerprint,
        provider_job_id=challenge.provider_job_id,
        source_sha=challenge.source_sha,
        image_digest=challenge.image_digest,
        result_sha256=result_digest,
    )
    mac = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    return CompletionEvidence(
        key_id=challenge.key_id,
        nonce=challenge.nonce,
        plan_fingerprint=challenge.plan_fingerprint,
        provider_job_id=challenge.provider_job_id,
        source_sha=challenge.source_sha,
        image_digest=challenge.image_digest,
        result_sha256=result_digest,
        mac_sha256=mac,
    )


def verify_completion(
    challenge: CompletionChallenge,
    evidence: CompletionEvidence,
    *,
    secret_key: bytes,
    expected_result_sha256: str,
) -> None:
    challenge.validate_shape()
    evidence.validate_shape()
    expected_result = _require_sha256(expected_result_sha256, "expected_result_sha256")
    if not isinstance(secret_key, bytes) or len(secret_key) < 32:
        raise CompletionEvidenceError("completion secret key must contain at least 32 bytes")

    for field in ("key_id", "nonce", "plan_fingerprint", "provider_job_id", "source_sha", "image_digest"):
        if getattr(evidence, field) != getattr(challenge, field):
            raise CompletionEvidenceError(f"completion evidence {field} does not match challenge")
    if evidence.result_sha256 != expected_result:
        raise CompletionEvidenceError("completion evidence result_sha256 does not match collected result bytes")

    expected = sign_completion(challenge, result_sha256=expected_result, secret_key=secret_key)
    if not hmac.compare_digest(evidence.mac_sha256, expected.mac_sha256):
        raise CompletionEvidenceError("completion evidence authentication failed")
