import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import worker from "./index.js";

const siteOrigin = "https://gpu-control-sites.unjuno.chatgpt.site";

function request(name, authorization = null) {
  return new Request(`${siteOrigin}/mcp`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(authorization ? { authorization } : {}),
    },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 1, method: "tools/call",
      params: { name, arguments: {} },
    }),
  });
}

test("public MCP data tools challenge anonymous callers before touching D1", async () => {
  let databaseReads = 0;
  const env = { DB: { prepare() {
    databaseReads++;
    throw new Error("anonymous request reached D1");
  } } };
  const response = await worker.fetch(request("experiment_list"), env);

  assert.equal(response.status, 401);
  assert.match(response.headers.get("www-authenticate"), /resource_metadata=/);
  assert.match(response.headers.get("www-authenticate"), /scope="experiments:read"/);
  assert.equal(databaseReads, 0);
});

test("MCP bearer authentication binds audience and separates read and execute scopes", async () => {
  const token = `gpc_at_${"a".repeat(43)}`;
  const tokenHash = createHash("sha256").update(token).digest("hex");
  let grantedScope = "experiments:read";
  const env = { DB: { prepare(sql) {
    return { bind(...values) {
      const tokenRow = sql.includes("FROM mcp_oauth_tokens") && values[0] === tokenHash
        ? { owner_id: "external-owner", client_id: "client", scope: grantedScope,
          resource: `${siteOrigin}/mcp`, expires_at: 1_900_000_000 }
        : null;
      return {
        first: async () => tokenRow,
        all: async () => ({ results: [] }),
      };
    } };
  } } };
  const send = (authToken, name) => worker.fetch(request(name, `Bearer ${authToken}`), env);

  const readOnly = await send(token, "experiment_list");
  assert.equal(readOnly.status, 200);
  const deniedWrite = await send(token, "experiment_prepare");
  assert.equal(deniedWrite.status, 403);
  assert.match(deniedWrite.headers.get("www-authenticate"), /scope="experiments:execute"/);

  grantedScope = "experiments:read experiments:execute";
  const allowedWrite = await send(token, "experiment_prepare");
  assert.equal(allowedWrite.status, 200);
  assert.equal((await allowedWrite.json()).result.isError, true);

  const wrongToken = await send(`gpc_at_${"b".repeat(43)}`, "experiment_list");
  assert.equal(wrongToken.status, 401);
  assert.match(wrongToken.headers.get("www-authenticate"), /error="invalid_token"/);
});
