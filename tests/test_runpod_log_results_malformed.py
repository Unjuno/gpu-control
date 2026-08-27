from __future__ import annotations

import base64
import hashlib
import json

import pytest

from gpu_control.completion import CompletionChallenge, execution_name_for, sign_completion
from gpu_control.providers.runpod_log_results import (
    COMPLETION_MARKER,
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


def completion_marker_for(result_bytes: bytes) -> str:
    evidence = sign_completion(
        challenge(),
        result_sha256="sha256:" + hashlib.sha256(result_bytes).hexdigest(),
        secret_key=SECRET,
    )
    completion_bytes = json.dumps(
        evidence.to_dict(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return marker(COMPLETION_MARKER, completion_bytes)


def authenticate(result_line: str, completion_line: str):  # type: ignore[no-untyped-def]
    return authenticate_runpod_log_result(
        (result_line, completion_line),
        challenge=challenge(),
        secret_key=SECRET,
        process_exit_code=0,
        expected_workload_id=WORKLOAD_ID,
    )


def test_json_integer_digit_limit_is_normalized_to_runpod_error() -> None:
    raw = b'{"schema_version":' + (b"9" * 5000) + b'}'
    with pytest.raises(RunPodV2Error, match="bounded UTF-8 JSON"):
        authenticate(marker(RESULT_MARKER, raw), completion_marker_for(raw))


def test_excessive_json_nesting_is_normalized_to_runpod_error() -> None:
    raw = b'{"nested":' + (b"[" * 1100) + b"0" + (b"]" * 1100) + b"}"
    assert len(raw) < 16 * 1024
    with pytest.raises(RunPodV2Error, match="bounded UTF-8 JSON"):
        authenticate(marker(RESULT_MARKER, raw), completion_marker_for(raw))


def test_unencodable_provider_log_text_is_normalized_to_runpod_error() -> None:
    valid_result = b"{}"
    with pytest.raises(RunPodV2Error, match="valid UTF-8 text"):
        authenticate_runpod_log_result(
            ("\ud800", marker(RESULT_MARKER, valid_result), completion_marker_for(valid_result)),
            challenge=challenge(),
            secret_key=SECRET,
            process_exit_code=0,
            expected_workload_id=WORKLOAD_ID,
        )


def test_standard_base64_alphabet_is_not_accepted_as_base64url() -> None:
    # 0xfbff encodes with '+' and '/' in the standard alphabet but '-' and '_'
    # in the URL-safe alphabet. The parser accepts only the producer's URL-safe form.
    raw = b"\xfb\xff"
    standard = base64.b64encode(raw).decode("ascii")
    assert "+" in standard or "/" in standard
    with pytest.raises(RunPodV2Error, match="not valid base64url"):
        authenticate(RESULT_MARKER + standard, completion_marker_for(raw))


def test_noncanonical_base64url_padding_is_rejected() -> None:
    raw = b"{}"
    canonical = base64.urlsafe_b64encode(raw).decode("ascii")
    assert canonical.endswith("=")
    without_padding = canonical.rstrip("=")
    with pytest.raises(RunPodV2Error, match="not valid base64url"):
        authenticate(RESULT_MARKER + without_padding, completion_marker_for(raw))
