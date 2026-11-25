"""Trusted in-container deadline supervisor for the fixed CPU smoke program."""
import os
import signal
import subprocess
import sys


def main():
    timeout = int(os.environ["GPU_CONTROL_RUNTIME_SECONDS"])
    if not 1 <= timeout <= 30:
        raise SystemExit("invalid_runtime_limit")
    env = {key: os.environ[key] for key in (
        "GPU_CONTROL_RUN_ID", "GPU_CONTROL_SOURCE_SHA", "GPU_CONTROL_PLAN_FINGERPRINT",
        "GPU_CONTROL_PARAMETERS_JSON", "GPU_CONTROL_RUNTIME_SECONDS",
    )}
    child = subprocess.Popen([sys.executable, "-I", "/app/smoke.py"], env=env, start_new_session=True)
    try:
        return child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
