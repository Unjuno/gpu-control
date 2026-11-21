"""Narrow, non-configurable RunPod Serverless queue relay."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

RUNPOD_ORIGIN = "https://api.runpod.ai"
MAX_RESPONSE_BYTES = 1024 * 1024
ENDPOINT_ID = re.compile(r"^[A-Za-z0-9_-]{4,128}$")
JOB_ID = re.compile(r"^[A-Za-z0-9_-]{4,128}$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def upstream_path(endpoint_id: str, operation: str, job_id: str | None) -> str:
    if ENDPOINT_ID.fullmatch(endpoint_id) is None:
        raise ValueError("invalid_endpoint")
    if operation == "run" and job_id is None:
        return f"/v2/{endpoint_id}/run"
    if operation in {"status", "cancel"} and isinstance(job_id, str) and JOB_ID.fullmatch(job_id):
        return f"/v2/{endpoint_id}/{operation}/{job_id}"
    raise ValueError("invalid_operation")


def relay(method: str, path: str, authorization: str, body: bytes) -> tuple[int, bytes, dict[str, str]]:
    expected_method = "GET" if "/status/" in path else "POST"
    if method != expected_method or not authorization.startswith("Bearer ") or len(authorization) > 1024:
        raise ValueError("invalid_request")
    request = urllib.request.Request(
        RUNPOD_ORIGIN + path, data=body if method == "POST" else None, method=method,
        headers={"Authorization": authorization, "Accept": "application/json",
                 **({"Content-Type": "application/json"} if method == "POST" else {})},
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        response = opener.open(request, timeout=35)
    except urllib.error.HTTPError as exc:
        response = exc
    status = int(response.status)
    if 300 <= status <= 399:
        response.close()
        raise ValueError("redirect_rejected")
    data = response.read(MAX_RESPONSE_BYTES + 1)
    response.close()
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("response_too_large")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_response") from exc
    if not isinstance(value, dict):
        raise ValueError("invalid_response")
    return status, json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode(), {
        "content-type": "application/json"
    }
