"""Exercise backup/artifact integrity queries against the dedicated test DB."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import time
import uuid

import pytest
from sqlalchemy import delete, insert, text

from gpu_gateway.store import Store, runs

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))
import backup_generation


@pytest.mark.skipif(
    not os.environ.get("GATEWAY_TEST_DATABASE_URL"),
    reason="PostgreSQL test URL is not configured",
)
def test_postgres_artifact_manifest_and_paired_backup_integrity(tmp_path, monkeypatch):
    url = os.environ["GATEWAY_TEST_DATABASE_URL"]
    store = Store(url)
    owner = "backup-integrity-" + uuid.uuid4().hex
    run_id = uuid.uuid4().hex
    artifact_id = "result.bin"
    payload = b"postgres-backed artifact integrity"
    digest = hashlib.sha256(payload).hexdigest()
    now = int(time.time())
    manifest = {
        "artifact_id": artifact_id,
        "sha256": digest,
        "size_bytes": len(payload),
        "media_type": "application/octet-stream",
        "expires_at": None,
    }
    scope = hashlib.sha256((owner + "\0" + run_id).encode()).hexdigest()
    blob_name = hashlib.sha256(artifact_id.encode()).hexdigest() + ".blob"
    artifact_root = tmp_path / "artifacts"
    blob_dir = artifact_root / scope
    blob_dir.mkdir(parents=True)
    blob_path = blob_dir / blob_name
    blob_path.write_bytes(payload)

    values = {
        "id": run_id,
        "owner": owner,
        "idempotency_key": "backup-integrity-" + uuid.uuid4().hex,
        "request_hash": "1" * 64,
        "fingerprint": "2" * 64,
        "plan": {},
        "state": "succeeded",
        "created_at": now,
        "started_at": now,
        "approved_until": 0,
        "approval_id": "",
        "handle": None,
        "result": {"artifacts": [manifest]},
        "error": "",
        "lease_until": 0,
        "lease_token": "",
        "cancel_requested": False,
        "slot_reserved": False,
        "record_version": 2,
        "cleanup_state": "complete",
        "finished_at": now,
        "result_manifest": None,
        "admission": None,
        "attempt": 1,
        "submission_intent": None,
        "last_observed_at": now,
    }
    inserted_run_ids: list[str] = []
    try:
        store.initialize()
        malformed_run_id = uuid.uuid4().hex
        malformed_values = dict(values)
        malformed_values.update({
            "id": malformed_run_id,
            "owner": owner + "-malformed",
            "idempotency_key": "backup-integrity-malformed-" + uuid.uuid4().hex,
            "result": {"artifacts": {"unexpected": "object"}},
        })
        with store.engine.begin() as connection:
            connection.execute(insert(runs).values(**values))
            inserted_run_ids.append(run_id)
            connection.execute(insert(runs).values(**malformed_values))
            inserted_run_ids.append(malformed_run_id)

        def query_database(query: str) -> str:
            with store.engine.connect() as connection:
                value = connection.execute(text(query)).scalar_one()
            return "" if value is None else str(value)

        monkeypatch.setattr(backup_generation, "_sql", query_database)
        array_shape_count = query_database(
            "SELECT count(*) FROM (VALUES "
            "('{\"artifacts\":{\"unexpected\":\"object\"}}'::json), "
            "('{\"artifacts\":[{\"artifact_id\":\"result.bin\"}]}'::json)"
            f") AS fixture(result) WHERE {backup_generation._HAS_ARTIFACT_MANIFEST}"
        )
        assert int(array_shape_count) == 1
        records = backup_generation._artifact_records()
        record = next(row for row in records if row.get("run_id") == run_id)
        assert record == {"owner": owner, "run_id": run_id, "artifacts": [manifest]}
        assert all(row.get("run_id") != malformed_run_id for row in records)
        assert backup_generation._verify_live_artifact_files(
            artifact_root, [record], now=now) == 1

        archive_path = tmp_path / "artifacts.tar"
        with tarfile.open(archive_path, "w") as archive:
            directory = tarfile.TarInfo("./" + scope)
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            member = tarfile.TarInfo("./" + scope + "/" + blob_name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        backup_generation._validate_artifact_archive(archive_path)
        assert backup_generation._verify_artifact_archive_manifests(
            archive_path, [record], now=now) == 1

        blob_path.write_bytes(b"x" * len(payload))
        with pytest.raises(ValueError, match="digest does not match"):
            backup_generation._verify_live_artifact_files(artifact_root, [record], now=now)
    finally:
        if inserted_run_ids:
            with store.engine.begin() as connection:
                connection.execute(delete(runs).where(runs.c.id.in_(inserted_run_ids)))
        store.engine.dispose()
