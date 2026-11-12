#!/usr/bin/env python3
"""GitHub Actions client. Only the trusted event file is parsed, never shell text.

validate/local-report/publish need only Python's standard library. invoke requests
an audience-bound GitHub OIDC token, then sends a comment ID and body hash to the
fixed gateway. It never accepts arbitrary tools, URLs, commands or provider keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gpu_gateway.ci_bridge import (BridgeError, Policy, public_summary, strict_json,
                                   validate_event)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(url, *, token=None, payload=None, limit=65536):
    headers = {"Accept": "application/json", "User-Agent": "gpu-control-comment-bridge"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            body = response.read(limit + 1)
            if len(body) > limit:
                raise BridgeError("response_too_large", 503)
            return strict_json(body)
    except urllib.error.HTTPError as exc:
        # Do not log URLs, headers, response bodies or exception text containing secrets.
        code = "remote_request_failed"
        try:
            value = strict_json(exc.read(4096))
            candidate = value.get("code") if isinstance(value, dict) else None
            if isinstance(candidate, str) and re.fullmatch(r"[a-z_]{1,64}", candidate):
                code = candidate
        except BridgeError:
            pass
        raise BridgeError(code, exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise BridgeError("network_request_failed", 503) from None


def oidc_token(policy, env):
    raw_url = env.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    bearer = env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    parsed = urllib.parse.urlsplit(raw_url)
    if (parsed.scheme != "https" or not (parsed.hostname or "").endswith(".actions.githubusercontent.com")
            or parsed.username or parsed.fragment or not bearer):
        raise BridgeError("actions_oidc_unavailable", 503)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query) if k != "audience"]
    query.append(("audience", policy.audience))
    url = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))
    result = http_json(url, token=bearer, limit=32768)
    value = result.get("value") if isinstance(result, dict) else None
    if not isinstance(value, str) or not 1 <= len(value) <= 16384:
        raise BridgeError("invalid_oidc_response", 503)
    return value


def event_context(policy, env):
    path = env.get("GITHUB_EVENT_PATH")
    if not path:
        raise BridgeError("github_event_required")
    raw = Path(path).read_bytes()
    if len(raw) > 262144:
        raise BridgeError("event_too_large")
    event = strict_json(raw)
    comment_id, command = validate_event(event, env, policy)
    return event, comment_id, command


def write_report(path, report):
    text = json.dumps(report, allow_nan=False, sort_keys=True, indent=2)
    Path(path).write_text(text + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("## GPU command result\n\n```json\n" + text.replace("`", "\\u0060") + "\n```\n")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["validate", "invoke", "local-report", "publish"])
    p.add_argument("--report", default="bridge-result.json")
    p.add_argument("--metrics")
    p.add_argument("--image-id")
    args = p.parse_args(argv)
    policy = Policy.load()
    event, comment_id, command = event_context(policy, os.environ)
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[1-9][0-9]{0,19}", run_id):
        raise BridgeError("invalid_workflow_run_id")
    base = {"operation": command.operation, "comment_id": comment_id, "workflow_run_id": run_id}
    if args.mode == "validate":
        target = os.environ.get("GITHUB_OUTPUT")
        if not target:
            raise BridgeError("github_output_required")
        with open(target, "a") as f:
            f.write("kind=" + ("local" if command.operation == "local" else "gateway") + "\n")
        return 0
    if args.mode == "invoke":
        if command.operation == "local":
            raise BridgeError("local_command_runs_in_ci")
        try:
            result = http_json(policy.audience, token=oidc_token(policy, os.environ), payload={
                "comment_id": comment_id,
                "body_sha256": hashlib.sha256(event["comment"]["body"].encode()).hexdigest(),
            })
            if not isinstance(result, dict) or result.get("comment_id") != comment_id or result.get("workflow_run_id") != run_id:
                raise BridgeError("invalid_gateway_receipt", 503)
            write_report(args.report, result)
            return 0
        except BridgeError as exc:
            write_report(args.report, dict(base, code=exc.code, http_status=exc.status))
            return 1
    if args.mode == "local-report":
        if command.operation != "local" or not args.metrics:
            raise BridgeError("local_metrics_required")
        data = Path(args.metrics).read_bytes()
        if len(data) > 8192:
            raise BridgeError("local_metrics_too_large")
        metrics = strict_json(data)
        if not isinstance(metrics, dict) or metrics.get("test") != "tiny-bigram-v1" or metrics.get("gpu_used") is not False:
            raise BridgeError("invalid_local_metrics")
        report = public_summary({"result": {"gpu_used": False, "metrics": metrics}}, policy.gateway_origin)
        report.update(base, state="succeeded", experiment="tiny-bigram-v1")
        if args.image_id:
            image = Path(args.image_id).read_text().strip()
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
                raise BridgeError("invalid_container_image_id")
            report["container_image_id"] = image
        write_report(args.report, report)
        return 0
    # Only called in a separate step with the short-lived issues:write token.
    report_path = Path(args.report)
    if report_path.exists():
        raw = report_path.read_bytes()
        if len(raw) > 32768:
            raise BridgeError("report_too_large")
        report = strict_json(raw)
    else:
        report = dict(base, code="command_failed_check_actions_log")
    text = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False)
    text = text.replace("`", "\\u0060").replace("@", "\\u0040").replace("<", "\\u003c")
    if len(text) > 12000:
        text = json.dumps(dict(base, code="report_in_actions_artifact"), indent=2)
    run_url = f"https://github.com/{policy.repository}/actions/runs/{run_id}"
    body = f"### GPU command: `{command.operation}`\n\n[Actions run]({run_url}) · request comment `{comment_id}`\n\n```json\n{text}\n```\n\nNo GPU credentials or raw workload logs are published here."
    if not os.environ.get("GITHUB_TOKEN"):
        raise BridgeError("github_comment_token_required")
    http_json(f"https://api.github.com/repos/{policy.repository}/issues/{policy.issue_number}/comments",
              token=os.environ["GITHUB_TOKEN"], payload={"body": body})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BridgeError as exc:
        print("Bridge error: " + exc.code, file=sys.stderr)
        raise SystemExit(1)
