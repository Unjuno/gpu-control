"""Temporary import path for legacy Gateway compatibility tests."""
from pathlib import Path
import sys

SITES_MODAL = Path(__file__).resolve().parents[2] / "sites" / "gpu-control-sites" / "modal"
if str(SITES_MODAL) not in sys.path:
    sys.path.insert(0, str(SITES_MODAL))
