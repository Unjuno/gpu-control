"""GitHub Actions ingress, separate from browser sessions and Remote MCP OAuth."""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .ci_bridge import (BridgeError, GitHubOIDC, Policy, positive_int, strict_json,
                        validate_remote_comment, owner_principal, public_summary)


class GitHubComments:
    """Public-repository API reads only. No redirects, caller URLs or secrets."""
    def __init__(self, policy: Policy):
        self.policy = policy

    def _get(self, suffix: str):
        url = f"https://api.github.com/repos/{self.policy.repository}/{suffix}"
        try:
            with httpx.Client(timeout=8, follow_redirects=False) as client:
                with client.stream("GET", url, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": "gpu-control-comment-bridge"}) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 65536:
                            raise BridgeError("github_response_too_large", 503)
            return strict_json(bytes(data))
        except (httpx.HTTPError, ValueError):
            raise BridgeError("github_comment_verification_unavailable", 503) from None

    def read(self, comment_id: int):
        if not positive_int(comment_id):
            raise BridgeError("invalid_comment_id")
        comment = self._get(f"issues/comments/{comment_id}")
        issue = self._get(f"issues/{self.policy.issue_number}")
        return comment, issue


def install_ci_routes(app, *, policy=None, verifier=None, comments=None):
    """Install once after create_app(). Dependencies are injectable for offline tests.

    No new database schema, provider credentials or browser-authorized principal.
    The existing service remains authoritative for approval, price and provider limits.
    """
    policy = policy or Policy.load()
    auth = app.state.auth
    service = app.state.service
    deployed_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")
    verifier = verifier or GitHubOIDC(policy, deployed_sha)
    comments = comments or GitHubComments(policy)

    def handle(token: str, envelope: dict):
        if not policy.enabled or auth is None or service is None:
            raise BridgeError("bridge_not_configured", 503)
        if auth.external or auth.settings.public_url != policy.gateway_origin:
            raise BridgeError("bridge_owner_mapping_not_configured", 503)
        claims = verifier.verify(token)
        # A CI token proves only workflow identity, not human approval of a GPU run.
        if not auth.configured():
            raise BridgeError("owner_setup_required", 503)
        if not isinstance(envelope, dict) or set(envelope) != {"comment_id", "body_sha256"} or not positive_int(envelope.get("comment_id")):
            raise BridgeError("invalid_comment_envelope")
        comment, issue = comments.read(envelope["comment_id"])
        command = validate_remote_comment(comment, issue, envelope, policy)
        if command.operation == "local":
            raise BridgeError("local_command_runs_in_ci")
        principal = owner_principal(policy.gateway_origin)
        result = service.invoke(principal, command.tool, command.arguments)
        report = public_summary(result, policy.gateway_origin)
        report.update(operation=command.operation, workflow_run_id=claims["run_id"],
                      comment_id=envelope["comment_id"], control_sha=claims["workflow_sha"])
        if command.operation == "submit":
            heartbeat = service.list(principal).get("worker_last_seen_at", 0)
            report["worker_last_seen_at"] = heartbeat
            report["worker_recently_seen"] = type(heartbeat) is int and 0 <= time.time() - heartbeat <= 120
            # queued is not success; an external worker must actually process it.
            report["gpu_execution_confirmed"] = False
        return report

    @app.post("/api/ci/comment")
    async def ci_comment(request: Request):
        try:
            # Browser cookies are never a credential for this endpoint.
            if request.headers.get("origin") is not None:
                raise BridgeError("browser_not_allowed", 403)
            header = request.headers.get("authorization", "")
            if not header.startswith("Bearer "):
                raise BridgeError("actions_identity_required", 401)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                raise BridgeError("json_required", 415)
            data = bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data) > 2048:
                    raise BridgeError("request_too_large", 413)
            result = await run_in_threadpool(handle, header[7:], strict_json(bytes(data)))
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except BridgeError as exc:
            return JSONResponse({"code": exc.code}, status_code=exc.status,
                                headers={"Cache-Control": "no-store"})
