from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from .config import Settings


@dataclass(frozen=True)
class Observation:
    state: str
    result: dict | None = None

    def __post_init__(self):
        if self.state not in {"running", "succeeded", "failed", "cancelled"}:
            raise ValueError("Backend returned an unsupported state")


class Backend(Protocol):
    """Terminal inspect() must mean billable compute is released.

    start consumes the persisted, approved plan. Reconcile must never create.
    Provider-specific permit and cleanup gates remain the adapter's responsibility.
    """
    def start(self, run: dict) -> dict: ...
    def inspect(self, handle: dict) -> Observation: ...
    def cancel(self, handle: dict) -> None: ...
    def reconcile(self, run: dict) -> dict | None: ...


class DemoBackend:
    """Deterministic, non-GPU integration fixture. Never reports a real GPU result."""
    def start(self, run: dict) -> dict:
        return {"id": run["id"], "parameters": run["plan"]["parameters"], "simulation": True}

    def inspect(self, handle: dict) -> Observation:
        return Observation("succeeded", {"simulation": True, "gpu_used": False, "parameters": handle["parameters"]})

    def cancel(self, handle: dict) -> None:
        return None

    def reconcile(self, run: dict) -> dict | None:
        return self.start(run)


def bounded_text(chunks, maximum: int) -> tuple[str, bool]:
    """Retain at most maximum UTF-8 bytes, without an unbounded read()."""
    output = bytearray()
    for chunk in chunks:
        raw = chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk)
        remaining = maximum - len(output)
        output.extend(raw[:remaining])
        if len(raw) > remaining:
            return output.decode("utf-8", errors="replace"), True
    return output.decode("utf-8", errors="replace"), False


class ModalSandboxBackend:
    """Worker-only SDK boundary. The API process never needs Modal credentials.

    Uses a prebuilt immutable Modal image, fixed argv and a provider timeout.
    No image build, arbitrary command, port or provider credential comes from a tool.
    """
    def __init__(self, settings: Settings, sdk: Any = None):
        self.settings = settings
        self.sdk = sdk

    def _sdk(self):
        if self.sdk is None:
            self.sdk = importlib.import_module("modal")
        return self.sdk

    def start(self, run: dict) -> dict:
        if not self.settings.enable_modal:
            raise RuntimeError("Modal submission is disabled")
        sdk = self._sdk()
        plan = run["plan"]
        manifest = plan["workload_manifest"]
        app = sdk.App.lookup(self.settings.modal_app, create_if_missing=False)
        sandbox = sdk.Sandbox.create(
            *manifest["argv"], app=app, name="gpu-control-" + run["id"],
            image=sdk.Image.from_id(manifest["image_id"]),
            gpu=manifest["gpu"], cpu=manifest["cpu"], memory=manifest["memory_mib"],
            timeout=plan["runtime_seconds"], block_network=True,
            env={"GPU_CONTROL_RUN_ID": run["id"],
                 "GPU_CONTROL_CONFIG_JSON": json.dumps(plan["parameters"], allow_nan=False),
                 "GPU_CONTROL_PLAN_FINGERPRINT": run["fingerprint"]},
        )
        return {"sandbox_id": sandbox.object_id, "app": self.settings.modal_app}

    def inspect(self, handle: dict) -> Observation:
        sandbox = self._sdk().Sandbox.from_id(handle["sandbox_id"])
        exit_code = sandbox.poll()
        if exit_code is None:
            return Observation("running")
        stdout, out_cut = bounded_text(sandbox.stdout, self.settings.max_output_bytes // 2)
        stderr, err_cut = bounded_text(sandbox.stderr, self.settings.max_output_bytes // 2)
        result = {"exit_code": exit_code, "stdout": stdout, "stderr": stderr,
                  "logs_truncated": out_cut or err_cut, "evidence": "provider_exit_code_and_logs"}
        # Metrics are workload output, not proof that the scientific result is correct.
        if not out_cut:
            try:
                metrics = json.loads(stdout.strip().splitlines()[-1])
                if isinstance(metrics, dict):
                    json.dumps(metrics, allow_nan=False)
                    result["metrics"] = metrics
            except (ValueError, IndexError):
                pass
        return Observation("succeeded" if exit_code == 0 else "failed", result)

    def cancel(self, handle: dict) -> None:
        # Cancellation requests remain allowed even after the new-run switch is off.
        self._sdk().Sandbox.from_id(handle["sandbox_id"]).terminate(wait=True)

    def reconcile(self, run: dict) -> dict | None:
        sdk = self._sdk()
        try:
            sandbox = sdk.Sandbox.from_name(self.settings.modal_app, "gpu-control-" + run["id"])
        except sdk.exception.NotFoundError:
            # An exited Sandbox may no longer resolve by name. Never create again.
            return None
        return {"sandbox_id": sandbox.object_id, "app": self.settings.modal_app}


class ExistingRunPodBridge:
    """Bridge to an operator's EXISTING approved RunPod pipeline.

    Factory is an operator-configured Python entrypoint, not a tool argument.
    It returns a Backend that retains that pipeline's existing plan, permit,
    pricing and cleanup gates. No GitHub workflow or RunPod API is guessed here.
    """
    def __init__(self, factory_path: str):
        module, separator, attribute = factory_path.partition(":")
        if not separator or not module or not attribute:
            raise ValueError("RunPod bridge must be module:factory")
        self.factory_path = factory_path
        self._backend = None

    def _get(self):
        if self._backend is None:
            module, attribute = self.factory_path.split(":", 1)
            self._backend = getattr(importlib.import_module(module), attribute)()
            for name in ("start", "inspect", "cancel", "reconcile"):
                if not callable(getattr(self._backend, name, None)):
                    raise TypeError("RunPod bridge does not implement the Backend contract")
        return self._backend

    def start(self, run: dict) -> dict:
        return self._get().start(run)

    def inspect(self, handle: dict) -> Observation:
        return self._get().inspect(handle)

    def cancel(self, handle: dict) -> None:
        return self._get().cancel(handle)

    def reconcile(self, run: dict) -> dict | None:
        return self._get().reconcile(run)


def build_backends(settings: Settings, registry=None) -> dict[str, Backend]:
    from .registry import default_registry
    registry = default_registry() if registry is None else registry
    # Disabled providers remain available for recovery of already-running jobs.
    return {name: entry.factory(settings) for name, entry in registry.items()
            if name != "runpod" or settings.runpod_factory}
