"""Fixed entry point baked into the reviewed custom training image."""
import json
import os
import subprocess
import sys
from pathlib import Path

from custom_training_job import run_custom_training


def main():
    # Reserve time inside the provider deadline for checkpoint hashing and
    # emitting the terminal record. This is not additional billable runtime.
    runtime = int(os.environ["GPU_CONTROL_RUNTIME_SECONDS"])
    if runtime < 120:
        raise ValueError("invalid_runtime")
    expected_python = os.environ["GPU_CONTROL_PYTHON_VERSION"]
    if (expected_python not in {"3.11", "3.12"} or
            f"{sys.version_info.major}.{sys.version_info.minor}" != expected_python):
        raise ValueError("runtime_python_version_mismatch")
    result = run_custom_training("/source-store", os.environ["GPU_CONTROL_COMMIT"],
                                 os.environ["GPU_CONTROL_ENTRYPOINT"],
                                 runtime - 45,
                                 "/output/checkpoint",
                                 expected_manifest_sha256=os.environ["GPU_CONTROL_MANIFEST_SHA256"],
                                 dependencies_lock=os.environ["GPU_CONTROL_DEPENDENCIES_LOCK"],
                                 expected_lock_sha256=os.environ["GPU_CONTROL_LOCK_SHA256"],
                                 run_id=os.environ["GPU_CONTROL_RUN_ID"],
                                 gpu_profile=os.environ["GPU_CONTROL_GPU_PROFILE"],
                                 wheelhouse=os.environ["GPU_CONTROL_WHEELHOUSE"])
    encoded = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    result_path = Path("/output/result.json")
    temp_path = result_path.with_suffix(".json.tmp")
    temp_path.write_text(encoded, encoding="utf-8")
    temp_path.replace(result_path)
    # Persist the run-scoped output snapshot with a fixed utility, never by
    # giving the training process Modal credentials.
    subprocess.run(["sync", "/output"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=10, check=True)
    print(encoded, flush=True)
    return 0 if result["state"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
