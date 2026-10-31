"""Worker-only detached Docker backend for the registered CPU smoke workload."""
from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import shutil
import subprocess
import time
from datetime import datetime
from decimal import Decimal

from .artifacts import MAX_ARTIFACT_BYTES
from .backends import ArtifactPayload, Observation
from .contracts import ResultV2, plan_fingerprint
from .container_runtime import container_hardening_args

MAX_OUTPUT = 65536
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _labels(run_id: str, owner: str, fingerprint: str, image_digest: str, source_sha: str) -> dict[str, str]:
    if not HEX32.fullmatch(run_id) or not HEX64.fullmatch(fingerprint):
        raise ValueError("invalid run identity")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest):
        raise ValueError("immutable image digest required")
    if not HEX40.fullmatch(source_sha):
        raise ValueError("immutable source SHA required")
    owner_digest = hashlib.sha256(owner.encode()).hexdigest()
    return {"io.unjuno.gpu-control.run-id": run_id,
            "io.unjuno.gpu-control.owner-sha256": owner_digest,
            "io.unjuno.gpu-control.plan-sha256": fingerprint,
            "io.unjuno.gpu-control.image-digest": image_digest,
            "io.unjuno.gpu-control.source-sha": source_sha}


def validate_image_architecture(image: dict | None, host: dict, *, expected_digest: str | None = None,
                                expected_source_repository: str | None = None,
                                expected_source_sha: str | None = None) -> None:
    if not isinstance(image, dict):
        raise ValueError("image is missing")
    if expected_digest and image.get("Id") != expected_digest:
        raise ValueError("image digest mismatch")
    if expected_source_repository is not None or expected_source_sha is not None:
        labels = (image.get("Config", {}).get("Labels", {})
                  if isinstance(image.get("Config"), dict) else {})
        if (not isinstance(labels, dict) or
                labels.get("org.opencontainers.image.source") != expected_source_repository or
                labels.get("org.opencontainers.image.revision") != expected_source_sha):
            raise ValueError("image source provenance does not match registered plan")
    if image.get("Os") != "linux" or host.get("OSType") != "linux":
        raise ValueError("Linux container image required")
    aliases = {"aarch64": "arm64", "x86_64": "amd64"}
    image_arch = aliases.get(image.get("Architecture"), image.get("Architecture"))
    host_arch = aliases.get(host.get("Architecture"), host.get("Architecture"))
    if image_arch != host_arch:
        raise ValueError("image architecture mismatch")


