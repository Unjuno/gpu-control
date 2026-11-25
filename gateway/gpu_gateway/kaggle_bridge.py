"""Compatibility import; production ownership moved to Sites/Modal."""
import sys
from . import _sites_provider_runtime  # noqa: F401
from gpu_gateway._provider_runtime import kaggle_bridge as _implementation

sys.modules[__name__] = _implementation
