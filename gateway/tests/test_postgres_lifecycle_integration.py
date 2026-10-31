"""Real PostgreSQL outage between local result capture and persistence."""
import json
import os
import shutil
import subprocess
import time
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update

from gpu_gateway.admission import evaluate_admission, plan_for_workload
from gpu_gateway.artifacts import ArtifactStore
from gpu_gateway.backends import build_backends
from gpu_gateway.config import Settings, Workload
from gpu_gateway.service import ExperimentService, Principal
from gpu_gateway.store import Store, control, runs
from gpu_gateway.worker import Worker

CPU_SMOKE_SOURCE_REPOSITORY = os.environ.get("GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY", "Unjuno/gpu-control")
CPU_SMOKE_SOURCE_SHA = os.environ.get("GPU_CONTROL_CPU_SMOKE_SOURCE_SHA", "a" * 40)


def fake_dedicated_filesystem(monkeypatch, root):
    original_stat = Path.stat

    def stat_with_separate_device(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if path in {root, root / ".gpu-control-probes"}:
            return SimpleNamespace(st_dev=2, st_mode=result.st_mode)
        return result

    monkeypatch.setattr(Path, "stat", stat_with_separate_device)


def _docker_ready():
    docker = shutil.which("docker")
    return bool(docker and subprocess.run([docker, "info"], stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, timeout=5).returncode == 0)


def _postgres_ready(docker: str, container: str) -> bool:
    return subprocess.run([docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "gateway_test"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0


@pytest.mark.skipif(not _docker_ready(), reason="Docker/OrbStack daemon is unavailable")
@pytest.mark.skipif(not os.environ.get("GATEWAY_TEST_DATABASE_URL"), reason="PostgreSQL test URL is not configured")
@pytest.mark.skipif(not os.environ.get("GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"), reason="CPU smoke image is not configured")
@pytest.mark.skipif(not os.environ.get("GPU_CONTROL_POSTGRES_CONTAINER"), reason="dedicated stoppable PostgreSQL container is not configured")
def test_postgres_outage_after_capture_retains_resource_and_recovers(tmp_path, monkeypatch):
    docker = shutil.which("docker") or "docker"
    pg_container = os.environ["GPU_CONTROL_POSTGRES_CONTAINER"]
    url = os.environ["GATEWAY_TEST_DATABASE_URL"]
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / ".gpu-control-probes").mkdir(mode=0o700)
    fake_dedicated_filesystem(monkeypatch, artifact_root)
    settings = Settings(database_url=url, artifact_dir=str(artifact_root))
    store = Store(url)
    store.initialize()
    scopes = frozenset({"experiments:read", "experiments:run", "experiments:cancel"})
    principal = Principal("db-outage-" + uuid.uuid4().hex, scopes)
    now = int(time.time())
    image = os.environ["GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"]
    policy = {"version": "local-cpu-v1", "enabled": True, "valid_until": now + 180,
              "workloads": ["cpu-smoke-v1"], "max_runtime_seconds": 30,
              "max_cost_usd": "0.00", "allowed_profiles": ["smoke"]}
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(policy))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))

    workload = Workload(provider="local_cpu", image_digest=image, execution_profile="smoke",
        requires_gpu=False, source_repository=CPU_SMOKE_SOURCE_REPOSITORY, source_sha=CPU_SMOKE_SOURCE_SHA,
        max_runtime_seconds=30, max_cost_usd=Decimal("0.01"),
        parameter_schema={"type": "object", "properties": {
            "iterations": {"type": "integer", "minimum": 1, "maximum": 20_000_000},
            "seed": {"type": "integer"}}, "required": ["iterations", "seed"],
            "additionalProperties": False})
    monkeypatch.setenv("GATEWAY_WORKLOADS_JSON", json.dumps({
        "cpu-smoke-v1": workload.model_dump(mode="json")}, allow_nan=False))
    service = ExperimentService(store, settings, {"cpu-smoke-v1": workload})
    candidate = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
        repository=CPU_SMOKE_SOURCE_REPOSITORY, source_sha=CPU_SMOKE_SOURCE_SHA,
        parameters={"iterations": 1000, "seed": 91}, runtime_seconds=30,
        max_cost_usd="0.00", now=now, policy=policy)
    prepared = service.prepare_local(principal, candidate, "pg-outage-" + uuid.uuid4().hex,
        policy, evaluate_admission(candidate, policy, now))
    with store.engine.connect() as connection:
        active_before = connection.execute(select(control.c.active_count)).scalar_one()
    service.submit(principal, prepared["id"])
    run_id = prepared["id"]
    run_label = "io.unjuno.gpu-control.run-id=" + run_id
    base_backend = build_backends(settings)["local_cpu"]

    class StopDatabaseAfterTerminalCapture:
        stopped = False
        def start(self, run): return base_backend.start(run)
        def inspect(self, handle): return base_backend.inspect(handle)
        def reconcile(self, run): return base_backend.reconcile(run)
        def cancel(self, handle): return base_backend.cancel(handle)
        def capture(self, handle):
            observation = base_backend.capture(handle)
            if observation.state != "running" and not self.stopped:
                subprocess.run([docker, "stop", "--time", "0", pg_container],
                               check=True, capture_output=True, timeout=15)
                self.stopped = True
            return observation
        def cleanup(self, handle): return base_backend.cleanup(handle)
        def is_clean(self, handle): return base_backend.is_clean(handle)

    outage_backend = StopDatabaseAfterTerminalCapture()
    outage_worker = Worker(store, settings, {"local_cpu": outage_backend})
    try:
        assert outage_worker.tick()  # Submit the real container.
        deadline = time.monotonic() + 40
        outage_error = None
        while time.monotonic() < deadline and not outage_backend.stopped:
            time.sleep(3.2)
            try:
                outage_worker.tick()
            except Exception as error:
                outage_error = error
                break
        assert outage_backend.stopped, "workload did not reach terminal capture"
        assert outage_error is not None, "the database outage did not fail the persistence operation"
    finally:
        subprocess.run([docker, "start", pg_container], check=False, capture_output=True, timeout=20)

    ready_deadline = time.monotonic() + 30
    while time.monotonic() < ready_deadline and not _postgres_ready(docker, pg_container):
        time.sleep(0.25)
    assert _postgres_ready(docker, pg_container), "PostgreSQL did not recover"

    try:
        interrupted = store.read(run_id)
        assert interrupted["state"] == "running"
        assert interrupted["result"] is None
        assert interrupted["slot_reserved"] is True
        found = subprocess.run([docker, "ps", "-aq", "--filter", "label=" + run_label],
                               check=True, capture_output=True, text=True, timeout=10).stdout.split()
        assert len(found) == 1
        with store.transaction() as connection:
            connection.execute(update(runs).where(runs.c.id == run_id).values(lease_until=0))

        recovery_worker = Worker(store, settings, build_backends(settings))
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            assert recovery_worker.tick()
            final = store.read(run_id)
            if final["state"] in {"succeeded", "failed", "cancelled", "expired"}:
                break
            time.sleep(3.2)
        assert final["state"] in {"succeeded", "failed"}
        assert final["result"]["run_id"] == run_id
        artifact = final["result"]["artifacts"][0]
        assert artifact["artifact_id"] == "cpu-smoke-result.json"
        artifact_data = ArtifactStore(settings.artifact_dir).get(
            principal.owner, run_id, artifact["artifact_id"], offset=0,
            length=24 * 1024, expected_sha256=artifact["sha256"],
            expected_size=artifact["size_bytes"])
        assert artifact_data == final["result"]["logs"].encode().removesuffix(b"\n")
        assert final["cleanup_state"] == "complete"
        with store.engine.connect() as connection:
            active_after = connection.execute(select(control.c.active_count)).scalar_one()
        assert active_after == active_before
    finally:
        subprocess.run([docker, "start", pg_container], check=False, capture_output=True, timeout=20)
        leftovers = subprocess.run([docker, "ps", "-aq", "--filter", "label=" + run_label],
                                   capture_output=True, text=True, timeout=10).stdout.split()
        if leftovers:
            subprocess.run([docker, "rm", "--force", *leftovers], check=False, capture_output=True, timeout=15)
        store.engine.dispose()
