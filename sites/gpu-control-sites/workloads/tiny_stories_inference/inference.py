"""Bounded inference with the pinned TinyStories 15M checkpoint."""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time

MODEL_ID = "karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin"
MODEL_SHA256 = "cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a"
TOKENIZER_SHA256 = "50a52ef822ee9e83de5ce9d0be0a025a773d019437f58b5ff9dcafb063ece361"
TEMPERATURE = 0.8
CHECKS = ["source_identity_present", "parameter_bounds", "model_digest_verified", "inference_completed",
          "non_root", "no_secret_environment", "no_docker_socket", "read_only_rootfs", "network_disabled"]
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def main() -> int:
    try:
        run_id = os.environ["GPU_CONTROL_RUN_ID"]
        source_sha = os.environ["GPU_CONTROL_SOURCE_SHA"]
        fingerprint = os.environ["GPU_CONTROL_PLAN_FINGERPRINT"]
        parameters = json.loads(os.environ["GPU_CONTROL_PARAMETERS_JSON"])
        runtime_seconds = int(os.environ["GPU_CONTROL_RUNTIME_SECONDS"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return 2
    if (not SHA40.fullmatch(source_sha) or not re.fullmatch(r"[0-9a-f]{32}", run_id) or
            not SHA64.fullmatch(fingerprint) or not isinstance(parameters, dict) or
            set(parameters) != {"max_new_tokens", "prompt", "seed"}):
        return 2
    prompt = parameters["prompt"]
    max_new_tokens = parameters["max_new_tokens"]
    seed = parameters["seed"]
    if (not isinstance(prompt, str) or not prompt or len(prompt.encode("utf-8", "strict")) > 128 or
            any(ord(char) < 0x20 or ord(char) == 0x7f for char in prompt) or
            type(max_new_tokens) is not int or not 1 <= max_new_tokens <= 32 or
            type(seed) is not int or not 1 <= seed <= 1000000 or
            not 1 <= runtime_seconds <= 30):
        return 2
    if os.getuid() != 10001 or os.path.exists("/var/run/docker.sock"):
        return 2
    forbidden = ("GITHUB_TOKEN", "MODAL_TOKEN_SECRET", "RUNPOD_API_KEY", "DATABASE_URL",
                 "GPU_CONTROL_RUNNER_BEARER_TOKEN", "GPU_CONTROL_SITES_SERVICE_TOKEN")
    if any(key in os.environ for key in forbidden):
        return 2
    try:
        with open("/work/write-probe", "w", encoding="utf-8") as probe:
            probe.write("unexpected")
    except OSError:
        pass
    else:
        return 2
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=0.2)
        return 2
    except OSError:
        pass
    if file_sha256("/work/stories15M.bin") != MODEL_SHA256 or file_sha256("/work/tokenizer.bin") != TOKENIZER_SHA256:
        return 2

    prompt_bytes = prompt.encode("utf-8")
    prompt_sha = hashlib.sha256(prompt_bytes).hexdigest()
    started = time.monotonic()
    try:
        generated = subprocess.run(
            ["/work/run", "/work/stories15M.bin", "-n", str(max_new_tokens), "-i", prompt,
             "-s", str(seed), "-t", str(TEMPERATURE), "-z", "/work/tokenizer.bin"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=max(1, runtime_seconds - 1), check=False,
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C", "TMPDIR": "/tmp"})
    except (OSError, subprocess.TimeoutExpired):
        return 3
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if generated.returncode != 0 or len(generated.stdout) > 2048 or generated.stderr[:64].startswith(b"Usage:"):
        return 3
    try:
        text = generated.stdout.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        return 3
    try:
        stderr = generated.stderr.decode("ascii", "strict")
    except UnicodeDecodeError:
        return 3
    token_counts = re.findall(r"^generated_tokens=(\d+)$", stderr, flags=re.MULTILINE)
    if (len(text.encode("utf-8")) > 1536 or not text.startswith(prompt) or text == prompt or
            len(token_counts) != 1 or not 1 <= int(token_counts[0]) <= max_new_tokens):
        return 3
    metrics = {"elapsed_ms": elapsed_ms, "generated_text": text, "generated_tokens": int(token_counts[0]),
               "max_new_tokens": max_new_tokens, "model_id": MODEL_ID, "model_sha256": MODEL_SHA256,
               "temperature": TEMPERATURE,
               "prompt_sha256": prompt_sha, "seed": seed}
    identity = {"run_id": run_id, "source_sha": source_sha, "plan_fingerprint": fingerprint,
                "metrics": metrics}
    result = {"schema_version": 1, "run_id": run_id, "source_sha": source_sha,
              "plan_fingerprint": fingerprint, "check": "tiny-stories-inference-v1", "status": "passed",
              "gpu_used": False, "checks": CHECKS, "metrics": metrics,
              "checksum": hashlib.sha256(canonical(identity)).hexdigest()}
    sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
