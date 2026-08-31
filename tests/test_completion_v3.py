import hashlib

import pytest

from gpu_control.completion import (
    CompletionChallenge,
    CompletionEvidenceError,
    CompletionEvidenceV3,
    execution_name_for,
    sign_completion_v3,
    verify_completion_v3,
)


SECRET = bytes(range(32))
PLAN = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
RESULT = "sha256:" + hashlib.sha256(b"result-bytes").hexdigest()
NONCE = "a" * 64


def challenge() -> CompletionChallenge:
    return CompletionChallenge(
        key_id="paid-runpod-v3",
        nonce=NONCE,
        plan_fingerprint=PLAN,
        execution_name=execution_name_for(PLAN, NONCE),
        source_sha="d" * 40,
        image_digest=IMAGE,
    )


def test_completion_v3_round_trip_binds_exit_code() -> None:
    value = sign_completion_v3(
        challenge(), result_sha256=RESULT, process_exit_code=0, secret_key=SECRET
    )
    assert value.schema_version == 3
    assert value.process_exit_code == 0
    assert CompletionEvidenceV3.from_dict(value.to_dict()) == value
    verify_completion_v3(challenge(), value, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_v3_exit_code_is_authenticated() -> None:
    value = sign_completion_v3(
        challenge(), result_sha256=RESULT, process_exit_code=0, secret_key=SECRET
    )
    tampered = CompletionEvidenceV3.from_dict({**value.to_dict(), "process_exit_code": 1})
    with pytest.raises(CompletionEvidenceError, match="authentication failed"):
        verify_completion_v3(challenge(), tampered, secret_key=SECRET, expected_result_sha256=RESULT)


@pytest.mark.parametrize("value", [-1, 256, True, 0.0, "0"])
def test_completion_v3_requires_bounded_integer_exit_code(value: object) -> None:
    with pytest.raises(CompletionEvidenceError, match="process_exit_code"):
        sign_completion_v3(
            challenge(), result_sha256=RESULT, process_exit_code=value, secret_key=SECRET  # type: ignore[arg-type]
        )


def test_completion_v3_rejects_cross_execution_replay() -> None:
    original = challenge()
    evidence = sign_completion_v3(
        original, result_sha256=RESULT, process_exit_code=0, secret_key=SECRET
    )
    other_nonce = "b" * 64
    other = CompletionChallenge(
        key_id=original.key_id,
        nonce=other_nonce,
        plan_fingerprint=original.plan_fingerprint,
        execution_name=execution_name_for(original.plan_fingerprint, other_nonce),
        source_sha=original.source_sha,
        image_digest=original.image_digest,
    )
    with pytest.raises(CompletionEvidenceError, match="nonce"):
        verify_completion_v3(other, evidence, secret_key=SECRET, expected_result_sha256=RESULT)
