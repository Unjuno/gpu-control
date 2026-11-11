#!/usr/bin/env python3
"""Poll the private Sites Worker and run only its registered inference image."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

RUNNER_ID = "local-cpu-1"
WORKLOAD = "tiny-stories-inference-v1"
MODEL_ID = "karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin"
MODEL_SHA256 = "cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a"
TEMPERATURE = 0.8
CHECKS = ["source_identity_present", "parameter_bounds", "model_digest_verified", "inference_completed",
          "non_root", "no_secret_environment", "no_docker_socket", "read_only_rootfs", "network_disabled"]
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
CONTAINER_ID = re.compile(r"^[0-9a-f]{12,64}$")


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Never forward runner credentials to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RunnerError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def config() -> dict[str, str]:
    values = {
        "origin": os.environ.get("GPU_CONTROL_SITE_URL", "").rstrip("/"),
        "runner_token": os.environ.get("GPU_CONTROL_RUNNER_BEARER_TOKEN", ""),
        "sites_token": os.environ.get("GPU_CONTROL_SITES_SERVICE_TOKEN", ""),
        "repository": os.environ.get("CPU_WORKLOAD_REPOSITORY", ""),
        "source_sha": os.environ.get("CPU_WORKLOAD_SOURCE_SHA", ""),
        "image_digest": os.environ.get("CPU_WORKLOAD_IMAGE_DIGEST", ""),
    }
    try:
        parsed_origin = urlsplit(values["origin"])
        valid_origin = (parsed_origin.scheme == "https" and bool(parsed_origin.hostname) and
                        parsed_origin.username is None and parsed_origin.password is None and
                        parsed_origin.path in ("", "/") and not parsed_origin.query and
                        not parsed_origin.fragment and parsed_origin.port in (None, 443))
    except ValueError:
        valid_origin = False
    if (not valid_origin or len(values["runner_token"]) < 32 or
            not re.fullmatch(r"[A-Za-z0-9._~+/=-]{32,512}", values["sites_token"]) or
            not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", values["repository"]) or
            not SHA40.fullmatch(values["source_sha"]) or
            not re.fullmatch(r"sha256:[0-9a-f]{64}", values["image_digest"])):
        raise RunnerError("CONFIGURATION_INVALID")
    values["origin"] = urlunsplit(("https", parsed_origin.netloc, "", "", ""))
    if not shutil.which("docker"):
        raise RunnerError("DOCKER_NOT_FOUND")
    return values


def safe_log(code: str) -> None:
    print(f"gpu-control-runner: {code}", file=sys.stderr, flush=True)


def post(cfg: dict[str, str], endpoint: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload or {}, separators=(",", ":"), allow_nan=False).encode()
    request = urllib.request.Request(
        cfg["origin"] + endpoint, data=body, method="POST",
        headers={"content-type": "application/json", "cache-control": "no-store",
                 "authorization": "Bearer " + cfg["runner_token"],
                 "OAI-Sites-Authorization": "Bearer " + cfg["sites_token"]},
    )
    try:
        opener = urllib.request.build_opener(RejectRedirects)
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise RunnerError("SITE_REQUEST_FAILED")
            raw = response.read(16385)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RunnerError("SITE_REQUEST_FAILED") from exc
    if len(raw) > 16384:
        raise RunnerError("SITE_RESPONSE_TOO_LARGE")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError("SITE_RESPONSE_INVALID") from exc
    if not isinstance(value, dict):
        raise RunnerError("SITE_RESPONSE_INVALID")
    return value


def docker(args: list[str], timeout: int = 15, *, allow_error: bool = False) -> bytes:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": os.environ.get("HOME", "/tmp"), "LANG": "C"}
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    result = subprocess.run(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout, env=env, check=False)
    if result.returncode and not allow_error:
        raise RunnerError("DOCKER_COMMAND_FAILED")
    return result.stdout if result.returncode == 0 else result.stderr


def inspect_image(cfg: dict[str, str]) -> None:
    try:
        image = json.loads(docker(["image", "inspect", "--format", "{{json .}}", cfg["image_digest"]], 10))
        host = json.loads(docker(["info", "--format", "{{json .}}"], 10))
    except (ValueError, TypeError) as exc:
        raise RunnerError("IMAGE_INSPECTION_FAILED") from exc
    labels = image.get("Config", {}).get("Labels", {})
    aliases = {"aarch64": "arm64", "x86_64": "amd64"}
    image_arch = aliases.get(image.get("Architecture"), image.get("Architecture"))
    host_arch = aliases.get(host.get("Architecture"), host.get("Architecture"))
    if (image.get("Id") != cfg["image_digest"] or image.get("Os") != "linux" or
            host.get("OSType") != "linux" or image_arch != host_arch or
            labels.get("org.opencontainers.image.source") != cfg["repository"] or
            labels.get("org.opencontainers.image.revision") != cfg["source_sha"]):
        raise RunnerError("IMAGE_PROVENANCE_MISMATCH")


def labels_match(item: dict, run: dict, cfg: dict[str, str]) -> bool:
    labels = item.get("Config", {}).get("Labels", {})
    return (labels.get("io.unjuno.gpu-control.run-id") == run["run_id"] and
            labels.get("io.unjuno.gpu-control.plan-sha256") == run["plan_fingerprint"] and
            labels.get("io.unjuno.gpu-control.source-sha") == run["source_sha"] and
            labels.get("io.unjuno.gpu-control.image-digest") == run["image_digest"] == cfg["image_digest"])


def container_ids(run_id: str) -> list[str]:
    raw = docker(["ps", "-aq", "--filter", "label=io.unjuno.gpu-control.run-id=" + run_id])
    ids = [row for row in raw.decode("ascii", "strict").splitlines() if row]
    if any(not CONTAINER_ID.fullmatch(item) for item in ids):
        raise RunnerError("CONTAINER_ID_INVALID")
    return ids


def recover(cfg: dict[str, str]) -> None:
    value = post(cfg, "/runner/recoveries")
    rows = value.get("recoveries")
    if not isinstance(rows, list) or len(rows) > 10:
        raise RunnerError("RECOVERY_LIST_INVALID")
    for row in rows:
        if (not isinstance(row, dict) or not re.fullmatch(r"[0-9a-f]{32}", row.get("run_id", "")) or
                not re.fullmatch(r"[0-9a-f]{32}", row.get("lease_id", "")) or
                not SHA64.fullmatch(row.get("plan_fingerprint", "")) or
                not SHA40.fullmatch(row.get("source_sha", "")) or
                row.get("image_digest") != cfg["image_digest"]):
            raise RunnerError("RECOVERY_IDENTITY_INVALID")
        ids = container_ids(row["run_id"])
        for container_id in ids:
            try:
                item = json.loads(docker(["inspect", "--format", "{{json .}}", container_id], 10))
            except (ValueError, TypeError) as exc:
                raise RunnerError("RECOVERY_INSPECTION_FAILED") from exc
            if not labels_match(item, row, cfg):
                raise RunnerError("RECOVERY_LABEL_MISMATCH")
            docker(["rm", "--force", container_id], 15)
        if container_ids(row["run_id"]):
            raise RunnerError("RECOVERY_CLEANUP_UNCONFIRMED")
        receipt = {"absent": True, "image_digest": row["image_digest"], "lease_id": row["lease_id"],
                   "plan_fingerprint": row["plan_fingerprint"], "run_id": row["run_id"],
                   "source_sha": row["source_sha"]}
        post(cfg, "/runner/recover", receipt)


def start_args(run: dict, cfg: dict[str, str]) -> tuple[list[str], str]:
    if (run.get("workload") != WORKLOAD or run.get("repository") != cfg["repository"] or
            run.get("source_sha") != cfg["source_sha"] or run.get("image_digest") != cfg["image_digest"] or
            not SHA64.fullmatch(run.get("fingerprint", "")) or
            not re.fullmatch(r"[0-9a-f]{32}", run.get("id", "")) or
            not re.fullmatch(r"[0-9a-f]{32}", run.get("lease_id", ""))):
        raise RunnerError("CLAIM_IDENTITY_MISMATCH")
    parameters = run.get("parameters")
    if not isinstance(parameters, dict) or set(parameters) != {"max_new_tokens", "prompt", "seed"}:
        raise RunnerError("CLAIM_PARAMETERS_INVALID")
    try:
        prompt_bytes = parameters["prompt"].encode("utf-8", "strict") if isinstance(parameters["prompt"], str) else b""
    except UnicodeEncodeError as exc:
        raise RunnerError("CLAIM_PARAMETERS_INVALID") from exc
    if (not prompt_bytes or len(prompt_bytes) > 128 or
            any(ord(char) < 0x20 or ord(char) == 0x7f for char in parameters["prompt"]) or
            type(parameters["max_new_tokens"]) is not int or not 1 <= parameters["max_new_tokens"] <= 32 or
            type(parameters["seed"]) is not int or not 1 <= parameters["seed"] <= 1000000 or
            type(run.get("runtime_seconds")) is not int or not 1 <= run["runtime_seconds"] <= 30):
        raise RunnerError("CLAIM_PARAMETERS_INVALID")
    run_id = run["id"]
    name = "gpu-control-" + run_id
    labels = {"io.unjuno.gpu-control.run-id": run_id,
              "io.unjuno.gpu-control.plan-sha256": run["fingerprint"],
              "io.unjuno.gpu-control.image-digest": run["image_digest"],
              "io.unjuno.gpu-control.source-sha": run["source_sha"]}
    args = ["create", "--name", name, "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", "10001:10001", "--pids-limit", "32",
            "--memory", "256m", "--cpus", "1", "--log-driver", "local", "--log-opt", "max-size=1m",
            "--log-opt", "max-file=2", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m"]
    for key, value in labels.items():
        args.extend(["--label", key + "=" + value])
    env = {"GPU_CONTROL_RUN_ID": run_id, "GPU_CONTROL_SOURCE_SHA": run["source_sha"],
           "GPU_CONTROL_PLAN_FINGERPRINT": run["fingerprint"],
           "GPU_CONTROL_RUNTIME_SECONDS": str(run["runtime_seconds"]),
           "GPU_CONTROL_PARAMETERS_JSON": json.dumps(parameters, sort_keys=True, separators=(",", ":"))}
    for key, value in env.items():
        args.extend(["--env", key + "=" + value])
    args.append(run["image_digest"])
    return args, name


def wait_result(run: dict, cfg: dict[str, str], container_id: str) -> tuple[str, dict | None]:
    deadline = time.monotonic() + run["runtime_seconds"] + 10
    while time.monotonic() < deadline:
        try:
            info = json.loads(docker(["inspect", "--format", "{{json .State}}", container_id], 5))
        except (ValueError, TypeError) as exc:
            raise RunnerError("CONTAINER_INSPECTION_FAILED") from exc
        if info.get("Running") is not True:
            code = info.get("ExitCode")
            break
        time.sleep(0.5)
    else:
        raise RunnerError("EXECUTION_TIMEOUT")
    logs = docker(["logs", container_id], timeout=10, allow_error=(code != 0))
    if len(logs) > 8192 or code != 0:
        return "failed", {"failure_code": "container_exit_nonzero" if code != 0 else "workload_output_invalid"}
    try:
        result = json.loads(logs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "failed", {"failure_code": "workload_output_invalid"}
    required = {"schema_version", "run_id", "source_sha", "plan_fingerprint", "check", "status",
                "gpu_used", "metrics", "checks", "checksum"}
    if (not isinstance(result, dict) or set(result) != required or result.get("schema_version") != 1 or
            result.get("run_id") != run["id"] or result.get("source_sha") != run["source_sha"] or
            result.get("plan_fingerprint") != run["fingerprint"] or result.get("check") != WORKLOAD or
            result.get("status") != "passed" or result.get("gpu_used") is not False or
            result.get("checks") != CHECKS):
        return "failed", {"failure_code": "workload_output_invalid"}
    metrics = result.get("metrics")
    if (not isinstance(metrics, dict) or set(metrics) != {
            "elapsed_ms", "generated_text", "generated_tokens", "max_new_tokens", "model_id", "model_sha256", "prompt_sha256", "seed", "temperature"} or
            type(metrics.get("elapsed_ms")) is not int or not 1 <= metrics["elapsed_ms"] <= run["runtime_seconds"] * 1000 or
            not isinstance(metrics.get("generated_text"), str) or
            metrics.get("temperature") != TEMPERATURE or
            not metrics["generated_text"].startswith(run["parameters"]["prompt"]) or
            metrics["generated_text"] == run["parameters"]["prompt"] or
            type(metrics.get("generated_tokens")) is not int or
            not 1 <= metrics["generated_tokens"] <= run["parameters"]["max_new_tokens"] or
            type(metrics.get("max_new_tokens")) is not int or
            metrics["max_new_tokens"] != run["parameters"]["max_new_tokens"] or
            type(metrics.get("seed")) is not int or metrics["seed"] != run["parameters"]["seed"] or
            type(metrics.get("temperature")) is not float or
            metrics["temperature"] != TEMPERATURE or metrics["model_id"] != MODEL_ID or
            metrics["model_sha256"] != MODEL_SHA256 or
            metrics["prompt_sha256"] != hashlib.sha256(run["parameters"]["prompt"].encode("utf-8")).hexdigest()):
        return "failed", {"failure_code": "workload_output_invalid"}
    try:
        if len(metrics["generated_text"].encode("utf-8", "strict")) > 1536:
            return "failed", {"failure_code": "workload_output_invalid"}
    except UnicodeEncodeError:
        return "failed", {"failure_code": "workload_output_invalid"}
    identity = {"run_id": run["id"], "source_sha": run["source_sha"],
                "plan_fingerprint": run["fingerprint"], "metrics": metrics}
    checksum = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    if result.get("checksum") != checksum:
        return "failed", {"failure_code": "workload_output_invalid"}
    return "passed", result


def execute(cfg: dict[str, str], run: dict) -> None:
    inspect_image(cfg)
    args, name = start_args(run, cfg)
    container_id = docker(args, 20).decode("ascii", "strict").strip()
    if not CONTAINER_ID.fullmatch(container_id):
        raise RunnerError("CONTAINER_ID_INVALID")
    docker(["start", container_id], 15)
    try:
        status, result = wait_result(run, cfg, container_id)
    except RunnerError as exc:
        if exc.code != "EXECUTION_TIMEOUT":
            raise
        status, result = "failed", {"failure_code": "execution_timeout"}
        docker(["stop", "--time", "2", container_id], 8, allow_error=True)
    docker(["rm", "--force", container_id], 15)
    if container_ids(run["id"]):
        raise RunnerError("CLEANUP_UNCONFIRMED")
    receipt = {"absent": True, "container_id": container_id, "container_name": name,
               "image_digest": run["image_digest"], "lease_id": run["lease_id"],
               "observed_at": int(time.time()), "plan_fingerprint": run["fingerprint"],
               "run_id": run["id"], "source_sha": run["source_sha"]}
    post(cfg, "/runner/result", {"cleanup_confirmation": receipt, "lease_id": run["lease_id"],
                                  "result": result, "run_id": run["id"], "status": status})


def run_once(cfg: dict[str, str]) -> None:
    post(cfg, "/runner/heartbeat", {"runner_id": RUNNER_ID, "image_digest": cfg["image_digest"],
                                     "source_sha": cfg["source_sha"]})
    recover(cfg)
    response = post(cfg, "/runner/claim")
    run = response.get("run")
    if run is not None:
        if not isinstance(run, dict):
            raise RunnerError("CLAIM_RESPONSE_INVALID")
        execute(cfg, run)


def main() -> int:
    try:
        cfg = config()
    except RunnerError as exc:
        safe_log(exc.code)
        return 2
    interval = max(2, min(30, int(os.environ.get("GPU_CONTROL_RUNNER_POLL_SECONDS", "5"))))
    while True:
        try:
            run_once(cfg)
        except RunnerError as exc:
            safe_log(exc.code)
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
            safe_log("RUNNER_OPERATION_FAILED")
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
