"""Emit a journal-visible capacity status for a dedicated artifact filesystem."""
from __future__ import annotations

import json
import os
from pathlib import Path


def inspect_capacity(root: str, minimum_free_bytes: int) -> dict:
    if type(minimum_free_bytes) is not int or minimum_free_bytes <= 0:
        return {"available": False, "reason": "invalid_minimum_free_bytes"}
    if not isinstance(root, str) or not root or not Path(root).is_absolute():
        return {"available": False, "reason": "invalid_artifact_path"}
    path = Path(root)
    try:
        if path.is_symlink():
            return {"available": False, "reason": "symlink"}
        if not path.is_dir():
            return {"available": False, "reason": "not_directory"}
        if path.stat().st_dev == path.parent.stat().st_dev:
            return {"available": False, "reason": "not_dedicated_filesystem"}
        values = os.statvfs(path)
        free_bytes = values.f_bavail * values.f_frsize
        return {"available": free_bytes >= minimum_free_bytes,
                "reason": None if free_bytes >= minimum_free_bytes else "below_minimum_free_bytes",
                "free_bytes": free_bytes,
                "minimum_free_bytes": minimum_free_bytes}
    except OSError:
        return {"available": False, "reason": "probe_failed"}


def main() -> int:
    root = os.environ.get("GATEWAY_ARTIFACT_DIR", "")
    raw_minimum = os.environ.get("GATEWAY_ARTIFACT_MIN_FREE_BYTES", "")
    try:
        minimum = int(raw_minimum)
    except (TypeError, ValueError):
        minimum = 0
    result = inspect_capacity(root, minimum)
    # Emit a stable state on every timer run so a journal/metrics bridge can
    # both raise and clear an alert. Delivery still belongs to the host sink.
    print(json.dumps({"check": "gpu-control-artifact-capacity",
                      "status": "ok" if result["available"] else "alert",
                      **result},
                     sort_keys=True, separators=(",", ":")), flush=True)
    return 0 if result["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
