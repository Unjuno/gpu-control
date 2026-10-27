"""Process-crash recovery against a real local Docker container."""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import update

from gpu_gateway.backends import build_backends
from gpu_gateway.artifacts import ArtifactStore
from gpu_gateway.config import Settings, Workload
from gpu_gateway.admission import evaluate_admission, plan_for_workload
from gpu_gateway.contracts import plan_fingerprint
from gpu_gateway.store import runs
from gpu_gateway.worker import Worker


def _docker_ready():
    docker = shutil.which("docker")
    return bool(docker and subprocess.run([docker, "info"], stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, timeout=5).returncode == 0)


@pytest.mark.skipif(not _docker_ready(), reason="Docker/OrbStack daemon is unavailable")
@pytest.mark.skipif(not os.environ.get("GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"),
                    reason="prebuilt digest-pinned CPU smoke image is not configured")
def test_os_worker_crash_after_container_start_reconciles_same_run(system, tmp_path, monkeypatch):
    system.settings = replace(system.settings, artifact_dir=str(tmp_path / "artifacts"))
    system.service.settings = system.settings
    image = os.environ["GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"]
    now = int(system.clock())
    policy = {"version": "local-cpu-v1", "enabled": True, "valid_until": now + 60,
              "workloads": ["cpu-smoke-v1"], "max_runtime_seconds": 30,
              "max_cost_usd": "0.00", "allowed_profiles": ["smoke"]}
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(policy))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    workload = Workload(provider="local_cpu", image_digest=image, execution_profile="smoke",
        requires_gpu=False, source_repository="Unjuno/gpu-control", source_sha="a" * 40,
        max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {
            "iterations": {"type": "integer", "minimum": 1, "maximum": 20_000_000},
            "seed": {"type": "integer"}}, "required": ["iterations", "seed"],
            "additionalProperties": False})
    system.service.workloads["cpu-smoke-v1"] = workload
    candidate = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
        repository="Unjuno/gpu-control", source_sha="a" * 40,
        parameters={"iterations": 1000, "seed": 17}, runtime_seconds=30,
        max_cost_usd="0.00", now=now, policy=policy)
    prepared = system.service.prepare_local(system.owner, candidate, "os-crash-recovery-0001",
        policy, evaluate_admission(candidate, policy, now))
    queued = system.service.submit(system.owner, prepared["id"])
    created = {"id": queued["id"]}
    fingerprint = plan_fingerprint(candidate)

    # Simulate SIGKILL at the exact ambiguous boundary: Docker has started the
    # container, but the worker has not returned/persisted its handle.
    child = r'''
import os, sys
from gpu_gateway.backends import build_backends
from gpu_gateway.config import Settings
from gpu_gateway.store import Store
from gpu_gateway.worker import Worker
settings = Settings(database_url=sys.argv[1])
class CrashAfterDockerStart:
    def __init__(self): self.backend = build_backends(settings)["local_cpu"]
    def start(self, job):
        self.backend.start(job)
        os._exit(73)
    def __getattr__(self, name): return getattr(self.backend, name)
Worker(Store(settings.database_url), settings, {"local_cpu": CrashAfterDockerStart()}).tick()
os._exit(74)
'''
    process = subprocess.run([sys.executable, "-c", child, system.settings.database_url],
                              cwd=os.path.dirname(os.path.dirname(__file__)),
                              capture_output=True, timeout=30)
    assert process.returncode == 73, process.stderr.decode("utf-8", "replace")[-2000:]

    docker = shutil.which("docker") or "docker"
    label = "io.unjuno.gpu-control.run-id=" + created["id"]
    found = subprocess.run([docker, "ps", "-aq", "--filter", "label=" + label],
                           check=True, capture_output=True, text=True, timeout=10).stdout.split()
    assert len(found) == 1
    crashed_row = system.store.read(created["id"])
    assert crashed_row["submission_intent"]["phase"] == "dispatching"
    assert crashed_row["submission_intent"]["attempt"] == 1

    # Force the persisted lease to expire, as would happen after process death.
    # claim() then changes submitting to submit_unknown, and reconcile must adopt
    # the one existing label-bound container instead of starting another one.
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(lease_until=0))

    recovery_supervisor = Worker(system.store, system.settings,
                                 build_backends(system.settings), system.clock,
                                 role="supervisor")
    cancel_run_id = None
    try:
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            assert recovery_supervisor.tick()
            record = system.store.read(created["id"])
            if record["state"] in {"succeeded", "failed", "cancelled", "expired"}:
                break
            system.clock.advance(4)
            time.sleep(0.25)
        assert record["state"] in {"succeeded", "failed"}
        assert record["result"]["run_id"] == created["id"]
        assert record["result"]["source_sha"] == candidate.source_sha
        assert record["result"]["plan_fingerprint"] == fingerprint
        assert record["cleanup_state"] == "complete"
        artifact = record["result"]["artifacts"][0]
        artifact_data = ArtifactStore(system.settings.artifact_dir).get(
            system.owner.owner, created["id"], artifact["artifact_id"], offset=0,
            length=24 * 1024, expected_sha256=artifact["sha256"],
            expected_size=artifact["size_bytes"])
        assert artifact_data == record["result"]["logs"].encode().rstrip(b"\n")
        assert record["submission_intent"]["phase"] == "handle_persisted"
        assert record["handle"]["container_id"].startswith(found[0]) or found[0].startswith(record["handle"]["container_id"])
        remaining = subprocess.run([docker, "ps", "-aq", "--filter", "label=" + label],
                                   check=True, capture_output=True, text=True, timeout=10).stdout.split()
        assert remaining == []

        # New submissions are disabled after this second run starts. Cancellation
        # and cleanup must still work for an already-admitted resource.
        worker = Worker(system.store, system.settings, build_backends(system.settings), system.clock)
        next_now = int(system.clock())
        cancel_candidate = plan_for_workload(workload_name="cpu-smoke-v1",
            workload_manifest=workload.model_dump(mode="json"), repository="Unjuno/gpu-control",
            source_sha="a" * 40, parameters={"iterations": 20_000_000, "seed": 18},
            runtime_seconds=30, max_cost_usd="0.00", now=next_now, policy=policy)
        cancel_prepared = system.service.prepare_local(system.owner, cancel_candidate,
            "cancel-after-policy-off-0001", policy, evaluate_admission(cancel_candidate, policy, next_now))
        cancel_queued = system.service.submit(system.owner, cancel_prepared["id"])
        cancel_run_id = cancel_queued["id"]
        assert worker.tick()
        assert system.store.read(cancel_queued["id"])["state"] == "running"
        policy_path.write_text(json.dumps({**policy, "enabled": False}))
        system.service.cancel(system.owner, cancel_queued["id"])
        # Simulate the execution worker stopping after cancellation is recorded.
        # The independent supervisor must cancel and clean the existing container.
        with system.store.transaction() as connection:
            connection.execute(update(runs).where(runs.c.id == cancel_queued["id"]).values(lease_until=0))
        recovery_supervisor = Worker(system.store, system.settings,
                                     build_backends(system.settings), system.clock,
                                     role="supervisor")
        assert recovery_supervisor.tick()
        cancelled = system.store.read(cancel_queued["id"])
        assert cancelled["state"] == "cancelled"
        assert cancelled["cleanup_state"] == "complete"
        assert system.service.cancel(system.owner, cancel_queued["id"])["state"] == "cancelled"
        cancel_label = "io.unjuno.gpu-control.run-id=" + cancel_queued["id"]
        cancel_remaining = subprocess.run([docker, "ps", "-aq", "--filter", "label=" + cancel_label],
            check=True, capture_output=True, text=True, timeout=10).stdout.split()
        assert cancel_remaining == []
    finally:
        # Test-owned leftovers only; never prune unrelated Docker resources.
        for run_id in (created["id"], cancel_run_id):
            if run_id is None:
                continue
            run_label = "io.unjuno.gpu-control.run-id=" + run_id
            remaining = subprocess.run([docker, "ps", "-aq", "--filter", "label=" + run_label],
                                       capture_output=True, text=True, timeout=10).stdout.split()
            if remaining:
                subprocess.run([docker, "rm", "--force", *remaining], check=False, timeout=15,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
