from __future__ import annotations

import base64
import hashlib
import json

import pytest

from gpu_control.completion import CompletionChallenge, execution_name_for, sign_completion
from gpu_control.lifecycle import JobState
from gpu_control.providers.runpod_log_results import (
    COMPLETION_MARKER,
    MAX_MARKER_BYTES,
    MAX_SCAN_BYTES,
    MAX_SCAN_LINES,
    RESULT_MARKER,
    authenticate_runpod_log_result,
)
from gpu_control.providers.runpod_v2 import RunPodV2Error


SECRET = bytes(range(32))
PLAN = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
SOURCE = "d" * 40
NONCE = "a" * 64
WORKLOAD_ID = "orbitune-runpod-training-canary-v1"


def challenge() -> CompletionChallenge:
    return CompletionChallenge(
        key_id="paid-runpod-v2",
        nonce=NONCE,
        plan_fingerprint=PLAN,
        execution_name=execution_name_for(PLAN, NONCE),
        source_sha=SOURCE,
        image_digest=IMAGE,
    )


def marker(prefix: str, raw: bytes) -> str:
    return prefix + base64.urlsafe_b64encode(raw).decode("ascii")


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


def wrapper_failure_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "workload_id": WORKLOAD_ID,
        "source_sha": SOURCE,
        "status": "fail",
        "failure_kind": "runner-exited-without-result",
        "runner_exit_code": 0,
    }
    payload.update(overrides)
    return payload


