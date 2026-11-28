"""Fixed trusted CPU staging entrypoint; it never imports repository code."""
import json
import os
import re

from custom_training_stage import stage_to_mounts


def main():
    repository = os.environ["GPU_CONTROL_REPOSITORY"]
    commit = os.environ["GPU_CONTROL_COMMIT"]
    run_id = os.environ["GPU_CONTROL_RUN_ID"]
    source_token = os.environ.get("GPU_CONTROL_SOURCE_TOKEN") or None
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", repository) or
            not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[a-f0-9]{32}", run_id)):
        raise ValueError("invalid_stage_identity")
    result = stage_to_mounts(repository, commit, run_id, source_token=source_token)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
