from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from types import MappingProxyType
from typing import Any

import pytest

from gpu_control.completion import CompletionEvidence, execution_name_for
from gpu_control.lifecycle import JobState
from gpu_control.providers.runpod_log_results import AuthenticatedRunPodLogResult, MAX_MARKER_BYTES
from gpu_control.workload_contracts.orbitune_canary import (
    MAX_CHECKPOINT_BYTES,
    SELECTED_SOURCE_SHA,
    WorkloadAcceptanceError,
    validate_orbitune_canary_result,
)


SOURCE = SELECTED_SOURCE_SHA
PLAN = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
NONCE = "a" * 64


def accepted_payload_dict(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "workload_id": "orbitune-runpod-training-canary-v1",
        "source_sha": SOURCE,
        "status": "pass",
        "purpose": "GPU/container/training/checkpoint infrastructure canary; not a musical-quality benchmark",
        "architecture": "orbitune-midi-gpt-v0",
        "tokenizer": "theory-remi-v0",
        "parameters": 10_200_960,
        "device_type": "cuda",
        "cuda_available": True,
        "gpu_name": "NVIDIA GeForce RTX 4090",
        "torch_version": "2.10.0",
        "cuda_version": "12.8",
        "steps": 250,
        "batch_size": 8,
        "seq_len": 256,
        "tokens_processed": 512_000,
        "elapsed_seconds": 20.0,
        "tokens_per_second": 25_600.0,
        "first_training_loss": 5.0,
        "final_training_loss": 2.0,
        "validation_history": [
            {"step": 50, "loss": 4.0},
            {"step": 100, "loss": 3.5},
            {"step": 150, "loss": 3.0},
            {"step": 200, "loss": 2.5},
            {"step": 250, "loss": 2.0},
        ],
        "peak_vram_bytes": 1_000_000,
        "artifacts": [
            {
                "name": "canary-base.pt",
                "bytes": 40_000_000,
                "sha256": "sha256:" + "5" * 64,
                "media_type": "application/x-pytorch-checkpoint",
                "transport": "container-local-only",
            }
        ],
    }
    payload.update(overrides)
    return payload


def result_bytes_for(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze_json(item) for item in value)
    return value


def completion_evidence(
    *,
    source_sha: str = SOURCE,
    plan_fingerprint: str = PLAN,
    image_digest: str = IMAGE,
    result_bytes: bytes | None = None,
) -> CompletionEvidence:
    bound_result_bytes = result_bytes if result_bytes is not None else result_bytes_for(accepted_payload_dict())
    return CompletionEvidence(
        key_id="paid-runpod-v2",
        nonce=NONCE,
        plan_fingerprint=plan_fingerprint,
        execution_name=execution_name_for(plan_fingerprint, NONCE),
        source_sha=source_sha,
        image_digest=image_digest,
        result_sha256="sha256:" + hashlib.sha256(bound_result_bytes).hexdigest(),
        mac_sha256="4" * 64,
    )


def authenticated_result(
    *,
    evidence: CompletionEvidence | None = None,
    result_bytes: bytes | None = None,
    **payload_overrides: object,
) -> AuthenticatedRunPodLogResult:
    plain_payload = accepted_payload_dict(**payload_overrides)
    bound_result_bytes = result_bytes if result_bytes is not None else result_bytes_for(plain_payload)
    frozen_payload = freeze_json(plain_payload)
    assert isinstance(frozen_payload, MappingProxyType)
    return AuthenticatedRunPodLogResult(
        state=JobState.SUCCEEDED,
        process_exit_code=0,
        result_bytes=bound_result_bytes,
        completion_bytes=b"authenticated-completion",
        result_payload=frozen_payload,
        completion_evidence=evidence or completion_evidence(result_bytes=bound_result_bytes),
    )


