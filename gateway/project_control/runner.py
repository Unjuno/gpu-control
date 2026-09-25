"""Owner-account Issue -> bounded external-source CPU check -> sanitized receipt.

No shell interpolation, target builds, provider keys, database or OAuth are needed.
Only registry-selected source files are downloaded; source code never runs on host.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parent
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_COMMENT_AGE_SECONDS = 6 * 60 * 60  # tolerate hosted-runner queueing, still bound stale requests


class Rejected(ValueError):
    pass


def require(value, code):
    if not value:
        raise Rejected(code)


def load_json(raw):
    def pairs(items):
        value = {}
        for k, v in items:
            require(k not in value, "duplicate_json_key")
            value[k] = v
        return value
    def invalid(_):
        raise Rejected("nonfinite_json")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise Rejected("invalid_json") from None


def parse_request(body, policy):
    require(isinstance(body, str) and len(body.encode()) <= 4096, "invalid_command_size")
    header, sep, payload = body.partition("\n")
    require(header.rstrip("\r") == "/gpu check" and sep, "use_gpu_check_json")
    request = load_json(payload)
    require(isinstance(request, dict) and set(request) == {"repository", "sha", "workload"}, "invalid_fields")
    require(all(isinstance(v, str) for v in request.values()), "invalid_field_type")
    require(HEX40.fullmatch(request["sha"]), "immutable_sha_required")
    entry = policy["workloads"].get(request["workload"])
    require(entry is not None and request["repository"] == entry["repository"], "unregistered_workload")
    return request


def validate_event(event, env, policy):
    try:
        require(env["GITHUB_EVENT_NAME"] == "issue_comment" and event["action"] == "created", "invalid_event")
        require(env["GITHUB_REPOSITORY"] == policy["repository"], "wrong_repository")
        require(env["GITHUB_REF"] == "refs/heads/main", "main_only")
        require(env["GITHUB_RUN_ATTEMPT"] == "1", "new_comment_required_for_retry")
        require(env["GITHUB_ACTOR_ID"] == str(policy["owner_id"]), "wrong_actor")
        require(HEX40.fullmatch(env["GITHUB_SHA"]), "invalid_control_sha")
        require(re.fullmatch(r"[1-9][0-9]{0,19}", env["GITHUB_RUN_ID"]), "invalid_run_id")
        repo, comment, issue = event["repository"], event["comment"], event["issue"]
        require(repo["id"] == policy["repository_id"] and repo["owner"]["id"] == policy["owner_id"], "wrong_repository_identity")
        require(event["sender"]["id"] == comment["user"]["id"] == policy["owner_id"], "owner_account_required")
        require(comment["user"]["type"] == "User", "owner_account_required")
        require(type(comment["id"]) is int and comment["id"] > 0, "invalid_comment_id")
        require(issue["number"] == policy["issue_number"] and "pull_request" not in issue and issue["state"] == "open", "wrong_control_issue")
        require(comment["created_at"] == comment["updated_at"], "edited_comment_rejected")
        return parse_request(comment["body"], policy)
    except (KeyError, TypeError, AttributeError):
        raise Rejected("malformed_event") from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def api(path, *, token=None, payload=None):
    require(path.startswith("/repos/"), "fixed_github_api_only")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "gpu-control-project-check"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request("https://api.github.com" + path, data=data, headers=headers)
    with build_opener(NoRedirect).open(req, timeout=20) as response:
        raw = response.read(1048577)
    require(len(raw) <= 1048576, "response_too_large")
    return load_json(raw)


def verify_live_comment(event, policy, get=api, now=None):
    old = event["comment"]
    actual = get(f'/repos/{policy["repository"]}/issues/comments/{old["id"]}')
    issue = get(f'/repos/{policy["repository"]}/issues/{policy["issue_number"]}')
    require(issue.get("state") == "open" and "pull_request" not in issue, "issue_closed_or_changed")
    require(actual.get("id") == old["id"] and actual.get("user", {}).get("id") == policy["owner_id"], "comment_identity_changed")
    require(actual.get("issue_url") == f'https://api.github.com/repos/{policy["repository"]}/issues/{policy["issue_number"]}', "wrong_control_issue")
    require(actual.get("body") == old["body"] and actual.get("updated_at") == actual.get("created_at") == old["created_at"], "comment_changed")
    created = datetime.fromisoformat(actual["created_at"].replace("Z", "+00:00"))
    require(created.tzinfo is not None, "invalid_comment_time")
    require(-30 <= (time.time() if now is None else now) - created.timestamp() <= MAX_COMMENT_AGE_SECONDS, "comment_expired")


def fetch_sources(request, policy, dest, get=api):
    entry = policy["workloads"][request["workload"]]
    repo, sha = request["repository"], request["sha"]
    metadata = get(f"/repos/{repo}")
    require(metadata.get("id") == entry["repository_id"] and metadata.get("owner", {}).get("id") == policy["owner_id"], "source_repository_changed")
    require(metadata.get("private") is False, "private_sources_not_published")
    require(get(f"/repos/{repo}/commits/{sha}").get("sha") == sha, "source_commit_mismatch")
    require(entry.get("profile") in {"orbitune-vocab-v1", "python-script-v1"}, "unregistered_profile")
    require(".execution.json" not in entry["files"], "reserved_source_path")
    if entry["profile"] == "python-script-v1":
        require(entry.get("entrypoint") in entry["files"], "entrypoint_must_be_registered")
        require(isinstance(entry.get("args", []), list) and all(isinstance(a, str) and "\0" not in a for a in entry.get("args", [])), "invalid_registered_args")
    blobs = {}
    for name in entry["files"]:
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_./-]+", name) and not name.startswith("/") and ".." not in PurePosixPath(name).parts, "invalid_registered_path")
        info = get(f"/repos/{repo}/contents/{name}?ref={sha}")
        require(info.get("type") == "file" and info.get("encoding") == "base64" and "target" not in info, "regular_file_required")
        raw = base64.b64decode("".join(info["content"].split()), validate=True)
        require(len(raw) <= 131072, "source_file_too_large")
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(blob == info.get("sha"), "source_blob_mismatch")
        target = Path(dest) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        require(not target.exists() and not target.is_symlink(), "source_must_be_fresh")
        target.write_bytes(raw)
        target.chmod(0o644)
        blobs[name] = blob
    (Path(dest) / ".execution.json").write_text(json.dumps(entry, allow_nan=False))
    return blobs


def clean_environment():
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp", "LANG": "C.UTF-8"}


def container_args(image, name):
    require(re.fullmatch(r"sha256:[a-f0-9]{64}", image), "resolved_image_required")
    return ["docker", "create", "--name", name, "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "10001:10001",
            "--pids-limit", "32", "--memory", "256m", "--cpus", "1", "--log-driver", "none",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m", image]


def bounded_process(argv, seconds=30, limit=65536):
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=clean_environment())
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + seconds
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                require(time.monotonic() < deadline, "container_timeout")
                for key, _ in selector.select(0.1):
                    chunk = os.read(key.fileobj.fileno(), 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        outputs[key.data].extend(chunk)
                        require(sum(map(len, outputs.values())) <= limit, "container_output_limit")
        return process.wait(timeout=max(0.1, deadline - time.monotonic())), bytes(outputs["stdout"])
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def execute(source, name, entry):
    env = clean_environment()
    # Materialize only reviewed control files plus validated source into a fresh
    # build context. COPY never executes target code and needs no host mount.
    with tempfile.TemporaryDirectory(prefix="gpu-check-build-") as directory:
        context = Path(directory)
        for fixed in ("Dockerfile", "run.py"):
            shutil.copyfile(ROOT / "container" / fixed, context / fixed)
        source = Path(source)
        require(source.is_dir() and not source.is_symlink(), "invalid_staging_directory")
        entries = list(source.rglob("*"))
        require(len(entries) <= 200, "too_many_source_entries")
        require(all(not path.is_symlink() and (path.is_dir() or path.is_file()) for path in entries), "regular_source_only")
        require(sum(path.stat().st_size for path in entries if path.is_file()) <= 1048576, "source_context_too_large")
        shutil.copytree(source, context / "source")
        built = subprocess.run(["docker", "build", "--pull", "-q", "-t", name, str(context)],
                               env=env, capture_output=True, text=True, timeout=180)
        require(built.returncode == 0, "trusted_image_build_failed")
    image = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", name], env=env, timeout=10, text=True).strip()
    started = time.monotonic()
    try:
        subprocess.run(container_args(image, name), env=env, check=True, capture_output=True, timeout=10)
        code, raw = bounded_process(["docker", "start", "--attach", name])
        require(code == 0, "project_check_failed")
        value = load_json(raw)
        require(isinstance(value, dict) and value.get("check") == entry["check"] and value.get("gpu_used") is False and value.get("status") == "passed", "invalid_check_output")
        require(isinstance(value.get("metrics"), dict), "check_metrics_required")
        metrics = {k: v for k, v in value["metrics"].items() if re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]{0,31}", k)
                   and type(v) in (int, float) and abs(v) < 1e100 and math.isfinite(v)}
        require(len(metrics) <= 32, "too_many_metrics")
        return {"values": metrics, "image_id": image,
                "elapsed_seconds": round(time.monotonic() - started, 3)}
    finally:
        subprocess.run(["docker", "rm", "-f", name], env=env, capture_output=True, timeout=15)



def public_receipt(report, base, policy):
    """Reconstruct a publishable receipt from a strict schema.

    The execute job handles untrusted project code. Its artifact is therefore
    treated as untrusted input by the separate reporter even when the artifact
    came from the expected workflow.
    """
    require(isinstance(report, dict), "invalid_report")
    require(all(report.get(k) == v for k, v in base.items()), "receipt_binding_failed")
    state = report.get("state")
    require(state in {"passed", "failed"}, "invalid_report_state")
    base_keys = set(base)
    if state == "failed":
        require(set(report) == base_keys | {"state", "code"}, "unexpected_report_fields")
        code = report.get("code")
        require(isinstance(code, str) and re.fullmatch(r"[a-z_]{1,64}", code), "invalid_failure_code")
        return dict(base, state="failed", code=code)

    require(set(report) == base_keys | {"state", "source_blobs", "metrics"}, "unexpected_report_fields")
    entry = policy["workloads"].get(base["workload"])
    require(isinstance(entry, dict), "unregistered_workload")
    blobs = report.get("source_blobs")
    require(isinstance(blobs, dict) and set(blobs) == set(entry["files"]), "invalid_source_evidence")
    clean_blobs = {}
    for path, digest in blobs.items():
        require(path in entry["files"] and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{40}", digest),
                "invalid_source_evidence")
        clean_blobs[path] = digest

    metrics = report.get("metrics")
    require(isinstance(metrics, dict) and set(metrics) == {"values", "image_id", "elapsed_seconds"},
            "invalid_metrics")
    image_id = metrics.get("image_id")
    require(isinstance(image_id, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", image_id),
            "invalid_image_evidence")
    elapsed = metrics.get("elapsed_seconds")
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 <= elapsed <= 300,
            "invalid_elapsed_time")
    values = metrics.get("values")
    require(isinstance(values, dict) and len(values) <= 32, "invalid_metrics")
    clean_values = {}
    for key, value in values.items():
        require(isinstance(key, str) and re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]{0,31}", key),
                "invalid_metric_name")
        require(type(value) in (int, float) and math.isfinite(value) and abs(value) < 1e100,
                "invalid_metric_value")
        clean_values[key] = value
    return dict(base, state="passed", source_blobs=clean_blobs,
                metrics={"values": clean_values, "image_id": image_id, "elapsed_seconds": elapsed})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["validate", "execute", "publish"])
    p.add_argument("--report", required=True)
    args = p.parse_args()
    policy = load_json((ROOT / "policy.json").read_bytes())
    raw_event = Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes()
    require(len(raw_event) <= 262144, "event_too_large")
    event = load_json(raw_event)
    request = validate_event(event, os.environ, policy)
    report_path = Path(args.report)
    run_id = os.environ["GITHUB_RUN_ID"]
    base = {"schema_version": 1, "repository": request["repository"], "source_sha": request["sha"],
            "workload": request["workload"], "control_sha": os.environ["GITHUB_SHA"], "workflow_run_id": run_id,
            "comment_id": event["comment"]["id"], "gpu_used": False, "gpu_authorized": False}
    if args.mode == "validate":
        verify_live_comment(event, policy)
        return
    if args.mode == "execute":
        try:
            verify_live_comment(event, policy)
            source = Path(os.environ["RUNNER_TEMP"]) / ("project-source-" + run_id)
            source.mkdir(mode=0o755)
            blobs = fetch_sources(request, policy, source)
            report = dict(base, state="passed", source_blobs=blobs, metrics=execute(source, "project-check-" + run_id, policy["workloads"][request["workload"]]))
        except Exception as exc:
            # No source/provider exceptions, logs, secrets or free-form text in public output.
            report = dict(base, state="failed", code=str(exc) if isinstance(exc, Rejected) else "check_infrastructure_error")
        report_path.write_text(json.dumps(report, sort_keys=True, allow_nan=False) + "\n")
        if report["state"] != "passed":
            raise SystemExit(1)
        return
    # Executed on a DIFFERENT runner from target code, with issues:write only here.
    if report_path.exists():
        raw = report_path.read_bytes()
        require(len(raw) <= 16384, "report_too_large")
        report = public_receipt(load_json(raw), base, policy)
    else:
        report = public_receipt(dict(base, state="failed", code="check_runner_failed_or_cancelled"), base, policy)
    # Public output is reconstructed from the strict receipt schema above. Raw
    # workload output and arbitrary artifact fields are never published.
    text = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2)
    text = text.replace("`", "\\u0060").replace("@", "\\u0040").replace("<", "\\u003c")
    require(len(text) <= 20000, "report_too_large")
    url = f'https://github.com/{policy["repository"]}/actions/runs/{run_id}'
    body = f"### Project CPU check\n\n[Actions run]({url})\n\n```json\n{text}\n```\n\nCPU evidence only; no GPU was requested or authorized."
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "comment_token_required")
    api(f'/repos/{policy["repository"]}/issues/{policy["issue_number"]}/comments', token=token, payload={"body": body})


if __name__ == "__main__":
    try:
        main()
    except Rejected as exc:
        raise SystemExit(str(exc)) from None