def container_create_args(plan: dict, *, run_id: str, owner: str, fingerprint: str) -> list[str]:
    image = plan.get("image_digest")
    if not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("immutable image digest required")
    if plan.get("provider") != "local_cpu" or plan.get("device_requirement", {}).get("requires_gpu") is not False:
        raise ValueError("local CPU backend refuses non-CPU plans")
    if type(plan.get("runtime_seconds")) is not int or not 1 <= plan["runtime_seconds"] <= 30:
        raise ValueError("runtime exceeds local CPU profile")
    name = "gpu-control-" + run_id
    args = ["create", "--name", name, *container_hardening_args(),
            "--log-driver", "local", "--log-opt", "max-size=1m",
            "--log-opt", "max-file=2", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m"]
    for key, value in _labels(run_id, owner, fingerprint, image, plan.get("source_sha", "")).items():
        args.extend(("--label", f"{key}={value}"))
    env = {
        "GPU_CONTROL_RUN_ID": run_id,
        "GPU_CONTROL_SOURCE_SHA": plan["source_sha"],
        "GPU_CONTROL_PLAN_FINGERPRINT": fingerprint,
        "GPU_CONTROL_RUNTIME_SECONDS": str(plan["runtime_seconds"]),
        "GPU_CONTROL_PARAMETERS_JSON": json.dumps(plan["parameters"], sort_keys=True,
                                                  separators=(",", ":"), allow_nan=False),
    }
    for key, value in env.items():
        args.extend(("--env", f"{key}={value}"))
    args.extend((image,))
    return args


def parse_smoke_result(raw: bytes, expected: dict, *, exit_code: int) -> dict:
    if not isinstance(raw, bytes) or len(raw) > MAX_OUTPUT:
        raise ValueError("result output limit exceeded")
    if exit_code != 0:
        raise ValueError("smoke workload exited unsuccessfully")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate result key")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    required = {"schema_version", "run_id", "source_sha", "plan_fingerprint", "check",
                "status", "gpu_used", "metrics", "checks", "checksum"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("result schema is invalid")
    if any(value.get(key) != expected.get(key) for key in ("run_id", "source_sha", "plan_fingerprint")):
        raise ValueError("result identity binding failed")
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1 or
            value["check"] != "cpu-smoke-v1" or value["status"] != "passed"):
        raise ValueError("result check is invalid")
    if value["gpu_used"] is not False:
        raise ValueError("CPU smoke result contains a GPU claim")
    if not isinstance(value["metrics"], dict) or set(value["metrics"]) != {"iterations", "checksum_value"}:
        raise ValueError("required metrics are missing")
    if any(type(number) is not int or number < 0 for number in value["metrics"].values()):
        raise ValueError("metrics must be nonnegative integers")
    if (not isinstance(value["checks"], list) or not 1 <= len(value["checks"]) <= 16 or
            any(not isinstance(check, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", check)
                for check in value["checks"])):
        raise ValueError("result checks are missing")
    if not isinstance(value["checksum"], str) or not HEX64.fullmatch(value["checksum"]):
        raise ValueError("result checksum is invalid")
    return {"simulation": False, "gpu_used": False, "checks": value["checks"],
            "checksum": value["checksum"], "metrics": value["metrics"]}


def _bounded_output(argv: list[str], timeout: int = 10, limit: int = MAX_OUTPUT,
                    env: dict[str, str] | None = None) -> tuple[int, bytes, bool]:
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env or {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                                           "HOME": os.environ.get("HOME", "/tmp"), "LANG": "C"})
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    selector.register(process.stderr, selectors.EVENT_READ)
    output = bytearray()
    truncated = False
    deadline = time.monotonic() + timeout
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                raise TimeoutError("docker observation timed out")
            for key, _ in selector.select(0.1):
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                retained = chunk[:max(0, limit - len(output))]
                output.extend(retained)
                if len(retained) < len(chunk):
                    truncated = True
        return process.wait(timeout=max(0.1, deadline - time.monotonic())), bytes(output), truncated
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def _timestamp(value: str | None) -> int | None:
    if not value or value.startswith("0001-"):
        return None
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


