"""Modal transport for the private, fixed MAP training function."""
import os
import re
import time

import modal

from map_training_job import validate_map_plan


APP_NAME = "gpu-control-map-training"
FUNCTION_NAME = "train_map"
CALL_ID = re.compile(r"^fc-[A-Za-z0-9]{8,128}$")


def _required_call_id(value):
    if not isinstance(value, str) or CALL_ID.fullmatch(value) is None:
        raise ValueError("training_call_id_invalid")
    return value


def _validate_training_authorization(value, owner, run_id, fingerprint, plan):
    """Require the exact one-use Sites confirmation at the provider boundary."""
    now = int(time.time())
    control_plane_sha = os.environ.get("MAP_TRAINING_CONTROL_PLANE_SHA", "")
    required = {
        "authorization_id", "authorization_source", "authorization_reference", "decision_record_id",
        "authorized_by", "control_plane_sha", "target_repository", "target_sha", "image_digest",
        "provider", "provider_resource_id", "gpu_count", "runtime_seconds", "max_cost_microusd",
        "authorized_at", "expires_at", "owner", "run_id", "plan_fingerprint",
    }
    if (not isinstance(value, dict) or set(value) != required
            or value.get("authorization_source") != "chatgpt_mcp_write_confirmation"
            or value.get("owner") != owner or value.get("authorized_by") != owner
            or value.get("run_id") != run_id or value.get("plan_fingerprint") != fingerprint
            or value.get("decision_record_id") != f"training-plan:{run_id}:{fingerprint}"
            or value.get("control_plane_sha") != control_plane_sha
            or re.fullmatch(r"[0-9a-f]{40}", control_plane_sha) is None
            or re.fullmatch(r"[0-9a-f]{32}", str(value.get("authorization_id", ""))) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(value.get("authorization_reference", ""))) is None
            or value.get("target_repository") != plan.get("repository")
            or value.get("target_sha") != plan.get("commit")
            or value.get("image_digest") != plan.get("image_digest")
            or value.get("provider") != plan.get("provider")
            or value.get("provider_resource_id") != plan.get("provider_resource_id")
            or value.get("gpu_count") != plan.get("gpu_count")
            or value.get("runtime_seconds") != plan.get("runtime_seconds")
            or value.get("max_cost_microusd") != plan.get("max_cost_microusd")
            or type(value.get("authorized_at")) is not int
            or type(value.get("expires_at")) is not int
            or value["authorized_at"] > now or value["authorized_at"] < now - 600
            or not now < value["expires_at"] <= min(value["authorized_at"] + 600, now + 600)):
        raise ValueError("training_authorization_invalid")


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
        if result == {"run_id": plan.get("run_id"), "failure_code": "TRAINING_WORKLOAD_FAILURE"}:
            return {"state": "failed", "failure_code": "TRAINING_WORKLOAD_FAILURE"}
        if (not isinstance(result, dict)
                or result.get("run_id") != plan["run_id"]
                or result.get("source_sha") != plan["commit"]
                or result.get("image_digest") != plan["image_digest"]
                or result.get("dataset") != plan["dataset"]
                or result.get("run_name") != plan["run_name"]
                or result.get("gpu_used") is not True
                or type(result.get("steps")) is not int or not 1 <= result["steps"] <= plan["steps"]):
            raise ValueError("training_result_identity_mismatch")
        checkpoint = result.get("checkpoint")
        if (not isinstance(checkpoint, dict)
                or not re.fullmatch(r"step-[0-9]{9}-[a-f0-9]{8}\.pt", str(checkpoint.get("filename", "")))
                or not re.fullmatch(r"[a-f0-9]{64}", str(checkpoint.get("sha256", "")))
                or type(checkpoint.get("size_bytes")) is not int
                or not 1 <= checkpoint["size_bytes"] <= 1024 ** 3):
            raise ValueError("training_checkpoint_manifest_invalid")
        return {"state": "succeeded", "steps": result["steps"], "gpu_used": True,
                "dataset": result["dataset"], "run_name": result["run_name"],
                "checkpoint": {key: checkpoint[key] for key in ("filename", "sha256", "size_bytes")}}

    def checkpoint_download(self, run_id, manifest):
        volume = modal.Volume.from_name("gpu-control-map-checkpoints", environment_name="main")
        return {
            "url": volume.get_dashboard_url(),
            "path": f"/{run_id}/{manifest['filename']}",
            "authentication": "modal_workspace",
        }

    def recover_checkpoint(self, run_id):
        reader = modal.Function.from_name(APP_NAME, "read_map_checkpoint", environment_name="main")
        return reader.remote(run_id, None, 0, 0)

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
        authorization = args.get("authorization")
        deadline = args.get("authorization_expires_at")
        if (not isinstance(authorization, dict) or type(deadline) is not int
                or deadline != authorization.get("expires_at") or deadline <= int(time.time())):
            return {"state": "blocked", "reason": "TRAINING_AUTHORIZATION_EXPIRED"}
        _validate_training_authorization(authorization, owner, run_id, fingerprint, plan)
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
        if record["state"] == "cancel_requested":
            return {"state": "cancel_requested"}
        response = backend.cancel(record["call_id"])
        store.put(key, {**record, "state": "cancel_requested"})
        return response
    if tool not in {"training_cancel", "training_status", "training_checkpoint"}:
        raise ValueError("training_tool_invalid")
    if terminal is None:
        result = backend.inspect(record["call_id"], record["plan"])
        if result["state"] in {"succeeded", "cancelled", "failed"}:
            terminal = result
            store.put(key, {**record, "state": result["state"], "terminal_result": result})
    else:
        result = terminal
    if result["state"] == "running" and record["state"] == "cancel_requested":
        result = {"state": "cancel_requested"}
    if tool == "training_checkpoint":
        checkpoint = result.get("checkpoint")
        if not checkpoint and result.get("failure_code") == "TRAINING_RUNTIME_LIMIT":
            checkpoint = backend.recover_checkpoint(run_id)
            if checkpoint:
                recovered = {**result, "checkpoint": checkpoint}
                store.put(key, {**record, "state": result["state"], "terminal_result": recovered})
        if not checkpoint:
            return {"state": "checkpoint_not_ready"}
        return {"state": "succeeded", "checkpoint_chunk": backend.checkpoint(
            run_id, checkpoint, args.get("offset"), args.get("max_bytes"))}
    if tool == "training_status" and result.get("checkpoint"):
        return {**result, "checkpoint_download": backend.checkpoint_download(run_id, result["checkpoint"])}
    return result
