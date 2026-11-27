from types import SimpleNamespace
import hashlib
import json

import pytest

from custom_training_backend import CustomTrainingBackend


class Volume:
    def with_mount_options(self, **options):
        return options


def test_stages_before_creation_and_observes_same_sandbox(tmp_path):
    events = []
    gpu_result = {"run_id": "a" * 32, "source_sha": "b" * 40,
              "manifest_sha256": "c" * 64, "lock_sha256": "d" * 64,
              "gpu_profile": "L4", "gpu_used": True, "gpu": {"name": "NVIDIA L4"},
              "checkpoint": {"filename": "checkpoint.pt", "size_bytes": 5, "sha256": "e" * 64},
              "metrics": {"filename": "metrics.json", "size_bytes": 12, "sha256": "f" * 64,
                          "values": {"loss": 0.5}}, "artifacts": []}
    stage_result = {"commit": "b" * 40, "manifest_sha256": "c" * 64,
                    "lock_sha256": "d" * 64, "dependencies_lock": "requirements.lock",
                    "entrypoint": "train.py", "wheelhouse_sha256": "9" * 64,
                    "wheelhouse_packages": 1, "wheelhouse_bytes": 1}
    stage = SimpleNamespace(object_id="sb-stage", poll=lambda: 0,
                            stdout=[json.dumps(stage_result).encode()],
                            terminate=lambda *, wait: events.append(("terminate_stage", wait)))
    sandbox = SimpleNamespace(object_id="sb-gpu", poll=lambda: 0,
                              stdout=[json.dumps(gpu_result).encode()],
                              terminate=lambda *, wait: events.append(("terminate_gpu", wait)))
    sandboxes = {}
    sandbox_options = []
    def create(*args, **kwargs):
        events.append(("create", kwargs["name"]))
        value = stage if "-stage-" in kwargs["name"] else sandbox
        if value is sandbox:
            sandbox_options.append(kwargs)
        sandboxes[kwargs["name"]] = value
        return value
    backend = CustomTrainingBackend(app=None, image=None, source_volume=Volume(), checkpoint_volume=Volume(),
                                    create=create, lookup=lambda name: sandboxes.get(name), stage=lambda: None,
                                    commit_source=lambda: events.append(("commit_source",)),
                                    commit_output=lambda: events.append(("commit_output",)),
                                    cleanup_source=lambda _run_id: True)
    plan = {"run_id": "a" * 32, "commit": "b" * 40, "repository": "owner/project",
            "command": ["python", "train.py"], "runtime_seconds": 120, "gpu": "L4",
            "manifest": {"python_version": "3.12"},
            "manifest_sha256": "c" * 64, "lock_sha256": "d" * 64,
            "dependencies_lock": "requirements.lock"}
    handle = "custom-training-" + "a" * 32
    run_root = tmp_path / plan["run_id"]
    run_root.mkdir()
    (run_root / ".gpu-control-stage.json").write_text(json.dumps(stage_result))
    backend.source_root = str(tmp_path)
    assert backend.start(plan) == handle
    assert [event[0] for event in events] == ["create"]
    observed = backend.inspect(handle, plan)
    assert observed["state"] == "succeeded" and observed["gpu_used"] is True
    assert observed["cleanup"] == "confirmed" and observed["checkpoint"] == gpu_result["checkpoint"]
    assert observed["metrics"] == gpu_result["metrics"]
    assert sandbox_options[0]["env"]["GPU_CONTROL_PYTHON_VERSION"] == "3.12"
    assert [event[0] for event in events] == ["create", "terminate_stage", "commit_source",
                                               "commit_output", "create", "terminate_gpu", "commit_output"]


def test_stage_failure_does_not_allocate_gpu():
    stage = SimpleNamespace(object_id="sb-stage", poll=lambda: 1, stdout=[],
                            terminate=lambda *, wait: None)
    sandboxes = {"custom-training-stage-" + "a" * 32: stage}
    def create(*args, **kwargs):
        if "-stage-" in kwargs["name"]:
            return stage
        pytest.fail("allocated GPU before stage success")
    backend = CustomTrainingBackend(app=None, image=None, source_volume=Volume(), checkpoint_volume=Volume(),
                                    create=create, lookup=lambda name: sandboxes.get(name), stage=lambda: None,
                                    cleanup_source=lambda _run_id: True, cleanup_checkpoint=lambda _run_id: True,
                                    commit_source=lambda: None)
    plan = {"repository": "owner/project", "commit": "b" * 40, "run_id": "a" * 32,
            "manifest_sha256": "c" * 64, "lock_sha256": "d" * 64, "dependencies_lock": "requirements.lock",
            "command": ["python", "train.py"], "runtime_seconds": 120, "gpu": "L4",
            "manifest": {"python_version": "3.12"}}
    assert backend.start(plan) == "custom-training-" + "a" * 32
    result = backend.inspect("custom-training-" + "a" * 32, plan)
    assert result["state"] == "failed" and result["gpu_used"] is False


def test_declared_artifact_chunk_is_owner_run_scoped_and_reverified(tmp_path):
    run_id = "a" * 32
    payload = b"metrics-data"
    artifact_path = "artifacts/eval.csv"
    artifact = {"artifact_id": hashlib.sha256(artifact_path.encode()).hexdigest(),
                "path": artifact_path, "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest()}
    path = tmp_path / run_id / "checkpoint" / artifact_path
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    backend = CustomTrainingBackend(app=None, image=None, source_volume=Volume(), checkpoint_volume=Volume(),
        create=lambda *_args, **_kwargs: None, lookup=lambda *_: None, stage=lambda: None,
        checkpoint_root=str(tmp_path))
    chunk = backend.artifact(run_id, artifact, 0, 5)
    assert chunk["data"] == "bWV0cmk="
    assert chunk["next_offset"] == 5 and chunk["eof"] is False
    path.write_bytes(b"metric-error")
    with pytest.raises(ValueError, match="artifact_checksum_mismatch"):
        backend.artifact(run_id, artifact, 0, 5)
