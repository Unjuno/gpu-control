import base64
import shutil
from dataclasses import replace

import pytest
from sqlalchemy import insert, select, update

from gpu_gateway.artifacts import ArtifactStore
from gpu_gateway.experiment_api import invoke
from gpu_gateway.local_oauth import oauth_sessions, oauth_tokens
import gpu_gateway.owner_migration as owner_migration_module
from gpu_gateway.owner_migration import migrate, owner_for
from gpu_gateway.service import GatewayError, Principal
from gpu_gateway.store import Store, control, runs


def _run(store, owner, run_id, *, key="request-key", state="succeeded", cleanup="complete",
         slot=False, result=None):
    with store.transaction() as connection:
        connection.execute(insert(runs).values(
            id=run_id, owner=owner, idempotency_key=key, request_hash="a" * 64,
            fingerprint="b" * 64, plan={"workload": "test", "provider": "demo"},
            state=state, created_at=1, started_at=1,
            approved_until=0, approval_id="", handle=None, result=result or {}, error="",
            lease_until=0, lease_token="", cancel_requested=False, slot_reserved=slot,
            record_version=2, cleanup_state=cleanup, finished_at=2, result_manifest=None,
            admission=None, attempt=1, submission_intent={"owner": owner}, last_observed_at=2,
        ))


def _database(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'migration.db'}")
    store.initialize()
    return store


def test_issuer_migration_preflight_and_apply_preserve_results_and_revoke_local_auth(tmp_path):
    store = _database(tmp_path)
    root = tmp_path / "artifacts"
    old, new = owner_for("https://old.example/", "owner"), owner_for("https://new.example", "owner")
    run_id, content = "a" * 32, b"migration result"
    metadata = ArtifactStore(str(root)).put(
        old, run_id, "report.json", content, media_type="application/json", expires_at=None)
    _run(store, old, run_id, result={"artifacts": [metadata]})
    with store.transaction() as connection:
        connection.execute(insert(oauth_tokens).values(
            token_hash="c" * 64, kind="refresh", client_id="client", subject="owner",
            scope="experiments:read", resource="https://old.example/mcp",
            expires_at=100, created_at=1, revoked=False))
        connection.execute(insert(oauth_sessions).values(
            token_hash="d" * 64, csrf="csrf", expires_at=100, created_at=1))

    preview = migrate(str(store.engine.url), str(root), "https://old.example", "https://new.example", "owner")
    assert preview["applied"] is False
    assert store.read(run_id)["owner"] == old

    result = migrate(str(store.engine.url), str(root), "https://old.example", "https://new.example", "owner", apply=True)
    assert result["applied"] is True
    row = store.read(run_id)
    assert row["owner"] == new
    assert row["submission_intent"]["owner"] == new
    retrieved = ArtifactStore(str(root)).get(
        new, run_id, "report.json", offset=0, length=128,
        expected_sha256=metadata["sha256"], expected_size=metadata["size_bytes"])
    assert retrieved == content
    assert any(path.name.startswith(".owner-migration-backup-") for path in root.iterdir())
    with store.engine.connect() as connection:
        assert connection.execute(select(oauth_tokens.c.revoked)).scalar_one() is True
        assert connection.execute(select(oauth_sessions)).all() == []
    store.engine.dispose()


@pytest.mark.parametrize(
    ("state", "cleanup", "slot"),
    [("running", "pending", True), ("succeeded", "unknown", False), ("succeeded", "complete", True)],
)
def test_issuer_migration_refuses_unsettled_runs_without_mutation(tmp_path, state, cleanup, slot):
    store = _database(tmp_path)
    old = owner_for("https://old.example", "owner")
    run_id = "e" * 32
    _run(store, old, run_id, state=state, cleanup=cleanup, slot=slot)
    with pytest.raises(ValueError, match="terminal, cleaned"):
        migrate(str(store.engine.url), "", "https://old.example", "https://new.example", "owner", apply=True)
    assert store.read(run_id)["owner"] == old
    store.engine.dispose()


