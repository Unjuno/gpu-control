"""Run an owner-specified argv inside an already isolated workload container.

This module is not a sandbox. The caller must supply an isolated container,
staged immutable source and appropriate filesystem/network/credential policy.
"""
import os
import signal
import subprocess
import threading
import time
from pathlib import Path


def run_command(command, source_dir, runtime_seconds, *, cancelled=lambda: False,
                output_limit=65536, poll_interval=0.1, checkpoint_dir=None,
                drop_privileges=False, on_poll=None):
    if (not isinstance(command, list) or not 1 <= len(command) <= 64
            or any(not isinstance(arg, str) or not arg or '\x00' in arg
                   or len(arg) > 4096 for arg in command)):
        raise ValueError("invalid_command")
    if (type(runtime_seconds) is not int or not 1 <= runtime_seconds <= 86400
            or type(output_limit) is not int or not 1 <= output_limit <= 1048576):
        raise ValueError("invalid_limits")
    cwd = Path(source_dir).resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError("invalid_source_directory")
    # No inherited provider credentials or arbitrary ambient environment.
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
           "PYTHONUNBUFFERED": "1"}
    if checkpoint_dir is not None:
        checkpoint_path = Path(checkpoint_dir).resolve(strict=True)
        if not checkpoint_path.is_dir():
            raise ValueError("invalid_checkpoint_directory")
        env["GPU_CONTROL_CHECKPOINT_DIR"] = os.fspath(checkpoint_path)
    privilege_args = {}
    if drop_privileges:
        if os.name != "posix" or os.geteuid() != 0:
            raise ValueError("cannot_drop_workload_privileges")
        privilege_args = {"user": 10001, "group": 10001, "extra_groups": ()}
    with subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          start_new_session=True, **privilege_args) as process:
        data = bytearray()
        def drain():
            while chunk := process.stdout.read(8192):
                remaining = output_limit + 1 - len(data)
                if remaining > 0:
                    data.extend(chunk[:remaining])
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        deadline = time.monotonic() + runtime_seconds
        reason = None
        gpu_activity_seen = False
        try:
            while process.poll() is None:
                if cancelled():
                    reason = "cancelled"
                    break
                if time.monotonic() >= deadline:
                    reason = "timeout"
                    break
                if on_poll is not None:
                    try:
                        gpu_activity_seen = bool(on_poll()) or gpu_activity_seen
                    except Exception:
                        # Instrumentation errors never manufacture GPU evidence.
                        pass
                time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        finally:
            # Terminate the process group even when the leader exits: children
            # must not outlive the job and keep writing artifacts or consuming CPU.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        reader.join(timeout=1)
    return {"state": reason or ("succeeded" if process.returncode == 0 else "failed"),
            "exit_code": process.returncode,
            "output": bytes(data[:output_limit]).decode("utf-8", errors="replace"),
            "output_truncated": len(data) > output_limit,
            "gpu_activity_seen": gpu_activity_seen}
