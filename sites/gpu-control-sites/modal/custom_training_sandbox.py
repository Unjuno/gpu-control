"""Private adapter for an already validated and budget-reserved training plan.

The caller must enforce authenticated ownership, durable dispatch claims,
current price and budget, trusted image identity, and source staging. This
module deliberately accepts no credentials and creates no public endpoint.
"""
import json
import re


def create_training_sandbox(plan, *, app, image, source_volume, checkpoint_volume, create):
    required = {"run_id", "commit", "command", "runtime_seconds", "gpu"}
    if not isinstance(plan, dict) or set(plan) != required:
        raise ValueError("invalid_sandbox_plan")
    run_id, commit, command = plan["run_id"], plan["commit"], plan["command"]
    runtime = plan["runtime_seconds"]
    if (not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None or
            not isinstance(commit, str) or re.fullmatch(r"[a-f0-9]{40}", commit) is None or
            not isinstance(command, list) or not 1 <= len(command) <= 64 or
            any(not isinstance(arg, str) or not arg or len(arg) > 4096 or "\x00" in arg for arg in command) or
            type(runtime) is not int or not 1 <= runtime <= 3000 or plan["gpu"] not in {"T4", "L4"}):
        raise ValueError("invalid_sandbox_plan")
    # Source and output mounts are scoped to the run. No shared checkpoint
    # root or provider credentials enter the workload's security boundary.
    return create("python", "/opt/gpu-control/custom_sandbox_entrypoint.py",
                  app=app, image=image, name=f"custom-training-{run_id}",
                  gpu=plan["gpu"], cpu=2, memory=8192, timeout=runtime,
                  block_network=True,
                  volumes={"/source-store": source_volume.with_mount_options(sub_path=f"/{run_id}", read_only=True),
                           "/output": checkpoint_volume.with_mount_options(sub_path=f"/{run_id}")},
                  env={"GPU_CONTROL_COMMIT": commit,
                       "GPU_CONTROL_COMMAND_JSON": json.dumps(command, ensure_ascii=True),
                       "GPU_CONTROL_RUNTIME_SECONDS": str(runtime)})
