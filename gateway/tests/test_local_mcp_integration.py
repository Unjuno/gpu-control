"""Authenticated MCP-to-real-Docker CPU vertical; requires an isolated daemon."""
import base64
import json
import os
import shutil
import subprocess
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from gpu_gateway.app import create_app
from gpu_gateway.backends import build_backends
from gpu_gateway.config import Workload
from gpu_gateway.worker import Worker

SOURCE_REPOSITORY = os.environ.get("GPU_CONTROL_CPU_SMOKE_SOURCE_REPOSITORY", "Unjuno/gpu-control")
SOURCE_SHA = os.environ.get("GPU_CONTROL_CPU_SMOKE_SOURCE_SHA", "a" * 40)


def _docker_ready():
    docker = shutil.which("docker")
    return bool(docker and subprocess.run([docker, "info"], stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, timeout=5).returncode == 0)


@pytest.mark.skipif(not _docker_ready(), reason="Docker/OrbStack daemon is unavailable")
@pytest.mark.skipif(not os.environ.get("GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"),
                    reason="prebuilt digest-pinned CPU smoke image is not configured")
def test_authenticated_mcp_cpu_run_and_cross_client_artifact_retrieval(web, tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    settings = replace(web.settings, artifact_dir=str(artifact_root), artifact_min_free_bytes=0)
    web.service.settings = settings
    workload = Workload(
        provider="local_cpu", image_digest=os.environ["GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"],
        execution_profile="smoke", source_repository=SOURCE_REPOSITORY,
        source_sha=SOURCE_SHA, requires_gpu=False, max_runtime_seconds=30,
        max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {
            "iterations": {"type": "integer", "minimum": 1, "maximum": 20_000_000},
            "seed": {"type": "integer", "minimum": 0, "maximum": 1_000_000}},
            "required": ["iterations", "seed"], "additionalProperties": False},
    )
    web.service.workloads = {"cpu-smoke-v1": workload}
    now = int(web.clock())
    policy = {"version": "local-cpu-v1", "enabled": True, "valid_until": now + 180,
              "workloads": ["cpu-smoke-v1"], "max_runtime_seconds": 30,
              "max_cost_usd": "0.00", "allowed_profiles": ["smoke"]}
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(policy))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))

    app = create_app(settings, service=web.service, auth=web.auth)
    first_conversation = TestClient(app)
    second_conversation = TestClient(app)
    run_id = None

    def call(client, name, arguments):
        response = client.post("/mcp", headers=web.headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        assert response.status_code == 200, response.text
        payload = response.json()["result"]
        assert payload.get("isError") is not True, payload
        return payload["structuredContent"]

    try:
        listed = first_conversation.post("/mcp", headers=web.headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/list",
        })
        assert listed.status_code == 200
        assert "experiment_prepare" in {item["name"] for item in listed.json()["result"]["tools"]}

        request = {"repository": SOURCE_REPOSITORY, "commit": SOURCE_SHA,
                   "workload": "cpu-smoke-v1", "parameters": {"iterations": 1000, "seed": 17},
                   "runtime_seconds": 30, "max_cost_usd": "0.00",
                   "idempotency_key": "mcp-local-e2e-0001", "requires_gpu": False}
        prepared = call(first_conversation, "experiment_prepare", request)
        assert prepared["status"] == "ok", prepared
        run_id = prepared["machine_state"]["run_id"]
        fingerprint = prepared["machine_state"]["plan_fingerprint"]
        replay = call(first_conversation, "experiment_prepare", request)
        assert replay["machine_state"]["run_id"] == run_id

        submitted = call(first_conversation, "experiment_submit", {
            "run_id": run_id, "plan_fingerprint": fingerprint,
        })
        assert submitted["machine_state"]["state"] == "queued"
        worker = Worker(web.service.store, settings, build_backends(settings), web.clock,
                        workloads=web.service.workloads)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            worker.tick()
            record = web.service.store.read(run_id)
            if record["state"] in {"succeeded", "failed", "cancelled", "expired"}:
                break
            web.clock.advance(4)
            time.sleep(0.1)
        assert record["state"] == "succeeded", record
        assert record["cleanup_state"] == "complete"

        retrieved = call(second_conversation, "experiment_result", {"run_id": run_id})
        result = retrieved["machine_state"]["result"]
        assert retrieved["status"] == "ok"
        assert result["simulation"] is False and result["gpu_used"] is False
        assert result["source_sha"] == SOURCE_SHA
        assert result["image_digest"] == os.environ["GPU_CONTROL_CPU_SMOKE_IMAGE_DIGEST"]
        assert result["cost_classification"] == "LOCAL"
        assert result["cleanup_state"] == "complete"
        manifest = result["artifacts"][0]
        artifact = call(second_conversation, "experiment_artifact", {
            "run_id": run_id, "artifact_id": manifest["artifact_id"],
            "offset": 0, "length": 24 * 1024,
        })["machine_state"]
        artifact_bytes = base64.b64decode(artifact["data_base64"], validate=True)
        assert artifact_bytes == result["logs"].encode().rstrip(b"\n")
        assert artifact["sha256"] == manifest["sha256"]
        assert artifact["complete"] is True
    finally:
        first_conversation.close()
        second_conversation.close()
        if run_id and shutil.which("docker"):
            matches = subprocess.run(
                ["docker", "ps", "-aq", "--filter",
                 "label=io.unjuno.gpu-control.run-id=" + run_id],
                capture_output=True, text=True, timeout=10,
            ).stdout.split()
            if matches:
                subprocess.run(["docker", "rm", "--force", *matches], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
