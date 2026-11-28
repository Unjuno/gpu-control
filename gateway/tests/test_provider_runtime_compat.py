"""Keep legacy Gateway imports as aliases to the Sites-owned runtime."""
from __future__ import annotations

from importlib import import_module

import pytest


@pytest.mark.parametrize("module_name", [
    "kaggle_backend",
    "huggingface_space_backend",
    "huggingface_artifacts",
    "kaggle_bridge",
    "orbitune_workload",
])
def test_gateway_compatibility_import_is_the_sites_runtime_module(module_name: str) -> None:
    compatibility = import_module(f"gpu_gateway.{module_name}")
    canonical = import_module(f"gpu_gateway._provider_runtime.{module_name}")

    assert compatibility is canonical
    assert canonical.__name__ == f"gpu_gateway._provider_runtime.{module_name}"
