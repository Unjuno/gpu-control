import assert from "node:assert/strict";
import test from "node:test";
import { CURRENT_MCP_VERSION, LEGACY_MCP_VERSIONS } from "./mcp_protocol.js";
import { mcpToolErrorResponse, mcpToolSuccessResponse, normalizeMcpToolResult } from "./mcp_tool_result.js";

test("tool values normalize to the shared versioned result envelope", () => {
  assert.deepEqual(normalizeMcpToolResult("experiment_status", { run_id: "r1" }), {
    schema_version: 2,
    status: "ok",
    human_summary: "experiment_status completed.",
    machine_state: { run_id: "r1" },
    next_allowed_actions: [],
    blocking_reason: null,
  });
  const blocked = { schema_version: 2, status: "blocked", human_summary: "blocked", machine_state: {}, blocking_reason: "OFF" };
  assert.deepEqual(normalizeMcpToolResult("tool", blocked), { next_allowed_actions: [], ...blocked });
});

test("MCP result projection preserves legacy and current-version response contracts", async () => {
  const value = normalizeMcpToolResult("tool", { status: "ok" });
  const legacy = await mcpToolSuccessResponse(1, "tool", value, LEGACY_MCP_VERSIONS[0]).json();
  assert.equal(legacy.result.structuredContent, undefined);
  assert.deepEqual(JSON.parse(legacy.result.content[0].text), value);

  const intermediate = await mcpToolSuccessResponse(2, "tool", value, LEGACY_MCP_VERSIONS[1]).json();
  assert.deepEqual(intermediate.result.structuredContent, value);
  assert.equal(intermediate.result.resultType, undefined);

  const current = await mcpToolSuccessResponse(3, "tool", value, CURRENT_MCP_VERSION).json();
  assert.deepEqual(current.result.structuredContent, value);
  assert.equal(current.result.resultType, "complete");
  assert.equal(current.result._meta["io.modelcontextprotocol/serverInfo"].name, "gpu-control-sites");
});

test("tool error projection exposes only the sanitized error code", async () => {
  const response = await mcpToolErrorResponse(9, "INTERNAL_ERROR").json();
  assert.deepEqual(response, { jsonrpc: "2.0", id: 9, result: {
    isError: true,
    content: [{ type: "text", text: JSON.stringify({ error: "INTERNAL_ERROR" }) }],
  } });
});
