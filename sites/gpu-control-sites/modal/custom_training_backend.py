"""Private Sandbox lifecycle transport; callers must validate and reserve first."""
import re

from custom_training_sandbox import create_training_sandbox


def _handle(value):
    if not isinstance(value, str) or re.fullmatch(r"sb-[A-Za-z0-9]{8,128}", value) is None:
        raise ValueError("invalid_sandbox_handle")
    return value


class CustomTrainingBackend:
    def __init__(self, *, app, image, source_volume, checkpoint_volume, create, lookup, stage):
        self.app, self.image = app, image
        self.source_volume, self.checkpoint_volume = source_volume, checkpoint_volume
        self.create, self.lookup, self.stage = create, lookup, stage

    def start(self, plan):
        # The staging implementation must use an isolated run subdirectory and
        # verify the commit. It runs before allocation, never inside the job.
        self.stage(plan["repository"], plan["commit"], plan["run_id"])
        sandbox_plan = {key: plan[key] for key in ("run_id", "commit", "command", "runtime_seconds", "gpu")}
        sandbox = create_training_sandbox(sandbox_plan, app=self.app, image=self.image,
                                          source_volume=self.source_volume,
                                          checkpoint_volume=self.checkpoint_volume, create=self.create)
        return _handle(sandbox.object_id)

    def inspect(self, handle, plan):
        sandbox = self.lookup(_handle(handle))
        code = sandbox.poll()
        if code is None:
            return {"state": "running"}
        if type(code) is not int:
            raise ValueError("invalid_provider_exit_code")
        # Provider exit status alone proves neither GPU use nor artifact
        # integrity, and does not prove all provider cleanup has completed.
        return {"state": "succeeded" if code == 0 else "failed", "exit_code": code,
                "gpu_used": "unverified", "cleanup": "unverified"}

    def cancel(self, handle):
        self.lookup(_handle(handle)).terminate(wait=True)
