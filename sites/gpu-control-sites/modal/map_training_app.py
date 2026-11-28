"""Private Modal entry point for the reviewed MAP training image."""
import json
import os
from pathlib import Path

import modal
from map_training_configuration import map_training_profile_settings

_PROFILE = map_training_profile_settings()
SOURCE_SHA = _PROFILE["source_sha"]
MODAL_IMAGE_ID = _PROFILE["image_id"]
IMAGE_DIGEST = _PROFILE["image_digest"]
RUNTIME_LIMIT = _PROFILE["runtime_seconds"]
HOURLY_MICROUSD = _PROFILE["hourly_microusd"]
QUOTE_EXPIRES_AT = _PROFILE["quote_expires_at"]

# Modal imports this module in both function containers. Forward only the
# non-secret settings required for that import and the runtime checks.
deployment_env = _PROFILE["runtime_environment"]

app = modal.App("gpu-control-map-training")
base_image = (modal.Image.from_id(MODAL_IMAGE_ID) if MODAL_IMAGE_ID else
              modal.Image.from_registry(f"ghcr.io/unjuno/gpu-control-map-training@{IMAGE_DIGEST}"))
image = base_image.add_local_python_source("map_training_job", "map_checkpoint")
corpus = modal.Volume.from_name("gpu-control-map-corpus", create_if_missing=False)
checkpoints = modal.Volume.from_name("gpu-control-map-checkpoints", create_if_missing=False)


@app.function(
    image=image.add_local_python_source("map_training_configuration"), env=deployment_env,
    gpu="L4", cpu=2, memory=8192, block_network=True,
    volumes={"/corpus": corpus.with_mount_options(read_only=True), "/checkpoints": checkpoints},
    timeout=RUNTIME_LIMIT, startup_timeout=600, retries=0, max_containers=1,
    single_use_containers=True,
)
def train_map(plan: dict) -> dict:
    try:
        from map_training_job import run_map_training
        from model_as_a_paper.training import train

        if os.environ.get("MAP_IMAGE_SOURCE_SHA") != SOURCE_SHA:
            raise ValueError("training_image_revision_mismatch")
        if plan["runtime_seconds"] != RUNTIME_LIMIT:
            raise ValueError("training_runtime_mismatch")
        with Path("/opt/map/configs/map44.json").open(encoding="utf-8") as stream:
            config = json.load(stream)
        checkpoints.reload()
        return run_map_training(
            plan, source_sha=SOURCE_SHA, image_digest=IMAGE_DIGEST,
            hourly_microusd=HOURLY_MICROUSD, quote_expires_at=QUOTE_EXPIRES_AT,
            config=config, corpus_dir=Path("/corpus"), runs_dir=Path("/checkpoints"),
            commit_volume=checkpoints.commit, train=train,
        )
    except Exception:
        import traceback

        traceback.print_exc()
        return {"run_id": plan["run_id"], "failure_code": "TRAINING_WORKLOAD_FAILURE"}


@app.function(
    volumes={"/checkpoints": checkpoints.with_mount_options(read_only=True)},
    image=modal.Image.debian_slim(python_version="3.11").add_local_python_source("map_checkpoint"),
    env=deployment_env, timeout=30, block_network=True, cpu=1, memory=256,
)
def read_map_checkpoint(run_id: str, manifest: dict | None, offset: int, max_bytes: int) -> dict:
    from map_checkpoint import checkpoint_manifest, read_checkpoint_chunk

    checkpoints.reload()
    if manifest is None:
        try:
            recovered = checkpoint_manifest(Path("/checkpoints"), run_id)
        except FileNotFoundError:
            return {}
        if int(recovered["filename"].split("-")[1]) == 0:
            return {}
        return recovered
    return read_checkpoint_chunk(Path("/checkpoints"), run_id, manifest, offset, max_bytes)
