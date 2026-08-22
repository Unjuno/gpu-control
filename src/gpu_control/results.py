from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
from importlib.resources import files
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence

import yaml

from .lifecycle import JobObservation, JobState, SubmissionReceipt, validate_observation


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ARTIFACT_KEYS = {
    "name",
    "sha256",
    "size_bytes",
    "media_type",
    "reference",
    "disposition",
}
_MANIFEST_KEYS = {
    "provider",
    "provider_job_id",
    "plan_fingerprint",
    "submission_receipt_fingerprint",
    "final_observation_fingerprint",
    "terminal_state",
    "collected_at_utc",
    "log_bytes_retained",
    "logs_truncated",
    "artifacts",
    "schema_version",
}
_TERMINAL_STATES = {
    JobState.SUCCEEDED,
    JobState.FAILED,
    JobState.CANCELLED,
    JobState.TIMED_OUT,
}


class ResultContractError(ValueError):
    """Raised when collected provider output violates the result contract."""


class ArtifactDisposition(str, Enum):
    COLLECTED = "collected"
    REFERENCE_ONLY = "reference_only"


@dataclass(frozen=True)
class ResultPolicy:
    max_log_bytes: int
    max_artifact_entries: int
    max_name_length: int
    max_reference_length: int
    max_media_type_length: int
    max_declared_artifact_bytes: int
    max_collected_file_bytes: int
    max_total_collected_bytes: int
    large_artifacts: str
    require_sha256: bool
    auto_fetch_references: bool
    schema_version: int = 1

    def validate_shape(self) -> None:
        if self.schema_version != 1:
            raise ResultContractError("unsupported result policy schema_version")
        positive_fields = {
            "max_log_bytes": self.max_log_bytes,
            "max_artifact_entries": self.max_artifact_entries,
            "max_name_length": self.max_name_length,
            "max_reference_length": self.max_reference_length,
            "max_media_type_length": self.max_media_type_length,
            "max_declared_artifact_bytes": self.max_declared_artifact_bytes,
            "max_collected_file_bytes": self.max_collected_file_bytes,
            "max_total_collected_bytes": self.max_total_collected_bytes,
        }
        for field, value in positive_fields.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ResultContractError(f"result policy {field} must be a positive integer")
        if self.max_collected_file_bytes > self.max_total_collected_bytes:
            raise ResultContractError("max_collected_file_bytes cannot exceed max_total_collected_bytes")
        if self.max_total_collected_bytes > self.max_declared_artifact_bytes * self.max_artifact_entries:
            raise ResultContractError("result policy total collection limit is internally inconsistent")
        if self.large_artifacts != "reference_only":
            raise ResultContractError("large artifacts must remain reference_only in the current policy")
        if self.require_sha256 is not True:
            raise ResultContractError("result policy must require sha256 digests")
        if self.auto_fetch_references is not False:
            raise ResultContractError("result policy must not auto-fetch artifact references")


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResultContractError(f"result policy {field} must be a positive integer")
    return value


def _parse_result_policy(text: str) -> ResultPolicy:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ResultContractError("result policy must be valid YAML") from exc
    if not isinstance(data, dict):
        raise ResultContractError("result policy must contain a mapping")
    if data.get("version") != 1:
        raise ResultContractError("unsupported result policy version")

    logs = data.get("logs")
    artifacts = data.get("artifacts")
    collection = data.get("collection")
    behavior = data.get("behavior")
    if not all(isinstance(section, dict) for section in (logs, artifacts, collection, behavior)):
        raise ResultContractError("result policy is missing required mappings")

    policy = ResultPolicy(
        max_log_bytes=_positive_int(logs.get("max_retained_bytes"), "logs.max_retained_bytes"),
        max_artifact_entries=_positive_int(artifacts.get("max_entries"), "artifacts.max_entries"),
        max_name_length=_positive_int(artifacts.get("max_name_length"), "artifacts.max_name_length"),
        max_reference_length=_positive_int(
            artifacts.get("max_reference_length"), "artifacts.max_reference_length"
        ),
        max_media_type_length=_positive_int(
            artifacts.get("max_media_type_length"), "artifacts.max_media_type_length"
        ),
        max_declared_artifact_bytes=_positive_int(
            artifacts.get("max_declared_bytes"), "artifacts.max_declared_bytes"
        ),
        max_collected_file_bytes=_positive_int(
            collection.get("max_collected_file_bytes"), "collection.max_collected_file_bytes"
        ),
        max_total_collected_bytes=_positive_int(
            collection.get("max_total_collected_bytes"), "collection.max_total_collected_bytes"
        ),
        large_artifacts=behavior.get("large_artifacts"),  # type: ignore[arg-type]
        require_sha256=behavior.get("require_sha256"),  # type: ignore[arg-type]
        auto_fetch_references=behavior.get("auto_fetch_references"),  # type: ignore[arg-type]
    )
    policy.validate_shape()
    return policy