class LocalContainerBackend:
    def __init__(self, settings):
        self.settings = settings
        self.docker = shutil.which("docker") or "docker"

    def _run(self, args, timeout=20):
        return subprocess.run([self.docker, *args], check=True, capture_output=True,
                              timeout=timeout, env=self._docker_env())

    @staticmethod
    def _docker_env() -> dict[str, str]:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "HOME": os.environ.get("HOME", "/tmp"), "LANG": "C"}
        for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    def start(self, run: dict) -> dict:
        plan = run["plan"]
        if plan_fingerprint_from_run(run) != run["fingerprint"]:
            raise ValueError("plan integrity failed")
        name = "gpu-control-" + run["id"]
        labels = _labels(run["id"], run["owner"], run["fingerprint"], plan["image_digest"], plan["source_sha"])
        try:
            image_raw = self._run(["image", "inspect", "--format", "{{json .}}", plan["image_digest"]], timeout=10)
            image = json.loads(image_raw.stdout)
        except Exception as error:
            raise ValueError("prebuilt image is missing or unavailable") from error
        try:
            host_raw = self._run(["info", "--format", "{{json .}}"], timeout=10)
            host = json.loads(host_raw.stdout)
        except Exception as error:
            raise ValueError("Docker host information is unavailable") from error
        validate_image_architecture(
            image, host, expected_digest=plan["image_digest"],
            expected_source_repository=plan["repository"],
            expected_source_sha=plan["source_sha"],
        )
        created = self._run(container_create_args(plan, run_id=run["id"], owner=run["owner"],
                                                 fingerprint=run["fingerprint"]), timeout=20)
        container_id = created.stdout.decode().strip()
        if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
            raise RuntimeError("docker returned an invalid container id")
        self._run(["start", container_id], timeout=20)
        return {"container_id": container_id, "container_name": name, "run_id": run["id"],
                "owner_digest": labels["io.unjuno.gpu-control.owner-sha256"],
                "plan_fingerprint": run["fingerprint"], "image_digest": plan["image_digest"],
                "source_sha": plan["source_sha"]}

    def inspect(self, handle: dict) -> Observation:
        return self.capture(handle)

    @staticmethod
    def _labels_match(item: dict, handle: dict) -> bool:
        labels = item.get("Config", {}).get("Labels", {})
        return (labels.get("io.unjuno.gpu-control.run-id") == handle["run_id"] and
                labels.get("io.unjuno.gpu-control.owner-sha256") == handle["owner_digest"] and
                labels.get("io.unjuno.gpu-control.plan-sha256") == handle["plan_fingerprint"] and
                labels.get("io.unjuno.gpu-control.image-digest") == handle["image_digest"] and
                labels.get("io.unjuno.gpu-control.source-sha") == handle["source_sha"])

    def capture(self, handle: dict) -> Observation:
        if not self._valid_handle(handle):
            raise ValueError("container handle binding failed")
        inspected = self._run(["inspect", handle["container_id"]], timeout=10)
        value = json.loads(inspected.stdout)
        item = value[0]
        if not self._labels_match(item, handle):
            raise ValueError("container label binding failed")
        state = item.get("State", {})
        if state.get("Running") is True:
            return Observation("running")
        code = state.get("ExitCode")
        if type(code) is not int:
            raise ValueError("container exit code is unavailable")
        output_limit = min(MAX_OUTPUT, self.settings.max_output_bytes)
        _, raw, truncated = _bounded_output([self.docker, "logs", handle["container_id"]],
                                            timeout=10, limit=output_limit, env=self._docker_env())
        expected = {"run_id": handle["run_id"], "source_sha": handle["source_sha"],
                    "plan_fingerprint": handle["plan_fingerprint"]}
        started, finished = _timestamp(state.get("StartedAt")), _timestamp(state.get("FinishedAt"))
        try:
            if truncated:
                raise ValueError("bounded workload logs were truncated")
            parsed = parse_smoke_result(raw, expected, exit_code=code)
            result_state = "succeeded"
            failure = None
        except (ValueError, TypeError, json.JSONDecodeError):
            parsed = {"simulation": False, "gpu_used": False, "checks": [], "checksum": "",
                      "metrics": {}, "failure_code": "output_truncated" if truncated else "invalid_or_missing_smoke_output"}
            result_state, failure = "failed", parsed["failure_code"]
        artifacts = ()
        if result_state == "succeeded":
            try:
                report = raw.removesuffix(b"\n")
                if len(report) > MAX_ARTIFACT_BYTES:
                    raise ValueError("artifact report exceeds the bounded storage limit")
                artifacts = (ArtifactPayload("cpu-smoke-result.json", report, "application/json"),)
            except (ValueError, OSError):
                result_state, failure = "failed", "artifact_missing_or_invalid"
        result = {"schema_version": 2, "run_id": handle["run_id"],
                  "source_sha": handle["source_sha"], "plan_fingerprint": handle["plan_fingerprint"],
                  "provider": "local_cpu", "image_digest": handle["image_digest"],
                  "simulation": False, "gpu_used": False, "device": "cpu",
                  "exit_code": code, "started_at": started, "finished_at": finished,
                  "runtime_seconds": max(0, finished - started) if started and finished else None,
                  "metrics": parsed["metrics"], "checks": parsed["checks"], "checksum": parsed["checksum"] or None,
                  "artifacts": [], "known_cost_usd": Decimal("0"), "cost_classification": "LOCAL",
                  "cleanup_state": "pending"}
        result = ResultV2.model_validate(result).model_dump(mode="json")
        result.update({"logs": raw.decode("utf-8", "replace"), "logs_truncated": truncated,
                       "failure_code": failure})
        return Observation(result_state, result, artifacts)

    def cleanup(self, handle: dict) -> None:
        """Remove only the identity-validated container; absence is the receipt."""
        if not self._valid_handle(handle):
            raise ValueError("container handle binding failed")
        result = subprocess.run([self.docker, "rm", "--force", handle["container_id"]],
                               capture_output=True, timeout=15, env=self._docker_env())
        if result.returncode != 0:
            # Docker returns nonzero when already absent; verify absence explicitly.
            inspected = subprocess.run([self.docker, "inspect", handle["container_id"]],
                                       capture_output=True, timeout=10, env=self._docker_env())
            if inspected.returncode == 0 or b"no such object" not in inspected.stderr.lower():
                raise RuntimeError("container cleanup is still pending")

    def is_clean(self, handle: dict) -> bool:
        if not self._valid_handle(handle):
            raise ValueError("container handle binding failed")
        inspected = subprocess.run([self.docker, "inspect", handle["container_id"]],
                                   capture_output=True, timeout=10, env=self._docker_env())
        if inspected.returncode == 0:
            try:
                return json.loads(inspected.stdout) == []
            except (ValueError, TypeError):
                return False
        if b"no such object" in inspected.stderr.lower():
            return True
        raise RuntimeError("Docker cannot confirm container absence")

    def cancel(self, handle: dict) -> None:
        if not self._valid_handle(handle):
            raise ValueError("container handle binding failed")
        self._run(["stop", "--time", "5", handle["container_id"]], timeout=10)

    def reconcile(self, run: dict) -> dict | None:
        plan = run["plan"]
        labels = _labels(run["id"], run["owner"], run["fingerprint"], plan["image_digest"], plan["source_sha"])
        label_filter = "label=io.unjuno.gpu-control.run-id=" + run["id"]
        found = self._run(["ps", "-aq", "--filter", label_filter], timeout=10).stdout.decode().splitlines()
        found = [item.strip() for item in found if item.strip()]
        if not found:
            return None
        if len(found) != 1:
            raise ValueError("multiple containers match one run")
        handle = {"container_id": found[0], "container_name": "gpu-control-" + run["id"],
                  "run_id": run["id"], "owner_digest": labels["io.unjuno.gpu-control.owner-sha256"],
                  "plan_fingerprint": run["fingerprint"], "image_digest": plan["image_digest"],
                  "source_sha": plan["source_sha"]}
        if not self._valid_handle(handle):
            raise ValueError("recovered container handle is invalid")
        inspected = self._run(["inspect", handle["container_id"]], timeout=10)
        items = json.loads(inspected.stdout)
        if len(items) == 1 and self._labels_match(items[0], handle):
            return handle
        if len(items) != 1:
            raise ValueError("recovered container is unavailable")
        raise ValueError("recovered container identity mismatch")

    @staticmethod
    def _valid_handle(handle: dict) -> bool:
        return (isinstance(handle, dict) and HEX32.fullmatch(handle.get("run_id", "")) is not None and
                re.fullmatch(r"[0-9a-f]{12,64}", handle.get("container_id", "")) is not None and
                handle.get("container_name") == "gpu-control-" + handle.get("run_id", "") and
                HEX64.fullmatch(handle.get("owner_digest", "")) is not None and
                HEX40.fullmatch(handle.get("source_sha", "")) is not None and
                HEX64.fullmatch(handle.get("plan_fingerprint", "")) is not None and
                re.fullmatch(r"sha256:[0-9a-f]{64}", handle.get("image_digest", "")) is not None)


def plan_fingerprint_from_run(run: dict) -> str:
    from .contracts import PlanV2
    return plan_fingerprint(PlanV2.model_validate_json(json.dumps(run["plan"], allow_nan=False)))
