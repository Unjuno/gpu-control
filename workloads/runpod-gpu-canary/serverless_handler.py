#!/usr/bin/env python3
"""Strict Runpod Serverless wrapper for the registered GPU canary."""
from __future__ import annotations

import os
import re
import subprocess

HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
B64_32 = re.compile(r"^[A-Za-z0-9+/]{43}=$")
EXPECTED_KEYS = {
    "schema_version", "run_id", "plan_fingerprint", "nonce", "completion_key_b64",
    "completion_key_id", "source_sha", "image_digest", "execution_name",
}


def handler(job: dict) -> dict:
    value = job.get("input")
    if not isinstance(value, dict) or set(value) != EXPECTED_KEYS or value.get("schema_version") != 1:
        raise ValueError("INVALID_REGISTERED_WORKLOAD_INPUT")
    run_id = value.get("run_id", "")
    if not HEX32.fullmatch(run_id) or not HEX64.fullmatch(value.get("plan_fingerprint", "")) or not HEX64.fullmatch(value.get("nonce", "")):
        raise ValueError("INVALID_EXECUTION_BINDING")
    if not B64_32.fullmatch(value.get("completion_key_b64", "")) or not HEX32.fullmatch(value.get("completion_key_id", "")) or not HEX40.fullmatch(value.get("source_sha", "")):
        raise ValueError("INVALID_EXECUTION_BINDING")
    if value.get("execution_name") != f"gpu-control-{run_id[:12]}":
        raise ValueError("INVALID_EXECUTION_NAME")
    if value.get("source_sha") != os.environ.get("GPU_CONTROL_SOURCE_SHA") or value.get("image_digest") != os.environ.get("GPU_CONTROL_IMAGE_DIGEST"):
        raise ValueError("IMMUTABLE_WORKLOAD_MISMATCH")
    child_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "GPU_CONTROL_COMPLETION_KEY_B64": value["completion_key_b64"],
        "GPU_CONTROL_COMPLETION_KEY_ID": value["completion_key_id"],
        "GPU_CONTROL_IMAGE_DIGEST": value["image_digest"],
        "GPU_CONTROL_SOURCE_SHA": value["source_sha"],
        "GPU_CONTROL_EXECUTION_NAME": value["execution_name"],
    }
    completed = subprocess.run(
        ["/opt/gpu-control/run-registered-workload", "--plan-fingerprint", value["plan_fingerprint"], "--nonce", value["nonce"]],
        check=False, capture_output=True, text=True, timeout=25, env=child_env,
    )
    lines = completed.stdout.splitlines()
    if completed.returncode != 0 or len(lines) != 2 or any(len(line.encode()) > 65536 for line in lines):
        raise RuntimeError("REGISTERED_WORKLOAD_FAILED")
    return {"schema_version": 1, "lines": lines}


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler})
