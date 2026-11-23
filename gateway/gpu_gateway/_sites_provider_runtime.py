"""Load the Sites-owned provider runtime under a private package namespace."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_PACKAGE = "gpu_gateway._provider_runtime"
_REPOSITORY_RUNTIME = (
    Path(__file__).resolve().parents[2]
    / "sites" / "gpu-control-sites" / "modal" / "provider_runtime"
)
_IMAGE_RUNTIME = Path(__file__).resolve().parents[1] / "provider_runtime"


def _load() -> None:
    if _PACKAGE in sys.modules:
        return
    runtime = next(
        (candidate for candidate in (_REPOSITORY_RUNTIME, _IMAGE_RUNTIME)
         if candidate.is_dir() and (candidate / "__init__.py").is_file()),
        None,
    )
    if runtime is None:
        raise ImportError("Sites provider runtime is not packaged")
    spec = spec_from_file_location(
        _PACKAGE,
        runtime / "__init__.py",
        submodule_search_locations=[str(runtime)],
    )
    if spec is None or spec.loader is None:
        raise ImportError("Sites provider runtime cannot be loaded")
    module = module_from_spec(spec)
    sys.modules[_PACKAGE] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(_PACKAGE, None)
        raise


_load()
