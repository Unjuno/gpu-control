from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from ..completion import CompletionEvidenceError
from ..lifecycle import JobState
from ..providers.runpod_log_results import AuthenticatedRunPodLogResult, MAX_MARKER_BYTES, RESULT_MARKER


WORKLOAD_ID = "orbitune-runpod-training-canary-v1"
SELECTED_SOURCE_SHA = "38594057d1b118a7acf6c843e39d7d8a25571316"
ARCHITECTURE = "orbitune-midi-gpt-v0"
TOKENIZER = "theory-remi-v0"
PARAMETERS = 10_200_960
STEPS = 250
BATCH_SIZE = 8
SEQUENCE_LENGTH = 256
TOKENS_PROCESSED = 512_000
VALIDATION_STEPS = (50, 100, 150, 200, 250)
MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class WorkloadAcceptanceError(ValueError):
    """Raised when authenticated workload output fails the trusted canary contract."""


@dataclass(frozen=True)
class OrbituneCanaryResultAcceptance:
    """Trusted result-side acceptance evidence for the selected Orbitune canary.

    This value certifies only the authenticated workload result contract. It does
    not certify provider cleanup, cost, pricing freshness, image publication, or
    final lifecycle completion. Those remain independent control-plane gates.

    The completion execution identity and exact result digest are retained so a
    future provider-finalization layer can bind this result to one concrete run,
    even when the same approved plan is submitted more than once.
    """

    source_sha: str
    plan_fingerprint: str
    image_digest: str
    execution_name: str
    completion_nonce: str
    result_sha256: str
    workload_id: str
    architecture: str
    tokenizer: str
    parameters: int
    tokens_processed: int
    gpu_name: str
    cuda_version: str
    validation_first_loss: float
    validation_last_loss: float
    checkpoint_sha256: str
    checkpoint_bytes: int
    schema_version: int = 1


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkloadAcceptanceError(f"{label} must be an authenticated object")
    return value


