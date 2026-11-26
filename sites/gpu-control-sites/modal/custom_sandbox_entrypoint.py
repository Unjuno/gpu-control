"""Fixed entry point baked into the reviewed custom training image."""
import json
import os

from custom_training_job import run_custom_training


def main():
    # Reserve time inside the provider deadline for checkpoint hashing and
    # emitting the terminal record. This is not additional billable runtime.
    runtime = int(os.environ["GPU_CONTROL_RUNTIME_SECONDS"])
    if runtime < 120:
        raise ValueError("invalid_runtime")
    result = run_custom_training("/source-store", os.environ["GPU_CONTROL_COMMIT"],
                                 json.loads(os.environ["GPU_CONTROL_COMMAND_JSON"]),
                                 runtime - 45,
                                 "/output/checkpoint")
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return 0 if result["state"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
