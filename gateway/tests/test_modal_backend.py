from dataclasses import replace
from types import SimpleNamespace

import pytest

from gpu_gateway.backends import ModalSandboxBackend, bounded_text


def test_modal_uses_fixed_manifest_timeout_and_no_provider_secrets(system):
    created = []
    sandbox = SimpleNamespace(object_id="sb-123", poll=lambda:0, stdout=iter(['{"loss":1.0}\n']), stderr=iter([]))
    sdk = SimpleNamespace(
        App=SimpleNamespace(lookup=lambda name, **kw: (name, kw)),
        Image=SimpleNamespace(from_id=lambda name:name),
        Sandbox=SimpleNamespace(create=lambda *args, **kw: (created.append((args,kw)) or sandbox), from_id=lambda identifier:sandbox))
    backend = ModalSandboxBackend(replace(system.settings, enable_modal=True), sdk)
    run = {"id":"a" * 32, "fingerprint":"f" * 64, "plan":{"parameters":{"steps":1}, "runtime_seconds":30,
        "workload_manifest":{"argv":["python","experiment.py"], "image_id":"im-fixed", "gpu":"T4", "cpu":1, "memory_mib":4096}}}
    handle = backend.start(run)
    args, kwargs = created[0]
    assert args == ("python", "experiment.py")
    assert kwargs["timeout"] == 30 and kwargs["block_network"] is True
    assert "secrets" not in kwargs
    assert set(kwargs["env"]) == {"GPU_CONTROL_RUN_ID", "GPU_CONTROL_CONFIG_JSON", "GPU_CONTROL_PLAN_FINGERPRINT"}
    result = backend.inspect(handle)
    assert result.state == "succeeded" and result.result["metrics"]["loss"] == 1.0


def test_modal_disabled_gate_precedes_sdk_import(system):
    backend = ModalSandboxBackend(system.settings)
    with pytest.raises(RuntimeError, match="disabled"): backend.start({})


def test_modal_cancel_remains_available_when_start_disabled(system):
    calls = []
    sdk = SimpleNamespace(Sandbox=SimpleNamespace(from_id=lambda identifier:SimpleNamespace(terminate=lambda **kwargs:calls.append(kwargs))))
    ModalSandboxBackend(system.settings, sdk).cancel({"sandbox_id":"sb-test"})
    assert calls == [{"wait":True}]


def test_bounded_output():
    output, truncated = bounded_text(iter(["abc", "def", "more"]), 5)
    assert output == "abcde" and truncated


def test_modal_sdk_surface_when_installed():
    modal = pytest.importorskip("modal")
    import inspect
    for name in ("create", "from_name", "from_id", "poll", "terminate"):
        assert callable(getattr(modal.Sandbox, name))
    assert "timeout" in inspect.signature(modal.Sandbox.create).parameters
    assert "block_network" in inspect.signature(modal.Sandbox.create).parameters
    assert "wait" in inspect.signature(modal.Sandbox.terminate).parameters