def accept(
    authenticated: AuthenticatedRunPodLogResult | None = None,
    *,
    expected_source_sha: str = SOURCE,
    expected_plan_fingerprint: str = PLAN,
    expected_image_digest: str = IMAGE,
):
    return validate_orbitune_canary_result(
        authenticated or authenticated_result(),
        expected_source_sha=expected_source_sha,
        expected_plan_fingerprint=expected_plan_fingerprint,
        expected_image_digest=expected_image_digest,
    )


def test_exact_gpu_canary_result_is_accepted_but_not_provider_finalized() -> None:
    evidence = accept()
    expected_result_sha256 = "sha256:" + hashlib.sha256(result_bytes_for(accepted_payload_dict())).hexdigest()

    assert evidence.schema_version == 1
    assert evidence.source_sha == SOURCE
    assert evidence.plan_fingerprint == PLAN
    assert evidence.image_digest == IMAGE
    assert evidence.execution_name == execution_name_for(PLAN, NONCE)
    assert evidence.completion_nonce == NONCE
    assert evidence.result_sha256 == expected_result_sha256
    assert evidence.workload_id == "orbitune-runpod-training-canary-v1"
    assert evidence.parameters == 10_200_960
    assert evidence.tokens_processed == 512_000
    assert evidence.gpu_name == "NVIDIA GeForce RTX 4090"
    assert evidence.validation_last_loss < evidence.validation_first_loss
    assert evidence.checkpoint_bytes == 40_000_000


def test_cpu_smoke_pass_is_not_paid_canary_acceptance() -> None:
    with pytest.raises(WorkloadAcceptanceError, match="requires CUDA"):
        accept(authenticated_result(device_type="cpu", cuda_available=False, gpu_name=None, cuda_version=None, peak_vram_bytes=0))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("parameters", 10_000_000, "parameter count"),
        ("steps", 249, "step count"),
        ("batch_size", 4, "batch size"),
        ("seq_len", 128, "sequence length"),
        ("tokens_processed", 511_999, "token count"),
        ("architecture", "other", "architecture"),
        ("tokenizer", "other", "tokenizer"),
    ],
)
def test_scaled_or_different_workload_result_is_not_canary_acceptance(field: str, value: object, message: str) -> None:
    with pytest.raises(WorkloadAcceptanceError, match=message):
        accept(authenticated_result(**{field: value}))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("parameters", 10_200_960.0, "parameter count"),
        ("steps", 250.0, "step count"),
        ("batch_size", 8.0, "batch size"),
        ("seq_len", 256.0, "sequence length"),
        ("tokens_processed", 512_000.0, "token count"),
    ],
)
def test_fixed_count_fields_require_actual_integers(field: str, value: object, message: str) -> None:
    with pytest.raises(WorkloadAcceptanceError, match=message):
        accept(authenticated_result(**{field: value}))


def test_validation_schedule_and_improvement_are_acceptance_gates() -> None:
    wrong_schedule = [
        {"step": 50, "loss": 4.0},
        {"step": 100, "loss": 3.5},
        {"step": 150, "loss": 3.0},
        {"step": 200, "loss": 2.5},
        {"step": 249, "loss": 2.0},
    ]
    with pytest.raises(WorkloadAcceptanceError, match="validation schedule"):
        accept(authenticated_result(validation_history=wrong_schedule))

    not_improved = [
        {"step": 50, "loss": 2.0},
        {"step": 100, "loss": 2.1},
        {"step": 150, "loss": 2.2},
        {"step": 200, "loss": 2.3},
        {"step": 250, "loss": 2.4},
    ]
    with pytest.raises(WorkloadAcceptanceError, match="did not improve"):
        accept(authenticated_result(validation_history=not_improved))


def test_validation_numeric_overflow_fails_closed() -> None:
    oversized = [
        {"step": 50, "loss": 10**400},
        {"step": 100, "loss": 3.5},
        {"step": 150, "loss": 3.0},
        {"step": 200, "loss": 2.5},
        {"step": 250, "loss": 2.0},
    ]
    with pytest.raises(WorkloadAcceptanceError, match="validation loss"):
        accept(authenticated_result(validation_history=oversized))


