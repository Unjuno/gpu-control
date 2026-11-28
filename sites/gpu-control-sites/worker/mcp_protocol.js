import { isMcpToolReadOnly } from "./mcp_tool_contract.js";
import { mcpAuthorizationChallenge } from "./mcp_request_auth.js";
import { EXECUTE_SCOPE, READ_SCOPE } from "./mcp_oauth.js";

export const LEGACY_MCP_VERSIONS = Object.freeze(["2025-03-26", "2025-06-18", "2025-11-25"]);
export const CURRENT_MCP_VERSION = "2026-07-28";
export const SUPPORTED_MCP_VERSIONS = Object.freeze([...LEGACY_MCP_VERSIONS, CURRENT_MCP_VERSION]);
export const MCP_META_PREFIX = "io.modelcontextprotocol/";

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: {
    "content-type": "application/json; charset=utf-8", "cache-control": "no-store",
  } });
}

export function mcpRpcError(id, code, message) {
  return json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}

/** Parse and authorize the MCP protocol envelope before tool dispatch. */
export async function parseMcpProtocolRequest(request, principal, readJson) {
  let message;
  try { message = await readJson(request); } catch (error) {
    return { response: mcpRpcError(null, -32700,
      error.message === "BODY_TOO_LARGE" ? "Request too large" : "Invalid JSON") };
  }
  const id = message?.id;
  if (message?.jsonrpc !== "2.0" || !message.method) {
    return { response: mcpRpcError(id, -32600, "Invalid Request") };
  }
  const requestedVersion = request.headers.get("mcp-protocol-version") || LEGACY_MCP_VERSIONS[0];
  if (!SUPPORTED_MCP_VERSIONS.includes(requestedVersion)) {
    return { response: json({ jsonrpc: "2.0", id, error: { code: -32022,
      message: "Unsupported protocol version", data: { supported: SUPPORTED_MCP_VERSIONS, requested: requestedVersion } } }, 400) };
  }
  const params = message.params && typeof message.params === "object" ? message.params : {};
  const requiredScope = message.method === "tools/call" && isMcpToolReadOnly(params.name)
    ? READ_SCOPE : message.method === "tools/call" ? EXECUTE_SCOPE : READ_SCOPE;
  if (!principal?.scopes?.includes(requiredScope)) {
    return { response: mcpAuthorizationChallenge(request, { error: "insufficient_scope", scope: requiredScope }) };
  }
  const meta = params._meta && typeof params._meta === "object" ? params._meta : {};
  if (requestedVersion === CURRENT_MCP_VERSION || meta[`${MCP_META_PREFIX}protocolVersion`] === CURRENT_MCP_VERSION) {
    if (meta[`${MCP_META_PREFIX}protocolVersion`] !== requestedVersion ||
        request.headers.get("mcp-method") !== message.method ||
        !meta[`${MCP_META_PREFIX}clientCapabilities`] || typeof meta[`${MCP_META_PREFIX}clientCapabilities`] !== "object") {
      return { response: json({ jsonrpc: "2.0", id, error: { code: -32020, message: "Request metadata/header mismatch" } }, 400) };
    }
    if (["tools/call", "prompts/get", "resources/read"].includes(message.method)) {
      const supplied = request.headers.get("mcp-name");
      const expected = message.method === "resources/read" ? params.uri : params.name;
      if (typeof expected !== "string" || supplied !== expected) {
        return { response: json({ jsonrpc: "2.0", id, error: { code: -32020,
          message: "Mcp-Name does not match the request" } }, 400) };
      }
    }
  }
  return { message, id, requestedVersion, params };
}
