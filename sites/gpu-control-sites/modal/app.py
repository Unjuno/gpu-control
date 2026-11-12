"""Authenticated Modal control endpoint for the fixed TinyStories CPU workload.

Deploy with Modal's proxy-token authentication enabled. The endpoint can only
create the pinned Sandbox image and fixed entrypoint below; request bodies carry
parameters, never a command, image, URL, provider credential, or owner identity.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import modal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from gpu_control_modal_bootstrap import normalize_exit_code, preflight_exit_code_map, sandbox_entrypoint

APP_NAME = "gpu-control-sites"
REPOSITORY = "Unjuno/gpu-control"
WORKLOAD = "tiny-stories-inference-v1"
WORKLOAD_SOURCE_SHA = "3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288"
REGISTERED_IMAGE_DIGEST = "sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541"
MODEL_ID = "karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin"
MODEL_SHA256 = "cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a"
TOKENIZER_SHA256 = "50a52ef822ee9e83de5ce9d0be0a025a773d019437f58b5ff9dcafb063ece361"
MAX_RUNTIME_SECONDS = 30
MAX_STDOUT_BYTES = 4096
MAX_STDERR_BYTES = 2048
RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SHA64_RE = re.compile(r"^[0-9a-f]{64}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
# Modal ignores Dockerfile USER and launches the image entrypoint as root.
# Drop privileges in this fixed bootstrap before executing the pinned workload.
SANDBOX_ENTRYPOINT = sandbox_entrypoint()

REMOTE_SITE_ROOT = Path("/root/gpu-control-sites")


def resolve_site_root(module_file: str | Path, remote_site_root: Path = REMOTE_SITE_ROOT) -> Path:
    """Find the packaged Site source both during deploy and in Modal imports."""
    module_path = Path(module_file).resolve()
    for parent in module_path.parents:
        if (parent / "workloads" / "tiny_stories_inference" / "Dockerfile").is_file():
            return parent
    if (remote_site_root / "workloads" / "tiny_stories_inference" / "Dockerfile").is_file():
        return remote_site_root
    raise RuntimeError("packaged gpu-control Site workload source is unavailable")


SITE_ROOT = resolve_site_root(__file__)
REPOSITORY_ROOT = next((parent for parent in SITE_ROOT.parents if (parent / ".git").exists()), None)
DOCKERFILE = SITE_ROOT / "workloads" / "tiny_stories_inference" / "Dockerfile"
INFERENCE = SITE_ROOT / "workloads" / "tiny_stories_inference" / "inference.py"
LLAMA2_C = SITE_ROOT / "workloads" / "third_party" / "llama2.c" / "run.c"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def workload_image_fingerprint() -> str:
    """Fingerprint all mutable local build inputs and the pinned model assets."""
    manifest = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "source_sha": WORKLOAD_SOURCE_SHA,
        "dockerfile_sha256": _sha256(DOCKERFILE.read_bytes()),
        "inference_sha256": _sha256(INFERENCE.read_bytes()),
        "llama2_c_sha256": _sha256(LLAMA2_C.read_bytes()),
        "model_id": MODEL_ID,
        "model_sha256": MODEL_SHA256,
        "tokenizer_sha256": TOKENIZER_SHA256,
        "entrypoint": ["python", "-I", "/work/inference.py"],
        "sandbox_entrypoint": list(SANDBOX_ENTRYPOINT),
        "preflight_exit_code_map": {
            str(code): diagnostic for code, diagnostic in sorted(preflight_exit_code_map().items())
        },
        "sandbox": {"cpu": 1, "memory_mib": 512, "network": "blocked", "max_runtime_seconds": MAX_RUNTIME_SECONDS},
    }
    return _sha256(_canonical(manifest))


WORKLOAD_IMAGE_FINGERPRINT = workload_image_fingerprint()


def verify_registered_source() -> None:
    """Reject source drift locally and verify pinned inputs after remote import."""
    expected_paths = (
        ("sites/gpu-control-sites/runner/tiny_stories_inference/inference.py", INFERENCE,
         "ac4f1e6cc248d29112119ae4c689287942f58055fbc9499aa500df21e5fc1351"),
        ("sites/gpu-control-sites/runner/third_party/llama2.c/run.c", LLAMA2_C,
         "78951c4623437da86cc5d835ea26af8c750c5132dfeb6e506c4a2db918e61682"),
    )
    for historical_path, current_path, expected_sha256 in expected_paths:
        if REPOSITORY_ROOT is not None:
            expected = subprocess.run(
                ["git", "show", f"{WORKLOAD_SOURCE_SHA}:{historical_path}"],
                cwd=REPOSITORY_ROOT, check=True, capture_output=True,
            ).stdout
            if expected != current_path.read_bytes():
                raise RuntimeError(f"registered workload source mismatch: {current_path.name}")
        elif _sha256(current_path.read_bytes()) != expected_sha256:
            raise RuntimeError(f"registered workload source digest mismatch: {current_path.name}")


verify_registered_source()

app = modal.App(APP_NAME)
workload_image = modal.Image.from_dockerfile(
    str(DOCKERFILE),
    context_dir=str(SITE_ROOT),
    build_args={"SOURCE_REPOSITORY": REPOSITORY, "SOURCE_SHA": WORKLOAD_SOURCE_SHA},
)
api_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(SITE_ROOT / "modal" / "requirements.txt"))
    .add_local_python_source("gpu_control_modal_bootstrap")
    .add_local_dir(str(SITE_ROOT / "workloads"), remote_path=str(REMOTE_SITE_ROOT / "workloads"), copy=True)
)
api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _validate_payload(run_id: str, payload: object) -> dict[str, Any]:
    if not RUN_ID_RE.fullmatch(run_id) or not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="INVALID_REQUEST")
    required = {"workload", "repository", "source_sha", "registered_image_digest",
                "image_fingerprint", "plan_fingerprint", "parameters", "runtime_seconds"}
    if set(payload) != required:
        raise HTTPException(status_code=400, detail="INVALID_REQUEST")
    if (payload["workload"] != WORKLOAD or payload["repository"] != REPOSITORY or
            payload["source_sha"] != WORKLOAD_SOURCE_SHA or
            payload["registered_image_digest"] != REGISTERED_IMAGE_DIGEST or
            payload["image_fingerprint"] != WORKLOAD_IMAGE_FINGERPRINT or
            not isinstance(payload["plan_fingerprint"], str) or
            not SHA64_RE.fullmatch(payload["plan_fingerprint"])):
        raise HTTPException(status_code=409, detail="REGISTERED_WORKLOAD_MISMATCH")
    params = payload["parameters"]
    if (not isinstance(params, dict) or set(params) != {"max_new_tokens", "prompt", "seed"} or
            not isinstance(params["prompt"], str) or not 1 <= len(params["prompt"].encode("utf-8")) <= 128 or
            any(ord(c) < 0x20 or ord(c) == 0x7f for c in params["prompt"]) or
            type(params["max_new_tokens"]) is not int or not 1 <= params["max_new_tokens"] <= 32 or
            type(params["seed"]) is not int or not 1 <= params["seed"] <= 1_000_000 or
            type(payload["runtime_seconds"]) is not int or
            not 1 <= payload["runtime_seconds"] <= MAX_RUNTIME_SECONDS):
        raise HTTPException(status_code=400, detail="INVALID_PARAMETERS")
    return payload


def _sandbox_name(run_id: str) -> str:
    return f"gpu-control-{run_id}"


def _find_sandbox(run_id: str):
    try:
        return modal.Sandbox.from_name(APP_NAME, _sandbox_name(run_id), include_terminated=True)
    except modal.exception.NotFoundError:
        return None


def _bounded_stream(stream, maximum: int) -> tuple[str, bool]:
    out = bytearray()
    truncated = False
    for chunk in stream:
        raw = chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk)
        remaining = maximum - len(out)
        out.extend(raw[:remaining])
        if len(raw) > remaining:
            truncated = True
            break
    return out.decode("utf-8", errors="replace"), truncated


def _capture(sandbox, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    raw_exit_code = sandbox.poll()
    if raw_exit_code is None:
        return {"state": "running", "sandbox_id": sandbox.object_id,
                "cleanup_state": "pending", "image_id": workload_image.object_id}
    exit_code, diagnostic_code = normalize_exit_code(raw_exit_code)
    stdout, stdout_truncated = _bounded_stream(sandbox.stdout, MAX_STDOUT_BYTES)
    stderr, stderr_truncated = _bounded_stream(sandbox.stderr, MAX_STDERR_BYTES)
    try:
        lines = [line for line in stdout.splitlines() if line.strip()]
        result = json.loads(lines[-1]) if lines and not stdout_truncated else None
    except (ValueError, IndexError):
        result = None
    if result is not None and (
        result.get("run_id") != run_id or
        result.get("source_sha") != WORKLOAD_SOURCE_SHA or
        result.get("plan_fingerprint") != payload["plan_fingerprint"] or
        result.get("check") != WORKLOAD or
        result.get("status") != "passed"
    ):
        result = None
    diagnostic_match = re.search(r"^GPU_CONTROL_PREFLIGHT_RETURN_LINE=([1-9][0-9]{0,3})$", stderr, re.MULTILINE) if exit_code == 2 else None
    system_exit_match = re.search(r"^GPU_CONTROL_SANDBOX_SYSTEM_EXIT=2$", stderr, re.MULTILINE) if exit_code == 2 else None
    sandbox_id = sandbox.object_id
    try:
        sandbox.terminate(wait=True)
        cleanup_state = "confirmed"
    except modal.exception.NotFoundError:
        cleanup_state = "confirmed"
    except Exception:
        cleanup_state = "pending"
    state = "succeeded" if exit_code == 0 and result is not None and cleanup_state == "confirmed" else "failed"
    return {
        "state": state,
        "sandbox_id": sandbox_id,
        "exit_code": exit_code,
        "cleanup_state": cleanup_state,
        "image_id": workload_image.object_id,
        "image_fingerprint": WORKLOAD_IMAGE_FINGERPRINT,
        "result": result,
        "stderr": stderr,
        "diagnostic_code": diagnostic_code or (
            f"PREFLIGHT_RETURN_LINE_{diagnostic_match.group(1)}" if diagnostic_match else
            "PREFLIGHT_SYSTEM_EXIT_2" if system_exit_match else None
        ),
        "logs_truncated": stdout_truncated or stderr_truncated,
    }


@api.get("/v1/health")
def health() -> dict[str, Any]:
    return {"ready": True, "provider": "modal_cpu", "workload": WORKLOAD,
            "source_sha": WORKLOAD_SOURCE_SHA, "registered_image_digest": REGISTERED_IMAGE_DIGEST,
            "image_fingerprint": WORKLOAD_IMAGE_FINGERPRINT, "max_runtime_seconds": MAX_RUNTIME_SECONDS}


@api.post("/v1/runs/{run_id}/submit")
async def submit(run_id: str, request: Request):
    payload = _validate_payload(run_id, await request.json())
    existing = _find_sandbox(run_id)
    if existing is not None:
        return _capture(existing, run_id, payload)
    try:
        sandbox = modal.Sandbox.create(
            *SANDBOX_ENTRYPOINT,
            app=app,
            image=workload_image,
            name=_sandbox_name(run_id),
            timeout=payload["runtime_seconds"],
            cpu=1,
            memory=512,
            block_network=True,
            env={
                "GPU_CONTROL_RUN_ID": run_id,
                "GPU_CONTROL_SOURCE_SHA": WORKLOAD_SOURCE_SHA,
                "GPU_CONTROL_PLAN_FINGERPRINT": payload["plan_fingerprint"],
                "GPU_CONTROL_PARAMETERS_JSON": json.dumps(payload["parameters"], sort_keys=True, separators=(",", ":")),
                "GPU_CONTROL_RUNTIME_SECONDS": str(payload["runtime_seconds"]),
                "GPU_CONTROL_MODAL_IMAGE_FINGERPRINT": WORKLOAD_IMAGE_FINGERPRINT,
            },
        )
    except modal.exception.AlreadyExistsError:
        # A concurrent retry won the deterministic-name reservation; attach to it.
        sandbox = _find_sandbox(run_id)
        if sandbox is None:
            raise HTTPException(status_code=503, detail="SUBMISSION_STATE_UNKNOWN")
    return _capture(sandbox, run_id, payload)


@api.post("/v1/runs/{run_id}/status")
async def status(run_id: str, request: Request):
    payload = _validate_payload(run_id, await request.json())
    sandbox = _find_sandbox(run_id)
    if sandbox is None:
        return JSONResponse({"state": "not_found", "cleanup_state": "unknown"}, status_code=404)
    return _capture(sandbox, run_id, payload)


@api.post("/v1/runs/{run_id}/cancel")
async def cancel(run_id: str, request: Request):
    payload = _validate_payload(run_id, await request.json())
    sandbox = _find_sandbox(run_id)
    if sandbox is None:
        return {"state": "not_found", "cleanup_state": "unknown"}
    sandbox_id = sandbox.object_id
    try:
        sandbox.terminate(wait=True)
    except modal.exception.NotFoundError:
        pass
    return {"state": "cancelled", "sandbox_id": sandbox_id, "cleanup_state": "confirmed",
            "image_id": workload_image.object_id,
            "image_fingerprint": WORKLOAD_IMAGE_FINGERPRINT}


@app.function(image=api_image, timeout=60, cpu=1, memory=512, max_containers=1)
@modal.asgi_app(requires_proxy_auth=True)
def control_api():
    return api
