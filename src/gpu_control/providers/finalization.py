from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from ..lifecycle import (
    CleanupState,
    JobObservation,
    JobState,
    LifecycleError,
    SubmissionReceipt,
    validate_observation,
    validate_observation_transition,
)
from ..results import (
    ArtifactDisposition,
    OutputArtifact,
    ResultContractError,
    ResultManifest,
    ResultPolicy,
    build_result_manifest,
    load_result_policy,
    validate_manifest_against_lifecycle,
)
from .base import ProviderAdapter, ProviderResultSnapshot
from .controller import ProviderContractError


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROVIDER_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_CAPTURE_KEYS = {
    "provider",
    "provider_job_id",
    "plan_fingerprint",
    "submission_receipt_fingerprint",
    "terminal_observation_fingerprint",
    "terminal_state",
    "captured_at_utc",
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


def _format_utc(value: datetime, field: str) -> str:
    if not isinstance(value, datetime):
        raise ProviderContractError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ProviderContractError(f"{field} must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ResultContractError(f"{field} must be a non-empty trimmed timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ResultContractError(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ResultContractError(f"{field} must be timezone-aware UTC")
    return parsed


def _require_text(value: object, field: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResultContractError(f"{field} is required")
    if value != value.strip():
        raise ResultContractError(f"{field} must not contain surrounding whitespace")
    if len(value) > max_length:
        raise ResultContractError(f"{field} exceeds maximum length {max_length}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ResultContractError(f"{field} must not contain control characters")
    return value


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
    except (json.JSONDecodeError, TypeError, ValueError, RecursionError) as exc:
        raise ResultContractError(f"{label} must be valid bounded JSON") from exc
    if not isinstance(payload, dict):
        raise ResultContractError(f"{label} must be a JSON object")
    return payload


def _validate_result_payload(
    *,
    artifacts: tuple[OutputArtifact, ...],
    log_bytes_retained: int,
    logs_truncated: bool,
    policy: ResultPolicy,
) -> None:
    policy.validate_shape()
    if (
        isinstance(log_bytes_retained, bool)
        or not isinstance(log_bytes_retained, int)
        or log_bytes_retained < 0
    ):
        raise ResultContractError("captured log_bytes_retained must be a non-negative integer")
    if log_bytes_retained > policy.max_log_bytes:
        raise ResultContractError("captured retained logs exceed result policy")
    if not isinstance(logs_truncated, bool):
        raise ResultContractError("captured logs_truncated must be a boolean")
    if not isinstance(artifacts, tuple):
        raise ResultContractError("captured artifacts must be a tuple")
    if len(artifacts) > policy.max_artifact_entries:
        raise ResultContractError("captured artifact count exceeds result policy")

    seen_names: set[str] = set()
    collected_total = 0
    for artifact in artifacts:
        if not isinstance(artifact, OutputArtifact):
            raise ResultContractError("captured artifacts must contain OutputArtifact values")
        artifact.validate_shape(policy)
        if artifact.name in seen_names:
            raise ResultContractError(f"duplicate captured artifact name: {artifact.name}")
        seen_names.add(artifact.name)
        if artifact.disposition is ArtifactDisposition.COLLECTED:
            collected_total += artifact.size_bytes
    if collected_total > policy.max_total_collected_bytes:
        raise ResultContractError("captured collected artifact total exceeds result policy")


def _adapter_provider(adapter: ProviderAdapter) -> str:
    try:
        provider = adapter.provider_name
    except Exception as exc:
        raise ProviderContractError("provider adapter must expose provider_name") from exc
    if not isinstance(provider, str) or not _PROVIDER_RE.fullmatch(provider):
        raise ProviderContractError("provider adapter name must be a canonical lowercase identifier")
    return provider


def _require_provider_match(adapter: ProviderAdapter, provider: str) -> None:
    adapter_provider = _adapter_provider(adapter)
    if adapter_provider != provider:
        raise ProviderContractError(
            f"provider adapter {adapter_provider!r} does not match lifecycle provider {provider!r}"
        )


def _require_job_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderContractError("provider_job_id is required")
    if value != value.strip():
        raise ProviderContractError("provider_job_id must not contain surrounding whitespace")
    if len(value) > 512:
        raise ProviderContractError("provider_job_id exceeds maximum length 512")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProviderContractError("provider_job_id must not contain control characters")
    return value


@dataclass(frozen=True)
class ProviderResultCapture:
    """Durable bounded result metadata captured before destructive cleanup."""

    provider: str
    provider_job_id: str
    plan_fingerprint: str
    submission_receipt_fingerprint: str
    terminal_observation_fingerprint: str
    terminal_state: JobState
    captured_at_utc: str
    log_bytes_retained: int
    logs_truncated: bool
    artifacts: tuple[OutputArtifact, ...]
    schema_version: int = 1

    def validate_shape(self, policy: ResultPolicy | None = None) -> datetime:
        effective_policy = policy or load_result_policy()
        effective_policy.validate_shape()
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int) or self.schema_version != 1:
            raise ResultContractError("unsupported provider result capture schema_version")
        provider = _require_text(self.provider, "capture provider", max_length=64)
        if not _PROVIDER_RE.fullmatch(provider):
            raise ResultContractError("capture provider must be a canonical lowercase identifier")
        _require_text(self.provider_job_id, "capture provider_job_id", max_length=512)
        for field, value in (
            ("plan_fingerprint", self.plan_fingerprint),
            ("submission_receipt_fingerprint", self.submission_receipt_fingerprint),
            ("terminal_observation_fingerprint", self.terminal_observation_fingerprint),
        ):
            if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
                raise ResultContractError(f"capture {field} must be a lowercase sha256 fingerprint")
        if not isinstance(self.terminal_state, JobState) or self.terminal_state not in _TERMINAL_STATES:
            raise ResultContractError("capture terminal_state must be a terminal JobState")
        _validate_result_payload(
            artifacts=self.artifacts,
            log_bytes_retained=self.log_bytes_retained,
            logs_truncated=self.logs_truncated,
            policy=effective_policy,
        )
        return _parse_utc(self.captured_at_utc, "captured_at_utc")

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "provider_job_id": self.provider_job_id,
            "plan_fingerprint": self.plan_fingerprint,
            "submission_receipt_fingerprint": self.submission_receipt_fingerprint,
            "terminal_observation_fingerprint": self.terminal_observation_fingerprint,
            "terminal_state": self.terminal_state.value,
            "captured_at_utc": self.captured_at_utc,
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
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        policy: ResultPolicy | None = None,
    ) -> ProviderResultCapture:
        if not isinstance(payload, Mapping):
            raise ResultContractError("provider result capture must be an object")
        _require_exact_keys(payload, _CAPTURE_KEYS, "provider result capture")
        schema_version = payload["schema_version"]
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
            raise ResultContractError("unsupported provider result capture schema_version")
        try:
            terminal_state = JobState(payload["terminal_state"])
        except (TypeError, ValueError) as exc:
            raise ResultContractError("provider result capture terminal_state is invalid") from exc
        raw_artifacts = payload["artifacts"]
        if not isinstance(raw_artifacts, list):
            raise ResultContractError("provider result capture artifacts must be a JSON array")
        effective_policy = policy or load_result_policy()
        artifacts = tuple(OutputArtifact.from_dict(item, effective_policy) for item in raw_artifacts)
        capture = cls(
            provider=payload["provider"],  # type: ignore[arg-type]
            provider_job_id=payload["provider_job_id"],  # type: ignore[arg-type]
            plan_fingerprint=payload["plan_fingerprint"],  # type: ignore[arg-type]
            submission_receipt_fingerprint=payload["submission_receipt_fingerprint"],  # type: ignore[arg-type]
            terminal_observation_fingerprint=payload["terminal_observation_fingerprint"],  # type: ignore[arg-type]
            terminal_state=terminal_state,
            captured_at_utc=payload["captured_at_utc"],  # type: ignore[arg-type]
            log_bytes_retained=payload["log_bytes_retained"],  # type: ignore[arg-type]
            logs_truncated=payload["logs_truncated"],  # type: ignore[arg-type]
            artifacts=artifacts,
            schema_version=schema_version,
        )
        capture.validate_shape(effective_policy)
        return capture

    @classmethod
    def from_json(
        cls,
        value: str,
        policy: ResultPolicy | None = None,
    ) -> ProviderResultCapture:
        return cls.from_dict(_load_json_object(value, "provider result capture"), policy)


@dataclass(frozen=True)
class FinalizedCapturedResults:
    """One pre-cleanup capture bound to cleanup-finalized lifecycle state."""

    capture: ProviderResultCapture
    final_observation: JobObservation
    result_manifest: ResultManifest


def validate_result_capture_against_lifecycle(
    capture: ProviderResultCapture,
    receipt: SubmissionReceipt,
    terminal_observation: JobObservation,
    *,
    policy: ResultPolicy | None = None,
) -> None:
    effective_policy = policy or load_result_policy()
    captured_at = capture.validate_shape(effective_policy)
    try:
        receipt.validate_shape()
        validate_observation(receipt, terminal_observation)
        terminal_at = terminal_observation.validate_shape()
        if not terminal_observation.terminal:
            raise LifecycleError("pre-cleanup result capture requires a terminal observation")
        if terminal_observation.cleanup_state is not CleanupState.NOT_STARTED:
            raise LifecycleError("pre-cleanup result capture requires cleanup_state not_started")
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc

    expected = {
        "provider": (capture.provider, receipt.provider),
        "provider_job_id": (capture.provider_job_id, receipt.provider_job_id),
        "plan_fingerprint": (capture.plan_fingerprint, receipt.plan_fingerprint),
        "submission_receipt_fingerprint": (capture.submission_receipt_fingerprint, receipt.fingerprint()),
        "terminal_observation_fingerprint": (
            capture.terminal_observation_fingerprint,
            terminal_observation.fingerprint(),
        ),
        "terminal_state": (capture.terminal_state, terminal_observation.state),
    }
    for field, (actual, trusted) in expected.items():
        if actual != trusted:
            raise ProviderContractError(f"provider result capture {field} does not match lifecycle state")
    if captured_at < terminal_at:
        raise ProviderContractError("provider result capture cannot predate the terminal observation")


def capture_provider_results_before_cleanup(
    adapter: ProviderAdapter,
    receipt: SubmissionReceipt,
    terminal_observation: JobObservation,
    *,
    captured_at_utc: datetime,
    policy: ResultPolicy | None = None,
) -> ProviderResultCapture:
    """Capture bounded provider result metadata while terminal resources still exist."""

    _require_provider_match(adapter, receipt.provider)
    effective_policy = policy or load_result_policy()
    captured_at_text = _format_utc(captured_at_utc, "captured_at_utc")
    try:
        receipt.validate_shape()
        validate_observation(receipt, terminal_observation)
        terminal_at = terminal_observation.validate_shape()
        if not terminal_observation.terminal:
            raise LifecycleError("pre-cleanup result capture requires a terminal observation")
        if terminal_observation.cleanup_state is not CleanupState.NOT_STARTED:
            raise LifecycleError("pre-cleanup result capture requires cleanup_state not_started")
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc
    if _parse_utc(captured_at_text, "captured_at_utc") < terminal_at:
        raise ProviderContractError("provider result capture cannot predate the terminal observation")

    response = adapter.collect_results(receipt, terminal_observation)
    if not isinstance(response, ProviderResultSnapshot):
        raise ProviderContractError("provider collect_results must return ProviderResultSnapshot")
    provider_job_id = _require_job_id(response.provider_job_id)
    if provider_job_id != receipt.provider_job_id:
        raise ProviderContractError("provider result job id does not match submission receipt")
    if not isinstance(response.artifacts, tuple):
        raise ProviderContractError("provider result artifacts must be a tuple")

    capture = ProviderResultCapture(
        provider=receipt.provider,
        provider_job_id=receipt.provider_job_id,
        plan_fingerprint=receipt.plan_fingerprint,
        submission_receipt_fingerprint=receipt.fingerprint(),
        terminal_observation_fingerprint=terminal_observation.fingerprint(),
        terminal_state=terminal_observation.state,
        captured_at_utc=captured_at_text,
        log_bytes_retained=response.log_bytes_retained,
        logs_truncated=response.logs_truncated,
        artifacts=response.artifacts,
    )
    validate_result_capture_against_lifecycle(
        capture,
        receipt,
        terminal_observation,
        policy=effective_policy,
    )
    return capture


def finalize_captured_provider_results(
    capture: ProviderResultCapture,
    receipt: SubmissionReceipt,
    terminal_observation: JobObservation,
    final_observation: JobObservation,
    *,
    committed_at_utc: datetime,
    policy: ResultPolicy | None = None,
) -> FinalizedCapturedResults:
    """Bind a durable pre-cleanup capture to successful lifecycle finalization.

    ``committed_at_utc`` is the time the already-captured bounded result is committed
    into the legacy ResultManifest after cleanup. The actual provider snapshot time
    remains independently preserved as ``capture.captured_at_utc``.
    """

    effective_policy = policy or load_result_policy()
    validate_result_capture_against_lifecycle(
        capture,
        receipt,
        terminal_observation,
        policy=effective_policy,
    )
    try:
        validate_observation(receipt, final_observation)
        final_at = final_observation.validate_shape()
        validate_observation_transition(terminal_observation, final_observation)
        if not final_observation.finalized:
            raise LifecycleError("captured provider results require cleanup-finalized lifecycle state")
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc

    captured_at = capture.validate_shape(effective_policy)
    if final_at < captured_at:
        raise ProviderContractError("cleanup final observation cannot predate provider result capture")
    committed_at_text = _format_utc(committed_at_utc, "committed_at_utc")
    committed_at = _parse_utc(committed_at_text, "committed_at_utc")
    if committed_at < final_at:
        raise ProviderContractError("result manifest commit cannot predate the final observation")

    manifest = build_result_manifest(
        receipt,
        final_observation,
        artifacts=capture.artifacts,
        log_bytes_retained=capture.log_bytes_retained,
        logs_truncated=capture.logs_truncated,
        collected_at_utc=committed_at_utc,
        policy=effective_policy,
    )
    validate_manifest_against_lifecycle(
        manifest,
        receipt,
        final_observation,
        policy=effective_policy,
    )
    if manifest.artifacts != capture.artifacts:
        raise ProviderContractError("final result manifest artifacts do not match provider result capture")
    if manifest.log_bytes_retained != capture.log_bytes_retained or manifest.logs_truncated != capture.logs_truncated:
        raise ProviderContractError("final result manifest logs do not match provider result capture")

    return FinalizedCapturedResults(
        capture=capture,
        final_observation=final_observation,
        result_manifest=manifest,
    )
