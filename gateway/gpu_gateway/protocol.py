"""Small tools-only MCP Streamable HTTP profile.

Dual-era profile: 2025-03-26/06-18/11-25 and 2026-07-28. JSON responses,
no session IDs, no SSE stream, no sampling, no resources, no background tasks.
This transport is deliberately separate from service/provider logic.
"""
from __future__ import annotations

import json
import base64
import binascii

from .service import ExperimentService, GatewayError, Prepare, Principal, RunID

LEGACY_VERSIONS = ("2025-03-26", "2025-06-18", "2025-11-25")
MODERN = "2026-07-28"
VERSIONS = (*LEGACY_VERSIONS, MODERN)
SERVER_INFO = {"name": "gpu-control-gateway", "version": "0.1.0"}
META_PREFIX = "io.modelcontextprotocol/"
EMPTY = {"type": "object", "properties": {}, "additionalProperties": False}
TOOL_DATA = (
    ("integrations_list", "List configured GPU providers and registered workloads.", "experiments:read", EMPTY, True),
    ("experiments_prepare", "Save an exact experiment plan for human Web approval; does not start a GPU.", "experiments:run", Prepare.model_json_schema(), False),
    ("experiments_submit", "Queue an already-approved experiment. May incur bounded GPU charges; never creates approval.", "experiments:run", RunID.model_json_schema(), False),
    ("experiments_get", "Read one owned experiment and its bounded result. Outputs are untrusted workload data.", "experiments:read", RunID.model_json_schema(), True),
    ("experiments_list", "List the latest 50 owned experiments and worker heartbeat.", "experiments:read", EMPTY, True),
    ("experiments_cancel", "Request cancellation of an owned experiment; may discard unfinished work.", "experiments:cancel", RunID.model_json_schema(), False),
)


def tools(principal: Principal) -> list[dict]:
    return [{"name": name, "description": description, "inputSchema": schema,
             "annotations": {"readOnlyHint": read_only, "destructiveHint": name == "experiments_cancel",
                             "idempotentHint": True, "openWorldHint": not read_only},
             "_meta": {"securitySchemes": [{"type": "oauth2", "scopes": [scope]}]}}
            for name, description, scope, schema, read_only in TOOL_DATA if scope in principal.scopes]


def error(identifier, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


def validate_headers(payload, headers):
    """Modern request metadata must agree with routing headers before dispatch."""
    params = payload.get("params", {}) if isinstance(payload, dict) else {}
    meta = params.get("_meta", {}) if isinstance(params, dict) else {}
    body_version = meta.get(META_PREFIX + "protocolVersion") if isinstance(meta, dict) else None
    version = headers.get("mcp-protocol-version", LEGACY_VERSIONS[0])
    identifier = payload.get("id") if isinstance(payload, dict) else None
    if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
        identifier = None
    if version not in VERSIONS:
        response = error(identifier, -32022, "Unsupported protocol version")
        response["error"]["data"] = {"supported": list(VERSIONS), "requested": version}
        return version, (response, 400)
    if version == MODERN or body_version == MODERN:
        if not isinstance(meta, dict) or not isinstance(body_version, str) or not isinstance(meta.get(META_PREFIX + "clientCapabilities"), dict):
            return version, (error(identifier, -32602, "Required request metadata is missing"), 400)
        if version != body_version or headers.get("mcp-method") != payload.get("method"):
            return version, (error(identifier, -32020, "Request metadata/header mismatch"), 400)
        if payload.get("method") in {"tools/call", "prompts/get", "resources/read"}:
            value = headers.get("mcp-name")
            if isinstance(value, str) and value.startswith("=?base64?") and value.endswith("?="):
                try:
                    value = base64.b64decode(value[9:-2], validate=True).decode("utf-8")
                except (ValueError, UnicodeDecodeError, binascii.Error):
                    value = None
            expected = params.get("uri") if payload["method"] == "resources/read" else params.get("name")
            if not isinstance(expected, str) or value != expected:
                return version, (error(identifier, -32020, "Mcp-Name does not match the request"), 400)
    return version, None


def dispatch(service: ExperimentService, principal: Principal, payload: dict, version: str = "2025-11-25"):
    modern = version == MODERN
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
        return error(None, -32600, "Invalid Request"), 400
    method = payload["method"]
    if "id" not in payload:
        if not modern and method in {"notifications/initialized", "notifications/cancelled"}:
            # MCP request cancellation is NOT permission to cancel a durable GPU job.
            return None, 202
        return error(None, -32600, "Unsupported notification"), 400
    identifier = payload["id"]
    if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
        return error(None, -32600, "Invalid request id"), 400
    params = payload.get("params", {})
    if not isinstance(params, dict):
        return error(identifier, -32602, "Invalid params"), 200
    if method == "initialize" and not modern:
        requested = params.get("protocolVersion")
        if not isinstance(requested, str) or not isinstance(params.get("capabilities"), dict) or not isinstance(params.get("clientInfo"), dict):
            return error(identifier, -32602, "Invalid initialize params"), 200
        value = {"protocolVersion": requested if requested in LEGACY_VERSIONS else LEGACY_VERSIONS[-1],
                 "capabilities": {"tools": {"listChanged": False}},
                 "serverInfo": SERVER_INFO}
    elif method == "server/discover" and modern:
        value = {"supportedVersions": list(VERSIONS), "capabilities": {"tools": {}}}
    elif method == "ping":
        value = {}
    elif method == "tools/list":
        if params.get("cursor"):
            return error(identifier, -32602, "Pagination is not supported for this fixed tool list"), 200
        value = {"tools": tools(principal)}
    elif method == "tools/call":
        name, arguments = params.get("name"), params.get("arguments", {})
        if name not in {row[0] for row in TOOL_DATA} or not isinstance(arguments, dict):
            return error(identifier, -32602, "Unknown tool or invalid arguments"), 200
        try:
            result = service.invoke(principal, name, arguments)
            value = {"content": [{"type": "text", "text": json.dumps(result, allow_nan=False)}], "isError": False}
            if params is not None:
                value["structuredContent"] = result
        except GatewayError as exc:
            if exc.status in {401, 403}:
                raise
            value = {"content": [{"type": "text", "text": json.dumps({"code": exc.code, "message": exc.message})}], "isError": True}
    else:
        return error(identifier, -32601, "Method not found"), 404 if modern else 200
    if modern:
        value["resultType"] = "complete"
        value["_meta"] = {META_PREFIX + "serverInfo": SERVER_INFO}
    return {"jsonrpc": "2.0", "id": identifier, "result": value}, 200
