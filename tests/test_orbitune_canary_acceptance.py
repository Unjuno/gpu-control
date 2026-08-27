from __future__ import annotations

from types import MappingProxyType

import pytest

from gpu_control.completion import CompletionEvidence, execution_name_for
from gpu_control.lifecycle import JobState
from gpu_control.providers.runpod_log_results import AuthenticatedRunPodLogResult
from gpu_control.workload_contracts.orbitune_canary import (
    MAX_CHECKPOINT_BYTES,
    WorkloadAcceptanceError,
    validate_orbitune_canary_result,
)


SOURCE = "38594057d1b118a7acf6c843e39d7d8a25571316"
PLAN = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
NONCE = "a" * 64


def completion_evidence() -> CompletionEvidence:
    return CompletionEvidence(
        key_id="paid-runpod-v2",
        nonce=NONCE,
        plan_fingerprint=PLAN,
        execution_name=execution_name_for(PLAN, NONCE),
        source_sha=SOURCE,
        image_digest=IMAGE,
        result_sha256="sha256:" + "3" * 64,
        mac_sha256="4" * 64,
    )


def accepted_payload(**overrides: object) -> MappingProxyType:
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
        "validation_history": (
            MappingProxyType({"step": 50, "loss": 4.0}),
            MappingProxyType({"step": 100, "loss": 3.5}),
            MappingProxyType({"step": 150, "loss": 3.0}),
            MappingProxyType({"step": 200, "loss": 2.5}),
            MappingProxyType({"step": 250, "loss": 2.0}),
        ),
        "peak_vram_bytes": 1_000_000,
        "artifacts": (
            MappingProxyType(
                {
                    "name": "canary-base.pt",
                    "bytes": 40_000_000,
                    "sha256": "sha256:" + "5" * 64,
                    "media_type": "application/x-pytorch-checkpoint",
                    "transport": "container-local-only",
                }
            ),
        ),
    }
    payload.update(overrides)
    return MappingProxyType(payload)


def authenticated_result(**payload_overrides: object) -> AuthenticatedRunPodLogResult:
    return AuthenticatedRunPodLogResult(
        state=JobState.SUCCEEDED,
        process_exit_code=0,
        result_bytes=b"authenticated-result",
        completion_bytes=b"authenticated-completion",
        result_payload=accepted_payload(**payload_overrides),
        completion_evidence=completion_evidence(),
    )


def test_exact_gpu_canary_result_is_accepted_but_not_provider_finalized() -> None:
    evidence = validate_orbitune_canary_result(
        authenticated_result(), expected_source_sha=SOURCE
    )

    assert evidence.schema_version == 1
    assert evidence.source_sha == SOURCE
    assert evidence.image_digest == IMAGE
    assert evidence.workload_id == "orbitune-runpod-training-canary-v1"
    assert evidence.parameters == 10_200_960
    assert evidence.tokens_processed == 512_000
    assert evidence.gpu_name == "NVIDIA GeForce RTX 4090"
    assert evidence.validation_last_loss < evidence.validation_first_loss
    assert evidence.checkpoint_bytes == 40_000_000


def test_cpu_smoke_pass_is_not_paid_canary_acceptance() -> None:
    with pytest.raises(WorkloadAcceptanceError, match="requires CUDA"):
        validate_orbitune_canary_result(
            authenticated_result(
                device_type="cpu",
                cuda_available=False,
                gpu_name=None,
                cuda_version=None,
                peak_vram_bytes=0,
            ),
            expected_source_sha=SOURCE,
        )


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
def test_scaled_or_different_workload_result_is_not_canary_acceptance(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(WorkloadAcceptanceError, match=message):
        validate_orbitune_canary_result(
            authenticated_result(**{field: value}), expected_source_sha=SOURCE
        )


def test_validation_schedule_and_improvement_are_acceptance_gates() -> None:
    wrong_schedule = (
        MappingProxyType({"step": 50, "loss": 4.0}),
        MappingProxyType({"step": 100, "loss": 3.5}),
        MappingProxyType({"step": 150, "loss": 3.0}),
        MappingProxyType({"step": 200, "loss": 2.5}),
        MappingProxyType({"step": 249, "loss": 2.0}),
    )
    with pytest.raises(WorkloadAcceptanceError, match="validation schedule"):
        validate_orbitune_canary_result(
            authenticated_result(validation_history=wrong_schedule),
            expected_source_sha=SOURCE,
        )

    not_improved = (
        MappingProxyType({"step": 50, "loss": 2.0}),
        MappingProxyType({"step": 100, "loss": 2.1}),
        MappingProxyType({"step": 150, "loss": 2.2}),
        MappingProxyType({"step": 200, "loss": 2.3}),
        MappingProxyType({"step": 250, "loss": 2.4}),
    )
    with pytest.raises(WorkloadAcceptanceError, match="did not improve"):
        validate_orbitune_canary_result(
            authenticated_result(validation_history=not_improved),
            expected_source_sha=SOURCE,
        )


def test_checkpoint_metadata_remains_bounded_and_container_local() -> None:
    oversized = (
        MappingProxyType(
            {
                "name": "canary-base.pt",
                "bytes": MAX_CHECKPOINT_BYTES + 1,
                "sha256": "sha256:" + "5" * 64,
                "media_type": "application/x-pytorch-checkpoint",
                "transport": "container-local-only",
            }
        ),
    )
    with pytest.raises(WorkloadAcceptanceError, match="checkpoint size"):
        validate_orbitune_canary_result(
            authenticated_result(artifacts=oversized), expected_source_sha=SOURCE
        )

    falsely_collected = (
        MappingProxyType(
            {
                "name": "canary-base.pt",
                "bytes": 40_000_000,
                "sha256": "sha256:" + "5" * 64,
                "media_type": "application/x-pytorch-checkpoint",
                "transport": "collected",
            }
        ),
    )
    with pytest.raises(WorkloadAcceptanceError, match="transport boundary"):
        validate_orbitune_canary_result(
            authenticated_result(artifacts=falsely_collected), expected_source_sha=SOURCE
        )


def test_source_sha_and_process_success_are_trusted_acceptance_inputs() -> None:
    with pytest.raises(WorkloadAcceptanceError, match="source_sha mismatch"):
        validate_orbitune_canary_result(
            authenticated_result(), expected_source_sha="e" * 40
        )

    failed = AuthenticatedRunPodLogResult(
        state=JobState.FAILED,
        process_exit_code=2,
        result_bytes=b"authenticated-result",
        completion_bytes=b"authenticated-completion",
        result_payload=accepted_payload(status="fail"),
        completion_evidence=completion_evidence(),
    )
    with pytest.raises(WorkloadAcceptanceError, match="process success"):
        validate_orbitune_canary_result(failed, expected_source_sha=SOURCE)
