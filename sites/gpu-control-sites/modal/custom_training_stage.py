"""Stage a verified public Git object store in per-run private Volumes."""
import io
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from custom_training_fetch import fetch_public_commit
from custom_training_source import stage_commit
from custom_training_dependencies import download_locked_wheels


def stage_to_volumes(repository, commit, run_id, *, source_volume, checkpoint_volume,
                     source_token=None, fetch=fetch_public_commit,
                     download=download_locked_wheels):
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise ValueError("invalid_run_id")
    with tempfile.TemporaryDirectory(prefix="gpu-control-stage-") as temp:
        root = Path(temp)
        objects = root / "objects"
        if source_token is None:
            fetch(repository, commit, objects)
        else:
            fetch(repository, commit, objects, source_token=source_token)
        # Reject unsafe or oversized trees before uploading. The Sandbox later
        # repeats this validation and materializes the same commit itself.
        verification = root / "verification"
        staged = stage_commit(objects, commit, verification)
        manifest_path = verification / ".gpu-control" / "experiment.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError("training_manifest_missing")
        manifest_bytes = manifest_path.read_bytes()
        if len(manifest_bytes) > 8192:
            raise ValueError("training_manifest_invalid")
        try:
            manifest = json.loads(manifest_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("training_manifest_invalid") from exc
        entrypoint = manifest.get("entrypoint") if isinstance(manifest, dict) else None
        python_version = manifest.get("python_version") if isinstance(manifest, dict) else None
        lock_path = manifest.get("dependencies_lock") if isinstance(manifest, dict) else None
        if (not isinstance(entrypoint, str) or not entrypoint.endswith(".py") or entrypoint.startswith("/") or
                any(not part or part in (".", "..") or re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None
                    for part in entrypoint.split("/")) or
                not isinstance(lock_path, str) or not lock_path.endswith(".lock") or lock_path.startswith("/") or
                any(not part or part in (".", "..") or re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None
                    for part in lock_path.split("/"))):
            raise ValueError("training_manifest_invalid")
        lock_file = verification / lock_path
        script_file = verification / entrypoint
        if (lock_file.is_symlink() or script_file.is_symlink() or not lock_file.is_file() or not script_file.is_file() or
                not lock_file.resolve().is_relative_to(verification.resolve()) or
                not script_file.resolve().is_relative_to(verification.resolve())):
            raise ValueError("training_source_file_missing")
        wheelhouse = root / "wheelhouse"
        if python_version not in {"3.11", "3.12"}:
            raise ValueError("training_manifest_invalid")
        wheels = download(lock_file, wheelhouse, python_version=python_version)
        _make_wheelhouse_readable(wheelhouse)
        source_binding = {"commit": staged["commit"],
                          "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                          "lock_sha256": hashlib.sha256(lock_file.read_bytes()).hexdigest(),
                          "dependencies_lock": lock_path, "entrypoint": entrypoint,
                          "wheelhouse_sha256": wheels["sha256"],
                          "wheelhouse_packages": wheels["packages"],
                          "wheelhouse_bytes": wheels["bytes"]}
        # No force overwrite: repeated staging under an occupied run ID fails.
        with source_volume.batch_upload() as upload:
            upload.put_directory(str(objects), f"/{run_id}")
        with source_volume.batch_upload() as upload:
            upload.put_directory(str(wheelhouse), f"/{run_id}/wheelhouse")
        # Ensure the per-run checkpoint subdirectory exists before mounting.
        with checkpoint_volume.batch_upload() as upload:
            upload.put_file(io.BytesIO(b""), f"/{run_id}/.gpu-control-run")
        source_volume.commit()
        checkpoint_volume.commit()
    return source_binding


def stage_to_mounts(repository, commit, run_id, *, source_root="/source-store",
                    checkpoint_root="/checkpoint-store", source_token=None,
                    fetch=fetch_public_commit, download=download_locked_wheels,
                    materialize=stage_commit):
    """Stage only through this fixed trusted CPU entrypoint inside a bounded Sandbox."""
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise ValueError("invalid_run_id")
    source_root, checkpoint_root = Path(source_root), Path(checkpoint_root)
    source_target, checkpoint_target = source_root / run_id, checkpoint_root / run_id
    if source_target.exists() or source_target.is_symlink() or checkpoint_target.exists() or checkpoint_target.is_symlink():
        raise ValueError("training_stage_already_exists")
    try:
        with tempfile.TemporaryDirectory(prefix="gpu-control-stage-") as temp:
            root = Path(temp)
            objects, verification, wheelhouse = root / "objects", root / "verification", root / "wheelhouse"
            if source_token is None:
                fetch(repository, commit, objects)
            else:
                fetch(repository, commit, objects, source_token=source_token)
            staged = materialize(objects, commit, verification)
            manifest_path = verification / ".gpu-control" / "experiment.json"
            if manifest_path.is_symlink() or not manifest_path.is_file():
                raise ValueError("training_manifest_missing")
            manifest_bytes = manifest_path.read_bytes()
            if len(manifest_bytes) > 8192:
                raise ValueError("training_manifest_invalid")
            try:
                manifest = json.loads(manifest_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("training_manifest_invalid") from exc
            entrypoint = manifest.get("entrypoint") if isinstance(manifest, dict) else None
            python_version = manifest.get("python_version") if isinstance(manifest, dict) else None
            lock_path = manifest.get("dependencies_lock") if isinstance(manifest, dict) else None
            if (not isinstance(entrypoint, str) or not entrypoint.endswith(".py") or entrypoint.startswith("/") or
                    any(not part or part in (".", "..") or re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None
                        for part in entrypoint.split("/")) or
                    not isinstance(lock_path, str) or not lock_path.endswith(".lock") or lock_path.startswith("/") or
                    any(not part or part in (".", "..") or re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None
                        for part in lock_path.split("/"))):
                raise ValueError("training_manifest_invalid")
            lock_file, script_file = verification / lock_path, verification / entrypoint
            if (lock_file.is_symlink() or script_file.is_symlink() or not lock_file.is_file() or
                    not script_file.is_file() or not lock_file.resolve().is_relative_to(verification.resolve()) or
                    not script_file.resolve().is_relative_to(verification.resolve())):
                raise ValueError("training_source_file_missing")
            if python_version not in {"3.11", "3.12"}:
                raise ValueError("training_manifest_invalid")
            wheels = download(lock_file, wheelhouse, python_version=python_version)
            _make_wheelhouse_readable(wheelhouse)
            binding = {"commit": staged["commit"],
                       "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                       "lock_sha256": hashlib.sha256(lock_file.read_bytes()).hexdigest(),
                       "dependencies_lock": lock_path, "entrypoint": entrypoint,
                       "wheelhouse_sha256": wheels["sha256"],
                       "wheelhouse_packages": wheels["packages"], "wheelhouse_bytes": wheels["bytes"]}
            shutil.copytree(objects, source_target)
            shutil.copytree(wheelhouse, source_target / "wheelhouse")
            marker = source_target / ".gpu-control-stage.json"
            marker.write_text(json.dumps(binding, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            marker.chmod(0o600)
            checkpoint_target.mkdir(mode=0o700, parents=False)
            (checkpoint_target / ".gpu-control-run").write_bytes(b"")
        return binding
    except Exception:
        shutil.rmtree(source_target, ignore_errors=True)
        shutil.rmtree(checkpoint_target, ignore_errors=True)
        raise


def _make_wheelhouse_readable(wheelhouse):
    """Allow the unprivileged workload UID to read only the staged wheels."""
    wheelhouse = Path(wheelhouse)
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ValueError("training_wheelhouse_invalid")
    for item in wheelhouse.iterdir():
        if item.is_symlink() or not item.is_file() or item.suffix != ".whl":
            raise ValueError("training_wheelhouse_invalid")
        item.chmod(0o444)
    wheelhouse.chmod(0o555)
