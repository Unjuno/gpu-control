"""Fixed entry point baked into the reviewed custom training image."""
import json
import os

from custom_training_job import run_custom_training


def main():
    result = run_custom_training("/source-store", os.environ["GPU_CONTROL_COMMIT"],
                                 json.loads(os.environ["GPU_CONTROL_COMMAND_JSON"]),
                                 int(os.environ["GPU_CONTROL_RUNTIME_SECONDS"]),
                                 "/output/checkpoint")
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
