from __future__ import annotations

import ast
import re
import sys
import types
from pathlib import Path

MODAL_DIR = Path(__file__).resolve().parents[1] / "sites" / "gpu-control-sites" / "modal"
sys.path.insert(0, str(MODAL_DIR))
import gpu_control_modal_bootstrap as modal_bootstrap  # noqa: E402


class FakeSandbox:
    object_id = "sb-test"

    def __init__(self, stdout, stderr=(), exit_code=0):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.terminated = False

    def poll(self):
        return self.exit_code

    def terminate(self, *, wait):
        assert wait is True
        self.terminated = True


def load_capture():
    source = (MODAL_DIR / "app.py").read_text(encoding="utf-8")
    function = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == "_capture")
    namespace = {
        "Any": object,
        "MAX_STDOUT_BYTES": 4096,
        "MAX_STDERR_BYTES": 2048,
        "WORKLOAD": "tiny-stories-inference-v1",
        "WORKLOAD_SOURCE_SHA": "source-sha",
        "WORKLOAD_IMAGE_FINGERPRINT": "image-fingerprint",
        "_bounded_stream": lambda stream, maximum: ("".join(stream), False),
        "normalize_exit_code": modal_bootstrap.normalize_exit_code,
        "parse_workload_result": modal_bootstrap.parse_workload_result,
        "re": re,
        "modal": types.SimpleNamespace(exception=types.SimpleNamespace(NotFoundError=type("NotFoundError", (Exception,), {}))),
        "workload_image": types.SimpleNamespace(object_id="im-test"),
    }
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(MODAL_DIR / "app.py"), "exec"), namespace)
    return namespace["_capture"]


def load_submission_observation():
    source = (MODAL_DIR / "app.py").read_text(encoding="utf-8")
    function = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == "_submission_observation")
    namespace = {
        "Any": object,
        "WORKLOAD_IMAGE_FINGERPRINT": "image-fingerprint",
        "workload_image": types.SimpleNamespace(object_id="im-test"),
    }
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(MODAL_DIR / "app.py"), "exec"), namespace)
    return namespace["_submission_observation"]


def test_non_object_json_fails_closed_and_still_terminates_sandbox():
    sandbox = FakeSandbox(["[]\n"])
    capture = load_capture()(sandbox, "a" * 32, {"plan_fingerprint": "b" * 64})
    assert capture["state"] == "failed"
    assert capture["result"] is None
    assert capture["cleanup_state"] == "confirmed"
    assert sandbox.terminated is True


def test_stream_error_still_terminates_sandbox_and_reports_capture_failure():
    def broken_stream():
        yield "partial"
        raise OSError("stream disconnected")

    sandbox = FakeSandbox(broken_stream())
    capture = load_capture()(sandbox, "a" * 32, {"plan_fingerprint": "b" * 64})
    assert capture["state"] == "failed"
    assert capture["diagnostic_code"] == "CAPTURE_FAILED"
    assert capture["cleanup_state"] == "confirmed"
    assert sandbox.terminated is True


def test_submit_returns_provider_acceptance_without_waiting_for_capture_or_cleanup():
    sandbox = FakeSandbox(["result must not be read during submit\n"])
    observation = load_submission_observation()(sandbox)
    assert observation == {
        "state": "running",
        "sandbox_id": "sb-test",
        "cleanup_state": "pending",
        "image_id": "im-test",
        "image_fingerprint": "image-fingerprint",
    }
    assert sandbox.terminated is False

    source = (MODAL_DIR / "app.py").read_text(encoding="utf-8")
    submit = next(node for node in ast.parse(source).body
                  if isinstance(node, ast.AsyncFunctionDef) and node.name == "submit")
    called_names = {node.func.id for node in ast.walk(submit)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "_submission_observation" in called_names
    assert "_capture" not in called_names
