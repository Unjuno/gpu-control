"""Private adapter for an already validated and budget-reserved training plan.

The caller must enforce authenticated ownership, durable dispatch claims,
current price and budget, trusted image identity, and source staging. This
module deliberately accepts no credentials and creates no public endpoint.
"""
import re

from custom_training_plan import validate_custom_command


def create_training_sandbox(plan, *, app, image, source_volume, checkpoint_volume, create,
                            expected_manifest_sha256, expected_lock_sha256, lock_path):
    required = {"run_id", "commit", "command", "runtime_seconds", "gpu", "python_version",
                "manifest_sha256", "lock_sha256", "dependencies_lock"}
    if not isinstance(plan, dict) or set(plan) != required:
        raise ValueError("invalid_sandbox_plan")
    run_id, commit, command = plan["run_id"], plan["commit"], plan["command"]
    runtime = plan["runtime_seconds"]
    if (not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None or
            not isinstance(commit, str) or re.fullmatch(r"[a-f0-9]{40}", commit) is None or
            type(runtime) is not int or not 120 <= runtime <= 3000 or plan["gpu"] not in {"T4", "L4"} or
            plan["python_version"] not in {"3.11", "3.12"}):
        raise ValueError("invalid_sandbox_plan")
    try:
        validate_custom_command(command)
    except ValueError as exc:
        raise ValueError("invalid_sandbox_plan") from exc
    if (plan["manifest_sha256"] != expected_manifest_sha256 or
            plan["lock_sha256"] != expected_lock_sha256 or
            plan["dependencies_lock"] != lock_path):
        raise ValueError("training_source_binding_mismatch")
    # Source and output mounts are scoped to the run. No shared checkpoint
    # root or provider credentials enter the workload's security boundary.
    return create("python", "/opt/gpu-control/custom_sandbox_entrypoint.py",
                  app=app, image=image, name=f"custom-training-{run_id}",
                  # Modal only supports GPU Sandboxes on gVisor. Keep this
                  # explicit so a future SDK default cannot select a different
                  # runtime for user-controlled source code.
                  runtime="gvisor", gpu=plan["gpu"], cpu=2, memory=8192, timeout=runtime,
                  block_network=True,
                  volumes={"/source-store": source_volume.with_mount_options(sub_path=f"/{run_id}", read_only=True),
                           "/output": checkpoint_volume.with_mount_options(sub_path=f"/{run_id}")},
                  env={"GPU_CONTROL_COMMIT": commit,
                       "GPU_CONTROL_RUN_ID": run_id,
                       "GPU_CONTROL_ENTRYPOINT": command[1],
                       "GPU_CONTROL_PYTHON_VERSION": plan["python_version"],
                       "GPU_CONTROL_MANIFEST_SHA256": expected_manifest_sha256,
                       "GPU_CONTROL_LOCK_SHA256": expected_lock_sha256,
                       "GPU_CONTROL_DEPENDENCIES_LOCK": lock_path,
                       "GPU_CONTROL_WHEELHOUSE": "/source-store/wheelhouse",
                       "GPU_CONTROL_GPU_PROFILE": plan["gpu"],
                       "GPU_CONTROL_RUNTIME_SECONDS": str(runtime)})


def create_training_stage_sandbox(plan, *, app, image, source_volume, checkpoint_volume,
                                  create, source_token=None):
    """Create a deterministic, CPU-only sandbox for fixed source staging."""
    if (not isinstance(plan, dict) or
            not isinstance(plan.get("run_id"), str) or re.fullmatch(r"[a-f0-9]{32}", plan["run_id"]) is None or
            not isinstance(plan.get("repository"), str) or
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", plan["repository"]) is None or
            not isinstance(plan.get("commit"), str) or re.fullmatch(r"[0-9a-f]{40}", plan["commit"]) is None):
        raise ValueError("invalid_stage_plan")
    if source_token is not None and (not isinstance(source_token, str) or not 20 <= len(source_token) <= 512 or
            any(not (char.isascii() and (char.isalnum() or char in "_-")) for char in source_token)):
        raise ValueError("invalid_source_token")
    env = {"GPU_CONTROL_REPOSITORY": plan["repository"], "GPU_CONTROL_COMMIT": plan["commit"],
           "GPU_CONTROL_RUN_ID": plan["run_id"]}
    if source_token is not None:
        # Only the fixed trusted staging program receives this short-lived,
        # exact-repository installation token. The GPU Sandbox never does.
        env["GPU_CONTROL_SOURCE_TOKEN"] = source_token
    return create("python", "/root/site-modal/custom_training_stage_entrypoint.py",
                  app=app, image=image, name=f"custom-training-stage-{plan['run_id']}",
                  runtime="gvisor", cpu=1, memory=1024, timeout=300,
                  # This fixed, trusted process is the only stage that can
                  # receive a repository-scoped GitHub token. Keep its egress
                  # to the exact GitHub and PyPI hosts needed for source and
                  # hash-pinned wheel retrieval. Modal added domain allowlists
                  # in SDK 1.5.0; requirements-worker pins 1.5.5.
                  outbound_domain_allowlist=["github.com", "pypi.org", "files.pythonhosted.org"],
                  volumes={"/source-store": source_volume,
                           "/checkpoint-store": checkpoint_volume}, env=env)
