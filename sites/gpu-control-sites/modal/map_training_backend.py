"""Modal transport for the private, fixed MAP training function."""
import os
import re

import modal

from map_training_job import validate_map_plan


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

    def validate(self, plan):
        validate_map_plan(
            plan, source_sha=os.environ.get("MAP_TRAINING_SOURCE_SHA"),
            image_digest=(os.environ.get("MAP_TRAINING_MODAL_IMAGE_ID")
                          or os.environ.get("MAP_TRAINING_IMAGE_DIGEST")),
            hourly_microusd=int(os.environ.get("MAP_TRAINING_HOURLY_MICROUSD", "0")),
            quote_expires_at=int(os.environ.get("MAP_TRAINING_QUOTE_EXPIRES_AT", "0")),
        )
        if plan["runtime_seconds"] != int(os.environ.get("MAP_TRAINING_RUNTIME_SECONDS", "0")):
            raise ValueError("training_runtime_mismatch")

    def start(self, plan):
        # Only a durable claim may reach spawn. Never retry ambiguous transport.
        self.validate(plan)
        call = self._function_lookup().spawn(plan)
        return _required_call_id(call.object_id)

    def inspect(self, call_id, plan):
        call = self._call_lookup(_required_call_id(call_id))
        try:
            result = call.get(timeout=0)
        except modal.exception.InputCancellation:
            return {"state": "cancelled"}
        except modal.exception.FunctionTimeoutError:
            return {"state": "failed", "failure_code": "TRAINING_RUNTIME_LIMIT"}
        except modal.exception.RemoteError:
            return {"state": "failed", "failure_code": "TRAINING_PROVIDER_FAILURE"}
        except (TimeoutError, modal.exception.TimeoutError) as exc:
            if type(exc) not in (TimeoutError, modal.exception.TimeoutError):
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

    def checkpoint(self, run_id, manifest, offset, max_bytes):
        if (type(offset) is not int or not 0 <= offset < manifest["size_bytes"]
                or type(max_bytes) is not int or not 1 <= max_bytes <= 24576):
            raise ValueError("invalid_checkpoint_range")
        reader = modal.Function.from_name(APP_NAME, "read_map_checkpoint", environment_name="main")
        return reader.remote(run_id, manifest, offset, max_bytes)

    def cancel(self, call_id):
        self._call_lookup(_required_call_id(call_id)).cancel(terminate_containers=True)
        return {"state": "cancel_requested"}


def dispatch_training_tool(store, backend, owner, tool, args, *, admission_enabled):
    """Bind every provider interaction to the signed owner and saved run."""
    run_id = args.get("run_id")
    fingerprint = args.get("plan_fingerprint")
    if (not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None
            or not isinstance(fingerprint, str) or re.fullmatch(r"[a-f0-9]{64}", fingerprint) is None):
        raise ValueError("training_run_identity_invalid")
    key = f"map-training:{run_id}"
    binding = {"owner": owner, "fingerprint": fingerprint}
    record = store.get(key)
    if record is not None and any(record.get(k) != v for k, v in binding.items()):
        raise ValueError("training_run_identity_mismatch")

    if tool == "training_submit" and record is None:
        if not admission_enabled:
            return {"state": "blocked", "reason": "TRAINING_ADMISSION_DISABLED"}
        plan = args.get("plan")
        if not isinstance(plan, dict) or plan.get("run_id") != run_id:
            raise ValueError("training_plan_invalid")
        backend.validate(plan)
        claim = {**binding, "plan": plan, "state": "dispatching"}
        if store.put(key, claim, skip_if_exists=True):
            call_id = backend.start(plan)
            store.put(key, {**claim, "call_id": call_id, "state": "running"})
            return {"state": "running"}
        record = store.get(key)
        if not isinstance(record, dict) or any(record.get(k) != v for k, v in binding.items()):
            raise ValueError("training_run_identity_mismatch")

    if record is None:
        return {"state": "not_found"}
    if tool == "training_submit":
        return {"state": record["state"]}
    if "call_id" not in record:
        return {"state": "uncertain"}
    terminal = record.get("terminal_result")
    if tool == "training_cancel" and terminal is None:
        return backend.cancel(record["call_id"])
    if tool not in {"training_cancel", "training_status", "training_checkpoint"}:
        raise ValueError("training_tool_invalid")
    if terminal is None:
        result = backend.inspect(record["call_id"], record["plan"])
        if result["state"] in {"succeeded", "cancelled", "failed"}:
            terminal = result
            store.put(key, {**record, "state": result["state"], "terminal_result": result})
    else:
        result = terminal
    if tool == "training_checkpoint":
        if result["state"] != "succeeded":
            return {"state": "checkpoint_not_ready"}
        return {"state": "succeeded", "checkpoint_chunk": backend.checkpoint(
            run_id, result["checkpoint"], args.get("offset"), args.get("max_bytes"))}
    return result
