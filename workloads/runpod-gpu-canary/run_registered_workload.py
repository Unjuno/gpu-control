#!/usr/bin/env python3
"""Root-owned signer for the fixed, unprivileged GPU canary."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time

RESULT_MARKER = "GPU_CONTROL_RESULT_JSON_V1:"
COMPLETION_MARKER = "GPU_CONTROL_COMPLETION_JSON_V3:"

def canonical(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()

def main() -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--plan-fingerprint", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--steps", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args()
    if not (len(args.plan_fingerprint) == 64 and all(c in "0123456789abcdef" for c in args.plan_fingerprint)):
        parser.error("invalid plan fingerprint")
    if not (len(args.nonce) == 64 and all(c in "0123456789abcdef" for c in args.nonce)):
        parser.error("invalid nonce")
    if not 1 <= args.steps <= 200 or not 1 <= args.seed <= 1_000_000:
        parser.error("bounded numeric input required")

    key_b64 = os.environ.pop("GPU_CONTROL_COMPLETION_KEY_B64", "")
    key_id = os.environ.pop("GPU_CONTROL_COMPLETION_KEY_ID", "")
    image_digest = os.environ.get("GPU_CONTROL_IMAGE_DIGEST", "")
    source_sha = os.environ.get("GPU_CONTROL_SOURCE_SHA", "")
    execution_name = os.environ.get("GPU_CONTROL_EXECUTION_NAME", "")
    try:
        key = base64.b64decode(key_b64, validate=True)
    except Exception:
        return 64
    if len(key) < 32 or not key_id or not execution_name:
        return 64

    child_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GPU_CONTROL_CONFIG_JSON": json.dumps({"steps": args.steps}, separators=(",", ":")),
    }
    started = time.time()
    completed = subprocess.run(
        [sys.executable, "-I", "/opt/gpu-control/tiny_lm.py", "--backend", "torch", "--device", "cuda"],
        check=False, capture_output=True, text=True, timeout=20, env=child_env,
        preexec_fn=lambda: (os.setgid(10001), os.setuid(10001)),
    )
    if completed.returncode != 0 or len(completed.stdout.encode()) > 8192:
        return completed.returncode or 70
    try:
        result = json.loads(completed.stdout)
    except Exception:
        return 70
    if result.get("gpu_used") is not True or result.get("device") != "cuda":
        return 70
    result.update({"seed": args.seed, "provider": "runpod_gpu", "source_sha": source_sha,
                   "image_digest": image_digest, "execution_name": execution_name,
                   "elapsed_wall_seconds": time.time() - started})
    result_bytes = canonical(result)
    result_sha256 = hashlib.sha256(result_bytes).hexdigest()
    completion = {
        "schema_version": 3, "key_id": key_id, "nonce": args.nonce,
        "plan_fingerprint": args.plan_fingerprint, "execution_name": execution_name,
        "source_sha": source_sha, "image_digest": image_digest,
        "result_sha256": result_sha256, "process_exit_code": 0,
    }
    completion["mac_sha256"] = hmac.new(key, canonical(completion), hashlib.sha256).hexdigest()
    print(RESULT_MARKER + base64.b64encode(result_bytes).decode())
    print(COMPLETION_MARKER + base64.b64encode(canonical(completion)).decode())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
