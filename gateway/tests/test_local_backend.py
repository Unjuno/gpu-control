import json
from types import SimpleNamespace

import pytest

from gpu_gateway.local_backend import (LocalContainerBackend, container_create_args,
                                      parse_smoke_result,
                                      validate_image_architecture)
from gpu_gateway.registry import default_registry
from gpu_gateway.container_runtime import container_hardening_args


def _valid_handle():
    run_id = "d" * 32
    return {"container_id": "a" * 64, "container_name": "gpu-control-" + run_id,
            "run_id": run_id, "owner_digest": "b" * 64,
            "plan_fingerprint": "c" * 64, "image_digest": "sha256:" + "e" * 64,
            "source_sha": "f" * 40}


def _mismatched_container(handle):
    return [{"Config": {"Labels": {
        "io.unjuno.gpu-control.run-id": handle["run_id"],
        "io.unjuno.gpu-control.owner-sha256": "0" * 64,
        "io.unjuno.gpu-control.plan-sha256": handle["plan_fingerprint"],
        "io.unjuno.gpu-control.image-digest": handle["image_digest"],
        "io.unjuno.gpu-control.source-sha": handle["source_sha"],
    }}}]


def test_local_container_constraints():
    plan = {"provider": "local_cpu", "image_digest": "sha256:" + "a" * 64,
            "source_sha": "b" * 40, "repository": "owner/repo", "workload": "cpu-smoke-v1",
            "runtime_seconds": 30, "max_cost_usd": "0",
            "device_requirement": {"requires_gpu": False}, "parameters": {"seed": 1}}
    args = container_create_args(plan, run_id="d" * 32, owner="owner-a", fingerprint="c" * 64)
    assert "--network" in args and args[args.index("--network") + 1] == "none"
    assert "--read-only" in args and "--cap-drop" in args and args[args.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in args and args[args.index("--security-opt") + 1] == "no-new-privileges"
    assert "--pids-limit" in args and args[args.index("--pids-limit") + 1] == "32"
    assert "--memory" in args and args[args.index("--memory") + 1] == "256m"
    assert "--cpus" in args and args[args.index("--cpus") + 1] == "1"
    assert "--log-driver" in args and args[args.index("--log-driver") + 1] == "local"
    assert "max-file=2" in args
    assert not any("docker.sock" in value for value in args)


def test_missing_or_mutable_image_blocks_container_creation():
    plan = {"provider": "local_cpu", "image_digest": "cpu-smoke:latest",
            "device_requirement": {"requires_gpu": False}}
    with pytest.raises(ValueError, match="immutable image"):
        container_create_args(plan, run_id="d" * 32, owner="owner-a", fingerprint="c" * 64)


def test_missing_image_or_architecture_blocks():
    with pytest.raises(ValueError, match="image is missing"):
        validate_image_architecture(None, {"OSType": "linux", "Architecture": "arm64"})
    with pytest.raises(ValueError, match="architecture mismatch"):
        validate_image_architecture({"Id": "sha256:" + "a" * 64, "Os": "linux", "Architecture": "amd64"},
                                    {"OSType": "linux", "Architecture": "arm64"},
                                    expected_digest="sha256:" + "a" * 64)


def test_smoke_result_binds_source_and_plan_and_rejects_fake_gpu_claims():
    expected = {"run_id": "d" * 32, "source_sha": "b" * 40, "plan_fingerprint": "c" * 64}
    value = {"schema_version": 1, **expected, "check": "cpu-smoke-v1", "status": "passed",
             "gpu_used": False, "metrics": {"iterations": 10, "checksum_value": 42},
             "checks": ["checksum_valid"], "checksum": "e" * 64}
    result = parse_smoke_result(json.dumps(value).encode(), expected, exit_code=0)
    assert result["simulation"] is False
    assert result["gpu_used"] is False
    assert result["metrics"]["checksum_value"] == 42
    with pytest.raises(ValueError, match="binding"):
        parse_smoke_result(json.dumps({**value, "source_sha": "e" * 40}).encode(), expected, exit_code=0)
    with pytest.raises(ValueError, match="GPU"):
        parse_smoke_result(json.dumps({**value, "gpu_used": True}).encode(), expected, exit_code=0)
    with pytest.raises(ValueError):
        parse_smoke_result(json.dumps({**value, "schema_version": True}).encode(), expected, exit_code=0)


def test_bounded_invalid_and_missing_output_is_failure():
    expected = {"run_id": "d" * 32, "source_sha": "b" * 40, "plan_fingerprint": "c" * 64}
    for raw in (b"{broken", b"", b'{"metrics":{"bad":NaN}}', b'{"schema_version":1}'):
        with pytest.raises(ValueError):
            parse_smoke_result(raw, expected, exit_code=0)
    with pytest.raises(ValueError, match="output limit"):
        parse_smoke_result(b"x" * 65537, expected, exit_code=0)


def test_local_backend_is_registered_but_policy_remains_disabled_by_default():
    registry = default_registry()
    assert "local_cpu" in registry
    assert registry["local_cpu"].execution == "local_worker_container"


def test_shared_container_hardening_options():
    args = container_hardening_args()
    assert args == ["--network", "none", "--read-only", "--cap-drop", "ALL",
                    "--security-opt", "no-new-privileges", "--user", "10001:10001",
                    "--pids-limit", "32", "--memory", "256m", "--cpus", "1"]


def test_reconcile_rejects_run_id_collision_with_wrong_identity_labels():
    backend = LocalContainerBackend(type("Settings", (), {"max_output_bytes": 65536})())
    run = {"id": "d" * 32, "owner": "owner-a", "fingerprint": "c" * 64,
           "plan": {"provider": "local_cpu", "image_digest": "sha256:" + "a" * 64,
                    "source_sha": "b" * 40}}
    labels = {
        "io.unjuno.gpu-control.run-id": run["id"],
        "io.unjuno.gpu-control.owner-sha256": "0" * 64,
        "io.unjuno.gpu-control.plan-sha256": run["fingerprint"],
        "io.unjuno.gpu-control.image-digest": run["plan"]["image_digest"],
        "io.unjuno.gpu-control.source-sha": run["plan"]["source_sha"],
    }
    calls = []

    def fake_run(args, timeout=20):
        calls.append(args)
        if args[0] == "ps":
            return SimpleNamespace(stdout=b"a" * 64)
        if args[0] == "inspect":
            return SimpleNamespace(stdout=json.dumps([{"Config": {"Labels": labels}}]).encode())
        raise AssertionError("reconcile must never mutate or remove an unverified resource")

    backend._run = fake_run
    with pytest.raises(ValueError, match="identity"):
        backend.reconcile(run)
    assert [call[0] for call in calls] == ["ps", "inspect"]


def test_cleanup_rejects_mismatched_container_labels_before_removal(monkeypatch):
    import gpu_gateway.local_backend as local_backend_module

    handle = _valid_handle()
    backend = LocalContainerBackend(type("Settings", (), {"max_output_bytes": 65536})())
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,
            stdout=json.dumps(_mismatched_container(handle)).encode(), stderr=b"")

    monkeypatch.setattr(local_backend_module.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="label"):
        backend.cleanup(handle)
    assert [call[1] for call in calls] == ["inspect"]


def test_cancel_rejects_mismatched_container_labels_before_stopping():
    handle = _valid_handle()
    backend = LocalContainerBackend(type("Settings", (), {"max_output_bytes": 65536})())
    calls = []

    def fake_run(args, timeout=20):
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps(_mismatched_container(handle)).encode())

    backend._run = fake_run
    with pytest.raises(ValueError, match="label"):
        backend.cancel(handle)
    assert [call[0] for call in calls] == ["inspect"]
