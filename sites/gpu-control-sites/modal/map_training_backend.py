"""Modal transport for the private, fixed MAP training function."""
import re

import modal


APP_NAME = "gpu-control-map-training"
FUNCTION_NAME = "train_map"
CALL_ID = re.compile(r"^fc-[A-Za-z0-9]{8,128}$")


def _required_call_id(value):
    if not isinstance(value, str) or CALL_ID.fullmatch(value) is None:
        raise ValueError("training_call_id_invalid")
    return value


class MapTrainingBackend:
    """Only the trusted adapter may supply plans and persisted call handles."""

    def __init__(self, function_lookup=None, call_lookup=None):
        self._function_lookup = function_lookup or (
            lambda: modal.Function.from_name(APP_NAME, FUNCTION_NAME, environment_name="main")
        )
        self._call_lookup = call_lookup or modal.FunctionCall.from_id

    def start(self, plan):
        # The adapter must durably claim this exact plan before calling start.
        # Transport errors are ambiguous. Callers must never retry spawn blindly.
        call = self._function_lookup().spawn(plan)
        return _required_call_id(call.object_id)

    def inspect(self, call_id, plan):
        call = self._call_lookup(_required_call_id(call_id))
        try:
            result = call.get(timeout=0)
        except modal.exception.InputCancellation:
            return {"state": "cancelled"}
        except modal.exception.TimeoutError as exc:
            if type(exc) is not modal.exception.TimeoutError:
                raise
            return {"state": "running"}
        if (not isinstance(result, dict)
                or result.get("run_id") != plan["run_id"]
                or result.get("source_sha") != plan["commit"]
                or result.get("image_digest") != plan["image_digest"]
                or result.get("gpu_used") is not True
                or type(result.get("steps")) is not int or result["steps"] < 1):
            raise ValueError("training_result_identity_mismatch")
        checkpoint = result.get("checkpoint")
        if (not isinstance(checkpoint, dict)
                or not re.fullmatch(r"step-[0-9]{9}-[a-f0-9]{8}\.pt", str(checkpoint.get("filename", "")))
                or not re.fullmatch(r"[a-f0-9]{64}", str(checkpoint.get("sha256", "")))
                or type(checkpoint.get("size_bytes")) is not int
                or not 1 <= checkpoint["size_bytes"] <= 1024 ** 3):
            raise ValueError("training_checkpoint_manifest_invalid")
        return {"state": "succeeded", "steps": result["steps"], "gpu_used": True,
                "checkpoint": {key: checkpoint[key] for key in ("filename", "sha256", "size_bytes")}}

    def cancel(self, call_id):
        self._call_lookup(_required_call_id(call_id)).cancel(terminate_containers=True)
        return {"state": "cancel_requested"}
