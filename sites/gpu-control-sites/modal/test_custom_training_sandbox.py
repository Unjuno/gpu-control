import json

import pytest

from custom_training_sandbox import create_training_sandbox, create_training_stage_sandbox


class Volume:
    def with_mount_options(self, **options):
        return options


def test_sandbox_is_network_blocked_and_mounts_only_its_run():
    plan = {"run_id": "a" * 32, "commit": "b" * 40, "command": ["python", "train.py"],
            "runtime_seconds": 120, "gpu": "L4", "python_version": "3.12", "manifest_sha256": "c" * 64,
            "lock_sha256": "d" * 64, "dependencies_lock": "requirements.lock"}
    def create(*args, **kwargs):
        return args, kwargs
    args, options = create_training_sandbox(plan, app=object(), image=object(),
        source_volume=Volume(), checkpoint_volume=Volume(), create=create,
        expected_manifest_sha256="c" * 64, expected_lock_sha256="d" * 64,
        lock_path="requirements.lock")
    assert args == ("python", "/opt/gpu-control/custom_sandbox_entrypoint.py")
    assert options["runtime"] == "gvisor"
    assert options["cpu"] == (2, 2) and options["memory"] == (8192, 8192)
    assert options["block_network"] is True and options["timeout"] == 120
    assert options["volumes"]["/source-store"] == {"sub_path": "/" + "a" * 32, "read_only": True}
    assert options["volumes"]["/output"] == {"sub_path": "/" + "a" * 32}
    assert options["env"]["GPU_CONTROL_ENTRYPOINT"] == "train.py"
    assert options["env"]["GPU_CONTROL_LOCK_SHA256"] == "d" * 64
    assert options["env"]["GPU_CONTROL_RUN_ID"] == "a" * 32
    assert options["env"]["GPU_CONTROL_GPU_PROFILE"] == "L4"
    assert set(options["env"]) == {"GPU_CONTROL_COMMIT", "GPU_CONTROL_RUN_ID", "GPU_CONTROL_ENTRYPOINT", "GPU_CONTROL_PYTHON_VERSION", "GPU_CONTROL_MANIFEST_SHA256",
                                    "GPU_CONTROL_LOCK_SHA256", "GPU_CONTROL_DEPENDENCIES_LOCK",
                                    "GPU_CONTROL_WHEELHOUSE", "GPU_CONTROL_GPU_PROFILE", "GPU_CONTROL_RUNTIME_SECONDS"}


def test_rejects_unbounded_or_unexpected_plan():
    plan = {"run_id": "a" * 32, "commit": "b" * 40, "command": ["python"],
            "runtime_seconds": 3001, "gpu": "L4", "python_version": "3.12", "manifest_sha256": "c" * 64,
            "lock_sha256": "d" * 64, "dependencies_lock": "requirements.lock"}
    with pytest.raises(ValueError, match="invalid_sandbox_plan"):
        create_training_sandbox(plan, app=None, image=None, source_volume=Volume(),
            checkpoint_volume=Volume(), create=lambda *a, **k: None,
            expected_manifest_sha256="c" * 64, expected_lock_sha256="d" * 64,
            lock_path="requirements.lock")


@pytest.mark.parametrize("command", [["bash", "-c", "python train.py"],
                                     ["python", "../outside.py"],
                                     ["python", "train.py", "--flag"]])
def test_sandbox_rejects_commands_outside_manifest_entrypoint(command):
    plan = {"run_id": "a" * 32, "commit": "b" * 40, "command": command,
            "runtime_seconds": 120, "gpu": "L4", "python_version": "3.12", "manifest_sha256": "c" * 64,
            "lock_sha256": "d" * 64, "dependencies_lock": "requirements.lock"}
    with pytest.raises(ValueError, match="invalid_sandbox_plan"):
        create_training_sandbox(plan, app=None, image=None, source_volume=Volume(),
            checkpoint_volume=Volume(), create=lambda *a, **k: pytest.fail("created"),
            expected_manifest_sha256="c" * 64, expected_lock_sha256="d" * 64,
            lock_path="requirements.lock")


def test_stage_sandbox_is_cpu_bounded_and_keeps_token_out_of_gpu_plan():
    plan = {"run_id": "a" * 32, "repository": "owner/project", "commit": "b" * 40}
    args, options = create_training_stage_sandbox(plan, app=object(), image=object(),
        source_volume=Volume(), checkpoint_volume=Volume(), create=lambda *args, **kwargs: (args, kwargs),
        source_token="x" * 32)
    assert args == ("python", "/root/site-modal/custom_training_stage_entrypoint.py")
    assert options["name"] == "custom-training-stage-" + "a" * 32
    assert options["runtime"] == "gvisor" and "gpu" not in options
    assert options["cpu"] == (1, 1) and options["memory"] == (1024, 1024) and options["timeout"] == 300
    assert options["outbound_domain_allowlist"] == [
        "github.com", "pypi.org", "files.pythonhosted.org"]
    assert "block_network" not in options
    assert options["env"]["GPU_CONTROL_SOURCE_TOKEN"] == "x" * 32
    gpu_plan = {"run_id": "a" * 32, "commit": "b" * 40, "command": ["python", "train.py"],
                "runtime_seconds": 120, "gpu": "L4", "python_version": "3.12", "manifest_sha256": "c" * 64,
                "lock_sha256": "d" * 64, "dependencies_lock": "requirements.lock"}
    _, gpu_options = create_training_sandbox(gpu_plan, app=object(), image=object(),
        source_volume=Volume(), checkpoint_volume=Volume(), create=lambda *args, **kwargs: (args, kwargs),
        expected_manifest_sha256="c" * 64, expected_lock_sha256="d" * 64,
        lock_path="requirements.lock")
    assert all("TOKEN" not in key for key in gpu_options["env"])