def load_result_policy(path: str | Path | None = None) -> ResultPolicy:
    """Load the bundled result policy or an explicit policy file."""

    if path is None:
        resource = files("gpu_control").joinpath("default_result_policy.yaml")
        return _parse_result_policy(resource.read_text(encoding="utf-8"))
    return _parse_result_policy(Path(path).read_text(encoding="utf-8"))


def _parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ResultContractError(f"{field} is required")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ResultContractError(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ResultContractError(f"{field} must be timezone-aware UTC")
    return parsed


def _format_utc(value: datetime, field: str) -> str:
    if not isinstance(value, datetime):
        raise ResultContractError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ResultContractError(f"{field} must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_exact_keys(payload: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(payload)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ResultContractError(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ResultContractError(f"{label} contains unknown fields: {', '.join(sorted(unknown))}")


def _load_json_object(value: str, label: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        raise ResultContractError(f"{label} JSON is required")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ResultContractError(f"{label} contains duplicate field: {key}")
            result[key] = item
        return result

    try:
        payload = json.loads(value, object_pairs_hook=reject_duplicates)
    except ResultContractError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise ResultContractError(f"{label} must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ResultContractError(f"{label} must be a JSON object")
    return payload


def _validate_text(value: object, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResultContractError(f"{field} is required")
    if value != value.strip():
        raise ResultContractError(f"{field} must not contain surrounding whitespace")
    if len(value) > max_length:
        raise ResultContractError(f"{field} exceeds maximum length {max_length}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ResultContractError(f"{field} must not contain control characters")
    return value


def _validate_artifact_name(value: object, policy: ResultPolicy) -> str:
    name = _validate_text(value, "artifact name", policy.max_name_length)
    if "\\" in name:
        raise ResultContractError("artifact name must use POSIX separators")
    segments = name.split("/")
    path = PurePosixPath(name)
    if path.is_absolute() or any(segment in {"", ".", ".."} for segment in segments):
        raise ResultContractError("artifact name must be a safe relative POSIX path")
    return name


@dataclass(frozen=True)
class OutputArtifact:
    name: str
    sha256: str
    size_bytes: int
    media_type: str
    reference: str
    disposition: ArtifactDisposition

    def validate_shape(self, policy: ResultPolicy) -> None:
        policy.validate_shape()
        _validate_artifact_name(self.name, policy)
        if not isinstance(self.sha256, str) or not _SHA256_RE.fullmatch(self.sha256):
            raise ResultContractError("artifact sha256 must be a lowercase sha256 digest")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ResultContractError("artifact size_bytes must be a non-negative integer")
        if self.size_bytes > policy.max_declared_artifact_bytes:
            raise ResultContractError("artifact declared size exceeds result policy")
        _validate_text(self.media_type, "artifact media_type", policy.max_media_type_length)
        _validate_text(self.reference, "artifact reference", policy.max_reference_length)
        if not isinstance(self.disposition, ArtifactDisposition):
            raise ResultContractError("artifact disposition is invalid")
        if self.disposition is ArtifactDisposition.COLLECTED and self.size_bytes > policy.max_collected_file_bytes:
            raise ResultContractError("collected artifact exceeds per-file collection limit")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "reference": self.reference,
            "disposition": self.disposition.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], policy: ResultPolicy) -> OutputArtifact:
        if not isinstance(payload, Mapping):
            raise ResultContractError("artifact entry must be an object")
        _require_exact_keys(payload, _ARTIFACT_KEYS, "artifact entry")
        try:
            disposition = ArtifactDisposition(payload["disposition"])
        except (TypeError, ValueError) as exc:
            raise ResultContractError("artifact disposition is invalid") from exc
        artifact = cls(
            name=payload["name"],  # type: ignore[arg-type]
            sha256=payload["sha256"],  # type: ignore[arg-type]
            size_bytes=payload["size_bytes"],  # type: ignore[arg-type]
            media_type=payload["media_type"],  # type: ignore[arg-type]
            reference=payload["reference"],  # type: ignore[arg-type]
            disposition=disposition,
        )
        artifact.validate_shape(policy)
        return artifact


@dataclass(frozen=True)
class ResultManifest:
    provider: str
    provider_job_id: str
    plan_fingerprint: str
    submission_receipt_fingerprint: str
    final_observation_fingerprint: str
    terminal_state: JobState
    collected_at_utc: str
    log_bytes_retained: int
    logs_truncated: bool
    artifacts: tuple[OutputArtifact, ...]
    schema_version: int = 1

    def validate_shape(self, policy: ResultPolicy) -> datetime:
        policy.validate_shape()
        if self.schema_version != 1:
            raise ResultContractError("unsupported result manifest schema_version")
        _validate_text(self.provider, "manifest provider", 128)
        _validate_text(self.provider_job_id, "manifest provider_job_id", 512)
        for field, value in (
            ("plan_fingerprint", self.plan_fingerprint),
            ("submission_receipt_fingerprint", self.submission_receipt_fingerprint),
            ("final_observation_fingerprint", self.final_observation_fingerprint),
        ):
            if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
                raise ResultContractError(f"{field} must be a lowercase sha256 fingerprint")
        if not isinstance(self.terminal_state, JobState) or self.terminal_state not in _TERMINAL_STATES:
            raise ResultContractError("terminal_state must be a terminal JobState")
        if (
            isinstance(self.log_bytes_retained, bool)
            or not isinstance(self.log_bytes_retained, int)
            or self.log_bytes_retained < 0
        ):
            raise ResultContractError("log_bytes_retained must be a non-negative integer")
        if self.log_bytes_retained > policy.max_log_bytes:
            raise ResultContractError("retained logs exceed result policy")
        if not isinstance(self.logs_truncated, bool):
            raise ResultContractError("logs_truncated must be a boolean")
        if not isinstance(self.artifacts, tuple):
            raise ResultContractError("artifacts must be a tuple")
        if len(self.artifacts) > policy.max_artifact_entries:
            raise ResultContractError("artifact count exceeds result policy")

        seen_names: set[str] = set()
        collected_total = 0
        for artifact in self.artifacts:
            if not isinstance(artifact, OutputArtifact):
                raise ResultContractError("artifacts must contain OutputArtifact values")
            artifact.validate_shape(policy)
            if artifact.name in seen_names:
                raise ResultContractError(f"duplicate artifact name: {artifact.name}")
            seen_names.add(artifact.name)
            if artifact.disposition is ArtifactDisposition.COLLECTED:
                collected_total += artifact.size_bytes
        if collected_total > policy.max_total_collected_bytes:
            raise ResultContractError("collected artifact total exceeds result policy")

        return _parse_utc(self.collected_at_utc, "collected_at_utc")

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "provider_job_id": self.provider_job_id,
            "plan_fingerprint": self.plan_fingerprint,
            "submission_receipt_fingerprint": self.submission_receipt_fingerprint,
            "final_observation_fingerprint": self.final_observation_fingerprint,
            "terminal_state": self.terminal_state.value,
            "collected_at_utc": self.collected_at_utc,
            "log_bytes_retained": self.log_bytes_retained,
            "logs_truncated": self.logs_truncated,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "schema_version": self.schema_version,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], policy: ResultPolicy) -> ResultManifest:
        if not isinstance(payload, Mapping):
            raise ResultContractError("result manifest must be an object")
        _require_exact_keys(payload, _MANIFEST_KEYS, "result manifest")
        schema_version = payload["schema_version"]
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
            raise ResultContractError("unsupported result manifest schema_version")
        try:
            terminal_state = JobState(payload["terminal_state"])
        except (TypeError, ValueError) as exc:
            raise ResultContractError("terminal_state is invalid") from exc
        raw_artifacts = payload["artifacts"]
        if not isinstance(raw_artifacts, list):
            raise ResultContractError("artifacts must be a JSON array")
        artifacts = tuple(OutputArtifact.from_dict(item, policy) for item in raw_artifacts)
        manifest = cls(
            provider=payload["provider"],  # type: ignore[arg-type]
            provider_job_id=payload["provider_job_id"],  # type: ignore[arg-type]
            plan_fingerprint=payload["plan_fingerprint"],  # type: ignore[arg-type]
            submission_receipt_fingerprint=payload["submission_receipt_fingerprint"],  # type: ignore[arg-type]
            final_observation_fingerprint=payload["final_observation_fingerprint"],  # type: ignore[arg-type]
            terminal_state=terminal_state,
            collected_at_utc=payload["collected_at_utc"],  # type: ignore[arg-type]
            log_bytes_retained=payload["log_bytes_retained"],  # type: ignore[arg-type]
            logs_truncated=payload["logs_truncated"],  # type: ignore[arg-type]
            artifacts=artifacts,
            schema_version=schema_version,
        )
        manifest.validate_shape(policy)
        return manifest

    @classmethod
    def from_json(cls, value: str, policy: ResultPolicy) -> ResultManifest:
        return cls.from_dict(_load_json_object(value, "result manifest"), policy)


def build_result_manifest(
    receipt: SubmissionReceipt,
    final_observation: JobObservation,
    *,
    artifacts: Sequence[OutputArtifact],
    log_bytes_retained: int,
    logs_truncated: bool,
    collected_at_utc: datetime,
    policy: ResultPolicy | None = None,
) -> ResultManifest:
    effective_policy = policy or load_result_policy()
    receipt.validate_shape()
    validate_observation(receipt, final_observation)
    final_observed_at = final_observation.validate_shape()
    if not final_observation.finalized:
        raise ResultContractError("result collection requires a finalized job observation")

    collected_at = _parse_utc(_format_utc(collected_at_utc, "collected_at_utc"), "collected_at_utc")
    if collected_at < final_observed_at:
        raise ResultContractError("result collection cannot predate the final observation")

    manifest = ResultManifest(
        provider=receipt.provider,
        provider_job_id=receipt.provider_job_id,
        plan_fingerprint=receipt.plan_fingerprint,
        submission_receipt_fingerprint=receipt.fingerprint(),
        final_observation_fingerprint=final_observation.fingerprint(),
        terminal_state=final_observation.state,
        collected_at_utc=_format_utc(collected_at, "collected_at_utc"),
        log_bytes_retained=log_bytes_retained,
        logs_truncated=logs_truncated,
        artifacts=tuple(artifacts),
    )
    manifest.validate_shape(effective_policy)
    return manifest


def validate_manifest_against_lifecycle(
    manifest: ResultManifest,
    receipt: SubmissionReceipt,
    final_observation: JobObservation,
    *,
    policy: ResultPolicy | None = None,
) -> None:
    effective_policy = policy or load_result_policy()
    manifest.validate_shape(effective_policy)
    receipt.validate_shape()
    validate_observation(receipt, final_observation)
    if not final_observation.finalized:
        raise ResultContractError("result manifest cannot bind to a non-finalized observation")

    expected = {
        "provider": (manifest.provider, receipt.provider),
        "provider_job_id": (manifest.provider_job_id, receipt.provider_job_id),
        "plan_fingerprint": (manifest.plan_fingerprint, receipt.plan_fingerprint),
        "submission_receipt_fingerprint": (
            manifest.submission_receipt_fingerprint,
            receipt.fingerprint(),
        ),
        "final_observation_fingerprint": (
            manifest.final_observation_fingerprint,
            final_observation.fingerprint(),
        ),
        "terminal_state": (manifest.terminal_state, final_observation.state),
    }
    for field, (actual, trusted) in expected.items():
        if actual != trusted:
            raise ResultContractError(f"result manifest {field} does not match lifecycle state")

    if _parse_utc(manifest.collected_at_utc, "collected_at_utc") < final_observation.validate_shape():
        raise ResultContractError("result collection cannot predate the final observation")
