import base64
import hashlib
import os
from dataclasses import replace

import pytest
from sqlalchemy import update

from gpu_gateway.artifacts import ArtifactStore
from gpu_gateway.backends import ArtifactPayload, Observation
from gpu_gateway.experiment_api import invoke
from gpu_gateway.service import GatewayError, Prepare, Principal
from gpu_gateway.store import runs
from gpu_gateway.worker import Worker


def test_artifact_store_writes_private_content_addressed_blob_and_verifies_chunks(tmp_path):
    store = ArtifactStore(str(tmp_path / "private"))
    data = bytes(range(256)) * 400
    metadata = store.put("owner", "a" * 32, "model-summary.bin", data,
                         media_type="application/octet-stream", expires_at=9999999999)

    chunks = [store.get("owner", "a" * 32, "model-summary.bin", offset=offset, length=24000,
                        expected_sha256=metadata["sha256"], expected_size=metadata["size_bytes"])
              for offset in range(0, len(data), 24000)]
    assert b"".join(chunks) == data
    assert metadata["sha256"] == hashlib.sha256(data).hexdigest()
    stored = list((tmp_path / "private").rglob("*.blob"))
    assert len(stored) == 1
    assert stored[0].stat().st_mode & 0o777 == 0o600
    assert store.put("owner", "a" * 32, "model-summary.bin", data,
                     media_type="application/octet-stream", expires_at=9999999999) == metadata
    with pytest.raises(ValueError, match="different content"):
        store.put("owner", "a" * 32, "model-summary.bin", b"replacement",
                  media_type="application/octet-stream", expires_at=9999999999)


def test_artifact_tool_is_owner_scoped_and_returns_bounded_chunks(system, tmp_path):
    prepared = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="artifact-result-0001"))
    artifact_id = "result.json"
    data = b'{"answer":42}'
    system.service.settings = replace(system.settings, artifact_dir=str(tmp_path / "artifacts"))
    worker = Worker(system.store, system.service.settings, {}, system.clock)
    result = worker._persist_artifacts(
        {"owner": system.owner.owner, "id": prepared["id"]},
        Observation("succeeded", {"artifacts": [], "simulation": False},
                    (ArtifactPayload(artifact_id, data, "application/json"),)))
    metadata = result["artifacts"][0]
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == prepared["id"]).values(
            state="succeeded", cleanup_state="complete", result=result))

    response = invoke(system.service, system.owner, "experiment_artifact", {
        "run_id": prepared["id"], "artifact_id": artifact_id, "offset": 0, "length": 64})
    payload = response["machine_state"]
    assert payload["complete"] is True
    assert payload["sha256"] == metadata["sha256"]
    assert base64.b64decode(payload["data_base64"]) == data

    other = Principal("other", system.owner.scopes)
    with pytest.raises(GatewayError) as error:
        invoke(system.service, other, "experiment_artifact", {
            "run_id": prepared["id"], "artifact_id": artifact_id})
    assert error.value.code == "not_found"


def test_artifact_tool_rejects_unlisted_artifact_and_expiry(system, tmp_path):
    system.service.settings = replace(system.settings, artifact_dir=str(tmp_path / "artifacts"))
    prepared = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="artifact-expired-0001"))
    expired = {"artifact_id": "old.bin", "sha256": hashlib.sha256(b"x").hexdigest(),
               "size_bytes": 1, "media_type": "application/octet-stream",
               "expires_at": int(system.clock()) - 1}
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == prepared["id"]).values(
            state="succeeded", cleanup_state="complete", result={"artifacts": [expired]}))

    with pytest.raises(GatewayError) as error:
        invoke(system.service, system.owner, "experiment_artifact", {
            "run_id": prepared["id"], "artifact_id": "old.bin"})
    assert error.value.code == "artifact_expired"

    with pytest.raises(GatewayError) as error:
        invoke(system.service, system.owner, "experiment_artifact", {
            "run_id": prepared["id"], "artifact_id": "not-listed"})
    assert error.value.code == "not_found"


def test_artifact_pruning_removes_expired_and_old_orphans_but_preserves_active_and_recent(tmp_path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    now = 100_000
    expired = store.put("owner", "a" * 32, "expired.bin", b"expired",
                        media_type="application/octet-stream", expires_at=now - 1)
    active = store.put("owner", "b" * 32, "active.bin", b"active",
                       media_type="application/octet-stream", expires_at=now - 1)
    old_orphan = store.put("owner", "c" * 32, "orphan.bin", b"orphan",
                           media_type="application/octet-stream", expires_at=None)
    recent_orphan = store.put("owner", "d" * 32, "recent.bin", b"recent",
                              media_type="application/octet-stream", expires_at=None)
    paths = {
        run_id: store._directory("owner", run_id, create=False) / (hashlib.sha256(artifact_id.encode()).hexdigest() + ".blob")
        for run_id, artifact_id in (("a" * 32, "expired.bin"), ("b" * 32, "active.bin"),
                                    ("c" * 32, "orphan.bin"), ("d" * 32, "recent.bin"))
    }
    os.utime(paths["c" * 32], (now - 90_000, now - 90_000))
    rows = [
        {"id": "a" * 32, "owner": "owner", "state": "succeeded", "result": {"artifacts": [expired]}},
        {"id": "b" * 32, "owner": "owner", "state": "running", "result": None},
        {"id": "c" * 32, "owner": "owner", "state": "failed", "result": {"artifacts": []}},
        {"id": "d" * 32, "owner": "owner", "state": "succeeded", "result": {"artifacts": []}},
    ]

    result = store.prune(rows, now=now)
    assert result == {"expired_files": 1, "orphan_files": 1, "bytes_removed": len(b"expired") + len(b"orphan")}
    assert not paths["a" * 32].exists()
    assert paths["b" * 32].exists()
    assert not paths["c" * 32].exists()
    assert paths["d" * 32].exists()
