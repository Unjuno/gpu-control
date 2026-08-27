import hashlib

import pytest

from gpu_control.completion import (
    CompletionChallenge,
    CompletionEvidenceError,
    execution_name_for,
    sign_completion,
    verify_completion,
)


SECRET = bytes(range(32))
PLAN = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
RESULT = "sha256:" + hashlib.sha256(b"result-bytes").hexdigest()
NONCE = "a" * 64


def challenge() -> CompletionChallenge:
    return CompletionChallenge(
        key_id="paid-runpod-v2",
        nonce=NONCE,
        execution_name=execution_name_for(plan_fingerprint=PLAN, nonce=NONCE),
        plan_fingerprint=PLAN,
        source_sha="d" * 40,
        image_digest=IMAGE,
    )


def test_completion_evidence_round_trip() -> None:
    c = challenge()
    evidence = sign_completion(c, result_sha256=RESULT, secret_key=SECRET)
    verify_completion(c, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_challenge_create_generates_pre_create_execution_name() -> None:
    c = CompletionChallenge.create(
        key_id="paid-runpod-v2",
        plan_fingerprint=PLAN,
        source_sha="d" * 40,
        image_digest=IMAGE,
    )
    c.validate_shape()
    assert c.execution_name.startswith("gpu-control-111111111111-")
    assert c.execution_name == execution_name_for(plan_fingerprint=PLAN, nonce=c.nonce)


def test_completion_evidence_rejects_modified_result() -> None:
    c = challenge()
    evidence = sign_completion(c, result_sha256=RESULT, secret_key=SECRET)
    with pytest.raises(CompletionEvidenceError, match="result_sha256"):
        verify_completion(
            c,
            evidence,
            secret_key=SECRET,
            expected_result_sha256="sha256:" + "3" * 64,
        )


def test_completion_evidence_rejects_wrong_secret() -> None:
    c = challenge()
    evidence = sign_completion(c, result_sha256=RESULT, secret_key=SECRET)
    with pytest.raises(CompletionEvidenceError, match="authentication failed"):
        verify_completion(c, evidence, secret_key=b"x" * 32, expected_result_sha256=RESULT)


def test_completion_evidence_rejects_cross_execution_replay() -> None:
    original = challenge()
    evidence = sign_completion(original, result_sha256=RESULT, secret_key=SECRET)
    other_nonce = "b" * 64
    other = CompletionChallenge(
        key_id=original.key_id,
        nonce=other_nonce,
        execution_name=execution_name_for(plan_fingerprint=original.plan_fingerprint, nonce=other_nonce),
        plan_fingerprint=original.plan_fingerprint,
        source_sha=original.source_sha,
        image_digest=original.image_digest,
    )
    with pytest.raises(CompletionEvidenceError, match="nonce|execution_name"):
        verify_completion(other, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_evidence_rejects_cross_plan_replay() -> None:
    original = challenge()
    evidence = sign_completion(original, result_sha256=RESULT, secret_key=SECRET)
    other_plan = "sha256:" + "9" * 64
    other = CompletionChallenge(
        key_id=original.key_id,
        nonce=original.nonce,
        execution_name=execution_name_for(plan_fingerprint=other_plan, nonce=original.nonce),
        plan_fingerprint=other_plan,
        source_sha=original.source_sha,
        image_digest=original.image_digest,
    )
    with pytest.raises(CompletionEvidenceError, match="execution_name|plan_fingerprint"):
        verify_completion(other, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_secret_is_never_serialized() -> None:
    payload = challenge().to_dict()
    assert "secret" not in payload
    assert "key" not in payload


def test_completion_requires_256_bit_secret() -> None:
    with pytest.raises(CompletionEvidenceError, match="at least 32 bytes"):
        sign_completion(challenge(), result_sha256=RESULT, secret_key=b"short")
