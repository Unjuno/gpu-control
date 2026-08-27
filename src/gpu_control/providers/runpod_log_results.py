from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from ..completion import CompletionChallenge, CompletionEvidence, CompletionEvidenceError, verify_completion
from ..lifecycle import JobState
from .runpod_v2 import RunPodV2Error


RESULT_MARKER = "GPU_CONTROL_RESULT_JSON_V1:"
COMPLETION_MARKER = "GPU_CONTROL_COMPLETION_JSON_V2:"
MAX_MARKER_BYTES = 16 * 1024
MAX_SCAN_LINES = 5000
MAX_SCAN_BYTES = 512 * 1024

_TRAINING_RESULT_KEYS = frozenset(
    {
        "schema_version",
        "workload_id",
        "source_sha",
        "status",
        "purpose",
        "architecture",
        "tokenizer",
        "parameters",
        "device_type",
        "cuda_available",
        "gpu_name",
        "torch_version",
        "cuda_version",
        "steps",
        "batch_size",
        "seq_len",
        "tokens_processed",
        "elapsed_seconds",
        "tokens_per_second",
        "first_training_loss",
        "final_training_loss",
        "validation_history",
        "peak_vram_bytes",
        "artifacts",
    }
)
_WRAPPER_FAILURE_KEYS = frozenset(
    {
        "schema_version",
        "workload_id",
        "source_sha",
        "status",
        "failure_kind",
        "runner_exit_code",
    }
)
_VALIDATION_POINT_KEYS = frozenset({"step", "loss"})
_ARTIFACT_KEYS = frozenset({"name", "bytes", "sha256", "media_type", "transport"})
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_WORKLOAD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")


@dataclass(frozen=True)
class AuthenticatedRunPodLogResult:
    """Exact result/completion bytes authenticated from one Pod's container logs.

    ``result_payload`` is recursively immutable. Authentication establishes that
    the exact result bytes were signed by the workload-side completion signer; it
    does not by itself establish that every scientific acceptance criterion passed.
    """

    state: JobState
    process_exit_code: int
    result_bytes: bytes
    completion_bytes: bytes
    result_payload: Mapping[str, Any]
    completion_evidence: CompletionEvidence


def _select_markers(lines: Iterable[str]) -> tuple[str, str]:
    """Scan a bounded log iterable once while retaining only marker candidates."""

    result_line: str | None = None
    completion_line: str | None = None
    scanned_lines = 0
    scanned_bytes = 0

    for line in lines:
        if not isinstance(line, str):
            raise RunPodV2Error("RunPod container log line must be a string")
        scanned_lines += 1
        if scanned_lines > MAX_SCAN_LINES:
            raise RunPodV2Error("RunPod container log scan exceeded bounded line count")

        remaining_bytes = MAX_SCAN_BYTES - scanned_bytes
        # UTF-8 uses at least one byte per Unicode code point. Reject an obviously
        # oversized provider line before materializing an encoded copy.
        if len(line) > remaining_bytes:
            raise RunPodV2Error("RunPod container log scan exceeded bounded byte count")
        try:
            encoded_line = line.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise RunPodV2Error("RunPod container log line is not valid UTF-8 text") from exc
        if len(encoded_line) > remaining_bytes:
            raise RunPodV2Error("RunPod container log scan exceeded bounded byte count")
        scanned_bytes += len(encoded_line)

        if line.startswith(RESULT_MARKER):
            if result_line is not None:
                raise RunPodV2Error(f"expected exactly one {RESULT_MARKER[:-1]} log marker")
            result_line = line
        elif line.startswith(COMPLETION_MARKER):
            if completion_line is not None:
                raise RunPodV2Error(f"expected exactly one {COMPLETION_MARKER[:-1]} log marker")
            completion_line = line

    if result_line is None:
        raise RunPodV2Error(f"expected exactly one {RESULT_MARKER[:-1]} log marker")
    if completion_line is None:
        raise RunPodV2Error(f"expected exactly one {COMPLETION_MARKER[:-1]} log marker")
    return result_line, completion_line


