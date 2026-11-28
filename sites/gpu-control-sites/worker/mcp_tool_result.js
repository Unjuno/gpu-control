import { CURRENT_MCP_VERSION, LEGACY_MCP_VERSIONS, MCP_META_PREFIX } from "./mcp_protocol.js";

/** Normalize domain tool values to the shared public GPU Control result envelope. */
export function normalizeMcpToolResult(name, value) {
  if (value && value.schema_version === 2 && ["blocked", "pending", "ok", "error"].includes(value.status) &&
      typeof value.human_summary === "string" && value.machine_state && typeof value.machine_state === "object") {
    return { next_allowed_actions: [], blocking_reason: null, ...value };
  }
  return {
    schema_version: 2,
    status: value?.status === "blocked" ? "blocked" : "ok",
    human_summary: typeof value?.human_summary === "string" ? value.human_summary : `${name} completed.`,
    machine_state: value && typeof value === "object" ? value : { value },
    next_allowed_actions: [],
    blocking_reason: null,
  };
}

function json(data) {
  return new Response(JSON.stringify(data), { headers: {
    "content-type": "application/json; charset=utf-8", "cache-control": "no-store",
  } });
}

/** Build the MCP success projection without changing the domain result envelope. */
export function mcpToolSuccessResponse(id, name, value, protocolVersion) {
  const toolResult = normalizeMcpToolResult(name, value);
  const result = { content: [{ type: "text", text: JSON.stringify(toolResult) }], isError: false };
  if (protocolVersion !== LEGACY_MCP_VERSIONS[0]) result.structuredContent = toolResult;
  if (protocolVersion === CURRENT_MCP_VERSION) {
    result.resultType = "complete";
    result._meta = { [`${MCP_META_PREFIX}serverInfo`]: { name: "gpu-control-sites", version: "0.1.0" } };
  }
  return json({ jsonrpc: "2.0", id, result });
}

/** Build the stable MCP tool-call error projection from an already sanitized code. */
export function mcpToolErrorResponse(id, code) {
  return json({ jsonrpc: "2.0", id, result: {
    isError: true,
    content: [{ type: "text", text: JSON.stringify({ error: code }) }],
  } });
}
