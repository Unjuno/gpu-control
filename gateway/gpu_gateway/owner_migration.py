"""Offline, fail-closed owner migration for issuer changes.

Run with API, worker, and supervisor stopped. Artifact directories are staged
first; destination scopes are installed only inside the transaction after the
complete source-row snapshot is locked and revalidated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from sqlalchemy import delete, select, update

from .artifacts import ArtifactStore
from .config import Settings
from .local_oauth import oauth_clients, oauth_codes, oauth_sessions, oauth_tokens
from .service import TERMINAL
from .store import Store, control, runs


def _fsync_tree(path: Path) -> None:
    for item in path.rglob("*"):
        if item.is_symlink():
            raise ValueError("artifact tree contains symlinks")
        if item.is_file():
            fd = os.open(item, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    for directory in sorted((item for item in path.rglob("*") if item.is_dir()),
                            key=lambda item: len(item.parts), reverse=True):
        fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def owner_for(issuer: str, subject: str) -> str:
    # Built-in LocalOAuth canonicalizes its origin with rstrip("/").
    issuer = issuer.rstrip("/")
    if not issuer or not subject or "\x00" in issuer or "\x00" in subject:
        raise ValueError("issuer and subject must be nonempty and NUL-free")
    return hashlib.sha256((issuer + "\x00" + subject).encode()).hexdigest()


def _verify_artifacts(store: ArtifactStore, owner: str, run: dict) -> None:
    result = run.get("result")
    artifacts = result.get("artifacts", []) if isinstance(result, dict) else []
    if not artifacts:
        return
    for item in artifacts:
        size = item.get("size_bytes")
        if type(size) is not int or size < 0:
            raise ValueError(f"invalid artifact manifest for run {run['id']}")
        data = store.get(owner, run["id"], item["artifact_id"], offset=0,
                         length=max(1, min(24 * 1024, size)),
                         expected_sha256=item["sha256"], expected_size=size)
        if size > len(data):
            # get() validates the entire object and returns a bounded first chunk.
            offset = len(data)
            while offset < size:
                data += store.get(owner, run["id"], item["artifact_id"], offset=offset,
                                  length=min(24 * 1024, size - offset),
                                  expected_sha256=item["sha256"], expected_size=size)
                offset = len(data)


def migrate(database_url: str, artifact_dir: str, old_issuer: str, new_issuer: str,
            subject: str, *, apply: bool = False) -> dict:
    old_owner, new_owner = owner_for(old_issuer, subject), owner_for(new_issuer, subject)
    if old_owner == new_owner:
        raise ValueError("source and destination owner are identical")
    store = Store(database_url)
    try:
        with store.engine.connect() as connection:
            active_count = connection.execute(select(control.c.active_count).where(control.c.id == 1)).scalar_one()
            if active_count != 0:
                raise ValueError("control-plane active_count must be zero before owner migration")
            source = [dict(row) for row in connection.execute(
                select(runs).where(runs.c.owner == old_owner)).mappings()]
            collisions = connection.execute(select(runs.c.id).where(
                runs.c.owner == new_owner,
                runs.c.idempotency_key.in_([row["idempotency_key"] for row in source] or ["__none__"])
            )).all()
        if not source:
            raise ValueError("no runs belong to the source issuer and subject")
        if collisions:
            raise ValueError("destination owner has colliding idempotency keys")
        unsettled = [row["id"] for row in source if row["state"] not in TERMINAL or
                     row["cleanup_state"] not in {"complete", "not_required"} or row["slot_reserved"]]
        if unsettled:
            raise ValueError("all source runs must be terminal, cleaned, and have no reserved slot")
        artifact_store = ArtifactStore(artifact_dir) if artifact_dir else None
        artifact_runs = []
        for row in source:
            result = row.get("result")
            items = result.get("artifacts", []) if isinstance(result, dict) else []
            if items:
                if artifact_store is None:
                    raise ValueError("source runs have artifacts but GATEWAY_ARTIFACT_DIR is unset")
                _verify_artifacts(artifact_store, old_owner, row)
                artifact_runs.append(row)

        summary = {"source_owner": old_owner, "destination_owner": new_owner,
                   "runs": len(source), "artifact_runs": len(artifact_runs), "applied": False}
        if not apply:
            return summary

        root = Path(artifact_dir).expanduser().absolute() if artifact_dir else None
        staged: list[tuple[Path, Path]] = []
        if root and artifact_runs:
            if root.is_symlink() or not root.is_dir():
                raise ValueError("artifact root must exist and be a real directory")
            for row in artifact_runs:
                old_path = root / ArtifactStore._scope(old_owner, row["id"])
                new_path = root / ArtifactStore._scope(new_owner, row["id"])
                backup_path = root / f".owner-migration-backup-{old_owner[:12]}-{row['id']}"
                if old_path.is_symlink() or not old_path.is_dir() or new_path.is_symlink():
                    raise ValueError("artifact source missing or a scope path is a symlink")
                _fsync_tree(old_path)
                if backup_path.is_symlink():
                    raise ValueError("rollback artifact path must not be a symlink")
                if backup_path.exists():
                    if not backup_path.is_dir():
                        raise ValueError("rollback artifact path is not a directory")
                    old_files = {p.name: p.read_bytes() for p in old_path.iterdir() if p.is_file() and not p.is_symlink()}
                    backup_files = {p.name: p.read_bytes() for p in backup_path.iterdir() if p.is_file() and not p.is_symlink()}
                    if old_files != backup_files or len(old_files) != len(list(old_path.iterdir())):
                        # Source-owner rows still exist, so the old scope remains
                        # authoritative. Rebuild a rollback copy interrupted by SIGKILL.
                        shutil.rmtree(backup_path)
                if not backup_path.exists():
                    try:
                        shutil.copytree(old_path, backup_path, symlinks=False)
                        _fsync_tree(backup_path)
                    except BaseException:
                        if backup_path.exists():
                            shutil.rmtree(backup_path)
                        raise
                old_files = {p.name: p.read_bytes() for p in old_path.iterdir() if p.is_file() and not p.is_symlink()}
                backup_files = {p.name: p.read_bytes() for p in backup_path.iterdir() if p.is_file() and not p.is_symlink()}
                if old_files != backup_files or len(old_files) != len(list(old_path.iterdir())):
                    raise ValueError("rollback artifact copy differs from source")
                if new_path.exists():
                    # A prior interrupted attempt may have installed the verified
                    # copy before committing DB ownership. Reuse only byte-identical trees.
                    new_files = {p.name: p.read_bytes() for p in new_path.iterdir() if p.is_file() and not p.is_symlink()}
                    if old_files != new_files or len(old_files) != len(list(old_path.iterdir())):
                        raise ValueError("existing destination artifact scope differs from source")
                    staged.append((new_path, new_path))
                    continue
                staged_path = root / (".owner-migration-" + row["id"])
                if staged_path.is_symlink():
                    raise ValueError("staging path must not be a symlink")
                if staged_path.exists():
                    if not staged_path.is_dir():
                        raise ValueError("staging path is not a directory")
                    # The old DB owner still names the authoritative source.
                    # A partial staging tree can therefore be safely rebuilt.
                    shutil.rmtree(staged_path)
                try:
                    shutil.copytree(old_path, staged_path, symlinks=False)
                    _fsync_tree(staged_path)
                except BaseException:
                    if staged_path.exists():
                        shutil.rmtree(staged_path)
                    raise
                if any(path.is_symlink() for path in staged_path.rglob("*")):
                    shutil.rmtree(staged_path)
                    raise ValueError("artifact tree contains symlinks")
                staged.append((staged_path, new_path))

        try:
            with store.transaction() as connection:
                active_count = connection.execute(select(control.c.active_count).where(
                    control.c.id == 1).with_for_update()).scalar_one()
                if active_count != 0:
                    raise ValueError("control-plane active_count changed during migration")
                current = [dict(row) for row in connection.execute(
                    select(runs).where(runs.c.owner == old_owner).with_for_update()).mappings()]
                source_by_id = {row["id"]: row for row in source}
                current_by_id = {row["id"]: row for row in current}
                if current_by_id != source_by_id:
                    raise ValueError("source run records changed during migration")
                if any(row["state"] not in TERMINAL or
                       row["cleanup_state"] not in {"complete", "not_required"} or
                       row["slot_reserved"] for row in current):
                    raise ValueError("source runs are no longer settled")
                keys = [row["idempotency_key"] for row in current]
                if connection.execute(select(runs.c.id).where(
                    runs.c.owner == new_owner,
                    runs.c.idempotency_key.in_(keys or ["__none__"])
                )).first() is not None:
                    raise ValueError("destination owner acquired a colliding idempotency key")

                # Lock and compare the complete source snapshot before installing
                # destination scopes. A crash before commit leaves the source owner
                # authoritative; retry can reuse only byte-identical destinations.
                for staged_path, new_path in staged:
                    if staged_path != new_path:
                        staged_path.rename(new_path)
                if root and staged:
                    fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                if root and artifact_runs:
                    for artifact_run in artifact_runs:
                        _verify_artifacts(artifact_store, new_owner, artifact_run)
                for row in current:
                    intent = row.get("submission_intent")
                    if isinstance(intent, dict) and intent.get("owner") == old_owner:
                        intent = intent | {"owner": new_owner}
                        connection.execute(update(runs).where(runs.c.id == row["id"]).values(
                            owner=new_owner, submission_intent=intent))
                    else:
                        connection.execute(update(runs).where(runs.c.id == row["id"]).values(owner=new_owner))
                # Opaque local tokens do not carry their mint-time issuer in the
                # token table. Revoke all credentials and force client re-registration.
                connection.execute(update(oauth_tokens).values(revoked=True))
                connection.execute(delete(oauth_sessions))
                connection.execute(delete(oauth_codes))
                connection.execute(delete(oauth_clients))
        except BaseException:
            for staged_path, new_path in staged:
                if staged_path != new_path and staged_path.exists():
                    shutil.rmtree(staged_path)
            raise
        summary["applied"] = True
        return summary
    finally:
        store.engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-issuer", required=True)
    parser.add_argument("--new-issuer", required=True)
    parser.add_argument("--subject", default="owner")
    parser.add_argument("--apply", action="store_true", help="perform migration; default is read-only preflight")
    parser.add_argument("--confirm-services-stopped-and-backup-complete", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.confirm_services_stopped_and_backup_complete:
        parser.error("--apply requires --confirm-services-stopped-and-backup-complete")
    settings = Settings.from_env()
    if settings.issuer:
        parser.error("this command migrates built-in single-owner OAuth only; external OIDC is not supported")
    if args.subject != "owner":
        parser.error("built-in single-owner OAuth currently uses the fixed subject 'owner'")
    if args.new_issuer.rstrip("/") != settings.public_url.rstrip("/"):
        parser.error("--new-issuer must match GATEWAY_PUBLIC_URL for the new deployment")
    try:
        result = migrate(settings.database_url, settings.artifact_dir, args.old_issuer,
                         args.new_issuer, args.subject, apply=args.apply)
    except Exception as exc:
        print(f"owner migration refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