def test_checkpoint_metadata_remains_bounded_and_container_local() -> None:
    oversized = [{
        "name": "canary-base.pt",
        "bytes": MAX_CHECKPOINT_BYTES + 1,
        "sha256": "sha256:" + "5" * 64,
        "media_type": "application/x-pytorch-checkpoint",
        "transport": "container-local-only",
    }]
    with pytest.raises(WorkloadAcceptanceError, match="checkpoint size"):
        accept(authenticated_result(artifacts=oversized))

    falsely_collected = [{
        "name": "canary-base.pt",
        "bytes": 40_000_000,
        "sha256": "sha256:" + "5" * 64,
        "media_type": "application/x-pytorch-checkpoint",
        "transport": "collected",
    }]
    with pytest.raises(WorkloadAcceptanceError, match="transport boundary"):
        accept(authenticated_result(artifacts=falsely_collected))


def test_selected_source_sha_is_frozen_and_payload_must_match_it() -> None:
    with pytest.raises(WorkloadAcceptanceError, match="not the selected"):
        accept(expected_source_sha="e" * 40)
    with pytest.raises(WorkloadAcceptanceError, match="source_sha mismatch"):
        accept(authenticated_result(source_sha="e" * 40))
    wrong_completion = completion_evidence(source_sha="e" * 40)
    with pytest.raises(WorkloadAcceptanceError, match="completion source_sha"):
        accept(authenticated_result(evidence=wrong_completion))


def test_approved_plan_and_image_identity_are_acceptance_inputs() -> None:
    with pytest.raises(WorkloadAcceptanceError, match="plan_fingerprint mismatch"):
        accept(expected_plan_fingerprint="sha256:" + "9" * 64)
    with pytest.raises(WorkloadAcceptanceError, match="image_digest mismatch"):
        accept(expected_image_digest="sha256:" + "8" * 64)
    wrong_plan = completion_evidence(plan_fingerprint="sha256:" + "9" * 64)
    with pytest.raises(WorkloadAcceptanceError, match="plan_fingerprint mismatch"):
        accept(authenticated_result(evidence=wrong_plan))
    wrong_image = completion_evidence(image_digest="sha256:" + "8" * 64)
    with pytest.raises(WorkloadAcceptanceError, match="image_digest mismatch"):
        accept(authenticated_result(evidence=wrong_image))


def test_result_bytes_remain_bound_to_completion_digest() -> None:
    wrong_digest = completion_evidence(result_bytes=b"other-result")
    with pytest.raises(WorkloadAcceptanceError, match="result_sha256"):
        accept(authenticated_result(evidence=wrong_digest))


def test_result_payload_must_match_exact_authenticated_result_bytes() -> None:
    different_result_bytes = result_bytes_for(accepted_payload_dict(gpu_name="different-gpu"))
    matching_evidence = completion_evidence(result_bytes=different_result_bytes)
    with pytest.raises(WorkloadAcceptanceError, match="payload does not match exact result bytes"):
        accept(authenticated_result(evidence=matching_evidence, result_bytes=different_result_bytes))


def test_reconstructed_result_bytes_remain_bounded() -> None:
    oversized = b"{" + (b" " * MAX_MARKER_BYTES) + b"}"
    with pytest.raises(WorkloadAcceptanceError, match="bounded marker contract"):
        accept(authenticated_result(result_bytes=oversized, evidence=completion_evidence(result_bytes=oversized)))


def test_schema_version_must_be_actual_integer() -> None:
    with pytest.raises(WorkloadAcceptanceError, match="schema_version"):
        accept(authenticated_result(schema_version=1.0))


def test_process_success_is_required_before_workload_acceptance() -> None:
    failed = replace(authenticated_result(status="fail"), state=JobState.FAILED, process_exit_code=2)
    with pytest.raises(WorkloadAcceptanceError, match="process success"):
        accept(failed)
