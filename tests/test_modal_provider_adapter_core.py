"""Collect the dependency-free Modal provider adapter contract in normal CI."""
from __future__ import annotations

import sys
from pathlib import Path


MODAL_SOURCE = Path(__file__).parents[1] / "sites" / "gpu-control-sites" / "modal"
sys.path.insert(0, str(MODAL_SOURCE))

from test_provider_adapter_core import *  # noqa: F401,F403,E402
