"""Create a quiesced, atomically published Gateway backup generation.

PostgreSQL connection settings are read from libpq environment variables or a
protected PGPASSFILE. Credentials are never accepted as command-line options.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path


TERMINAL_STATES = "'succeeded','failed','cancelled','expired'"
_SCOPE_NAME = re.compile(r"^[0-9a-f]{64}$")
_BLOB_NAME = re.compile(r"^[0-9a-f]{64}\.blob$")
_MAX_ARTIFACT_BYTES = 1024 * 1024
_MAX_RUN_ARTIFACT_BYTES = 10 * 1024 * 1024
_MAX_ARTIFACTS_PER_RUN = 10
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_HAS_ARTIFACT_MANIFEST = (
    "CASE WHEN json_typeof(result->'artifacts')='array' "
    "THEN json_array_length(result->'artifacts') ELSE 0 END > 0"
)
SYSTEMD_BACKUP_UNITS = (
    "gpu-control-api.service",
    "gpu-control-worker.service",
    "gpu-control-supervisor.service",
    "gpu-control-db-migrate.service",
    "gpu-control-artifact-capacity.service",
    "gpu-control-artifact-capacity.timer",
    "gpu-control-capacity-bridge.service",
)


def _assert_gateway_systemd_units_stopped() -> dict[str, str]:
    """Require the installed Gateway units to be loaded and inactive locally."""
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        raise ValueError("systemctl is required to verify stopped Gateway services")
    observations = {}
    for unit in SYSTEMD_BACKUP_UNITS:
        try:
            result = subprocess.run(
                [systemctl, "show", "--property=LoadState", "--property=ActiveState",
                 "--value", unit],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, check=False, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError("could not verify Gateway systemd service state") from None
        state = result.stdout.splitlines()
        if result.returncode != 0 or state != ["loaded", "inactive"]:
            raise ValueError("all Gateway systemd services must be loaded and inactive")
        observations[unit] = state[1]
    return observations


def _validate_artifact_archive(path: Path) -> None:
    """Validate tar members against the opaque owner/run artifact layout without extracting."""
    seen: set[str] = set()
    run_bytes: dict[str, int] = {}
    run_counts: dict[str, int] = {}
    try:
        with tarfile.open(path, mode="r:") as archive:
            for member in archive:
                raw = member.name
                if raw in {".", "./"}:
                    if not member.isdir():
                        raise ValueError("unsafe artifact archive member")
                    continue
                if not isinstance(raw, str) or raw.startswith("/") or "\\" in raw or "\x00" in raw:
                    raise ValueError("unsafe artifact archive member")
                name = raw[2:] if raw.startswith("./") else raw
                if name.endswith("/"):
                    if not member.isdir():
                        raise ValueError("unsafe artifact archive member")
                    name = name[:-1]
                parts = name.split("/")
                if any(part in {"", ".", ".."} for part in parts) or name in seen:
                    raise ValueError("unsafe artifact archive member")
                seen.add(name)
                if len(parts) == 1 and _SCOPE_NAME.fullmatch(parts[0]) and member.isdir():
                    continue
                if (len(parts) != 2 or not _SCOPE_NAME.fullmatch(parts[0]) or
                        not _BLOB_NAME.fullmatch(parts[1]) or not member.isfile()):
                    raise ValueError("unsafe artifact archive member")
                if member.size < 0 or member.size > _MAX_ARTIFACT_BYTES:
                    raise ValueError("artifact archive object exceeds per-object size limit")
                scope = parts[0]
                run_bytes[scope] = run_bytes.get(scope, 0) + member.size
                run_counts[scope] = run_counts.get(scope, 0) + 1
                if (run_bytes[scope] > _MAX_RUN_ARTIFACT_BYTES or
                        run_counts[scope] > _MAX_ARTIFACTS_PER_RUN):
                    raise ValueError("artifact archive scope exceeds per-run limits")
    except (OSError, tarfile.TarError) as exc:
        raise ValueError("artifact archive is not a readable uncompressed tar") from exc


def _run(args: list[str], *, capture: bool = False, env: dict[str, str] | None = None) -> str:
    process_env = None if env is None else os.environ | env
    result = subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=process_env,
        text=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or "").strip()
        raise RuntimeError(f"{Path(args[0]).name} failed with exit {result.returncode}: {detail}")
    return result.stdout.strip() if capture else ""


def _sql(query: str) -> str:
    return _run(["psql", "--no-psqlrc", "--tuples-only", "--no-align",
                 "--set=ON_ERROR_STOP=1", "--command", query], capture=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _artifact_root(path_value: str | None, backup_dir: Path) -> Path | None:
    if path_value is None:
        return None
    root = Path(path_value)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("artifact directory must be an absolute, existing, non-symlink directory")
    root = root.resolve(strict=True)
    if backup_dir == root or backup_dir.is_relative_to(root):
        raise ValueError("backup output directory must not be inside the artifact directory")
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            if (Path(current) / name).is_symlink():
                raise ValueError("artifact tree contains a symlink")
    return root


def _artifact_records() -> list[dict]:
    """Read artifact manifests needed to verify the paired filesystem backup."""
    raw = _sql(
        "SELECT COALESCE(json_agg(json_build_object('owner', owner, 'run_id', id, "
        f"'artifacts', result->'artifacts')) FILTER (WHERE {_HAS_ARTIFACT_MANIFEST}), "
        "'[]'::json)::text "
        "FROM gateway_runs_v1"
    )
    records = json.loads(raw)
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("database artifact manifest query returned invalid data")
    return records


def _verify_live_artifact_files(root: Path, records: list[dict], *, now: int | None = None) -> int:
    """Verify every unexpired DB artifact reference against its no-follow blob."""
    observed_at = int(time.time()) if now is None else now
    verified = 0
    for row in records:
        owner, run_id, artifacts = row.get("owner"), row.get("run_id"), row.get("artifacts")
        if not isinstance(owner, str) or not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
            raise ValueError("database artifact manifest identity is invalid")
        if not isinstance(artifacts, list):
            raise ValueError("database artifact manifest list is invalid")
        scope = hashlib.sha256((owner + "\0" + run_id).encode()).hexdigest()
        for item in artifacts:
            if not isinstance(item, dict):
                raise ValueError("database artifact manifest entry is invalid")
            artifact_id = item.get("artifact_id")
            digest = item.get("sha256")
            size = item.get("size_bytes")
            expiry = item.get("expires_at")
            if (not isinstance(artifact_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", artifact_id) or
                    not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or
                    type(size) is not int or not 0 <= size <= _MAX_ARTIFACT_BYTES or
                    (expiry is not None and type(expiry) is not int)):
                raise ValueError("database artifact manifest entry is invalid")
            if expiry is not None and expiry <= observed_at:
                continue
            name = hashlib.sha256(artifact_id.encode()).hexdigest() + ".blob"
            path = root / scope / name
            try:
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            except OSError as exc:
                raise ValueError("live artifact referenced by database is missing or unsafe") from exc
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                    raise ValueError("live artifact type or size does not match database manifest")
                hasher = hashlib.sha256()
                with os.fdopen(fd, "rb", closefd=False) as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        hasher.update(chunk)
                if hasher.hexdigest() != digest:
                    raise ValueError("live artifact digest does not match database manifest")
            finally:
                os.close(fd)
            verified += 1
    return verified


def _verify_artifact_archive_manifests(
        archive_path: Path, records: list[dict], *, now: int | None = None) -> int:
    """Ensure every unexpired DB reference is present and intact in the tar."""
    observed_at = int(time.time()) if now is None else now
    verified = 0
    try:
        with tarfile.open(archive_path, mode="r:") as archive:
            members = {
                (member.name[2:] if member.name.startswith("./") else member.name): member
                for member in archive
            }
            for row in records:
                owner, run_id, artifacts = row.get("owner"), row.get("run_id"), row.get("artifacts")
                if not isinstance(owner, str) or not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
                    raise ValueError("database artifact manifest identity is invalid")
                if not isinstance(artifacts, list):
                    raise ValueError("database artifact manifest list is invalid")
                scope = hashlib.sha256((owner + "\0" + run_id).encode()).hexdigest()
                for item in artifacts:
                    if not isinstance(item, dict):
                        raise ValueError("database artifact manifest entry is invalid")
                    artifact_id, digest = item.get("artifact_id"), item.get("sha256")
                    size, expiry = item.get("size_bytes"), item.get("expires_at")
                    if (not isinstance(artifact_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", artifact_id) or
                            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or
                            type(size) is not int or not 0 <= size <= _MAX_ARTIFACT_BYTES or
                            (expiry is not None and type(expiry) is not int)):
                        raise ValueError("database artifact manifest entry is invalid")
                    if expiry is not None and expiry <= observed_at:
                        continue
                    name = hashlib.sha256(artifact_id.encode()).hexdigest() + ".blob"
                    member = members.get(f"{scope}/{name}")
                    if member is None:
                        raise ValueError("live artifact referenced by database is missing from backup")
                    source = archive.extractfile(member)
                    if source is None:
                        raise ValueError("live artifact referenced by database is missing from backup")
                    hasher = hashlib.sha256()
                    actual_size = 0
                    with source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            actual_size += len(chunk)
                            hasher.update(chunk)
                    if actual_size != size:
                        raise ValueError("live artifact size does not match database manifest")
                    if hasher.hexdigest() != digest:
                        raise ValueError("live artifact digest does not match database manifest")
                    verified += 1
    except (OSError, KeyError, tarfile.TarError) as exc:
        raise ValueError("live artifact referenced by database is missing or unsafe") from exc
    return verified


def _quiescence() -> dict:
    nonterminal = int(_sql(
        f"SELECT count(*) FROM gateway_runs_v1 WHERE state NOT IN ({TERMINAL_STATES})"
    ))
    active_count = int(_sql(
        "SELECT COALESCE((SELECT active_count FROM gateway_control_v1 WHERE id=1), -1)"
    ))
    if nonterminal or active_count != 0:
        raise ValueError("database is not quiescent: require zero nonterminal runs and active_count=0")

    columns = _sql(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='gateway_runs_v1' "
        "AND column_name IN ('cleanup_state','slot_reserved')"
    )
    cleanup_columns = int(columns)
    if cleanup_columns == 2:
        unsettled = int(_sql(
            "SELECT count(*) FROM gateway_runs_v1 "
            "WHERE cleanup_state NOT IN ('complete','not_required') OR slot_reserved IS TRUE"
        ))
        if unsettled:
            raise ValueError("database has terminal runs without cleanup proof or a reserved slot")
    elif cleanup_columns != 0:
        raise ValueError("database has an incomplete cleanup schema")

    artifact_manifests = int(_sql(
        "SELECT count(*) FROM gateway_runs_v1 "
        f"WHERE result IS NOT NULL AND {_HAS_ARTIFACT_MANIFEST}"
    ))

    schema_table = _sql("SELECT to_regclass('public.gateway_schema_version')::text")
    schema_version = "unversioned"
    if schema_table:
        schema_version = _sql(
            "SELECT COALESCE((SELECT version::text FROM gateway_schema_version WHERE id=1), 'missing')"
        )
        if schema_version == "missing":
            raise ValueError("database has a schema-version table without a version row")
    return {
        "schema_version": schema_version,
        "run_count": int(_sql("SELECT count(*) FROM gateway_runs_v1")),
        "active_count": active_count,
        "artifact_manifest_runs": artifact_manifests,
    }


def create_generation(output_dir: str, artifact_dir: str | None = None, *,
                     services_stopped_confirmed: bool = False) -> Path:
    if services_stopped_confirmed is not True:
        raise ValueError("operator must confirm all Gateway services are stopped")
    systemd_units = _assert_gateway_systemd_units_stopped()
    output = Path(output_dir)
    if not output.is_absolute() or output.is_symlink() or not output.is_dir():
        raise ValueError("output directory must be an absolute, existing, non-symlink directory")
    output = output.resolve(strict=True)
    if output.stat().st_mode & 0o077:
        raise ValueError("output directory must not be accessible by group or other users")
    artifact_root = _artifact_root(artifact_dir, output)
    quiescence = _quiescence()
    artifact_records = _artifact_records()
    artifact_check_time = int(time.time())
    if artifact_root is None and quiescence["artifact_manifest_runs"]:
        raise ValueError("database contains artifact manifests but --artifact-dir was omitted")
    if artifact_root is None and artifact_records:
        raise ValueError("database contains artifact manifests but --artifact-dir was omitted")
    if artifact_root is not None:
        _verify_live_artifact_files(artifact_root, artifact_records, now=artifact_check_time)

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    generation_id = f"{stamp}-{uuid.uuid4().hex}"
    final = output / f"gpu-control-{generation_id}"
    stage = Path(tempfile.mkdtemp(prefix=".gpu-control-incomplete-", dir=output))
    os.chmod(stage, 0o700)
    try:
        database_dump = stage / "database.dump"
        _run(["pg_dump", "--format=custom", "--no-owner", "--no-acl",
              f"--file={database_dump}"])
        if not database_dump.is_file() or database_dump.stat().st_size == 0:
            raise RuntimeError("pg_dump did not create a nonempty database archive")
        os.chmod(database_dump, 0o600)
        _run(["pg_restore", "--list", str(database_dump)])
        _fsync_file(database_dump)

        artifacts = None
        if artifact_root is not None:
            artifact_archive = stage / "artifacts.tar"
            _run(["tar", "--create", "--file", str(artifact_archive),
                  "--exclude=.gpu-control-probes",
                  "--directory", str(artifact_root), "."],
                 env={"COPYFILE_DISABLE": "1"})
            if not artifact_archive.is_file() or artifact_archive.stat().st_size == 0:
                raise RuntimeError("tar did not create a nonempty artifact archive")
            os.chmod(artifact_archive, 0o600)
            _run(["tar", "--list", "--file", str(artifact_archive)])
            _validate_artifact_archive(artifact_archive)
            _verify_artifact_archive_manifests(
                artifact_archive, artifact_records, now=artifact_check_time)
            _fsync_file(artifact_archive)
            artifacts = {
                "archive": "artifacts.tar",
                "size_bytes": artifact_archive.stat().st_size,
                "sha256": _sha256(artifact_archive),
                "source_device": artifact_root.stat().st_dev,
            }

        manifest = {
            "format": 1,
            "generation_id": generation_id,
            "created_at_utc": stamp,
            "consistency": "quiesced",
            "services_stopped_confirmed": True,
            "systemd_units": systemd_units,
            **quiescence,
            "database": {
                "archive": "database.dump",
                "size_bytes": database_dump.stat().st_size,
                "sha256": _sha256(database_dump),
            },
            "artifacts": artifacts,
        }
        manifest_path = stage / "manifest.json"
        fd = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            target.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
            target.flush()
            os.fsync(target.fileno())
        _fsync_directory(stage)

        if final.exists():
            raise FileExistsError(f"backup generation already exists: {final.name}")
        os.rename(stage, final)
        _fsync_directory(output)
        return final
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def verify_generation(generation_dir: str) -> dict:
    generation = Path(generation_dir)
    if not generation.is_absolute() or generation.is_symlink() or not generation.is_dir():
        raise ValueError("generation must be an absolute, existing, non-symlink directory")
    generation = generation.resolve(strict=True)
    manifest_path = generation / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("generation manifest is missing or unsafe")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("format") != 1 or
            manifest.get("consistency") != "quiesced" or
            generation.name != f"gpu-control-{manifest.get('generation_id')}"):
        raise ValueError("generation manifest identity or format is invalid")
    if ("services_stopped_confirmed" in manifest and
            manifest["services_stopped_confirmed"] is not True):
        raise ValueError("generation does not record stopped-service confirmation")
    if ("systemd_units" in manifest and
            manifest["systemd_units"] != {unit: "inactive" for unit in SYSTEMD_BACKUP_UNITS}):
        raise ValueError("generation does not record all Gateway systemd units inactive")

    expected = {"manifest.json", "database.dump"}
    database = manifest.get("database")
    if not isinstance(database, dict) or database.get("archive") != "database.dump":
        raise ValueError("database archive metadata is invalid")
    database_path = generation / "database.dump"
    if (database_path.is_symlink() or not database_path.is_file() or
            database_path.stat().st_size != database.get("size_bytes") or
            _sha256(database_path) != database.get("sha256")):
        raise ValueError("database archive size or checksum does not match manifest")
    _run(["pg_restore", "--list", str(database_path)])

    artifacts = manifest.get("artifacts")
    if manifest.get("artifact_manifest_runs", 0) and artifacts is None:
        raise ValueError("generation omitted artifact bytes referenced by database manifests")
    if artifacts is not None:
        expected.add("artifacts.tar")
        if not isinstance(artifacts, dict) or artifacts.get("archive") != "artifacts.tar":
            raise ValueError("artifact archive metadata is invalid")
        artifact_path = generation / "artifacts.tar"
        if (artifact_path.is_symlink() or not artifact_path.is_file() or
                artifact_path.stat().st_size != artifacts.get("size_bytes") or
                _sha256(artifact_path) != artifacts.get("sha256")):
            raise ValueError("artifact archive size or checksum does not match manifest")
        _run(["tar", "--list", "--file", str(artifact_path)])
        _validate_artifact_archive(artifact_path)
    elif "artifacts.tar" in {entry.name for entry in generation.iterdir()}:
        raise ValueError("unmanifested artifact archive is present")

    actual = {entry.name for entry in generation.iterdir()}
    if actual != expected:
        raise ValueError("generation contains missing or unexpected files")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output-dir",
                        help="existing private directory on the backup filesystem")
    action.add_argument("--verify-generation",
                        help="verify a completed generation before restore")
    parser.add_argument("--artifact-dir",
                        help="configured artifact directory; omit only when no artifacts exist")
    parser.add_argument("--confirm-services-stopped", action="store_true",
                        help="attest that API, worker, and recovery supervisor are stopped")
    args = parser.parse_args(argv)
    try:
        if args.verify_generation:
            if args.artifact_dir:
                parser.error("--artifact-dir is only valid with --output-dir")
            if args.confirm_services_stopped:
                parser.error("--confirm-services-stopped is only valid with --output-dir")
            manifest = verify_generation(args.verify_generation)
            print(json.dumps({"verified": True,
                              "generation_id": manifest["generation_id"],
                              "schema_version": manifest["schema_version"]},
                             sort_keys=True))
            return 0
        if not args.confirm_services_stopped:
            parser.error("--output-dir requires --confirm-services-stopped")
        generation = create_generation(args.output_dir, args.artifact_dir,
                                       services_stopped_confirmed=True)
    except Exception as exc:
        print(f"backup generation failed: {exc}", file=sys.stderr)
        return 2
    print(generation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
