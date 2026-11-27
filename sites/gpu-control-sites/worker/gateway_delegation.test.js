import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import { canonical, delegateGatewayTool, gatewayDelegationConfigured } from "./gateway_delegation.js";

const key = Buffer.from("sites-delegation-test-key-material-32-bytes");
const env = {
  PROVIDER_ADAPTER_URL: "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run",
  PROVIDER_ADAPTER_KEY_ID: "sites-v1",
  PROVIDER_ADAPTER_HMAC_KEY_B64: key.toString("base64"),
  PROVIDER_ADAPTER_PROXY_TOKEN_ID: "wk-adaptertest123",
  PROVIDER_ADAPTER_PROXY_TOKEN_SECRET: "ws-adaptertestsecret123",
};

test("delegation signs the exact owner, tool, arguments and bounded validity window", async () => {
  let observed;
  const result = await delegateGatewayTool(env, "owner-123", "experiment_capabilities", {}, async (url, init) => {
    observed = { url, init, payload: JSON.parse(init.body) };
    return new Response(JSON.stringify({ schema_version: 2, status: "ok", human_summary: "ready",
      machine_state: {}, next_allowed_actions: [], blocking_reason: null }), {
      status: 200, headers: { "content-type": "application/json" },
    });
  }, 1000);
  assert.equal(result.status, "ok");
  assert.equal(observed.url, "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run/internal/sites/v1/tools/experiment_capabilities");
  assert.equal(observed.init.redirect, "manual");
  assert.equal(observed.init.headers.authorization, "Bearer wk-adaptertest123.ws-adaptertestsecret123");
  assert.equal(observed.payload.owner, "owner-123");
  assert.equal(observed.payload.issued_at, 1000);
  assert.equal(observed.payload.expires_at, 1060);
  assert.match(observed.payload.nonce, /^[0-9a-f]{32}$/);
  const expected = createHmac("sha256", key).update(canonical(observed.payload)).digest("hex");
  assert.equal(observed.init.headers["x-gpu-control-sites-signature"], expected);
});

test("training artifact retrieval is an allowed delegated lifecycle tool", async () => {
  const result = await delegateGatewayTool(env, "owner-123", "training_artifact",
    { run_id: "a".repeat(32) }, async () => new Response(JSON.stringify({
      schema_version: 2, status: "ok", human_summary: "artifact ready",
      machine_state: {}, next_allowed_actions: [], blocking_reason: null,
    }), { status: 200, headers: { "content-type": "application/json" } }), 1000);
  assert.equal(result.status, "ok");
});

test("configuration pins the adapter to a standard-port Modal origin", () => {
  assert.equal(gatewayDelegationConfigured(env), true);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_URL: "http://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run" }), false);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_URL: "https://u:p@unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run" }), false);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_URL: "https://adapter.example" }), false);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_URL: "https://modal.run" }), false);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_URL: "https://another-tenant.modal.run" }), false);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_URL: "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run:444" }), false);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_URL: "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run/path" }), false);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_HMAC_KEY_B64: Buffer.from("weak").toString("base64") }), false);
  assert.equal(gatewayDelegationConfigured({ ...env, PROVIDER_ADAPTER_PROXY_TOKEN_SECRET: "bad" }), false);
});

test("delegation rejects an oversized response before JSON parsing", async () => {
  await assert.rejects(
    delegateGatewayTool(env, "owner-123", "experiment_list", {}, async () => new Response("{}", {
      status: 200, headers: { "content-length": "65537" },
    }), 1000),
    /GATEWAY_DELEGATION_RESPONSE_TOO_LARGE/,
  );
});

test("delegation returns only bounded stable remote error codes", async () => {
  await assert.rejects(
    delegateGatewayTool(env, "owner-123", "experiment_list", {}, async () => new Response(
      JSON.stringify({ code: "delegation_replayed", message: "provider-controlled text" }),
      { status: 409, headers: { "content-type": "application/json" } },
    ), 1000),
    /GATEWAY_DELEGATION_DELEGATION_REPLAYED/,
  );
});
