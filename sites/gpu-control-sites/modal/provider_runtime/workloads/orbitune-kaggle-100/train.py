#!/usr/bin/env python3
"""Registered Orbitune 100-step synthetic-data GPU training workload.

The trusted worker stages the exact Orbitune package at SOURCE_SHA beside this
file.  This workload has no network credentials and never uploads to the Hub;
the worker collects its output and performs that transfer separately.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


_ORBITUNE_BUNDLE_B64 = "__GPU_CONTROL_ORBITUNE_BUNDLE_B64__"
_ORBITUNE_BUNDLE_SHA256 = "__GPU_CONTROL_ORBITUNE_BUNDLE_SHA256__"


def _install_embedded_orbitune() -> None:
    try:
        bundle = base64.b64decode(_ORBITUNE_BUNDLE_B64, validate=True)
    except ValueError as exc:
        raise RuntimeError("embedded Orbitune bundle is invalid") from exc
    if hashlib.sha256(bundle).hexdigest() != _ORBITUNE_BUNDLE_SHA256:
        raise RuntimeError("embedded Orbitune bundle checksum mismatch")
    path = Path(f"/tmp/gpu-control-orbitune-{_ORBITUNE_BUNDLE_SHA256}.zip")
    if path.exists():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != _ORBITUNE_BUNDLE_SHA256:
            raise RuntimeError("embedded Orbitune bundle path is unsafe")
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(bundle)
    sys.path.insert(0, str(path))


_install_embedded_orbitune()

import torch

from orbitune.model import OrbituneConfig, OrbituneGPT
from orbitune.tokenizer.vocab import TheoryRemiVocab


SOURCE_REPOSITORY = "Unjuno/orbitune"
SOURCE_SHA = "44a1b806160ab5bc721a370d034a6dfcb28f27a8"
WORKLOAD_ID = "orbitune-kaggle-100-step-v1"
STEPS = 100
SEED = 61112


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def batch(cfg: OrbituneConfig, *, seed: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    values = torch.randint(0, cfg.vocab_size, (8, cfg.max_seq_len + 1), generator=generator)
    return values[:, :-1].to(device), values[:, 1:].to(device)


def evaluate(checkpoint: Path, output: Path) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; evaluation will not silently fall back to CPU")
    device = torch.device("cuda")
    model = OrbituneGPT.load_checkpoint(checkpoint, map_location="cpu").to(device).eval()
    inputs, targets = batch(model.config, seed=SEED + 10_000, device=device)
    with torch.no_grad():
        logits, loss = model(inputs, targets)
    assert loss is not None
    output.write_text(json.dumps({
        "validation_loss": float(loss.item()),
        "logits_shape": list(logits.shape),
        "checkpoint_sha256": sha256(checkpoint),
        "separate_process": True,
    }, allow_nan=False, sort_keys=True) + "\n", encoding="utf-8")


def train() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; training will not silently fall back to CPU")
    if (SOURCE_SHA != "44a1b806160ab5bc721a370d034a6dfcb28f27a8" or
            STEPS != 100 or len(_ORBITUNE_BUNDLE_SHA256) != 64):
        raise RuntimeError("trusted workload provenance does not match the registered contract")
    device = torch.device("cuda")
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    vocab = TheoryRemiVocab()
    cfg = OrbituneConfig(
        vocab_size=len(vocab), max_seq_len=64, n_layer=2, n_embd=128, n_head=4, dropout=0.0,
    )
    model = OrbituneGPT(cfg).to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)
    losses: list[dict[str, float | int]] = []
    started = time.perf_counter()
    for step in range(1, STEPS + 1):
        inputs, targets = batch(cfg, seed=SEED + step, device=device)
        optimizer.zero_grad(set_to_none=True)
        _logits, loss = model(inputs, targets)
        assert loss is not None
        loss.backward()
        optimizer.step()
        losses.append({"step": step, "loss": float(loss.detach().item())})
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    output = Path(os.environ.get("GPU_CONTROL_OUTPUT_DIR", "/kaggle/working/gpu-control-output"))
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / "checkpoint.pt"
    model.save_checkpoint(checkpoint)
    config = {
        "workload_id": WORKLOAD_ID,
        "source_repository": SOURCE_REPOSITORY,
        "source_sha": SOURCE_SHA,
        "data_kind": "synthetic",
        "dataset_identity": f"synthetic-theory-remi-seed-{SEED}",
        "steps": STEPS,
        "seed": SEED,
        "model_config": asdict(cfg),
    }
    (output / "training-config.json").write_text(
        json.dumps(config, allow_nan=False, sort_keys=True) + "\n", encoding="utf-8",
    )
    evaluation_path = output / "evaluation.json"
    completed = subprocess.run(
        (sys.executable, str(Path(__file__).resolve()), "--evaluate", str(checkpoint), str(evaluation_path)),
        check=False, timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError("checkpoint reload evaluation failed")
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    result = {
        **config,
        "status": "succeeded",
        "exit_status": 0,
        "gpu_name": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "elapsed_seconds": elapsed,
        "loss_history": losses,
        "first_loss": losses[0]["loss"],
        "final_loss": losses[-1]["loss"],
        "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "evaluation": evaluation,
    }
    (output / "result.json").write_text(
        json.dumps(result, allow_nan=False, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(result, allow_nan=False, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--evaluate", nargs=2, metavar=("CHECKPOINT", "OUTPUT"))
    args = parser.parse_args()
    if args.evaluate:
        evaluate(Path(args.evaluate[0]), Path(args.evaluate[1]))
    else:
        train()


if __name__ == "__main__":
    main()

