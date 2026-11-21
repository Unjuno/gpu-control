"""Authenticated Modal adapter for registered external and Modal GPU work.

This is infrastructure for two of the four compute providers, not another
provider or a general Gateway.  It has no PostgreSQL dependency and no API for
arbitrary code, commands, images, URLs, repositories, or credentials.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import modal
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


APP_NAME = "gpu-control-provider-adapter"
SOURCE_SHA = "44a1b806160ab5bc721a370d034a6dfcb28f27a8"
MAX_BODY_BYTES = 64 * 1024
MAX_CLOCK_SKEW_SECONDS = 60
MAX_LIFETIME_SECONDS = 120
TOOLS = re.compile(r"^(?:experiment_(?:capabilities|prepare|submit|status|result|artifact|cancel|list)|runpod_queue_request)$")
OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$")
NONCE = re.compile(r"^[0-9a-f]{32}$")
RUNPOD_ENDPOINT_ID = "wwlos460xbfw5q"

REPOSITORY_ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "gateway" / "gpu_gateway").is_dir()),
    Path("/root"),
)
PROVIDER_MODULE_ROOT = REPOSITORY_ROOT / "gateway" / "gpu_gateway"
MODAL_ROOT = REPOSITORY_ROOT / "sites" / "gpu-control-sites" / "modal"
WORKLOAD_ROOT = REPOSITORY_ROOT / "gateway" / "workloads"

# The provider adapter deliberately vendors only the reviewed Kaggle/Hugging
# Face implementation modules.  Copying the old Gateway tree would also ship
# PostgreSQL, OAuth, worker, and service code that is not part of the Sites
# control plane and must never become an accidental deployment dependency.
PROVIDER_MODULES = (
    "__init__.py",
    "backends.py",
    "config.py",
    "huggingface_artifacts.py",
    "huggingface_space_backend.py",
    "kaggle_backend.py",
    "kaggle_bridge.py",
    "orbitune_workload.py",
)

app = modal.App(APP_NAME)
data_volume = modal.Volume.from_name("gpu-control-provider-adapter-data", create_if_missing=True)
nonce_store = modal.Dict.from_name("gpu-control-provider-adapter-nonces", create_if_missing=True)
submission_store = modal.Dict.from_name("gpu-control-provider-adapter-submissions", create_if_missing=True)
provider_secret = modal.Secret.from_name("gpu-control-worker")
adapter_auth_secret = modal.Secret.from_name("gpu-control-provider-adapter-auth")

adapter_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install(
        "fastapi==0.162.2", "pydantic==2.13.4", "jsonschema==4.26.0",
        "cryptography==46.0.4", "kaggle==2.2.5", "six==1.17.0",
        "huggingface_hub==2.4.0", "gradio_client==2.7.2",
    )
    .run_commands(
        f"mkdir -p /opt/orbitune-cache && git clone --filter=blob:none https://github.com/Unjuno/orbitune.git /opt/orbitune-cache/{SOURCE_SHA}",
        f"git -C /opt/orbitune-cache/{SOURCE_SHA} checkout --detach {SOURCE_SHA}",
        f"test \"$(git -C /opt/orbitune-cache/{SOURCE_SHA} rev-parse HEAD)\" = {SOURCE_SHA}",
        f"test -z \"$(git -C /opt/orbitune-cache/{SOURCE_SHA} status --porcelain --untracked-files=all)\"",
    )
    .run_commands("mkdir -p /root/provider-runtime/gpu_gateway")
)
for provider_module in PROVIDER_MODULES:
    adapter_image = adapter_image.add_local_file(
        str(PROVIDER_MODULE_ROOT / provider_module),
        remote_path=f"/root/provider-runtime/gpu_gateway/{provider_module}",
        copy=True,
    )
adapter_image = (
    adapter_image
    .add_local_dir(str(WORKLOAD_ROOT), remote_path="/root/provider-runtime/workloads", copy=True)
    .add_local_dir(str(MODAL_ROOT), remote_path="/root/site-modal", copy=True)
    .env({"PYTHONPATH": "/root/provider-runtime:/root/site-modal"})
)

api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

SAFE_PROVIDER_FAILURE_CODES = {
    "Kaggle worker token is not configured": "kaggle_token_not_configured",
    "Kaggle quota failed": "kaggle_quota_unavailable",
    "Kaggle quota returned invalid JSON": "kaggle_quota_invalid",
    "Kaggle quota returned an invalid object": "kaggle_quota_invalid",
    "Kaggle GPU quota is unknown or insufficient": "kaggle_quota_insufficient",
    "Kaggle latest snapshot failed": "kaggle_latest_snapshot_failed",
    "Kaggle latest snapshot returned invalid JSON": "kaggle_latest_snapshot_invalid",
    "Kaggle latest snapshot returned an invalid object": "kaggle_latest_snapshot_invalid",
    "Kaggle submission outcome unknown": "kaggle_submission_unknown",
}


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"code": code}, status_code=status)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _auth_key() -> tuple[str, bytes]:
    key_id = os.environ.get("PROVIDER_ADAPTER_KEY_ID", "")
    encoded = os.environ.get("PROVIDER_ADAPTER_HMAC_KEY_B64", "")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", key_id) is None:
        raise RuntimeError("adapter auth is not configured")
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("adapter auth is not configured") from exc
    if not 32 <= len(key) <= 4096:
        raise RuntimeError("adapter auth is not configured")
    return key_id, key


def _verify(raw: bytes, signature: str | None, expected_tool: str) -> tuple[str, str, dict[str, Any]]:
    if not raw or len(raw) > MAX_BODY_BYTES or not isinstance(signature, str) or re.fullmatch(r"[0-9a-f]{64}", signature) is None:
        raise ValueError("invalid_delegation")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_delegation") from exc
    if not isinstance(payload, dict) or _canonical(payload) != raw or set(payload) != {
        "version", "key_id", "owner", "tool", "arguments", "nonce", "issued_at", "expires_at"
    }:
        raise ValueError("invalid_delegation")
    key_id, key = _auth_key()
    if payload["version"] != 1 or payload["key_id"] != key_id or not hmac.compare_digest(
            hmac.new(key, raw, hashlib.sha256).hexdigest(), signature):
        raise PermissionError("invalid_delegation")
    owner, tool, arguments = payload["owner"], payload["tool"], payload["arguments"]
    nonce, issued, expires = payload["nonce"], payload["issued_at"], payload["expires_at"]
    now = int(time.time())
    if (not isinstance(owner, str) or OWNER.fullmatch(owner) is None or
            not isinstance(tool, str) or TOOLS.fullmatch(tool) is None or tool != expected_tool or
            not isinstance(arguments, dict) or not isinstance(nonce, str) or NONCE.fullmatch(nonce) is None or
            type(issued) is not int or type(expires) is not int or issued > now + MAX_CLOCK_SKEW_SECONDS or
            expires < now or expires <= issued or expires - issued > MAX_LIFETIME_SECONDS or
            issued < now - MAX_LIFETIME_SECONDS - MAX_CLOCK_SKEW_SECONDS):
        raise ValueError("invalid_delegation")
    previous = nonce_store.get(nonce)
    if previous is not None:
        raise FileExistsError("delegation_replayed")
    nonce_store[nonce] = expires
    return owner, tool, arguments


def _service():
    if "/root/provider-runtime" not in sys.path:
        sys.path.insert(0, "/root/provider-runtime")
    if "/root/site-modal" not in sys.path:
        sys.path.insert(0, "/root/site-modal")
    from gpu_gateway.config import Settings
    from gpu_gateway.huggingface_artifacts import HuggingFaceArtifactStore
    from gpu_gateway.huggingface_space_backend import HuggingFaceSpaceBackend
    from gpu_gateway.kaggle_backend import KaggleBackend
    from modal_gpu_backend import ModalGpuBackend
    from provider_adapter_core import ProviderAdapter

    kaggle_token = os.environ.get("KAGGLE_API_TOKEN", "")
    hf_write = os.environ.get("HF_ARTIFACT_WRITE_TOKEN", "")
    hf_read = os.environ.get("HF_SPACE_READ_TOKEN", "")
    settings = Settings(
        enable_kaggle=bool(kaggle_token), kaggle_api_token=kaggle_token,
        kaggle_username="UnjunoOrg", kaggle_staging_root="/data/kaggle-stage",
        kaggle_source_cache_root="/opt/orbitune-cache",
        enable_huggingface_space=bool(hf_read), hf_space_read_token=hf_read,
        hf_artifact_write_token=hf_write,
        hf_artifact_repositories=("Unjuno/gpu-control-orbitune-artifacts",),
        hf_space_allowlist=("Unjuno/gpu-control-orbitune-zero-gpu",),
        max_output_bytes=65536,
    )
    settings.validate()
    kaggle = KaggleBackend(settings, artifact_store=HuggingFaceArtifactStore(settings)) if kaggle_token else None
    huggingface = HuggingFaceSpaceBackend(settings) if hf_read else None
    return ProviderAdapter(kaggle, huggingface, ModalGpuBackend())


def _submission_binding(owner: str) -> str:
    return hashlib.sha256(owner.encode("utf-8")).hexdigest()


def _queued_handle(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": run["plan"]["provider"],
        "run_id": run["id"],
        "plan_fingerprint": run["fingerprint"],
        "transport": "modal_spawn_v1",
    }


def _queued_response(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "status": "pending",
        "human_summary": "登録済み無料providerへの投入を受け付けました。",
        "machine_state": {
            "run_id": run["id"], "state": "queued",
            "provider": run["plan"]["provider"],
            "provider_handle": _queued_handle(run),
        },
        "next_allowed_actions": ["experiment_status", "experiment_cancel"],
        "blocking_reason": None,
    }


@app.function(
    image=adapter_image, secrets=[provider_secret, adapter_auth_secret],
    volumes={"/data": data_volume}, timeout=120, cpu=1, memory=1024,
    max_containers=1,
)
def provider_submit_worker(owner: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run slow provider submission outside the bounded Sites HTTP request."""
    run_id = arguments.get("run_id", "")
    failure_stage = "service_initialization"
    try:
        service = _service()
        failure_stage = "submission_validation"
        run = service.validate_submission(owner, arguments)
        failure_stage = "claim_verification"
        record = submission_store.get(run_id)
        expected = {
            "owner_binding_sha256": _submission_binding(owner),
            "plan_fingerprint": run["fingerprint"],
        }
        if not isinstance(record, dict) or any(record.get(key) != value for key, value in expected.items()):
            raise RuntimeError("submission claim mismatch")
        submission_store.put(run_id, {**record, "state": "running"})
        failure_stage = "provider_submission"
        response = service.submit_validated(run)
        failure_stage = "submission_persistence"
        submission_store.put(run_id, {**record, "state": "submitted", "response": response})
        data_volume.commit()
        return response
    except Exception as exc:
        from provider_adapter_core import AdapterError
        code = exc.code if isinstance(exc, AdapterError) else SAFE_PROVIDER_FAILURE_CODES.get(
            str(exc), "provider_operation_failed")
        record = submission_store.get(run_id, {})
        # Keep diagnostics private and non-sensitive: never persist provider
        # stderr, exception text, credentials, paths, or request arguments.
        # The stable stage and Python exception class are sufficient to
        # distinguish adapter bugs from provider/quota failures.
        submission_store.put(run_id, {
            **record, "state": "failed", "error_code": code,
            "failure_stage": failure_stage,
            "exception_type": type(exc).__name__[:64],
        })
        return {"schema_version": 2, "status": "error", "code": code}