def test_issuer_migration_refuses_destination_idempotency_collision(tmp_path):
    store = _database(tmp_path)
    old, new = owner_for("https://old.example", "owner"), owner_for("https://new.example", "owner")
    _run(store, old, "1" * 32)
    _run(store, new, "2" * 32)
    with pytest.raises(ValueError, match="colliding idempotency"):
        migrate(str(store.engine.url), "", "https://old.example", "https://new.example", "owner", apply=True)
    assert store.read("1" * 32)["owner"] == old
    store.engine.dispose()


def test_issuer_migration_refuses_nonzero_global_active_count(tmp_path):
    store = _database(tmp_path)
    old = owner_for("https://old.example", "owner")
    _run(store, old, "6" * 32)
    with store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
    with pytest.raises(ValueError, match="active_count"):
        migrate(str(store.engine.url), "", "https://old.example", "https://new.example", "owner", apply=True)
    assert store.read("6" * 32)["owner"] == old
    store.engine.dispose()


def test_issuer_migration_refuses_corrupt_artifact_before_owner_update(tmp_path):
    store = _database(tmp_path)
    root = tmp_path / "artifacts"
    old = owner_for("https://old.example", "owner")
    run_id = "3" * 32
    content = b"known result"
    metadata = ArtifactStore(str(root)).put(
        old, run_id, "report", content, media_type="application/json", expires_at=None)
    _run(store, old, run_id, result={"artifacts": [metadata]})
    path = next(root.rglob("*.blob"))
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact size|digest"):
        migrate(str(store.engine.url), str(root), "https://old.example", "https://new.example", "owner", apply=True)
    assert store.read(run_id)["owner"] == old
    store.engine.dispose()


def test_issuer_migration_resumes_after_destination_scope_install(tmp_path):
    store = _database(tmp_path)
    root = tmp_path / "artifacts"
    old, new = owner_for("https://old.example", "owner"), owner_for("https://new.example", "owner")
    run_id, content = "4" * 32, b"recovery payload"
    metadata = ArtifactStore(str(root)).put(
        old, run_id, "report", content, media_type="application/json", expires_at=None)
    _run(store, old, run_id, result={"artifacts": [metadata]})
    source = root / ArtifactStore._scope(old, run_id)
    installed = root / ArtifactStore._scope(new, run_id)
    shutil.copytree(source, installed)

    result = migrate(str(store.engine.url), str(root), "https://old.example", "https://new.example", "owner", apply=True)

    assert result["applied"] is True
    assert store.read(run_id)["owner"] == new
    assert ArtifactStore(str(root)).get(
        new, run_id, "report", offset=0, length=128,
        expected_sha256=metadata["sha256"], expected_size=metadata["size_bytes"]) == content
    store.engine.dispose()


def test_issuer_migration_refuses_run_result_change_during_artifact_copy(tmp_path, monkeypatch):
    store = _database(tmp_path)
    root = tmp_path / "artifacts"
    old, new = owner_for("https://old.example", "owner"), owner_for("https://new.example", "owner")
    run_id, content = "8" * 32, b"authoritative result"
    metadata = ArtifactStore(str(root)).put(
        old, run_id, "report", content, media_type="application/json", expires_at=None)
    original_result = {"artifacts": [metadata]}
    _run(store, old, run_id, result=original_result)
    verify = owner_migration_module._verify_artifacts
    calls = 0

    def change_result_after_preflight(artifact_store, owner, run):
        nonlocal calls
        verify(artifact_store, owner, run)
        calls += 1
        if calls == 1:
            changed = {"artifacts": [metadata | {"sha256": "f" * 64}]}
            with store.transaction() as connection:
                connection.execute(update(runs).where(runs.c.id == run_id).values(result=changed))

    monkeypatch.setattr(owner_migration_module, "_verify_artifacts", change_result_after_preflight)

    with pytest.raises(ValueError, match="source run records changed"):
        migrate(str(store.engine.url), str(root), "https://old.example", "https://new.example", "owner", apply=True)

    assert store.read(run_id)["owner"] == old
    assert store.read(run_id)["result"] == {"artifacts": [metadata | {"sha256": "f" * 64}]}
    assert not (root / ArtifactStore._scope(new, run_id)).exists()
    store.engine.dispose()


