from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping, Sequence

from ..lifecycle import JobState
from ..providers.runpod_log_results import AuthenticatedRunPodLogResult


WORKLOAD_ID = "orbitune-runpod-training-canary-v1"
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
    """

    source_sha: str
    image_digest: str
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
    parsed = float(value)
    if not math.isfinite(parsed):
        raise WorkloadAcceptanceError(f"{label} must be finite")
    return parsed


def _require_expected_source_sha(value: object) -> str:
    if not isinstance(value, str) or not _SOURCE_SHA_RE.fullmatch(value):
        raise WorkloadAcceptanceError("trusted expected_source_sha is invalid")
    return value


def validate_orbitune_canary_result(
    authenticated: AuthenticatedRunPodLogResult,
    *,
    expected_source_sha: str,
) -> OrbituneCanaryResultAcceptance:
    """Apply the frozen Orbitune paid-canary result criteria to authenticated bytes.

    The caller must still finalize provider cleanup separately before treating the
    overall paid canary as accepted.
    """

    if not isinstance(authenticated, AuthenticatedRunPodLogResult):
        raise WorkloadAcceptanceError("authenticated RunPod result is required")
    trusted_source_sha = _require_expected_source_sha(expected_source_sha)
    if authenticated.state is not JobState.SUCCEEDED or authenticated.process_exit_code != 0:
        raise WorkloadAcceptanceError("Orbitune canary result requires authenticated process success")

    payload = _require_mapping(authenticated.result_payload, "result_payload")
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        raise WorkloadAcceptanceError("Orbitune canary result schema_version must be integer 1")
    if payload.get("workload_id") != WORKLOAD_ID:
        raise WorkloadAcceptanceError("Orbitune canary workload_id mismatch")
    if payload.get("source_sha") != trusted_source_sha:
        raise WorkloadAcceptanceError("Orbitune canary source_sha mismatch")
    if authenticated.completion_evidence.source_sha != trusted_source_sha:
        raise WorkloadAcceptanceError("Orbitune completion source_sha mismatch")
    if payload.get("status") != "pass":
        raise WorkloadAcceptanceError("Orbitune canary result status must be pass")
    if payload.get("architecture") != ARCHITECTURE:
        raise WorkloadAcceptanceError("Orbitune canary architecture mismatch")
    if payload.get("tokenizer") != TOKENIZER:
        raise WorkloadAcceptanceError("Orbitune canary tokenizer mismatch")
    if payload.get("parameters") != PARAMETERS:
        raise WorkloadAcceptanceError("Orbitune canary parameter count mismatch")
    if payload.get("steps") != STEPS:
        raise WorkloadAcceptanceError("Orbitune canary step count mismatch")
    if payload.get("batch_size") != BATCH_SIZE:
        raise WorkloadAcceptanceError("Orbitune canary batch size mismatch")
    if payload.get("seq_len") != SEQUENCE_LENGTH:
        raise WorkloadAcceptanceError("Orbitune canary sequence length mismatch")
    if payload.get("tokens_processed") != TOKENS_PROCESSED:
        raise WorkloadAcceptanceError("Orbitune canary token count mismatch")
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

    image_digest = authenticated.completion_evidence.image_digest
    if not _SHA256_RE.fullmatch(image_digest):
        raise WorkloadAcceptanceError("Orbitune completion image digest is invalid")

    return OrbituneCanaryResultAcceptance(
        source_sha=trusted_source_sha,
        image_digest=image_digest,
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
