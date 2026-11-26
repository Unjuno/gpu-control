import json

import pytest

from custom_training_sandbox import create_training_sandbox


class Volume:
    def with_mount_options(self, **options):
        return options


def test_sandbox_is_network_blocked_and_mounts_only_its_run():
    plan = {"run_id": "a" * 32, "commit": "b" * 40, "command": ["python", "train.py"],
            "runtime_seconds": 60, "gpu": "L4"}
    def create(*args, **kwargs):
        return args, kwargs
    args, options = create_training_sandbox(plan, app=object(), image=object(),
                                             source_volume=Volume(), checkpoint_volume=Volume(), create=create)
    assert args == ("python", "/opt/gpu-control/custom_sandbox_entrypoint.py")
    assert options["block_network"] is True and options["timeout"] == 60
    assert options["volumes"]["/source-store"] == {"sub_path": "/" + "a" * 32, "read_only": True}
    assert options["volumes"]["/output"] == {"sub_path": "/" + "a" * 32}
    assert json.loads(options["env"]["GPU_CONTROL_COMMAND_JSON"]) == plan["command"]
    assert set(options["env"]) == {"GPU_CONTROL_COMMIT", "GPU_CONTROL_COMMAND_JSON", "GPU_CONTROL_RUNTIME_SECONDS"}


def test_rejects_unbounded_or_unexpected_plan():
    plan = {"run_id": "a" * 32, "commit": "b" * 40, "command": ["python"],
            "runtime_seconds": 3001, "gpu": "L4"}
    with pytest.raises(ValueError, match="invalid_sandbox_plan"):
        create_training_sandbox(plan, app=None, image=None, source_volume=Volume(),
                                checkpoint_volume=Volume(), create=lambda *a, **k: None)
