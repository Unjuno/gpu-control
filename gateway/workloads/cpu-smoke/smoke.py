"""Deterministic, bounded CPU-only smoke workload; no network or dependencies."""
import hashlib
import json
import os
import re
import socket
import sys


def main():
    run_id = os.environ["GPU_CONTROL_RUN_ID"]
    source_sha = os.environ["GPU_CONTROL_SOURCE_SHA"]
    fingerprint = os.environ["GPU_CONTROL_PLAN_FINGERPRINT"]
    parameters = json.loads(os.environ["GPU_CONTROL_PARAMETERS_JSON"])
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise SystemExit("invalid_run_id")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise SystemExit("invalid_source_sha")
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise SystemExit("invalid_plan_fingerprint")
    iterations = parameters.get("iterations", 1000)
    seed = parameters.get("seed", 17)
    if type(iterations) is not int or not 1 <= iterations <= 20000000:
        raise SystemExit("invalid_iterations")
    if type(seed) is not int or not 0 <= seed <= 1000000:
        raise SystemExit("invalid_seed")
    if os.getuid() != 10001:
        raise SystemExit("non_root_identity_required")
    if any(key in os.environ for key in ("GITHUB_TOKEN", "MODAL_TOKEN_SECRET", "RUNPOD_API_KEY", "DATABASE_URL")):
        raise SystemExit("unexpected_secret_environment")
    if os.path.exists("/var/run/docker.sock"):
        raise SystemExit("docker_socket_must_not_be_mounted")
    try:
        with open("/app/write-probe", "w", encoding="utf-8") as probe:
            probe.write("unexpected")
    except OSError:
        pass
    else:
        raise SystemExit("root_filesystem_must_be_read_only")
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=0.2)
    except OSError:
        pass
    else:
        raise SystemExit("container_network_must_be_disabled")
    accumulator = 0
    for index in range(iterations):
        accumulator = (accumulator * 33 + (index ^ seed)) & 0xFFFFFFFF
    identity = {"run_id": run_id, "source_sha": source_sha,
                "plan_fingerprint": fingerprint, "iterations": iterations,
                "seed": seed, "checksum_value": accumulator}
    checksum = hashlib.sha256(json.dumps(identity, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    result = {"schema_version": 1, "run_id": run_id, "source_sha": source_sha,
              "plan_fingerprint": fingerprint, "check": "cpu-smoke-v1", "status": "passed",
              "gpu_used": False,
              "metrics": {"iterations": iterations, "checksum_value": accumulator},
              "checks": ["source_identity_present", "parameter_bounds", "checksum_verified",
                         "non_root", "no_secret_environment", "no_docker_socket",
                         "read_only_rootfs", "network_disabled"],
              "checksum": checksum}
    report = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    sys.stdout.write(report.decode("utf-8") + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
