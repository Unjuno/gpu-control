"""Real Docker acceptance; requires a live isolated Docker/OrbStack worker."""
import os
import json
import shutil
import subprocess
import time
import uuid
from decimal import Decimal

import pytest

from gpu_gateway.config import Settings
from gpu_gateway.contracts import PlanV2, plan_fingerprint
from gpu_gateway.local_backend import LocalContainerBackend


def _docker_ready():
    docker = shutil.which("docker")
    if not docker:
        return False
    return subprocess.run([docker, "info"], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=5).returncode == 0


@pytest.mark.skipif(not _docker_ready(), reason="Docker/OrbStack daemon is unavailable")
@pytest.mark.skipif(not os.environ.get("GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"),
                    reason="prebuilt digest-pinned CPU smoke image is not configured")
def test_real_cpu_smoke_result():
    now = int(time.time())
    plan = PlanV2(
        schema_version=2, repository="Unjuno/gpu-control", source_sha="a" * 40,
        workload="cpu-smoke-v1", workload_manifest_digest="b" * 64,
        image_digest=os.environ["GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"],
        parameters={"iterations": 1000, "seed": 17}, provider="local_cpu",
        device_requirement={"kind": "cpu", "requires_gpu": False, "profile": "smoke"},
        runtime_seconds=20, max_cost_usd=Decimal("0"),
        cost_evidence={"classification": "LOCAL", "additional_cost_usd": Decimal("0"),
                       "reference": "operator-local-container-smoke", "observed_at": now,
                       "expires_at": now + 60},
        authorization_policy_version="local-cpu-v1",
    )
    fingerprint = plan_fingerprint(plan)
    run_id = uuid.uuid4().hex
    run = {"id": run_id, "owner": "integration-test-owner", "fingerprint": fingerprint,
           "plan": plan.model_dump(mode="json")}
    backend = LocalContainerBackend(Settings())
    handle = backend.start(run)
    try:
        assert handle["run_id"] == run_id
        inspected = subprocess.run(["docker", "inspect", handle["container_id"]], check=True,
                                   capture_output=True, text=True, timeout=10)
        config = json.loads(inspected.stdout)[0]
        host = config["HostConfig"]
        assert config["Config"]["User"] == "10001:10001"
        assert host["NetworkMode"] == "none"
        assert host["ReadonlyRootfs"] is True
        assert host["CapDrop"] == ["ALL"]
        assert host["PidsLimit"] == 32
        assert host["Memory"] == 256 * 1024 * 1024
        assert host["NanoCpus"] == 1_000_000_000
        assert host["LogConfig"]["Type"] == "local"
        assert host.get("Binds") is None
        assert config["Mounts"] == []
        recovered = backend.reconcile(run)
        assert handle["container_id"].startswith(recovered["container_id"])
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            observation = backend.inspect(recovered)
            if observation.state != "running":
                assert observation.state == "succeeded"
                result = observation.result
                assert result["simulation"] is False
                assert result["gpu_used"] is False
                assert result["cleanup_state"] == "pending"
                assert result["source_sha"] == plan.source_sha
                assert result["plan_fingerprint"] == fingerprint
                assert result["checks"] and result["checksum"]
                assert len(observation.artifacts) == 1
                assert observation.artifacts[0].artifact_id == "cpu-smoke-result.json"
                assert observation.artifacts[0].data == result["logs"].encode().rstrip(b"\n")
                assert observation.artifacts[0].media_type == "application/json"
                assert {"non_root", "no_secret_environment", "no_docker_socket",
                        "read_only_rootfs", "network_disabled"} <= set(result["checks"])
                # Capture is durable data; cleanup is a separate idempotent step.
                backend.cleanup(recovered)
                assert backend.is_clean(recovered)
                break
            time.sleep(0.25)
        else:
            pytest.fail("CPU smoke container exceeded its 35 second acceptance deadline")
    finally:
        try:
            backend.cleanup(handle)
        except Exception:
            pass

    timeout_plan = PlanV2.model_validate_json(json.dumps(plan.model_dump(mode="json") | {
        "parameters": {"iterations": 20_000_000, "seed": 17}, "runtime_seconds": 1,
    }))
    timeout_run_id = uuid.uuid4().hex
    timeout_fingerprint = plan_fingerprint(timeout_plan)
    timeout_run = {"id": timeout_run_id, "owner": "integration-test-owner",
                   "fingerprint": timeout_fingerprint,
                   "plan": timeout_plan.model_dump(mode="json")}
    timeout_handle = backend.start(timeout_run)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            observation = backend.inspect(timeout_handle)
            if observation.state != "running":
                assert observation.state == "failed"
                assert observation.result["exit_code"] == 124
                assert observation.result["failure_code"] == "invalid_or_missing_smoke_output"
                assert observation.result["cleanup_state"] == "pending"
                backend.cleanup(timeout_handle)
                assert backend.is_clean(timeout_handle)
                break
            time.sleep(0.1)
        else:
            pytest.fail("trusted supervisor did not stop the over-deadline workload")
    finally:
        try:
            backend.cleanup(timeout_handle)
        except Exception:
            pass
