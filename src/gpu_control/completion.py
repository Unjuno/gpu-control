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
_EXECUTION_NAME_RE = re.compile(r"^gpu-control-[0-9a-f]{12}-[0-9a-f]{12}$")


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


def execution_name_for(*, plan_fingerprint: str, nonce: str) -> str:
    """Return the unique provider request name known before Pod creation."""

    fingerprint = _require_sha256(plan_fingerprint, "plan_fingerprint")
    if not isinstance(nonce, str) or not _HEX_64_RE.fullmatch(nonce):
        raise CompletionEvidenceError("nonce must be 32 random bytes encoded as lowercase hex")
    return f"gpu-control-{fingerprint[7:19]}-{nonce[:12]}"


def _canonical_payload(
    *,
    key_id: str,
    nonce: str,
    execution_name: str,
    plan_fingerprint: str,
    source_sha: str,
    image_digest: str,
    result_sha256: str,
) -> bytes:
    payload = {
        "execution_name": execution_name,
        "image_digest": image_digest,
        "key_id": key_id,
        "nonce": nonce,
        "plan_fingerprint": plan_fingerprint,
        "result_sha256": result_sha256,
        "source_sha": source_sha,
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class CompletionChallenge:
    """Public correlation data generated before a provider create call.

    RunPod assigns ``provider_job_id`` only after POST /pods, while the container
    environment is fixed in that same create request. Completion therefore binds
    to a unique, pre-create ``execution_name`` plus a random nonce and exact plan.
    The returned provider job id is correlated separately by SubmissionReceipt.
    The HMAC key is deliberately absent and must never be persisted.
    """

    key_id: str
    nonce: str
    execution_name: str
    plan_fingerprint: str
    source_sha: str
    image_digest: str
    schema_version: int = 2

    def validate_shape(self) -> None:
        if self.schema_version != 2:
            raise CompletionEvidenceError("unsupported completion challenge schema_version")
        if not isinstance(self.key_id, str) or not _KEY_ID_RE.fullmatch(self.key_id):
            raise CompletionEvidenceError("key_id is invalid")
        if not isinstance(self.nonce, str) or not _HEX_64_RE.fullmatch(self.nonce):
            raise CompletionEvidenceError("nonce must be 32 random bytes encoded as lowercase hex")
        _require_sha256(self.plan_fingerprint, "plan_fingerprint")
        if not isinstance(self.execution_name, str) or not _EXECUTION_NAME_RE.fullmatch(self.execution_name):
            raise CompletionEvidenceError("execution_name is invalid")
        if self.execution_name != execution_name_for(plan_fingerprint=self.plan_fingerprint, nonce=self.nonce):
            raise CompletionEvidenceError("execution_name does not match plan fingerprint and nonce")
        if not isinstance(self.source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", self.source_sha):
            raise CompletionEvidenceError("source_sha must be a lowercase 40-character commit SHA")
        _require_sha256(self.image_digest, "image_digest")

    def to_dict(self) -> dict[str, object]:
        self.validate_shape()
        return {
            "key_id": self.key_id,
            "nonce": self.nonce,
            "execution_name": self.execution_name,
            "plan_fingerprint": self.plan_fingerprint,
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
        source_sha: str,
        image_digest: str,
    ) -> "CompletionChallenge":
        nonce = secrets.token_hex(32)
        value = cls(
            key_id=key_id,
            nonce=nonce,
            execution_name=execution_name_for(plan_fingerprint=plan_fingerprint, nonce=nonce),
            plan_fingerprint=plan_fingerprint,
            source_sha=source_sha,
            image_digest=image_digest,
        )
        value.validate_shape()
        return value


@dataclass(frozen=True)
class CompletionEvidence:
    """Authenticated statement that the exact execution finalized result bytes."""

    key_id: str
    nonce: str
    execution_name: str
    plan_fingerprint: str
    source_sha: str
    image_digest: str
    result_sha256: str
    mac_sha256: str
    schema_version: int = 2

    def validate_shape(self) -> None:
        if self.schema_version != 2:
            raise CompletionEvidenceError("unsupported completion evidence schema_version")
        if not isinstance(self.key_id, str) or not _KEY_ID_RE.fullmatch(self.key_id):
            raise CompletionEvidenceError("key_id is invalid")
        if not isinstance(self.nonce, str) or not _HEX_64_RE.fullmatch(self.nonce):
            raise CompletionEvidenceError("nonce is invalid")
        if not isinstance(self.execution_name, str) or not _EXECUTION_NAME_RE.fullmatch(self.execution_name):
            raise CompletionEvidenceError("execution_name is invalid")
        _require_sha256(self.plan_fingerprint, "plan_fingerprint")
        if self.execution_name != execution_name_for(plan_fingerprint=self.plan_fingerprint, nonce=self.nonce):
            raise CompletionEvidenceError("execution_name does not match plan fingerprint and nonce")
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
            "execution_name": self.execution_name,
            "plan_fingerprint": self.plan_fingerprint,
            "source_sha": self.source_sha,
            "image_digest": self.image_digest,
            "result_sha256": self.result_sha256,
            "mac_sha256": self.mac_sha256,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionEvidence":
        expected = {
            "key_id", "nonce", "execution_name", "plan_fingerprint", "source_sha",
            "image_digest", "result_sha256", "mac_sha256", "schema_version",
        }
        if set(payload) != expected:
            raise CompletionEvidenceError("completion evidence fields do not match schema")
        value = cls(
            key_id=payload["key_id"],  # type: ignore[arg-type]
            nonce=payload["nonce"],  # type: ignore[arg-type]
            execution_name=payload["execution_name"],  # type: ignore[arg-type]
            plan_fingerprint=payload["plan_fingerprint"],  # type: ignore[arg-type]
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
        execution_name=challenge.execution_name,
        plan_fingerprint=challenge.plan_fingerprint,
        source_sha=challenge.source_sha,
        image_digest=challenge.image_digest,
        result_sha256=result_digest,
    )
    mac = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    return CompletionEvidence(
        key_id=challenge.key_id,
        nonce=challenge.nonce,
        execution_name=challenge.execution_name,
        plan_fingerprint=challenge.plan_fingerprint,
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

    for field in ("key_id", "nonce", "execution_name", "plan_fingerprint", "source_sha", "image_digest"):
        if getattr(evidence, field) != getattr(challenge, field):
            raise CompletionEvidenceError(f"completion evidence {field} does not match challenge")
    if evidence.result_sha256 != expected_result:
        raise CompletionEvidenceError("completion evidence result_sha256 does not match collected result bytes")

    expected = sign_completion(challenge, result_sha256=expected_result, secret_key=secret_key)
    if not hmac.compare_digest(evidence.mac_sha256, expected.mac_sha256):
        raise CompletionEvidenceError("completion evidence authentication failed")