def authenticated_lines(payload: dict[str, object] | None = None):  # type: ignore[no-untyped-def]
    result_payload = training_payload() if payload is None else payload
    result_bytes = json.dumps(
        result_payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    evidence = sign_completion(
        challenge(),
        result_sha256="sha256:" + hashlib.sha256(result_bytes).hexdigest(),
        secret_key=SECRET,
    )
    completion_bytes = json.dumps(
        evidence.to_dict(),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return (
        "ordinary log line",
        marker(RESULT_MARKER, result_bytes),
        marker(COMPLETION_MARKER, completion_bytes),
    ), result_bytes, completion_bytes


def authenticate(
    lines,  # type: ignore[no-untyped-def]
    *,
    exit_code: int = 0,
    expected_workload_id: str = WORKLOAD_ID,
):
    return authenticate_runpod_log_result(
        lines,
        challenge=challenge(),
        secret_key=SECRET,
        process_exit_code=exit_code,
        expected_workload_id=expected_workload_id,
    )


def test_authenticated_pass_result_requires_zero_exit_and_maps_to_succeeded() -> None:
    lines, result_bytes, completion_bytes = authenticated_lines()
    value = authenticate(lines, exit_code=0)

    assert value.state is JobState.SUCCEEDED
    assert value.process_exit_code == 0
    assert value.result_bytes == result_bytes
    assert value.completion_bytes == completion_bytes
    assert value.result_payload["status"] == "pass"
    assert value.result_payload["workload_id"] == WORKLOAD_ID
    assert value.completion_evidence.execution_name == challenge().execution_name


def test_authenticated_full_fail_result_requires_nonzero_exit_and_maps_to_failed() -> None:
    lines, _, _ = authenticated_lines(training_payload(status="fail"))
    value = authenticate(lines, exit_code=2)
    assert value.state is JobState.FAILED
    assert value.process_exit_code == 2


def test_authenticated_wrapper_failure_variant_is_supported() -> None:
    lines, _, _ = authenticated_lines(wrapper_failure_payload())
    value = authenticate(lines, exit_code=5)
    assert value.state is JobState.FAILED
    assert value.result_payload["failure_kind"] == "runner-exited-without-result"
    assert value.result_payload["runner_exit_code"] == 0


def test_authenticated_status_must_agree_with_process_exit_code() -> None:
    pass_lines, _, _ = authenticated_lines()
    with pytest.raises(RunPodV2Error, match="pass result disagrees"):
        authenticate(pass_lines, exit_code=2)

    fail_lines, _, _ = authenticated_lines(training_payload(status="fail"))
    with pytest.raises(RunPodV2Error, match="fail result disagrees"):
        authenticate(fail_lines, exit_code=0)


@pytest.mark.parametrize("value", [True, False, -1, 256, 1.0, "0"])
def test_process_exit_code_must_be_bounded_integer(value: object) -> None:
    lines, _, _ = authenticated_lines()
    with pytest.raises(RunPodV2Error, match="process_exit_code"):
        authenticate_runpod_log_result(
            lines,
            challenge=challenge(),
            secret_key=SECRET,
            process_exit_code=value,  # type: ignore[arg-type]
            expected_workload_id=WORKLOAD_ID,
        )


def test_trusted_workload_id_is_required_and_result_must_match_it() -> None:
    lines, _, _ = authenticated_lines()
    with pytest.raises(RunPodV2Error, match="expected_workload_id"):
        authenticate(lines, expected_workload_id=" invalid ")

    wrong_lines, _, _ = authenticated_lines(training_payload(workload_id="other-workload"))
    with pytest.raises(RunPodV2Error, match="workload_id does not match"):
        authenticate(wrong_lines)


def test_duplicate_or_missing_markers_fail_closed() -> None:
    lines, _, _ = authenticated_lines()
    with pytest.raises(RunPodV2Error, match="exactly one GPU_CONTROL_RESULT_JSON_V1"):
        authenticate((*lines, lines[1]))
    with pytest.raises(RunPodV2Error, match="exactly one GPU_CONTROL_COMPLETION_JSON_V2"):
        authenticate(lines[:-1])


def test_marker_scan_does_not_retain_ordinary_log_stream() -> None:
    lines, _, _ = authenticated_lines()

    def source():  # type: ignore[no-untyped-def]
        for _ in range(1000):
            yield "x"
        yield lines[1]
        for _ in range(1000):
            yield "y"
        yield lines[2]

    value = authenticate(source())
    assert value.state is JobState.SUCCEEDED


def test_log_scan_has_explicit_line_and_byte_bounds() -> None:
    lines, _, _ = authenticated_lines()
    with pytest.raises(RunPodV2Error, match="bounded line count"):
        authenticate(("x" for _ in range(MAX_SCAN_LINES + 1)))

    oversized_ordinary_line = "x" * (MAX_SCAN_BYTES + 1)
    with pytest.raises(RunPodV2Error, match="bounded byte count"):
        authenticate((oversized_ordinary_line, lines[1], lines[2]))


def test_oversized_line_is_rejected_before_utf8_copy() -> None:
    lines, _, _ = authenticated_lines()

    class EncodeBomb(str):
        def encode(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("oversized line must be rejected before encode")

    oversized = EncodeBomb("x" * (MAX_SCAN_BYTES + 1))
    with pytest.raises(RunPodV2Error, match="bounded byte count"):
        authenticate((oversized, lines[1], lines[2]))


def test_non_string_log_line_is_rejected() -> None:
    lines, _, _ = authenticated_lines()
    with pytest.raises(RunPodV2Error, match="must be a string"):
        authenticate((lines[1], 123, lines[2]))  # type: ignore[arg-type]


def test_bound_applies_to_actual_encoded_marker_including_prefix() -> None:
    oversized = RESULT_MARKER + "A" * (MAX_MARKER_BYTES - len(RESULT_MARKER) + 1)
    lines, _, _ = authenticated_lines()
    with pytest.raises(RunPodV2Error, match="bounded encoded size"):
        authenticate((oversized, lines[2]))


def test_invalid_base64url_is_rejected() -> None:
    lines, _, _ = authenticated_lines()
    with pytest.raises(RunPodV2Error, match="not valid base64url"):
        authenticate((RESULT_MARKER + "***", lines[2]))


def test_result_tampering_fails_hmac_verification() -> None:
    lines, _, _ = authenticated_lines()
    tampered_payload = training_payload(status="fail")
    tampered = json.dumps(tampered_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(RunPodV2Error, match="result_sha256"):
        authenticate((marker(RESULT_MARKER, tampered), lines[2]))


def test_authenticated_result_source_must_match_challenge() -> None:
    lines, _, _ = authenticated_lines(training_payload(source_sha="e" * 40))
    with pytest.raises(RunPodV2Error, match="source_sha"):
        authenticate(lines)


@pytest.mark.parametrize("schema_version", [True, False, 1.0, "1", 2])
def test_authenticated_result_requires_exact_integer_schema(schema_version: object) -> None:
    lines, _, _ = authenticated_lines(training_payload(schema_version=schema_version))
    with pytest.raises(RunPodV2Error, match="schema_version"):
        authenticate(lines)


def test_result_schema_rejects_unknown_or_missing_top_level_fields() -> None:
    extra = training_payload(untrusted_extension="do-not-consume")
    lines, _, _ = authenticated_lines(extra)
    with pytest.raises(RunPodV2Error, match="fields do not match"):
        authenticate(lines)

    missing = training_payload()
    del missing["architecture"]
    lines, _, _ = authenticated_lines(missing)
    with pytest.raises(RunPodV2Error, match="fields do not match"):
        authenticate(lines)


def test_nested_result_schema_is_strict_and_self_consistent() -> None:
    bad_tokens = training_payload(tokens_processed=15)
    lines, _, _ = authenticated_lines(bad_tokens)
    with pytest.raises(RunPodV2Error, match="tokens_processed"):
        authenticate(lines)

    bad_history = training_payload(validation_history=[{"step": 1, "loss": 3.5, "extra": 1}])
    lines, _, _ = authenticated_lines(bad_history)
    with pytest.raises(RunPodV2Error, match="validation_history entry fields"):
        authenticate(lines)

    bad_artifact = training_payload()
    artifact = dict(bad_artifact["artifacts"][0])  # type: ignore[index]
    artifact["transport"] = "collected"
    bad_artifact["artifacts"] = [artifact]
    lines, _, _ = authenticated_lines(bad_artifact)
    with pytest.raises(RunPodV2Error, match="container-local-only"):
        authenticate(lines)


def test_nonfinite_numeric_result_fields_are_rejected() -> None:
    lines, _, _ = authenticated_lines(training_payload(final_training_loss=float("nan")))
    with pytest.raises(RunPodV2Error, match="final_training_loss"):
        authenticate(lines)


@pytest.mark.parametrize(
    "field",
    ["elapsed_seconds", "tokens_per_second", "first_training_loss", "final_training_loss"],
)
def test_oversized_numeric_result_fields_fail_closed(field: str) -> None:
    lines, _, _ = authenticated_lines(training_payload(**{field: 10**400}))
    with pytest.raises(RunPodV2Error, match=field):
        authenticate(lines)


@pytest.mark.parametrize("status", [[], {}])
def test_unhashable_status_is_rejected_as_schema_data(status: object) -> None:
    lines, _, _ = authenticated_lines(training_payload(status=status))
    with pytest.raises(RunPodV2Error, match="status"):
        authenticate(lines)


@pytest.mark.parametrize("device_type", [[], {}])
def test_unhashable_device_type_is_rejected_as_schema_data(device_type: object) -> None:
    lines, _, _ = authenticated_lines(training_payload(device_type=device_type))
    with pytest.raises(RunPodV2Error, match="device_type"):
        authenticate(lines)


def test_wrapper_failure_schema_is_exact() -> None:
    extra = wrapper_failure_payload(extra="untrusted")
    lines, _, _ = authenticated_lines(extra)
    with pytest.raises(RunPodV2Error, match="supported Orbitune result schema"):
        authenticate(lines, exit_code=5)

    wrong_kind = wrapper_failure_payload(failure_kind="other")
    lines, _, _ = authenticated_lines(wrong_kind)
    with pytest.raises(RunPodV2Error, match="failure_kind"):
        authenticate(lines, exit_code=5)


def test_authenticated_result_payload_is_recursively_immutable() -> None:
    lines, _, _ = authenticated_lines()
    value = authenticate(lines)

    with pytest.raises(TypeError):
        value.result_payload["status"] = "fail"  # type: ignore[index]
    assert isinstance(value.result_payload["validation_history"], tuple)
    assert isinstance(value.result_payload["artifacts"], tuple)
    with pytest.raises(TypeError):
        value.result_payload["artifacts"][0]["name"] = "tampered.pt"  # type: ignore[index]


def test_duplicate_json_fields_are_rejected_before_schema_validation() -> None:
    raw = (
        b'{"schema_version":1,"workload_id":"' + WORKLOAD_ID.encode("ascii")
        + b'","source_sha":"' + SOURCE.encode("ascii")
        + b'","status":"pass","status":"fail"}'
    )
    evidence = sign_completion(
        challenge(),
        result_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
        secret_key=SECRET,
    )
    completion_bytes = json.dumps(evidence.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(RunPodV2Error, match="duplicate field: status"):
        authenticate((marker(RESULT_MARKER, raw), marker(COMPLETION_MARKER, completion_bytes)))
