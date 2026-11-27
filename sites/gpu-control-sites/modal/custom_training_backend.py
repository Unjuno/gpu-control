"""Private Sandbox lifecycle transport; callers must validate and reserve first."""
import json
import base64
import hashlib
import math
import os
import re
import stat

from custom_training_sandbox import create_training_sandbox, create_training_stage_sandbox


def _handle(value):
    if not isinstance(value, str) or re.fullmatch(r"custom-training-[a-f0-9]{32}", value) is None:
        raise ValueError("invalid_sandbox_handle")
    return value


class CustomTrainingBackend:
    def __init__(self, *, app, image, stage_image=None, source_volume, checkpoint_volume, create, lookup, stage,
                 cleanup_source=None, cleanup_checkpoint=None, commit_source=None,
                 commit_output=None, checkpoint_root=None, source_root="/source-store"):
        self.app, self.image, self.stage_image = app, image, stage_image or image
        self.source_volume, self.checkpoint_volume = source_volume, checkpoint_volume
        self.create, self.lookup, self.stage = create, lookup, stage
        self.cleanup_source, self.commit_output = cleanup_source, commit_output
        self.cleanup_checkpoint, self.commit_source = cleanup_checkpoint, commit_source
        self.checkpoint_root = checkpoint_root
        self.source_root = source_root

    def start(self, plan, source_token=None):
        # Create only a deterministic CPU staging Sandbox here. GitHub/PyPI
        # access runs asynchronously in its fixed trusted entrypoint, keeping
        # Sites' HTTP request inside its short delegation deadline.
        create_training_stage_sandbox(plan, app=self.app, image=self.stage_image,
            source_volume=self.source_volume, checkpoint_volume=self.checkpoint_volume,
            create=self.create, source_token=source_token)
        return _handle(f"custom-training-{plan['run_id']}")

    @staticmethod
    def _valid_stage_binding(staged, plan):
        return (isinstance(staged, dict) and staged.get("commit") == plan["commit"] and
                staged.get("manifest_sha256") == plan["manifest_sha256"] and
                staged.get("lock_sha256") == plan["lock_sha256"] and
                staged.get("dependencies_lock") == plan["dependencies_lock"] and
                staged.get("entrypoint") == plan["command"][1] and
                isinstance(staged.get("wheelhouse_sha256"), str) and
                re.fullmatch(r"[0-9a-f]{64}", staged["wheelhouse_sha256"]) is not None and
                type(staged.get("wheelhouse_packages")) is int and
                1 <= staged["wheelhouse_packages"] <= 128 and
                type(staged.get("wheelhouse_bytes")) is int and
                1 <= staged["wheelhouse_bytes"] <= 1024 ** 3)

    @staticmethod
    def _valid_metrics(value):
        if (not isinstance(value, dict) or value.get("filename") != "metrics.json" or
                type(value.get("size_bytes")) is not int or not 1 <= value["size_bytes"] <= 8192 or
                not isinstance(value.get("sha256"), str) or
                re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None or
                not isinstance(value.get("values"), dict) or not 1 <= len(value["values"]) <= 64):
            return False
        for key, item in value["values"].items():
            if (not isinstance(key, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", key) is None or
                    not (type(item) in {int, float, bool} or
                         isinstance(item, str) and len(item.encode("utf-8")) <= 256) or
                    type(item) is float and not math.isfinite(item)):
                return False
        return True

    @staticmethod
    def _valid_artifacts(value):
        if not isinstance(value, list) or len(value) > 14:
            return False
        seen = set()
        for item in value:
            if (not isinstance(item, dict) or set(item) != {"artifact_id", "path", "size_bytes", "sha256"} or
                    not isinstance(item.get("path"), str) or not item["path"].startswith("artifacts/") or
                    "*" in item["path"] or any(not part or part in {".", ".."} or
                        re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None for part in item["path"].split("/")) or
                    not isinstance(item.get("artifact_id"), str) or
                    item["artifact_id"] != hashlib.sha256(item["path"].encode()).hexdigest() or
                    type(item.get("size_bytes")) is not int or not 1 <= item["size_bytes"] <= 256 * 1024 * 1024 or
                    not isinstance(item.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None or
                    item["artifact_id"] in seen):
                return False
            seen.add(item["artifact_id"])
        return True

    def _start_gpu_from_stage(self, stage, plan, handle, cancel_requested=False):
        code = stage.poll()
        if code is None:
            return {"state": "cancel_requested" if cancel_requested else "staging", "phase": "source_staging"}
        if cancel_requested:
            cleanup = self._finish_stage(stage, plan["run_id"], cleanup=True)
            return {"state": "cancelled" if cleanup else "cleanup_pending", "gpu_used": False,
                    "checkpoint": None, "cleanup": "confirmed" if cleanup else "pending"}
        if type(code) is not int or code != 0:
            self._finish_stage(stage, plan["run_id"], cleanup=True)
            return {"state": "failed", "exit_code": code if type(code) is int else None,
                    "gpu_used": False, "checkpoint": None,
                    "cleanup": "confirmed" if self.cleanup_source(plan["run_id"]) and
                    self.cleanup_checkpoint(plan["run_id"]) else "pending",
                    "failure_code": "TRAINING_SOURCE_STAGE_FAILED"}
        if not self._finish_stage(stage, plan["run_id"], cleanup=False):
            return {"state": "staging", "phase": "source_commit_pending"}
        staged = None
        try:
            marker = os.path.join(self.source_root, plan["run_id"], ".gpu-control-stage.json")
            fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if stat.S_ISREG(info.st_mode) and 0 < info.st_size <= 16384:
                    staged = json.loads(stream.read(16385).decode("utf-8"))
        except Exception:
            staged = None
        if not self._valid_stage_binding(staged, plan):
            self._finish_stage(stage, plan["run_id"], cleanup=True)
            return {"state": "failed", "exit_code": code, "gpu_used": False,
                    "checkpoint": None,
                    "cleanup": "confirmed" if self.cleanup_source(plan["run_id"]) and
                    self.cleanup_checkpoint(plan["run_id"]) else "pending",
                    "failure_code": "TRAINING_SOURCE_BINDING_MISMATCH"}
        sandbox_plan = {key: plan[key] for key in ("run_id", "commit", "command", "runtime_seconds", "gpu", "python_version",
                                                   "manifest_sha256", "lock_sha256", "dependencies_lock")}
        try:
            sandbox = create_training_sandbox(sandbox_plan, app=self.app, image=self.image,
                                              source_volume=self.source_volume,
                                              checkpoint_volume=self.checkpoint_volume, create=self.create,
                                              expected_manifest_sha256=plan["manifest_sha256"],
                                              expected_lock_sha256=plan["lock_sha256"],
                                              lock_path=plan["dependencies_lock"])
        except Exception:
            # Create may have succeeded before the response was lost. Retain
            # the immutable source until status recovery proves the Sandbox is
            # gone and cleanup is complete.
            raise
        return sandbox

    def _finish_stage(self, stage, run_id, *, cleanup):
        try:
            stage.terminate(wait=True)
        except Exception as exc:
            if type(exc).__name__ != "NotFoundError":
                return False
        try:
            if self.commit_source is not None:
                self.commit_source()
            if self.commit_output is not None:
                self.commit_output()
            if cleanup:
                source_ok = self.cleanup_source is not None and self.cleanup_source(run_id) is True
                checkpoint_ok = self.cleanup_checkpoint is not None and self.cleanup_checkpoint(run_id) is True
                return source_ok and checkpoint_ok
            return True
        except Exception:
            return False

    def inspect(self, handle, plan, cancel_requested=False):
        handle = _handle(handle)
        sandbox = self.lookup(handle)
        if sandbox is None:
            stage = self.lookup(f"custom-training-stage-{plan['run_id']}")
            if stage is None:
                cleanup = ("confirmed" if self.cleanup_source is not None and
                           self.cleanup_source(plan["run_id"]) is True else "pending")
                return {"state": "failed", "exit_code": None, "gpu_used": False,
                        "checkpoint": None, "cleanup": cleanup,
                        "failure_code": "PROVIDER_SANDBOX_NOT_FOUND"}
            staged_result = self._start_gpu_from_stage(stage, plan, handle, cancel_requested)
            if staged_result is None:
                return {"state": "staging", "phase": "source_staging"}
            if isinstance(staged_result, dict):
                return staged_result
            sandbox = staged_result
        if sandbox is None:
            try:
                if self.commit_output is not None:
                    self.commit_output()
                cleanup = ("confirmed" if self.cleanup_source is not None and
                           self.cleanup_source(plan["run_id"]) is True else "pending")
            except Exception:
                cleanup = "pending"
            return {"state": "failed", "exit_code": None, "gpu_used": False,
                    "checkpoint": None, "cleanup": cleanup,
                    "failure_code": "PROVIDER_SANDBOX_NOT_FOUND"}
        code = sandbox.poll()
        if code is None:
            return {"state": "cancel_requested" if cancel_requested else "running"}
        if type(code) is not int:
            raise ValueError("invalid_provider_exit_code")
        result = None
        log_truncated = False
        try:
            output = bytearray()
            for chunk in sandbox.stdout:
                raw = chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk)
                if len(output) + len(raw) > 262144:
                    log_truncated = True
                    break
                output.extend(raw)
            if not log_truncated:
                candidate = json.loads(bytes(output).decode("utf-8"))
                if isinstance(candidate, dict):
                    result = candidate
        except Exception:
            result = None
        try:
            sandbox.terminate(wait=True)
            cleanup = "confirmed"
        except Exception as exc:
            if type(exc).__name__ == "NotFoundError":
                cleanup = "confirmed"
            else:
                cleanup = "pending"
        if cleanup == "confirmed":
            try:
                if self.commit_output is not None:
                    self.commit_output()
                if self.cleanup_source is None or self.cleanup_source(plan["run_id"]) is not True:
                    cleanup = "pending"
            except Exception:
                cleanup = "pending"
        expected = result is not None and (
            result.get("run_id") == plan["run_id"] and
            result.get("source_sha") == plan["commit"] and
            result.get("manifest_sha256") == plan["manifest_sha256"] and
            result.get("lock_sha256") == plan["lock_sha256"] and
            result.get("gpu_profile") == plan["gpu"] and
            result.get("gpu_used") is True and self._valid_metrics(result.get("metrics")) and
            self._valid_artifacts(result.get("artifacts")))
        checkpoint = result.get("checkpoint") if expected else None
        if (not isinstance(checkpoint, dict) or checkpoint.get("filename") != "checkpoint.pt" or
                not isinstance(checkpoint.get("sha256"), str) or
                re.fullmatch(r"[0-9a-f]{64}", checkpoint["sha256"]) is None or
                type(checkpoint.get("size_bytes")) is not int or
                not 1 <= checkpoint["size_bytes"] <= 1024 ** 3):
            expected = False
            checkpoint = None
        state = "succeeded" if code == 0 and expected else "cancelled" if cancel_requested else "failed"
        return {"state": state, "exit_code": code, "gpu_used": expected,
                "gpu": result.get("gpu") if expected else None,
                "checkpoint": checkpoint, "metrics": result.get("metrics") if expected else None,
                "artifacts": result.get("artifacts") if expected else [],
                "cleanup": cleanup,
                "failure_code": (None if state == "succeeded" else
                                 result.get("failure_code") if isinstance(result, dict) else
                                 "CUSTOM_TRAINING_RESULT_INVALID"),
                "output": result.get("output", "") if isinstance(result, dict) else "",
                "output_truncated": log_truncated or bool(result.get("output_truncated")) if isinstance(result, dict) else log_truncated}

    def recover(self, plan):
        """Recover the deterministic stage/GPU name without creating a second run."""
        handle = _handle(f"custom-training-{plan['run_id']}")
        return handle if (self.lookup(handle) is not None or
                          self.lookup(f"custom-training-stage-{plan['run_id']}") is not None) else None

    def cancel(self, handle):
        handle = _handle(handle)
        sandbox = self.lookup(handle)
        if sandbox is not None:
            sandbox.terminate(wait=True)
            return {"state": "cancel_requested"}
        stage = self.lookup(f"custom-training-stage-{handle.removeprefix('custom-training-')}")
        if stage is None:
            return {"state": "uncertain"}
        if not self._finish_stage(stage, handle.removeprefix("custom-training-"), cleanup=True):
            return {"state": "uncertain"}
        return {"state": "cancelled", "cleanup": "confirmed", "gpu_used": False}

    def checkpoint(self, run_id, manifest, offset, max_bytes):
        if (self.checkpoint_root is None or
                not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None or
                not isinstance(manifest, dict) or manifest.get("filename") != "checkpoint.pt" or
                type(manifest.get("size_bytes")) is not int or not 1 <= manifest["size_bytes"] <= 1024 ** 3 or
                not isinstance(manifest.get("sha256"), str) or
                re.fullmatch(r"[a-f0-9]{64}", manifest["sha256"]) is None or
                type(offset) is not int or not 0 <= offset < manifest["size_bytes"] or
                type(max_bytes) is not int or not 1 <= max_bytes <= 24576):
            raise ValueError("invalid_checkpoint_range")
        path = os.path.join(self.checkpoint_root, run_id, "checkpoint", "checkpoint.pt")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != manifest["size_bytes"]:
                raise ValueError("checkpoint_manifest_mismatch")
            stream.seek(offset)
            chunk = stream.read(min(max_bytes, manifest["size_bytes"] - offset))
        return {"offset": offset, "data": base64.b64encode(chunk).decode("ascii"),
                "next_offset": offset + len(chunk), "eof": offset + len(chunk) == manifest["size_bytes"],
                "size_bytes": manifest["size_bytes"], "sha256": manifest["sha256"]}

    def artifact(self, run_id, manifest, offset, max_bytes):
        path_value = manifest.get("path") if isinstance(manifest, dict) else None
        parts = path_value.split("/") if isinstance(path_value, str) else []
        artifact_id = hashlib.sha256(path_value.encode("utf-8")).hexdigest() if path_value else ""
        if (self.checkpoint_root is None or not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None or
                not self._valid_artifacts([manifest]) or manifest.get("artifact_id") != artifact_id or
                any(part in {"", ".", ".."} for part in parts) or
                type(offset) is not int or not 0 <= offset < manifest["size_bytes"] or
                type(max_bytes) is not int or not 1 <= max_bytes <= 24576):
            raise ValueError("invalid_artifact_range")
        root = os.path.join(self.checkpoint_root, run_id, "checkpoint")
        current = root
        for part in parts[:-1]:
            current = os.path.join(current, part)
            if not stat.S_ISDIR(os.lstat(current).st_mode):
                raise ValueError("invalid_artifact_path")
        path = os.path.join(root, *parts)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != manifest["size_bytes"]:
                raise ValueError("artifact_manifest_mismatch")
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != manifest["sha256"]:
                raise ValueError("artifact_checksum_mismatch")
            stream.seek(offset)
            chunk = stream.read(min(max_bytes, manifest["size_bytes"] - offset))
        return {"artifact_id": manifest["artifact_id"], "path": manifest["path"],
                "offset": offset, "data": base64.b64encode(chunk).decode("ascii"),
                "next_offset": offset + len(chunk), "eof": offset + len(chunk) == manifest["size_bytes"],
                "size_bytes": manifest["size_bytes"], "sha256": manifest["sha256"]}
