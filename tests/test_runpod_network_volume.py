from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

import pytest

from gpu_control.completion import CompletionChallenge, execution_name_for, sign_completion_v3
from gpu_control.lifecycle import JobState
from gpu_control.providers.runpod_network_volume import (
    COMPLETION_V3_OBJECT_KEY,
    MAX_RESULT_FILE_BYTES,
    RESULT_OBJECT_KEY,
    RunPodNetworkVolumeEvidence,
    RunPodNetworkVolumeS3Client,
    RunPodS3Credentials,
    authenticate_runpod_volume_result,
    collect_runpod_network_volume_result,
)
from gpu_control.providers.runpod_v2 import RunPodV2Error


SECRET = bytes(range(32))
PLAN = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
SOURCE = "d" * 40
NONCE = "a" * 64
WORKLOAD_ID = "orbitune-runpod-training-canary-v1"
NOW = datetime(2026, 8, 30, 13, 30, tzinfo=timezone.utc)


def challenge() -> CompletionChallenge:
    return CompletionChallenge(
        key_id="paid-runpod-v3",
        nonce=NONCE,
        plan_fingerprint=PLAN,
        execution_name=execution_name_for(PLAN, NONCE),
        source_sha=SOURCE,
        image_digest=IMAGE,
    )


def training_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "workload_id": WORKLOAD_ID,
        "source_sha": SOURCE,
        "status": "pass",
        "purpose": "GPU/container/training/checkpoint infrastructure canary; not a musical-quality benchmark",
        "architecture": "orbitune-midi-gpt-v0",
        "tokenizer": "theory-remi-v0",
        "parameters": 10_200_960,
        "device_type": "cpu",
        "cuda_available": False,
        "gpu_name": None,
        "torch_version": "2.10.0",
        "cuda_version": None,
        "steps": 1,
        "batch_size": 1,
        "seq_len": 16,
        "tokens_processed": 16,
        "elapsed_seconds": 0.25,
        "tokens_per_second": 64.0,
        "first_training_loss": 5.0,
        "final_training_loss": 4.0,
        "validation_history": [{"step": 1, "loss": 3.5}],
        "peak_vram_bytes": 0,
        "artifacts": [
            {
                "name": "canary-base.pt",
                "bytes": 1024,
                "sha256": "sha256:" + "3" * 64,
                "media_type": "application/x-pytorch-checkpoint",
                "transport": "container-local-only",
            }
        ],
    }
    payload.update(overrides)
    return payload


