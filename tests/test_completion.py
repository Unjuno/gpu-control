import hashlib

import pytest

from gpu_control.completion import (
    CompletionChallenge,
    CompletionEvidence,
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
EXECUTION_NAME = execution_name_for(PLAN, NONCE)


def challenge() -> CompletionChallenge:
    return CompletionChallenge(
        key_id="paid-runpod-v2",
        nonce=NONCE,
        plan_fingerprint=PLAN,
        execution_name=EXECUTION_NAME,
        source_sha="d" * 40,
        image_digest=IMAGE,
    )


def test_completion_evidence_round_trip() -> None:
    c = challenge()
    evidence = sign_completion(c, result_sha256=RESULT, secret_key=SECRET)
    assert evidence.schema_version == 2
    assert evidence.execution_name == EXECUTION_NAME
    assert "provider_job_id" not in evidence.to_dict()
    verify_completion(c, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_challenge_create_uses_pre_create_identity() -> None:
    c = CompletionChallenge.create(
        key_id="paid-runpod-v2",
        plan_fingerprint=PLAN,
        source_sha="d" * 40,
        image_digest=IMAGE,
    )
    assert c.schema_version == 2
    assert len(c.nonce) == 64
    assert c.execution_name == execution_name_for(PLAN, c.nonce)
    assert "provider_job_id" not in c.to_dict()


def test_completion_evidence_from_dict_is_exact_schema() -> None:
    evidence = sign_completion(challenge(), result_sha256=RESULT, secret_key=SECRET)
    assert CompletionEvidence.from_dict(evidence.to_dict()) == evidence
    with pytest.raises(CompletionEvidenceError, match="fields do not match schema"):
        CompletionEvidence.from_dict({**evidence.to_dict(), "provider_job_id": "pod-123"})


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
        plan_fingerprint=original.plan_fingerprint,
        execution_name=execution_name_for(original.plan_fingerprint, other_nonce),
        source_sha=original.source_sha,
        image_digest=original.image_digest,
    )
    with pytest.raises(CompletionEvidenceError, match="nonce"):
        verify_completion(other, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_evidence_rejects_cross_plan_replay() -> None:
    original = challenge()
    evidence = sign_completion(original, result_sha256=RESULT, secret_key=SECRET)
    other_plan = "sha256:" + "9" * 64
    other = CompletionChallenge(
        key_id=original.key_id,
        nonce=original.nonce,
        plan_fingerprint=other_plan,
        execution_name=execution_name_for(other_plan, original.nonce),
        source_sha=original.source_sha,
        image_digest=original.image_digest,
    )
    with pytest.raises(CompletionEvidenceError, match="plan_fingerprint"):
        verify_completion(other, evidence, secret_key=SECRET, expected_result_sha256=RESULT)


def test_completion_rejects_execution_name_not_derived_from_plan_and_nonce() -> None:
    c = CompletionChallenge(
        key_id="paid-runpod-v2",
        nonce=NONCE,
        plan_fingerprint=PLAN,
        execution_name="gpu-control-ffffffffffff-aaaaaaaaaaaa",
        source_sha="d" * 40,
        image_digest=IMAGE,
    )
    with pytest.raises(CompletionEvidenceError, match="does not match"):
        c.validate_shape()


def test_completion_secret_is_never_serialized() -> None:
    payload = challenge().to_dict()
    assert "secret" not in payload
    assert "key" not in payload


def test_completion_requires_256_bit_secret() -> None:
    with pytest.raises(CompletionEvidenceError, match="at least 32 bytes"):
        sign_completion(challenge(), result_sha256=RESULT, secret_key=b"short")
