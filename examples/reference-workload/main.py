from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket


_SENSITIVE_ENV_NAMES = (
    "GITHUB_TOKEN",
    "RUNPOD_API_KEY",
    "GPU_CONTROL_SECRET_SENTINEL",
)
_GPU_DEVICE_PATHS = (
    "/dev/nvidia0",
    "/dev/nvidiactl",
    "/dev/nvidia-uvm",
)


def _network_is_blocked() -> bool:
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=0.25):
            return False
    except OSError:
        return True


def main() -> None:
    values = list(range(10_000))
    total = sum(value * value for value in values)
    digest = hashlib.sha256(str(total).encode("utf-8")).hexdigest()

    isolation_checks = {
        "credentials_absent": all(name not in os.environ for name in _SENSITIVE_ENV_NAMES),
        "docker_socket_absent": not Path("/var/run/docker.sock").exists(),
        "gpu_devices_absent": all(not Path(path).exists() for path in _GPU_DEVICE_PATHS),
        "network_blocked": _network_is_blocked(),
    }

    failed = [name for name, passed in isolation_checks.items() if not passed]
    if failed:
        raise RuntimeError(f"isolation checks failed: {', '.join(sorted(failed))}")

    result = {
        "schema_version": 1,
        "status": "ok",
        "workload_id": "gpu-control-reference",
        "calculation": {
            "sum_of_squares_0_to_9999": total,
            "sha256": digest,
        },
        "isolation_checks": isolation_checks,
    }

    output_dir = Path("/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