@pytest.mark.parametrize("interrupted_copy", ["rollback", "staging"])
def test_issuer_migration_rebuilds_partial_interrupted_copy(tmp_path, interrupted_copy):
    store = _database(tmp_path)
    root = tmp_path / "artifacts"
    old, new = owner_for("https://old.example", "owner"), owner_for("https://new.example", "owner")
    run_id, content = "7" * 32, b"authoritative source content"
    metadata = ArtifactStore(str(root)).put(
        old, run_id, "report", content, media_type="application/json", expires_at=None)
    _run(store, old, run_id, result={"artifacts": [metadata]})
    interrupted = (root / f".owner-migration-backup-{old[:12]}-{run_id}"
                   if interrupted_copy == "rollback" else root / f".owner-migration-{run_id}")
    interrupted.mkdir()
    (interrupted / "partial.tmp").write_bytes(b"incomplete copy")

    migrate(str(store.engine.url), str(root), "https://old.example", "https://new.example", "owner", apply=True)

    assert store.read(run_id)["owner"] == new
    assert ArtifactStore(str(root)).get(
        new, run_id, "report", offset=0, length=128,
        expected_sha256=metadata["sha256"], expected_size=metadata["size_bytes"]) == content
    store.engine.dispose()


def test_migrated_owner_can_retrieve_run_and_artifact_but_old_and_unrelated_owners_cannot(system, tmp_path):
    root = tmp_path / "owner-artifacts"
    old, new = owner_for("https://old.example", "owner"), owner_for("https://new.example", "owner")
    run_id, content = "5" * 32, b"owner scoped output"
    metadata = ArtifactStore(str(root)).put(
        old, run_id, "output.json", content, media_type="application/json", expires_at=None)
    _run(system.store, old, run_id, result={"artifacts": [metadata]})
    system.service.settings = replace(system.settings, artifact_dir=str(root))
    migrate(str(system.store.engine.url), str(root), "https://old.example", "https://new.example", "owner", apply=True)

    scopes = frozenset({"experiments:read"})
    migrated = Principal(new, scopes)
    previous = Principal(old, scopes)
    unrelated = Principal("unrelated-owner", scopes)
    listed = invoke(system.service, migrated, "experiment_list", {})
    assert [item["run_id"] for item in listed["experiments"]] == [run_id]
    assert invoke(system.service, migrated, "experiment_status", {"run_id": run_id})["status"] == "ok"
    result = invoke(system.service, migrated, "experiment_result", {"run_id": run_id})
    assert result["machine_state"]["result"]["artifacts"] == [metadata]
    artifact = invoke(system.service, migrated, "experiment_artifact", {
        "run_id": run_id, "artifact_id": "output.json", "offset": 0, "length": 128})
    assert base64.b64decode(artifact["machine_state"]["data_base64"]) == content

    assert invoke(system.service, previous, "experiment_list", {})["experiments"] == []
    for principal in (previous, unrelated):
        for tool, args in (
            ("experiment_status", {"run_id": run_id}),
            ("experiment_result", {"run_id": run_id}),
            ("experiment_artifact", {"run_id": run_id, "artifact_id": "output.json"}),
        ):
            with pytest.raises(GatewayError) as error:
                invoke(system.service, principal, tool, args)
            assert error.value.status == 404
        assert invoke(system.service, principal, "experiment_list", {})["experiments"] == []