def _decode_marker(line: str, marker: str) -> bytes:
    if not line.startswith(marker):
        raise RunPodV2Error(f"expected {marker[:-1]} log marker")
    try:
        line_bytes = line.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RunPodV2Error(f"{marker[:-1]} log marker must be ASCII") from exc
    if len(line_bytes) > MAX_MARKER_BYTES:
        raise RunPodV2Error(f"{marker[:-1]} log marker exceeds bounded encoded size")

    encoded = line[len(marker):]
    if not encoded:
        raise RunPodV2Error(f"{marker[:-1]} log marker payload is empty")
    if not _BASE64URL_RE.fullmatch(encoded):
        raise RunPodV2Error(f"{marker[:-1]} log marker is not valid base64url")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), altchars=b"-_", validate=True)
    except Exception as exc:
        raise RunPodV2Error(f"{marker[:-1]} log marker is not valid base64url") from exc
    if base64.urlsafe_b64encode(raw).decode("ascii") != encoded:
        raise RunPodV2Error(f"{marker[:-1]} log marker is not valid base64url")
    return raw


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise RunPodV2Error(f"{label} marker contains duplicate field: {key}")
            value[key] = item
        return value

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except RunPodV2Error:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise RunPodV2Error(f"{label} marker is not valid bounded UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise RunPodV2Error(f"{label} marker must contain a JSON object")
    return payload


def _validated_process_exit_code(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RunPodV2Error("trusted process_exit_code must be an integer")
    if not 0 <= value <= 255:
        raise RunPodV2Error("trusted process_exit_code must be between 0 and 255")
    return value


def _validated_expected_workload_id(value: object) -> str:
    if not isinstance(value, str) or not _WORKLOAD_ID_RE.fullmatch(value):
        raise RunPodV2Error("trusted expected_workload_id is invalid")
    return value


def _require_actual_int(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RunPodV2Error(f"authenticated result {label} must be an integer >= {minimum}")
    return value


def _require_finite_number(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunPodV2Error(f"authenticated result {label} must be a finite number")
    try:
        parsed = float(value)
    except (OverflowError, ValueError) as exc:
        raise RunPodV2Error(f"authenticated result {label} must be a finite number") from exc
    if not math.isfinite(parsed) or (positive and parsed <= 0):
        qualifier = "positive finite" if positive else "finite"
        raise RunPodV2Error(f"authenticated result {label} must be a {qualifier} number")
    return parsed


def _require_trimmed_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise RunPodV2Error(f"authenticated result {label} must be a non-empty trimmed string")
    return value


def _validate_common_result_identity(
    payload: Mapping[str, Any],
    *,
    challenge: CompletionChallenge,
    expected_workload_id: str,
) -> str:
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
        raise RunPodV2Error("authenticated result schema_version must be integer 1")
    if payload.get("workload_id") != expected_workload_id:
        raise RunPodV2Error("authenticated result workload_id does not match trusted expected workload")
    if payload.get("source_sha") != challenge.source_sha:
        raise RunPodV2Error("authenticated result source_sha does not match completion challenge")
    status = payload.get("status")
    if not isinstance(status, str) or status not in {"pass", "fail"}:
        raise RunPodV2Error("authenticated result status must be pass or fail")
    return status


def _validate_validation_history(value: object, *, steps: int) -> None:
    if not isinstance(value, list) or not value:
        raise RunPodV2Error("authenticated result validation_history must be a non-empty array")
    previous_step = 0
    for item in value:
        if not isinstance(item, Mapping) or set(item) != _VALIDATION_POINT_KEYS:
            raise RunPodV2Error("authenticated result validation_history entry fields are invalid")
        step = _require_actual_int(item.get("step"), "validation_history.step", minimum=1)
        _require_finite_number(item.get("loss"), "validation_history.loss")
        if step <= previous_step or step > steps:
            raise RunPodV2Error("authenticated result validation_history steps are not strictly increasing within training")
        previous_step = step
    if previous_step != steps:
        raise RunPodV2Error("authenticated result validation_history must end at the final training step")


def _validate_artifacts(value: object) -> None:
    if not isinstance(value, list) or len(value) != 1:
        raise RunPodV2Error("authenticated result artifacts must contain exactly one checkpoint metadata entry")
    artifact = value[0]
    if not isinstance(artifact, Mapping) or set(artifact) != _ARTIFACT_KEYS:
        raise RunPodV2Error("authenticated result checkpoint metadata fields are invalid")
    if artifact.get("name") != "canary-base.pt":
        raise RunPodV2Error("authenticated result checkpoint name is invalid")
    _require_actual_int(artifact.get("bytes"), "artifacts.bytes", minimum=1)
    digest = artifact.get("sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise RunPodV2Error("authenticated result checkpoint sha256 is invalid")
    if artifact.get("media_type") != "application/x-pytorch-checkpoint":
        raise RunPodV2Error("authenticated result checkpoint media_type is invalid")
    if artifact.get("transport") != "container-local-only":
        raise RunPodV2Error("authenticated result checkpoint transport must remain container-local-only")


def _validate_training_result(payload: Mapping[str, Any]) -> None:
    if set(payload) != _TRAINING_RESULT_KEYS:
        raise RunPodV2Error("authenticated training result fields do not match Orbitune result schema v1")

    _require_trimmed_string(payload.get("purpose"), "purpose")
    _require_trimmed_string(payload.get("architecture"), "architecture")
    _require_trimmed_string(payload.get("tokenizer"), "tokenizer")
    _require_trimmed_string(payload.get("torch_version"), "torch_version")

    _require_actual_int(payload.get("parameters"), "parameters", minimum=1)
    steps = _require_actual_int(payload.get("steps"), "steps", minimum=1)
    batch_size = _require_actual_int(payload.get("batch_size"), "batch_size", minimum=1)
    seq_len = _require_actual_int(payload.get("seq_len"), "seq_len", minimum=2)
    tokens_processed = _require_actual_int(payload.get("tokens_processed"), "tokens_processed", minimum=1)
    if tokens_processed != steps * batch_size * seq_len:
        raise RunPodV2Error("authenticated result tokens_processed does not match steps * batch_size * seq_len")
    _require_actual_int(payload.get("peak_vram_bytes"), "peak_vram_bytes", minimum=0)

    if not isinstance(payload.get("cuda_available"), bool):
        raise RunPodV2Error("authenticated result cuda_available must be a boolean")
    device_type = payload.get("device_type")
    if not isinstance(device_type, str) or device_type not in {"cpu", "cuda"}:
        raise RunPodV2Error("authenticated result device_type must be cpu or cuda")
    gpu_name = payload.get("gpu_name")
    if gpu_name is not None:
        _require_trimmed_string(gpu_name, "gpu_name")
    cuda_version = payload.get("cuda_version")
    if cuda_version is not None:
        _require_trimmed_string(cuda_version, "cuda_version")
    if device_type == "cuda" and payload.get("cuda_available") is not True:
        raise RunPodV2Error("authenticated CUDA result requires cuda_available true")
    if device_type == "cuda" and gpu_name is None:
        raise RunPodV2Error("authenticated CUDA result requires gpu_name")

    _require_finite_number(payload.get("elapsed_seconds"), "elapsed_seconds", positive=True)
    throughput = _require_finite_number(payload.get("tokens_per_second"), "tokens_per_second")
    if throughput < 0:
        raise RunPodV2Error("authenticated result tokens_per_second must be non-negative")
    _require_finite_number(payload.get("first_training_loss"), "first_training_loss")
    _require_finite_number(payload.get("final_training_loss"), "final_training_loss")
    _validate_validation_history(payload.get("validation_history"), steps=steps)
    _validate_artifacts(payload.get("artifacts"))


def _validate_wrapper_failure_result(payload: Mapping[str, Any]) -> None:
    if set(payload) != _WRAPPER_FAILURE_KEYS:
        raise RunPodV2Error("authenticated wrapper failure fields do not match Orbitune result schema v1")
    if payload.get("status") != "fail":
        raise RunPodV2Error("authenticated wrapper failure must have fail status")
    if payload.get("failure_kind") != "runner-exited-without-result":
        raise RunPodV2Error("authenticated wrapper failure_kind is invalid")
    runner_exit_code = payload.get("runner_exit_code")
    if isinstance(runner_exit_code, bool) or not isinstance(runner_exit_code, int) or not -255 <= runner_exit_code <= 255:
        raise RunPodV2Error("authenticated wrapper runner_exit_code must be an integer between -255 and 255")


def _validate_result_schema(payload: Mapping[str, Any]) -> None:
    keys = set(payload)
    if keys == _TRAINING_RESULT_KEYS:
        _validate_training_result(payload)
        return
    if keys == _WRAPPER_FAILURE_KEYS:
        _validate_wrapper_failure_result(payload)
        return
    raise RunPodV2Error("authenticated result fields do not match a supported Orbitune result schema v1 variant")


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def authenticate_runpod_log_result(
    lines: Iterable[str],
    *,
    challenge: CompletionChallenge,
    secret_key: bytes,
    process_exit_code: int,
    expected_workload_id: str,
) -> AuthenticatedRunPodLogResult:
    """Authenticate one exact bounded Orbitune result/completion marker pair.

    This function performs no network or provider calls. The caller must supply
    complete bounded container-log lines from the exact provider execution,
    a trusted process exit code for that same execution, and the workload id from
    trusted control-plane state. An authenticated result marker alone can never
    establish successful execution.
    """

    challenge.validate_shape()
    trusted_exit_code = _validated_process_exit_code(process_exit_code)
    trusted_workload_id = _validated_expected_workload_id(expected_workload_id)
    result_line, completion_line = _select_markers(lines)
    result_bytes = _decode_marker(result_line, RESULT_MARKER)
    completion_bytes = _decode_marker(completion_line, COMPLETION_MARKER)
    result_payload = _json_object(result_bytes, "result")
    completion_payload = _json_object(completion_bytes, "completion")

    try:
        evidence = CompletionEvidence.from_dict(completion_payload)
        result_sha256 = "sha256:" + hashlib.sha256(result_bytes).hexdigest()
        verify_completion(
            challenge,
            evidence,
            secret_key=secret_key,
            expected_result_sha256=result_sha256,
        )
    except CompletionEvidenceError as exc:
        raise RunPodV2Error(str(exc)) from exc

    status = _validate_common_result_identity(
        result_payload,
        challenge=challenge,
        expected_workload_id=trusted_workload_id,
    )
    _validate_result_schema(result_payload)

    if status == "pass":
        if trusted_exit_code != 0:
            raise RunPodV2Error("authenticated pass result disagrees with nonzero process exit code")
        state = JobState.SUCCEEDED
    else:
        if trusted_exit_code == 0:
            raise RunPodV2Error("authenticated fail result disagrees with zero process exit code")
        state = JobState.FAILED

    frozen_payload = _freeze_json(result_payload)
    assert isinstance(frozen_payload, Mapping)
    return AuthenticatedRunPodLogResult(
        state=state,
        process_exit_code=trusted_exit_code,
        result_bytes=result_bytes,
        completion_bytes=completion_bytes,
        result_payload=frozen_payload,
        completion_evidence=evidence,
    )