def _require_sequence(value: object, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise WorkloadAcceptanceError(f"{label} must be an authenticated sequence")
    return value


def _require_finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorkloadAcceptanceError(f"{label} must be finite")
    try:
        parsed = float(value)
    except (OverflowError, ValueError) as exc:
        raise WorkloadAcceptanceError(f"{label} must be finite") from exc
    if not math.isfinite(parsed):
        raise WorkloadAcceptanceError(f"{label} must be finite")
    return parsed


def _require_exact_int(value: object, expected: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != expected:
        raise WorkloadAcceptanceError(f"Orbitune canary {label} mismatch")
    return value


def _require_selected_source_sha(value: object) -> str:
    if not isinstance(value, str) or not _SOURCE_SHA_RE.fullmatch(value):
        raise WorkloadAcceptanceError("trusted expected_source_sha is invalid")
    if value != SELECTED_SOURCE_SHA:
        raise WorkloadAcceptanceError("trusted expected_source_sha is not the selected Orbitune canary source")
    return value


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise WorkloadAcceptanceError(f"trusted {label} is invalid")
    return value


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain_json(item) for item in value]
    return value


def _strict_result_object(raw: bytes) -> dict[str, Any]:
    # The provider boundary limits the complete ASCII marker, not merely decoded
    # JSON bytes. Mirror that exact length contract without allocating a base64 copy.
    encoded_payload_bytes = 4 * ((len(raw) + 2) // 3)
    if len(RESULT_MARKER) + encoded_payload_bytes > MAX_MARKER_BYTES:
        raise WorkloadAcceptanceError("Orbitune authenticated result bytes exceed the bounded marker contract")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise WorkloadAcceptanceError(f"Orbitune authenticated result bytes contain duplicate field: {key}")
            value[key] = item
        return value

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except WorkloadAcceptanceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise WorkloadAcceptanceError("Orbitune authenticated result bytes are not valid bounded UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise WorkloadAcceptanceError("Orbitune authenticated result bytes must contain a JSON object")
    return payload


def validate_orbitune_canary_result(
    authenticated: AuthenticatedRunPodLogResult,
    *,
    expected_source_sha: str,
    expected_plan_fingerprint: str,
    expected_image_digest: str,
) -> OrbituneCanaryResultAcceptance:
    """Apply frozen paid-canary criteria to one authenticated workload result.

    ``authenticated`` must come from the completion-verifying provider boundary.
    The caller additionally supplies the current trusted source, approved-plan
    fingerprint, and approved immutable image digest. Provider cleanup remains a
    separate finalization gate and is intentionally not certified here.
    """

    if not isinstance(authenticated, AuthenticatedRunPodLogResult):
        raise WorkloadAcceptanceError("authenticated RunPod result is required")
    trusted_source_sha = _require_selected_source_sha(expected_source_sha)
    trusted_plan_fingerprint = _require_sha256(expected_plan_fingerprint, "expected_plan_fingerprint")
    trusted_image_digest = _require_sha256(expected_image_digest, "expected_image_digest")

    if authenticated.state is not JobState.SUCCEEDED or authenticated.process_exit_code != 0:
        raise WorkloadAcceptanceError("Orbitune canary result requires authenticated process success")
    if not isinstance(authenticated.result_bytes, bytes):
        raise WorkloadAcceptanceError("Orbitune canary authenticated result bytes are invalid")

    reparsed_payload = _strict_result_object(authenticated.result_bytes)
    if _plain_json(authenticated.result_payload) != reparsed_payload:
        raise WorkloadAcceptanceError("Orbitune authenticated result payload does not match exact result bytes")

    evidence = authenticated.completion_evidence
    try:
        evidence.validate_shape()
    except CompletionEvidenceError as exc:
        raise WorkloadAcceptanceError(str(exc)) from exc
    if evidence.source_sha != trusted_source_sha:
        raise WorkloadAcceptanceError("Orbitune completion source_sha mismatch")
    if evidence.plan_fingerprint != trusted_plan_fingerprint:
        raise WorkloadAcceptanceError("Orbitune completion plan_fingerprint mismatch")
    if evidence.image_digest != trusted_image_digest:
        raise WorkloadAcceptanceError("Orbitune completion image_digest mismatch")
    observed_result_sha256 = "sha256:" + hashlib.sha256(authenticated.result_bytes).hexdigest()
    if evidence.result_sha256 != observed_result_sha256:
        raise WorkloadAcceptanceError("Orbitune completion result_sha256 does not match authenticated result bytes")

    payload = _require_mapping(authenticated.result_payload, "result_payload")
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
        raise WorkloadAcceptanceError("Orbitune canary result schema_version must be integer 1")
    if payload.get("workload_id") != WORKLOAD_ID:
        raise WorkloadAcceptanceError("Orbitune canary workload_id mismatch")
    if payload.get("source_sha") != trusted_source_sha:
        raise WorkloadAcceptanceError("Orbitune canary source_sha mismatch")
    if payload.get("status") != "pass":
        raise WorkloadAcceptanceError("Orbitune canary result status must be pass")
    if payload.get("architecture") != ARCHITECTURE:
        raise WorkloadAcceptanceError("Orbitune canary architecture mismatch")
    if payload.get("tokenizer") != TOKENIZER:
        raise WorkloadAcceptanceError("Orbitune canary tokenizer mismatch")
    _require_exact_int(payload.get("parameters"), PARAMETERS, "parameter count")
    _require_exact_int(payload.get("steps"), STEPS, "step count")
    _require_exact_int(payload.get("batch_size"), BATCH_SIZE, "batch size")
    _require_exact_int(payload.get("seq_len"), SEQUENCE_LENGTH, "sequence length")
    _require_exact_int(payload.get("tokens_processed"), TOKENS_PROCESSED, "token count")
    if payload.get("device_type") != "cuda" or payload.get("cuda_available") is not True:
        raise WorkloadAcceptanceError("Orbitune paid canary requires CUDA execution")

    gpu_name = payload.get("gpu_name")
    if not isinstance(gpu_name, str) or not gpu_name.strip() or gpu_name != gpu_name.strip():
        raise WorkloadAcceptanceError("Orbitune paid canary requires a concrete GPU name")
    cuda_version = payload.get("cuda_version")
    if not isinstance(cuda_version, str) or not cuda_version.strip() or cuda_version != cuda_version.strip():
        raise WorkloadAcceptanceError("Orbitune paid canary requires a CUDA runtime version")
    peak_vram_bytes = payload.get("peak_vram_bytes")
    if isinstance(peak_vram_bytes, bool) or not isinstance(peak_vram_bytes, int) or peak_vram_bytes <= 0:
        raise WorkloadAcceptanceError("Orbitune paid canary requires positive CUDA peak VRAM evidence")

    validation_history = _require_sequence(payload.get("validation_history"), "validation_history")
    if len(validation_history) != len(VALIDATION_STEPS):
        raise WorkloadAcceptanceError("Orbitune canary validation point count mismatch")
    validation_losses: list[float] = []
    observed_steps: list[int] = []
    for item in validation_history:
        point = _require_mapping(item, "validation_history entry")
        step = point.get("step")
        if isinstance(step, bool) or not isinstance(step, int):
            raise WorkloadAcceptanceError("Orbitune validation step must be an integer")
        observed_steps.append(step)
        validation_losses.append(_require_finite(point.get("loss"), "Orbitune validation loss"))
    if tuple(observed_steps) != VALIDATION_STEPS:
        raise WorkloadAcceptanceError("Orbitune canary validation schedule mismatch")
    if not validation_losses[-1] < validation_losses[0]:
        raise WorkloadAcceptanceError("Orbitune canary validation loss did not improve")

    artifacts = _require_sequence(payload.get("artifacts"), "artifacts")
    if len(artifacts) != 1:
        raise WorkloadAcceptanceError("Orbitune canary requires exactly one checkpoint metadata entry")
    artifact = _require_mapping(artifacts[0], "checkpoint metadata")
    if artifact.get("name") != "canary-base.pt":
        raise WorkloadAcceptanceError("Orbitune canary checkpoint name mismatch")
    checkpoint_bytes = artifact.get("bytes")
    if (
        isinstance(checkpoint_bytes, bool)
        or not isinstance(checkpoint_bytes, int)
        or not 0 < checkpoint_bytes <= MAX_CHECKPOINT_BYTES
    ):
        raise WorkloadAcceptanceError("Orbitune canary checkpoint size is outside the accepted bound")
    checkpoint_sha256 = artifact.get("sha256")
    if not isinstance(checkpoint_sha256, str) or not _SHA256_RE.fullmatch(checkpoint_sha256):
        raise WorkloadAcceptanceError("Orbitune canary checkpoint digest is invalid")
    if artifact.get("media_type") != "application/x-pytorch-checkpoint":
        raise WorkloadAcceptanceError("Orbitune canary checkpoint media type mismatch")
    if artifact.get("transport") != "container-local-only":
        raise WorkloadAcceptanceError("Orbitune canary checkpoint transport boundary mismatch")

    return OrbituneCanaryResultAcceptance(
        source_sha=trusted_source_sha,
        plan_fingerprint=trusted_plan_fingerprint,
        image_digest=trusted_image_digest,
        execution_name=evidence.execution_name,
        completion_nonce=evidence.nonce,
        result_sha256=evidence.result_sha256,
        workload_id=WORKLOAD_ID,
        architecture=ARCHITECTURE,
        tokenizer=TOKENIZER,
        parameters=PARAMETERS,
        tokens_processed=TOKENS_PROCESSED,
        gpu_name=gpu_name,
        cuda_version=cuda_version,
        validation_first_loss=validation_losses[0],
        validation_last_loss=validation_losses[-1],
        checkpoint_sha256=checkpoint_sha256,
        checkpoint_bytes=checkpoint_bytes,
    )
