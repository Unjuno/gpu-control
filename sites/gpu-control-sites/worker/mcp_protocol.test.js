import assert from "node:assert/strict";
import test from "node:test";
import { CURRENT_MCP_VERSION, LEGACY_MCP_VERSIONS, parseMcpProtocolRequest } from "./mcp_protocol.js";

const origin = "https://gpu-control.example";
const readPrincipal = { scopes: ["experiments:read"] };
const readJson = async (request) => request.json();
function request(message, headers = {}) {
  return new Request(`${origin}/mcp`, { method: "POST", headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(message) });
}

test("MCP protocol negotiation defaults to the oldest supported client version", async () => {
  const parsed = await parseMcpProtocolRequest(request({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }),
    readPrincipal, readJson);
  assert.equal(parsed.requestedVersion, LEGACY_MCP_VERSIONS[0]);
});

test("MCP rejects unsupported versions and current-version metadata mismatches", async () => {
  const unsupported = await parseMcpProtocolRequest(request({ jsonrpc: "2.0", id: 2, method: "tools/list" }, {
    "mcp-protocol-version": "2099-01-01",
  }), readPrincipal, readJson);
  assert.equal(unsupported.response.status, 400);
  assert.equal((await unsupported.response.json()).error.code, -32022);

  const mismatch = await parseMcpProtocolRequest(request({ jsonrpc: "2.0", id: 3, method: "tools/list",
    params: { _meta: { "io.modelcontextprotocol/protocolVersion": CURRENT_MCP_VERSION,
      "io.modelcontextprotocol/clientCapabilities": {} } } }, { "mcp-protocol-version": CURRENT_MCP_VERSION,
    "mcp-method": "tools/call" }), readPrincipal, readJson);
  assert.equal(mismatch.response.status, 400);
  assert.equal((await mismatch.response.json()).error.code, -32020);
});

test("MCP scopes distinguish read-only calls from prepare and submit", async () => {
  const readCall = await parseMcpProtocolRequest(request({ jsonrpc: "2.0", id: 4, method: "tools/call",
    params: { name: "experiment_list", arguments: {} } }), readPrincipal, readJson);
  assert.equal(readCall.message.method, "tools/call");

  const writeCall = await parseMcpProtocolRequest(request({ jsonrpc: "2.0", id: 5, method: "tools/call",
    params: { name: "experiment_prepare", arguments: {} } }), readPrincipal, readJson);
  assert.equal(writeCall.response.status, 403);
  assert.match(writeCall.response.headers.get("www-authenticate"), /scope="experiments:execute"/);
});
