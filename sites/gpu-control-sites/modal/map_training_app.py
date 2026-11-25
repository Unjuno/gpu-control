"""Private Modal entry point for the reviewed MAP training image."""
import json
import os
import re
from pathlib import Path

import modal

from map_training_job import run_map_training


SOURCE_SHA = os.environ["MAP_TRAINING_SOURCE_SHA"]
IMAGE_DIGEST = os.environ["MAP_TRAINING_IMAGE_DIGEST"]
RUNTIME_LIMIT = int(os.environ["MAP_TRAINING_RUNTIME_SECONDS"])
HOURLY_MICROUSD = int(os.environ["MAP_TRAINING_HOURLY_MICROUSD"])
QUOTE_EXPIRES_AT = int(os.environ["MAP_TRAINING_QUOTE_EXPIRES_AT"])
if not re.fullmatch(r"[0-9a-f]{40}", SOURCE_SHA):
    raise ValueError("invalid MAP source commit")
if not re.fullmatch(r"sha256:[0-9a-f]{64}", IMAGE_DIGEST):
    raise ValueError("invalid MAP image digest")
if not 120 <= RUNTIME_LIMIT <= 3000:
    raise ValueError("invalid MAP runtime")

app = modal.App("gpu-control-map-training")
image = (
    modal.Image.from_registry(f"ghcr.io/unjuno/gpu-control-map-training@{IMAGE_DIGEST}")
    .add_local_python_source("map_training_job", "map_checkpoint")
)
corpus = modal.Volume.from_name("gpu-control-map-corpus", create_if_missing=False)
checkpoints = modal.Volume.from_name("gpu-control-map-checkpoints", create_if_missing=False)


@app.function(
    image=image, gpu="L4", cpu=2, memory=8192, block_network=True,
    volumes={"/corpus": corpus.with_mount_options(read_only=True), "/checkpoints": checkpoints},
    timeout=RUNTIME_LIMIT, startup_timeout=600, retries=0, max_containers=1,
    single_use_containers=True,
)
def train_map(plan: dict) -> dict:
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
        config=config, corpus_dir=Path("/corpus/papers"), runs_dir=Path("/checkpoints"),
        commit_volume=checkpoints.commit, train=train,
    )