def _async_submit(owner: str, arguments: dict[str, Any]) -> dict[str, Any]:
    service = _service()
    run = service.validate_submission(owner, arguments)
    run_id = run["id"]
    binding = _submission_binding(owner)
    claim = {
        "schema_version": 1, "state": "claimed", "run_id": run_id,
        "provider": run["plan"]["provider"],
        "plan_fingerprint": run["fingerprint"],
        "owner_binding_sha256": binding, "claimed_at": int(time.time()),
    }
    inserted = submission_store.put(run_id, claim, skip_if_exists=True)
    record = claim if inserted else submission_store.get(run_id)
    if (not isinstance(record, dict) or record.get("owner_binding_sha256") != binding or
            record.get("plan_fingerprint") != run["fingerprint"] or
            record.get("provider") != run["plan"]["provider"]):
        from provider_adapter_core import AdapterError
        raise AdapterError("submission_identity_conflict", 409)
    if inserted:
        try:
            provider_submit_worker.spawn(owner, arguments)
        except Exception:
            submission_store.put(run_id, {**claim, "state": "failed", "error_code": "provider_spawn_failed"})
            raise
    if record.get("state") == "submitted" and isinstance(record.get("response"), dict):
        return record["response"]
    if record.get("state") == "failed":
        from provider_adapter_core import AdapterError
        raise AdapterError(str(record.get("error_code", "provider_operation_failed")), 503)
    return _queued_response(run)


