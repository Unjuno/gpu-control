from __future__ import annotations

import base64
import hashlib
import json

import pytest

from gpu_control.completion import CompletionChallenge, sign_completion
from gpu_control.lifecycle import JobState
from gpu_control.providers.runpod_log_results import (
    COMPLETION_MARKER,
    RESULT_MARKER,
    authenticate_runpod_log_result,
)
from gpu_control.providers.runpod_v2 import RunPodV2Error


PLAN = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
SOURCE = "d" * 40
SECRET = bytes(range(32))


def challenge() -> CompletionChallenge:
    return CompletionChallenge(
        key_id="paid-runpod-v2",
        nonce="a" * 64,
        execution_name="gpu-control-111111111111-aaaaaaaaaaaa",
        plan_fingerprint=PLAN,
        source_sha=SOURCE,
        image_digest=IMAGE,
    )


def marker(prefix: str, raw: bytes) -> str:
    return prefix + base64.urlsafe_b64encode(raw).decode("ascii")


def lines_for(status: str = "pass") -> tuple[str, ...]:
    c = challenge()
    result = json.dumps(
        {"schema_version": 1, "source_sha": SOURCE, "status": status},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    evidence = sign_completion(
        c,
        result_sha256="sha256:" + hashlib.sha256(result).hexdigest(),
        secret_key=SECRET,
    )
    completion = json.dumps(evidence.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return (
        "ordinary workload output",
        marker(RESULT_MARKER, result),
        marker(COMPLETION_MARKER, completion),
    )


def test_authenticated_log_result_maps_pass_and_fail() -> None:
    passed = authenticate_runpod_log_result(lines_for("pass"), challenge=challenge(), secret_key=SECRET)
    failed = authenticate_runpod_log_result(lines_for("fail"), challenge=challenge(), secret_key=SECRET)
    assert passed.state is JobState.SUCCEEDED
    assert failed.state is JobState.FAILED
    assert {artifact.name for artifact in passed.artifacts(provider_job_id="pod-1")} == {
        "result.json",
        "completion.json",
    }


def test_tampered_result_is_rejected_by_hmac_binding() -> None:
    values = list(lines_for("pass"))
    raw = json.dumps(
        {"schema_version": 1, "source_sha": SOURCE, "status": "fail"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    values[1] = marker(RESULT_MARKER, raw)
    with pytest.raises(RunPodV2Error, match="result_sha256"):
        authenticate_runpod_log_result(values, challenge=challenge(), secret_key=SECRET)


def test_duplicate_or_missing_markers_fail_closed() -> None:
    values = lines_for("pass")
    with pytest.raises(RunPodV2Error, match="exactly one"):
        authenticate_runpod_log_result(values + (values[1],), challenge=challenge(), secret_key=SECRET)
    with pytest.raises(RunPodV2Error, match="exactly one"):
        authenticate_runpod_log_result((values[1],), challenge=challenge(), secret_key=SECRET)
