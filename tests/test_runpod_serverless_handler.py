from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).parents[1] / "workloads" / "runpod-gpu-canary" / "serverless_handler.py"
SPEC = importlib.util.spec_from_file_location("runpod_serverless_handler", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def valid_input() -> dict:
    run_id = "1" * 32
    return {"input": {"schema_version": 1, "run_id": run_id, "plan_fingerprint": "2" * 64,
        "nonce": "3" * 64, "completion_key_b64": "A" * 43 + "=", "completion_key_id": "4" * 32,
        "source_sha": "5" * 40, "image_digest": "sha256:" + "6" * 64,
        "execution_name": f"gpu-control-{run_id[:12]}"}}


def test_handler_runs_only_the_fixed_workload(monkeypatch: pytest.MonkeyPatch) -> None:
    value = valid_input()
    monkeypatch.setenv("GPU_CONTROL_SOURCE_SHA", value["input"]["source_sha"])
    monkeypatch.setenv("GPU_CONTROL_IMAGE_DIGEST", value["input"]["image_digest"])
    captured = {}
    def fake_run(argv, **kwargs):
        captured.update(argv=argv, kwargs=kwargs)
        return SimpleNamespace(returncode=0, stdout="GPU_CONTROL_RESULT_JSON_V1:a\nGPU_CONTROL_COMPLETION_JSON_V3:b\n")
    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    assert MODULE.handler(value)["lines"] == ["GPU_CONTROL_RESULT_JSON_V1:a", "GPU_CONTROL_COMPLETION_JSON_V3:b"]
    assert captured["argv"][0] == "/opt/gpu-control/run-registered-workload"
    assert captured["kwargs"]["timeout"] == 25
    assert "completion_key_b64" not in str(captured["argv"])


def test_handler_rejects_unbound_or_extra_input(monkeypatch: pytest.MonkeyPatch) -> None:
    value = valid_input()
    monkeypatch.setenv("GPU_CONTROL_SOURCE_SHA", value["input"]["source_sha"])
    monkeypatch.setenv("GPU_CONTROL_IMAGE_DIGEST", value["input"]["image_digest"])
    value["input"]["extra"] = "command"
    with pytest.raises(ValueError, match="INVALID_REGISTERED_WORKLOAD_INPUT"):
        MODULE.handler(value)
