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

function rpcRequest(message, headers = {}) {
  return new Request(`${siteOrigin}/mcp`, {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(message),
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

test("ChatGPT and external OAuth clients share the MCP tools and owner run ledger", async () => {
  const token = `gpc_at_${"c".repeat(43)}`;
  const tokenHash = createHash("sha256").update(token).digest("hex");
  const ownerIdsReadFromLedger = [];
  const ownedRun = {
    run_id: "shared-owner-run", state: "succeeded", created_at: 100, updated_at: 110,
    completed_at: 110, cleanup_state: "confirmed", result_json: "{}",
    result_artifact_id: null, lease_id: null, cleanup_receipt_json: null,
    workload: "tiny-stories-inference-v1", repository: "owner/research",
    source_sha: "a".repeat(40), image_digest: "sha256:" + "b".repeat(64), provider: "modal_cpu",
  };
  const env = {
    GPU_CONTROL_ALLOWED_USER_IDS: "shared-owner",
    DB: { prepare(sql) {
      return { bind(...values) {
        const tokenRow = sql.includes("FROM mcp_oauth_tokens") && values[0] === tokenHash
          ? { owner_id: "shared-owner", client_id: "external-client", scope: "experiments:read",
            resource: `${siteOrigin}/mcp`, expires_at: 1_900_000_000 }
          : null;
        if (sql.includes("FROM runs r")) ownerIdsReadFromLedger.push(values[0]);
        return {
          first: async () => tokenRow,
          all: async () => ({ results: sql.includes("FROM runs r") ? [ownedRun] : [] }),
        };
      } };
    } },
  };
  const message = { jsonrpc: "2.0", id: 1, method: "tools/list", params: {} };
  const chatgptResponse = await worker.fetch(rpcRequest(message,
    { "oai-authenticated-user-id": "shared-owner" }), env);
  const externalResponse = await worker.fetch(rpcRequest(message,
    { authorization: `Bearer ${token}` }), env);

  assert.equal(chatgptResponse.status, 200);
  assert.equal(externalResponse.status, 200);
  const chatgptTools = (await chatgptResponse.json()).result.tools;
  const externalTools = (await externalResponse.json()).result.tools;
  assert.deepEqual(externalTools, chatgptTools);
  assert.ok(chatgptTools.some((tool) => tool.name === "experiment_capabilities"));

  const runList = { jsonrpc: "2.0", id: 2, method: "tools/call",
    params: { name: "experiment_list", arguments: {} } };
  const chatgptRunsResponse = await worker.fetch(rpcRequest(runList,
    { "oai-authenticated-user-id": "shared-owner" }), env);
  const externalRunsResponse = await worker.fetch(rpcRequest(runList,
    { authorization: `Bearer ${token}` }), env);
  assert.equal(chatgptRunsResponse.status, 200);
  assert.equal(externalRunsResponse.status, 200);
  const chatgptRuns = await chatgptRunsResponse.json();
  const externalRuns = await externalRunsResponse.json();
  assert.deepEqual(externalRuns.result, chatgptRuns.result);
  const runListValue = JSON.parse(chatgptRuns.result.content[0].text);
  assert.deepEqual(runListValue.machine_state.experiments.map((run) => run.run_id), ["shared-owner-run"]);
  assert.deepEqual(ownerIdsReadFromLedger, ["shared-owner", "shared-owner"]);
});
