"""Authenticated Modal adapter for registered Kaggle and Hugging Face work.

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
TOOLS = re.compile(r"^experiment_(?:capabilities|prepare|submit|status|result|artifact|cancel|list)$")
OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$")
NONCE = re.compile(r"^[0-9a-f]{32}$")

REPOSITORY_ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "gateway" / "gpu_gateway").is_dir()),
    Path("/root"),
)
PROVIDER_MODULE_ROOT = REPOSITORY_ROOT / "gateway" / "gpu_gateway"
MODAL_ROOT = REPOSITORY_ROOT / "sites" / "gpu-control-sites" / "modal"

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
    "orbitune_workload.py",
)

app = modal.App(APP_NAME)
data_volume = modal.Volume.from_name("gpu-control-provider-adapter-data", create_if_missing=True)
nonce_store = modal.Dict.from_name("gpu-control-provider-adapter-nonces", create_if_missing=True)
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
    .add_local_dir(str(MODAL_ROOT), remote_path="/root/site-modal", copy=True)
    .env({"PYTHONPATH": "/root/provider-runtime:/root/site-modal"})
)

api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


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
    return ProviderAdapter(kaggle, huggingface)


@api.get("/v1/health")
def health() -> dict[str, Any]:
    try:
        key_id, _key = _auth_key()
    except RuntimeError:
        return {"ready": False, "provider_adapter": True, "auth_configured": False}
    return {"ready": True, "provider_adapter": True, "auth_configured": True,
            "key_id": key_id, "providers": ["kaggle", "huggingface_space"],
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