def signed_files(*, status: str = "pass", exit_code: int = 0) -> tuple[bytes, bytes]:
    result_bytes = json.dumps(
        training_payload(status=status), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    evidence = sign_completion_v3(
        challenge(),
        result_sha256="sha256:" + hashlib.sha256(result_bytes).hexdigest(),
        process_exit_code=exit_code,
        secret_key=SECRET,
    )
    completion_bytes = json.dumps(
        evidence.to_dict(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return result_bytes, completion_bytes


def volume() -> RunPodNetworkVolumeEvidence:
    return RunPodNetworkVolumeEvidence(
        network_volume_id="vol_test123",
        data_center_id="US-KS-2",
        verification_reference="runpod-network-volume:test",
    )


class Response:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.status = 200
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *args):  # type: ignore[no-untyped-def]
        return False

    def read(self, size: int) -> bytes:
        return self.body[:size]


class Opener:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.requests = []

    def __call__(self, request, *, timeout):  # type: ignore[no-untyped-def]
        self.requests.append((request, timeout))
        assert request.full_url.startswith("https://s3api-us-ks-2.runpod.io/vol_test123/")
        assert "secret-value" not in request.full_url
        assert "AWS4-HMAC-SHA256" in request.get_header("Authorization")
        assert request.get_header("Host") == "s3api-us-ks-2.runpod.io"
        key = request.full_url.rsplit("/", 1)[1]
        return Response(self.objects[key])


def test_volume_binding_is_fixed_to_supported_s3_location_and_outputs_mount() -> None:
    value = volume()
    value.validate_shape()
    assert value.mount_path == "/outputs"
    assert value.s3_endpoint == "https://s3api-us-ks-2.runpod.io"
    with pytest.raises(RunPodV2Error, match="supported S3 datacenter"):
        RunPodNetworkVolumeEvidence(
            network_volume_id="vol_test123",
            data_center_id="US-XX-9",
            verification_reference="x",
        ).validate_shape()
    with pytest.raises(RunPodV2Error, match="mount path"):
        RunPodNetworkVolumeEvidence(
            network_volume_id="vol_test123",
            data_center_id="US-KS-2",
            verification_reference="x",
            mount_path="/workspace",
        ).validate_shape()


def test_fixed_origin_s3_client_reads_only_bounded_bytes() -> None:
    result_bytes, completion_bytes = signed_files()
    opener = Opener({RESULT_OBJECT_KEY: result_bytes, COMPLETION_V3_OBJECT_KEY: completion_bytes})
    client = RunPodNetworkVolumeS3Client(
        volume(),
        RunPodS3Credentials(access_key_id="user_test", secret_access_key="secret-value"),
        opener=opener,
        clock=lambda: NOW,
    )
    assert client.get_object(RESULT_OBJECT_KEY) == result_bytes
    assert client.get_object(COMPLETION_V3_OBJECT_KEY) == completion_bytes
    assert len(opener.requests) == 2
    with pytest.raises(RunPodV2Error, match="canonical relative path"):
        client.get_object("../secret")


def test_s3_client_rejects_oversized_object_before_acceptance() -> None:
    opener = Opener({RESULT_OBJECT_KEY: b"x" * (MAX_RESULT_FILE_BYTES + 1)})
    client = RunPodNetworkVolumeS3Client(
        volume(),
        RunPodS3Credentials(access_key_id="user_test", secret_access_key="secret-value"),
        opener=opener,
        clock=lambda: NOW,
    )
    with pytest.raises(RunPodV2Error, match="exceeds bounded"):
        client.get_object(RESULT_OBJECT_KEY)


def test_volume_result_uses_signed_exit_code_not_provider_status() -> None:
    result_bytes, completion_bytes = signed_files(status="pass", exit_code=0)
    value = authenticate_runpod_volume_result(
        result_bytes,
        completion_bytes,
        challenge=challenge(),
        secret_key=SECRET,
        expected_workload_id=WORKLOAD_ID,
        collection_reference="runpod-s3:test",
    )
    assert value.state is JobState.SUCCEEDED
    assert value.process_exit_code == 0
    assert value.result_payload["status"] == "pass"


def test_volume_result_rejects_status_exit_disagreement_and_tampering() -> None:
    result_bytes, completion_bytes = signed_files(status="pass", exit_code=2)
    with pytest.raises(RunPodV2Error, match="pass result disagrees"):
        authenticate_runpod_volume_result(
            result_bytes,
            completion_bytes,
            challenge=challenge(),
            secret_key=SECRET,
            expected_workload_id=WORKLOAD_ID,
            collection_reference="runpod-s3:test",
        )

    clean_result, clean_completion = signed_files()
    tampered = clean_result.replace(b'"status":"pass"', b'"status":"fail"')
    with pytest.raises(RunPodV2Error, match="result_sha256"):
        authenticate_runpod_volume_result(
            tampered,
            clean_completion,
            challenge=challenge(),
            secret_key=SECRET,
            expected_workload_id=WORKLOAD_ID,
            collection_reference="runpod-s3:test",
        )


def test_collector_fetches_exact_two_named_objects() -> None:
    result_bytes, completion_bytes = signed_files()
    opener = Opener({RESULT_OBJECT_KEY: result_bytes, COMPLETION_V3_OBJECT_KEY: completion_bytes})
    client = RunPodNetworkVolumeS3Client(
        volume(),
        RunPodS3Credentials(access_key_id="user_test", secret_access_key="secret-value"),
        opener=opener,
        clock=lambda: NOW,
    )
    value = collect_runpod_network_volume_result(
        client,
        challenge=challenge(),
        secret_key=SECRET,
        expected_workload_id=WORKLOAD_ID,
    )
    assert value.state is JobState.SUCCEEDED
    urls = [request.full_url for request, _ in opener.requests]
    assert urls == [
        "https://s3api-us-ks-2.runpod.io/vol_test123/result.json",
        "https://s3api-us-ks-2.runpod.io/vol_test123/completion-v3.json",
    ]
