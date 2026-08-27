import hashlib

import pytest

from gpu_control.completion import (
    CompletionChallenge,
    CompletionEvidenceError,
    sign_completion,
    verify_completion,
)


SECRET = bytes(range(32))
PLAN = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
RESULT = "sha256:" + hashlib.sha256(b"result-bytes").hexdigest()


def challenge() -> CompletionChallenge:
    return CompletionChallenge(
        key_id="paid-runpod-v1",
        nonce="a" * 64,
        plan_fingerprint=PLAN,
        provider_job_id="pod-123",
        source_sha="d" * 40,
        image_digest=IMAGE,
    )


def test_completion_evidence_round_trip() -> None:
    c = challenge()
    evidence = sign_completion(c, result_sha256=RESULT, secret_key=SECRET)
    verify_completion(c, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


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


def test_completion_evidence_rejects_cross_job_replay() -> None:
    original = challenge()
    evidence = sign_completion(original, result_sha256=RESULT, secret_key=SECRET)
    other = CompletionChallenge(
        key_id=original.key_id,
        nonce=original.nonce,
        plan_fingerprint=original.plan_fingerprint,
        provider_job_id="pod-999",
        source_sha=original.source_sha,
        image_digest=original.image_digest,
    )
    with pytest.raises(CompletionEvidenceError, match="provider_job_id"):
        verify_completion(other, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_evidence_rejects_cross_plan_replay() -> None:
    original = challenge()
    evidence = sign_completion(original, result_sha256=RESULT, secret_key=SECRET)
    other = CompletionChallenge(
        key_id=original.key_id,
        nonce=original.nonce,
        plan_fingerprint="sha256:" + "9" * 64,
        provider_job_id=original.provider_job_id,
        source_sha=original.source_sha,
        image_digest=original.image_digest,
    )
    with pytest.raises(CompletionEvidenceError, match="plan_fingerprint"):
        verify_completion(other, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_secret_is_never_serialized() -> None:
    payload = challenge().to_dict()
    assert "secret" not in payload
    assert "key" not in payload


def test_completion_requires_256_bit_secret() -> None:
    with pytest.raises(CompletionEvidenceError, match="at least 32 bytes"):
        sign_completion(challenge(), result_sha256=RESULT, secret_key=b"short")
