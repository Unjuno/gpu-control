from types import SimpleNamespace

import pytest

from custom_training_backend import CustomTrainingBackend


class Volume:
    def with_mount_options(self, **options):
        return options


def test_stages_before_creation_and_observes_same_sandbox():
    events = []
    sandbox = SimpleNamespace(object_id="sb-abcdefgh", poll=lambda: 0,
                              terminate=lambda *, wait: events.append(("terminate", wait)))
    def create(*args, **kwargs):
        events.append(("create", kwargs["name"]))
        return sandbox
    backend = CustomTrainingBackend(app=None, image=None, source_volume=Volume(), checkpoint_volume=Volume(),
                                    create=create, lookup=lambda handle: sandbox,
                                    stage=lambda *args: events.append(("stage", args)))
    plan = {"run_id": "a" * 32, "commit": "b" * 40, "repository": "owner/project",
            "command": ["python", "train.py"], "runtime_seconds": 120, "gpu": "L4"}
    assert backend.start(plan) == "sb-abcdefgh"
    assert [event[0] for event in events] == ["stage", "create"]
    assert backend.inspect("sb-abcdefgh", plan) == {"state": "succeeded", "exit_code": 0,
                                                   "gpu_used": "unverified", "cleanup": "unverified"}
    backend.cancel("sb-abcdefgh")
    assert events[-1] == ("terminate", True)


def test_stage_failure_does_not_allocate():
    def fail(*_):
        raise ValueError("source_invalid")
    backend = CustomTrainingBackend(app=None, image=None, source_volume=Volume(), checkpoint_volume=Volume(),
                                    create=lambda *a, **k: pytest.fail("allocated"), lookup=None, stage=fail)
    with pytest.raises(ValueError, match="source_invalid"):
        backend.start({"repository": "owner/project", "commit": "b" * 40, "run_id": "a" * 32})
