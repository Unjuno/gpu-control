from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..completion import CompletionChallenge, CompletionEvidence, CompletionEvidenceError, verify_completion
from ..lifecycle import JobState
from ..results import ArtifactDisposition, OutputArtifact
from .runpod_v2 import RunPodV2Error


RESULT_MARKER = "GPU_CONTROL_RESULT_JSON_V1:"
COMPLETION_MARKER = "GPU_CONTROL_COMPLETION_JSON_V2:"
_MAX_DECODED_MARKER_BYTES = 128 * 1024


@dataclass(frozen=True)
class AuthenticatedRunPodLogResult:
    state: JobState
    result_bytes: bytes
    completion_bytes: bytes
    result_payload: Mapping[str, Any]
    completion_evidence: CompletionEvidence

    def artifacts(self, *, provider_job_id: str) -> tuple[OutputArtifact, ...]:
        result_sha = "sha256:" + hashlib.sha256(self.result_bytes).hexdigest()
        completion_sha = "sha256:" + hashlib.sha256(self.completion_bytes).hexdigest()
        return (
            OutputArtifact(
                name="result.json",
                sha256=result_sha,
                size_bytes=len(self.result_bytes),
                media_type="application/json",
                reference=f"runpod-v2:pod:{provider_job_id}:logs:{RESULT_MARKER[:-1]}",
                disposition=ArtifactDisposition.COLLECTED,
            ),
            OutputArtifact(
                name="completion.json",
                sha256=completion_sha,
                size_bytes=len(self.completion_bytes),
                media_type="application/json",
                reference=f"runpod-v2:pod:{provider_job_id}:logs:{COMPLETION_MARKER[:-1]}",
                disposition=ArtifactDisposition.COLLECTED,
            ),
        )


def _decode_one_marker(lines: Iterable[str], marker: str) -> bytes:
    matches = [line[len(marker):] for line in lines if line.startswith(marker)]
    if len(matches) != 1:
        raise RunPodV2Error(f"expected exactly one {marker[:-1]} log marker")
    encoded = matches[0]
    try:
        raw = base64.b64decode(encoded.encode("ascii"), altchars=b"-_", validate=True)
    except Exception as exc:
        raise RunPodV2Error(f"{marker[:-1]} marker is not valid base64url") from exc
    if len(raw) > _MAX_DECODED_MARKER_BYTES:
        raise RunPodV2Error(f"{marker[:-1]} marker exceeds bounded decoded size")
    return raw


def _json_object(raw: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunPodV2Error(f"{label} marker is not valid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise RunPodV2Error(f"{label} marker must contain a JSON object")
    return value


def authenticate_runpod_log_result(
    lines: Iterable[str],
    *,
    challenge: CompletionChallenge,
    secret_key: bytes,
) -> AuthenticatedRunPodLogResult:
    """Authenticate the bounded result/completion pair emitted by the workload."""

    line_values = tuple(lines)
    result_bytes = _decode_one_marker(line_values, RESULT_MARKER)
    completion_bytes = _decode_one_marker(line_values, COMPLETION_MARKER)
    result_payload = _json_object(result_bytes, "result")
    completion_payload = _json_object(completion_bytes, "completion")
    try:
        evidence = CompletionEvidence.from_dict(completion_payload)
        result_sha = "sha256:" + hashlib.sha256(result_bytes).hexdigest()
        verify_completion(
            challenge,
            evidence,
            secret_key=secret_key,
            expected_result_sha256=result_sha,
        )
    except CompletionEvidenceError as exc:
        raise RunPodV2Error(str(exc)) from exc

    if result_payload.get("source_sha") != challenge.source_sha:
        raise RunPodV2Error("authenticated result source_sha does not match completion challenge")
    status = result_payload.get("status")
    if status == "pass":
        state = JobState.SUCCEEDED
    elif status == "fail":
        state = JobState.FAILED
    else:
        raise RunPodV2Error("authenticated result status must be pass or fail")

    return AuthenticatedRunPodLogResult(
        state=state,
        result_bytes=result_bytes,
        completion_bytes=completion_bytes,
        result_payload=result_payload,
        completion_evidence=evidence,
    )
