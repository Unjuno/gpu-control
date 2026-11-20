"""Approved private-artifact Orbitune evaluation contract for a ZeroGPU Space.

Deploy this source only after vendoring the audited Orbitune package at the
registered commit. The Space receives a separate read-only Hub token; it never
receives the worker's artifact write token.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import zipfile

import gradio as gr
from huggingface_hub import hf_hub_download
import spaces
import torch

from orbitune.model import OrbituneGPT


SOURCE_SHA = "44a1b806160ab5bc721a370d034a6dfcb28f27a8"
REQUEST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}-[0-9a-f]{12}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PATH_RE = re.compile(r"^runs/[0-9a-f]{32}/orbitune-output\.zip$")
MAX_BUNDLE_BYTES = 67 * 1024 * 1024
MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024
_RESULTS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parameters(value: str) -> dict[str, str]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise gr.Error("INVALID_ARTIFACT_REFERENCE") from exc
    expected = {"artifact_repo_id", "artifact_revision", "artifact_path", "artifact_sha256"}
    allowed_repo = os.environ.get("GPU_CONTROL_HF_ARTIFACT_REPO", "")
    if (not isinstance(parsed, dict) or set(parsed) != expected or
            parsed.get("artifact_repo_id") != allowed_repo or
            REVISION_RE.fullmatch(parsed.get("artifact_revision", "")) is None or
            PATH_RE.fullmatch(parsed.get("artifact_path", "")) is None or
            SHA256_RE.fullmatch(parsed.get("artifact_sha256", "")) is None):
        raise gr.Error("INVALID_ARTIFACT_REFERENCE")
    return parsed


def _batch(model: OrbituneGPT, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    generator = torch.Generator(device="cpu").manual_seed(71112)
    values = torch.randint(
        0, model.config.vocab_size, (8, model.config.max_seq_len + 1), generator=generator,
    )
    return values[:, :-1].to(device), values[:, 1:].to(device)


@spaces.GPU(duration=60, size="large")
def evaluate(request_id: str, parameters_json: str, source_sha: str) -> dict:
    if REQUEST_RE.fullmatch(request_id or "") is None or source_sha != SOURCE_SHA:
        raise gr.Error("INVALID_REQUEST_IDENTITY")
    parameters = _parameters(parameters_json)
    with _LOCK:
        existing = _RESULTS.get(request_id)
        if existing is not None:
            return existing
        _RESULTS[request_id] = {"request_id": request_id, "state": "running"}
    started = time.perf_counter()
    try:
        token = os.environ.get("HF_READ_TOKEN", "")
        if not token:
            raise RuntimeError("READ_TOKEN_UNAVAILABLE")
        bundle = Path(hf_hub_download(
            repo_id=parameters["artifact_repo_id"],
            filename=parameters["artifact_path"], repo_type="model",
            revision=parameters["artifact_revision"], token=token,
        ))
        if (not bundle.is_file() or bundle.stat().st_size > MAX_BUNDLE_BYTES or
                _sha256(bundle) != parameters["artifact_sha256"]):
            raise RuntimeError("ARTIFACT_INTEGRITY_FAILED")
        with zipfile.ZipFile(bundle) as archive:
            names = set(archive.namelist())
            expected = {
                "gpu-control-output/checkpoint.pt", "gpu-control-output/result.json",
                "gpu-control-output/training-config.json", "gpu-control-output/evaluation.json",
            }
            if names != expected:
                raise RuntimeError("ARTIFACT_LAYOUT_INVALID")
            info = archive.getinfo("gpu-control-output/checkpoint.pt")
            if info.file_size < 1 or info.file_size > MAX_CHECKPOINT_BYTES:
                raise RuntimeError("CHECKPOINT_SIZE_INVALID")
            checkpoint_bytes = archive.read(info)
            training_result = json.loads(archive.read(
                "gpu-control-output/result.json").decode("utf-8"))
        if (training_result.get("source_sha") != SOURCE_SHA or
                hashlib.sha256(checkpoint_bytes).hexdigest() !=
                training_result.get("checkpoint_sha256")):
            raise RuntimeError("CHECKPOINT_IDENTITY_INVALID")
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.pt"
            checkpoint.write_bytes(checkpoint_bytes)
            device = torch.device("cuda")
            if not torch.cuda.is_available():
                raise RuntimeError("GPU_NOT_ALLOCATED")
            model = OrbituneGPT.load_checkpoint(checkpoint, map_location="cpu").to(device).eval()
            inputs, targets = _batch(model, device)
            with torch.no_grad():
                _logits, loss = model(inputs, targets)
            assert loss is not None
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - started
            response = {
                "request_id": request_id, "state": "succeeded",
                "result": {
                    "score": float(loss.item()), "device": torch.cuda.get_device_name(0),
                    "gpu_used": True, "exit_code": 0,
                    "checksum": training_result["checkpoint_sha256"],
                    "runtime_seconds": elapsed,
                },
            }
    except Exception:
        response = {"request_id": request_id, "state": "failed"}
    with _LOCK:
        _RESULTS[request_id] = response
    return response


def status(request_id: str) -> dict:
    if REQUEST_RE.fullmatch(request_id or "") is None:
        raise gr.Error("INVALID_REQUEST_IDENTITY")
    with _LOCK:
        return _RESULTS.get(request_id, {"request_id": request_id, "state": "failed"})


def cancel(request_id: str) -> dict:
    if REQUEST_RE.fullmatch(request_id or "") is None:
        raise gr.Error("INVALID_REQUEST_IDENTITY")
    with _LOCK:
        current = _RESULTS.get(request_id)
        if current is None:
            current = {"request_id": request_id, "state": "cancelled"}
            _RESULTS[request_id] = current
        return current


with gr.Blocks() as demo:
    gr.Markdown("GPU Control approved Orbitune evaluation endpoint")
    request = gr.Textbox(label="request_id", visible=False)
    parameters = gr.Textbox(label="parameters_json", visible=False)
    source = gr.Textbox(label="source_sha", visible=False)
    output = gr.JSON(label="result")
    gr.Button("Evaluate", visible=False).click(
        evaluate, [request, parameters, source], output, api_name="evaluate",
    )
    gr.Button("Status", visible=False).click(status, request, output, api_name="status")
    gr.Button("Cancel", visible=False).click(cancel, request, output, api_name="cancel")


if __name__ == "__main__":
    demo.launch()
