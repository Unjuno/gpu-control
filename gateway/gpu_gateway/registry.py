"""One operator-owned registry shared by admission, UI and worker.

Add a GPU provider here and implement Backend; MCP and WebMCP stay unchanged.
Registry entries are trusted application code, never user-supplied import paths.
"""
from dataclasses import dataclass
from typing import Callable

from .config import Settings


@dataclass(frozen=True)
class ProviderRegistration:
    name: str
    execution: str
    enabled: Callable[[Settings], bool]
    factory: Callable
    note: str = ""


def default_registry() -> dict[str, ProviderRegistration]:
    # Lazy imports keep provider SDKs out of the API process.
    from .backends import DemoBackend, ExistingRunPodBridge, ModalSandboxBackend
    entries = (
        ProviderRegistration("demo", "local_simulation_no_gpu", lambda s: True, lambda s: DemoBackend()),
        ProviderRegistration("modal", "dedicated_worker", lambda s: s.enable_modal, ModalSandboxBackend),
        ProviderRegistration("runpod", "existing_core_bridge",
            lambda s: s.enable_runpod_bridge and bool(s.runpod_factory),
            lambda s: ExistingRunPodBridge(s.runpod_factory),
            "Existing RunPod CI is unchanged; this gateway does not dispatch it."),
    )
    return {entry.name: entry for entry in entries}
