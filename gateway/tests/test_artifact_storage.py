import base64
import hashlib
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from gpu_gateway.artifacts import ArtifactStore, inspect_artifact_storage


def create_probe_directory(root):
    probe = root / ".gpu-control-probes"
    probe.mkdir(mode=0o3770)
    probe.chmod(0o3770)
    return probe
from gpu_gateway.backends import ArtifactPayload, Observation
from gpu_gateway.experiment_api import invoke
from gpu_gateway.service import GatewayError, Prepare, Principal
from gpu_gateway.store import runs
from gpu_gateway.worker import Worker


def fake_dedicated_filesystem(monkeypatch, root):
    original_stat = Path.stat

    def stat_with_separate_device(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_dev=2 if path in {root, root / ".gpu-control-probes"} else result.st_dev,
                               st_mode=result.st_mode)

    monkeypatch.setattr("gpu_gateway.artifacts.Path.stat", stat_with_separate_device)


def test_artifact_storage_probe_fails_closed_on_missing_or_symlink_root(tmp_path, monkeypatch):
    assert inspect_artifact_storage("")["reason"] == "not_configured"
    missing = inspect_artifact_storage(str(tmp_path / "missing"))
    assert missing["available"] is False
    assert missing["reason"] == "not_directory"
    root = tmp_path / "private"
    root.mkdir()
    create_probe_directory(root)
    fake_dedicated_filesystem(monkeypatch, root)
    original_write = os.write

    def write_after_unlink(fd, data):
        assert list((root / ".gpu-control-probes").iterdir()) == []
        return original_write(fd, data)

    monkeypatch.setattr("gpu_gateway.artifacts.os.write", write_after_unlink)
    available = inspect_artifact_storage(str(root))
    assert available["configured"] is True
    assert available["available"] is True
    assert type(available["free_bytes"]) is int and available["free_bytes"] > 0
    assert list((root / ".gpu-control-probes").iterdir()) == []
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    assert inspect_artifact_storage(str(alias))["reason"] == "symlink"


def test_artifact_storage_probe_fails_closed_when_write_probe_fails(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir()
    create_probe_directory(root)
    fake_dedicated_filesystem(monkeypatch, root)
    original_open = os.open

    def reject_probe(path, flags, *args, **kwargs):
        if isinstance(path, str) and path.startswith(".gpu-control-write-probe-"):
            raise OSError("read-only artifact filesystem")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr("gpu_gateway.artifacts.os.open", reject_probe)
    result = inspect_artifact_storage(str(root))
    assert result["configured"] is True
    assert result["available"] is False
    assert result["reason"] == "write_probe_failed"
    assert list((root / ".gpu-control-probes").iterdir()) == []


def test_artifact_storage_probe_fails_closed_when_statvfs_raises(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir()
    create_probe_directory(root)
    fake_dedicated_filesystem(monkeypatch, root)

    def unavailable(_path):
        raise OSError("simulated capacity query failure")

    monkeypatch.setattr("gpu_gateway.artifacts.os.statvfs", unavailable)
    result = inspect_artifact_storage(str(root))
    assert result == {"configured": True, "available": False,
                      "free_bytes": None, "reason": "unavailable"}


def test_artifact_storage_probe_enforces_configured_minimum_free_bytes(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir()
    create_probe_directory(root)
    fake_dedicated_filesystem(monkeypatch, root)
    monkeypatch.setattr("gpu_gateway.artifacts.os.statvfs", lambda _: SimpleNamespace(
        f_bavail=8, f_frsize=1024 * 1024))
    result = inspect_artifact_storage(str(root), 9 * 1024 * 1024)
    assert result == {"configured": True, "available": False,
                      "free_bytes": 8 * 1024 * 1024,
                      "minimum_free_bytes": 9 * 1024 * 1024,
                      "reason": "below_minimum_free_bytes"}


def test_artifact_storage_probe_requires_separate_filesystem_when_floor_is_configured(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    result = inspect_artifact_storage(str(root), 1024)
    assert result == {"configured": True, "available": False, "free_bytes": None,
                      "minimum_free_bytes": 1024,
                      "reason": "not_dedicated_filesystem"}


def test_artifact_storage_probe_requires_separate_filesystem_without_capacity_floor(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    create_probe_directory(root)
    result = inspect_artifact_storage(str(root), 0)
    assert result == {"configured": True, "available": False, "free_bytes": None,
                      "minimum_free_bytes": 0,
                      "reason": "not_dedicated_filesystem"}


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
    assert stored[0].stat().st_mode & 0o777 == 0o640
    assert stored[0].parent.stat().st_mode & 0o7777 == 0o2750
    assert (tmp_path / "private").stat().st_mode & 0o7777 == 0o2750
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
