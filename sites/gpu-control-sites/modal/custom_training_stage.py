"""Stage a verified public Git object store in per-run private Volumes."""
import io
import re
import tempfile
from pathlib import Path

from custom_training_fetch import fetch_public_commit
from custom_training_source import stage_commit


def stage_to_volumes(repository, commit, run_id, *, source_volume, checkpoint_volume,
                     fetch=fetch_public_commit):
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise ValueError("invalid_run_id")
    with tempfile.TemporaryDirectory(prefix="gpu-control-stage-") as temp:
        root = Path(temp)
        objects = root / "objects"
        fetch(repository, commit, objects)
        # Reject unsafe or oversized trees before uploading. The Sandbox later
        # repeats this validation and materializes the same commit itself.
        stage_commit(objects, commit, root / "verification")
        # No force overwrite: repeated staging under an occupied run ID fails.
        with source_volume.batch_upload() as upload:
            upload.put_directory(str(objects), f"/{run_id}")
        # Ensure the per-run checkpoint subdirectory exists before mounting.
        with checkpoint_volume.batch_upload() as upload:
            upload.put_file(io.BytesIO(b""), f"/{run_id}/.gpu-control-run")