def _async_observe(owner: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    handle = arguments.get("provider_handle")
    if not isinstance(handle, dict) or handle.get("transport") != "modal_spawn_v1":
        return None
    run_id = arguments.get("run_id")
    record = submission_store.get(run_id)
    if (not isinstance(record, dict) or record.get("owner_binding_sha256") != _submission_binding(owner) or
            record.get("plan_fingerprint") != handle.get("plan_fingerprint") or
            record.get("provider") != handle.get("provider")):
        from provider_adapter_core import AdapterError
        raise AdapterError("provider_handle_mismatch", 409)
    if record.get("state") == "failed":
        return {
            "schema_version": 2, "status": "error",
            "human_summary": "providerへの投入に失敗しました。",
            "machine_state": {"run_id": run_id, "state": "failed", "provider": record["provider"],
                              "provider_resource_created": False, "cleanup_state": "confirmed"},
            "next_allowed_actions": [],
            "blocking_reason": str(record.get("error_code", "PROVIDER_OPERATION_FAILED")).upper(),
        }
    response = record.get("response")
    actual = response.get("machine_state", {}).get("provider_handle") if isinstance(response, dict) else None
    if isinstance(actual, dict):
        return _service().observe(tool, {**arguments, "provider_handle": actual})
    if tool == "experiment_cancel":
        return {
            "schema_version": 2, "status": "blocked",
            "human_summary": "provider投入処理中のため、状態確定後に取消を再試行してください。",
            "machine_state": {"run_id": run_id, "state": record.get("state", "queued"),
                              "provider": record["provider"], "provider_handle": handle},
            "next_allowed_actions": ["experiment_status"],
            "blocking_reason": "SUBMISSION_IN_PROGRESS",
        }
    return {
        "schema_version": 2, "status": "pending",
        "human_summary": "provider投入処理中です。",
        "machine_state": {"run_id": run_id, "state": record.get("state", "queued"),
                          "provider": record["provider"], "provider_handle": handle},
        "next_allowed_actions": ["experiment_status", "experiment_cancel"],
        "blocking_reason": None,
    }


def _runpod_key() -> str:
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not 20 <= len(key) <= 512 or re.search(r"[\s\x00-\x1f\x7f]", key):
        raise ValueError("runpod_not_configured")
    return key


def _runpod_relay(owner: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Perform one fixed RunPod operation under the signed Sites envelope.

    A create is claimed before network I/O and is never sent twice. Status and
    cancellation must match the owner, plan, run and provider job recorded by
    that claim. Read-only endpoint/catalog checks are also fixed operations;
    callers cannot supply a URL, endpoint, method or authorization header.
    """
    from runpod_relay import relay, upstream_path

    operation = arguments.get("operation")
    if operation in {"endpoint", "catalog"}:
        if set(arguments) != {"operation"}:
            raise ValueError("invalid_request")
        path = (f"/v2/serverless/{RUNPOD_ENDPOINT_ID}" if operation == "endpoint"
                else "/v2/catalog/gpus")
        status, body, _headers = relay("GET", path, f"Bearer {_runpod_key()}", b"")
        return {"status": status, "body": json.loads(body)}

    required = {"operation", "run_id", "plan_fingerprint"}
    if operation == "run":
        required.add("body")
    elif operation == "receipt":
        pass
    elif operation in {"status", "cancel"}:
        required.add("job_id")
    else:
        raise ValueError("invalid_operation")
    if set(arguments) != required:
        raise ValueError("invalid_request")
    run_id = arguments.get("run_id")
    fingerprint = arguments.get("plan_fingerprint")
    if (not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None or
            not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None):
        raise ValueError("invalid_execution_binding")
    binding = {
        "owner_binding_sha256": _submission_binding(owner),
        "plan_fingerprint": fingerprint,
    }
    claim_key = f"runpod:{run_id}"

    if operation == "receipt":
        record = submission_store.get(claim_key)
        if not isinstance(record, dict) or any(record.get(k) != v for k, v in binding.items()):
            raise ValueError("provider_handle_mismatch")
        response = record.get("response")
        if (record.get("state") == "completed" and isinstance(response, dict) and
                isinstance(response.get("status"), int) and 200 <= response["status"] < 300 and
                isinstance(response.get("body"), dict)):
            return {"state": "completed", "response": response["body"]}
        return {"state": "pending" if record.get("state") == "claimed" else "uncertain"}

    if operation == "run":
        request_body = arguments["body"]
        expected_input = request_body.get("input") if isinstance(request_body, dict) else None
        expected_policy = request_body.get("policy") if isinstance(request_body, dict) else None
        if (not isinstance(request_body, dict) or set(request_body) != {"input", "policy"} or not isinstance(expected_input, dict) or
                set(expected_input) != {"schema_version", "run_id", "plan_fingerprint", "nonce",
                                        "completion_key_b64", "completion_key_id", "source_sha",
                                        "image_digest", "execution_name"} or
                expected_input.get("schema_version") != 1 or expected_input.get("run_id") != run_id or
                expected_input.get("plan_fingerprint") != fingerprint or
                expected_input.get("execution_name") != f"gpu-control-{run_id[:12]}" or
                not isinstance(expected_policy, dict) or expected_policy != {
                    "executionTimeout": 30_000, "ttl": 300_000}):
            raise ValueError("invalid_execution_binding")
        claim = {**binding, "state": "claimed", "claimed_at": int(time.time())}
        inserted = submission_store.put(claim_key, claim, skip_if_exists=True)
        record = claim if inserted else submission_store.get(claim_key)
        if not isinstance(record, dict) or any(record.get(k) != v for k, v in binding.items()):
            raise ValueError("submission_identity_conflict")
        if not inserted:
            if record.get("state") == "completed" and isinstance(record.get("response"), dict):
                return record["response"]
            raise FileExistsError("runpod_submission_already_claimed")
        try:
            status, body, _headers = relay(
                "POST", upstream_path(RUNPOD_ENDPOINT_ID, "run", None),
                f"Bearer {_runpod_key()}", _canonical(request_body))
            value = json.loads(body)
            response = {"status": status, "body": value}
            job_id = value.get("id") if 200 <= status < 300 and isinstance(value, dict) else None
            if job_id is not None and (not isinstance(job_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{4,128}", job_id) is None):
                raise ValueError("invalid_response")
            submission_store.put(claim_key, {**claim, "state": "completed", "job_id": job_id,
                                             "response": response})
            return response
        except Exception:
            submission_store.put(claim_key, {**claim, "state": "uncertain"})
            raise

    record = submission_store.get(claim_key)
    job_id = arguments.get("job_id")
    if (not isinstance(record, dict) or any(record.get(k) != v for k, v in binding.items()) or
            record.get("state") != "completed" or record.get("job_id") != job_id or
            not isinstance(job_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{4,128}", job_id) is None):
        raise ValueError("provider_handle_mismatch")
    method = "GET" if operation == "status" else "POST"
    status, body, _headers = relay(
        method, upstream_path(RUNPOD_ENDPOINT_ID, operation, job_id),
        f"Bearer {_runpod_key()}", b"")
    return {"status": status, "body": json.loads(body)}


@api.get("/v1/health")
def health() -> dict[str, Any]:
    try:
        key_id, _key = _auth_key()
    except RuntimeError:
        return {"ready": False, "provider_adapter": True, "auth_configured": False}
    return {"ready": True, "provider_adapter": True, "auth_configured": True,
            "key_id": key_id, "providers": ["kaggle", "huggingface_space", "modal_gpu"],
            "paid_fallback": False}


@api.post("/internal/sites/v1/tools/{tool}")
async def invoke(tool: str, request: Request):
    content_length = request.headers.get("content-length")
    if content_length is not None and (not content_length.isdigit() or int(content_length) > MAX_BODY_BYTES):
        return _error("request_too_large", 413)
    raw = await request.body()
    try:
        owner, verified_tool, arguments = _verify(
            raw, request.headers.get("x-gpu-control-sites-signature"), tool)
        if verified_tool == "runpod_queue_request":
            result = _runpod_relay(owner, arguments)
        elif verified_tool == "experiment_submit":
            result = _async_submit(owner, arguments)
        elif verified_tool in {"experiment_status", "experiment_result", "experiment_cancel"}:
            result = _async_observe(owner, verified_tool, arguments)
            if result is None:
                result = _service().invoke(owner, verified_tool, arguments)
        else:
            result = _service().invoke(owner, verified_tool, arguments)
        if len(_canonical(result)) > MAX_BODY_BYTES:
            return _error("response_too_large", 502)
        data_volume.commit()
        return result
    except PermissionError:
        return _error("invalid_delegation", 401)
    except FileExistsError:
        return _error("delegation_replayed", 409)
    except ValueError:
        return _error("invalid_delegation", 400)
    except Exception as exc:
        from provider_adapter_core import AdapterError
        if isinstance(exc, AdapterError):
            return _error(exc.code, exc.status)
        return _error("provider_operation_failed", 503)


@app.function(
    image=adapter_image, secrets=[provider_secret, adapter_auth_secret],
    volumes={"/data": data_volume}, timeout=120, cpu=1, memory=1024,
    max_containers=1,
)
@modal.asgi_app(requires_proxy_auth=True)
def provider_adapter_api():
    return api
