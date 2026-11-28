import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { completeGoogleColabOAuth, createGoogleColabConnectionUrl, beginGoogleColabOAuth } from "./google_colab_connection.js";
import { callGoogleColabMcpTool } from "./google_colab_mcp_client.js";
import { handleGoogleColabTool } from "./google_colab_tools.js";

const env = {
  GOOGLE_COLAB_OAUTH_CLIENT_ID: "client-123456.apps.googleusercontent.com",
  GOOGLE_COLAB_OAUTH_CLIENT_SECRET: "google-colab-client-secret-for-tests",
  GOOGLE_COLAB_OAUTH_CALLBACK_URL: "https://gpu-control-sites.unjuno.chatgpt.site/google/oauth/callback",
  GOOGLE_COLAB_TOKEN_ENCRYPTION_KEY: randomBytes(32).toString("base64url"),
};
const colabScope = "https://www.googleapis.com/auth/colaboratory";

function database() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(readFileSync(new URL("../drizzle/0034_google_colab_account_connection.sql", import.meta.url), "utf8"));
  return { prepare(sql) { return { bind(...values) {
    const statement = sqlite.prepare(sql);
    return { run: async () => statement.run(...values), first: async () => statement.get(...values) };
  } }; }, close: () => sqlite.close() };
}

function response(value, status = 200, contentType = "application/json") {
  return new Response(JSON.stringify(value), { status, headers: { "content-type": contentType } });
}

async function connect(db, owner) {
  const link = await createGoogleColabConnectionUrl(db, owner, 1_800_000_000);
  const state = new URL(link.authorization_url).searchParams.get("state");
  const authorization = await beginGoogleColabOAuth(db, state, env, 1_800_000_001);
  const cookie = authorization.pkce_cookie.split(";")[0].split("=")[1];
  const [oauthState, verifier] = cookie.split(".");
  await completeGoogleColabOAuth(db, env, oauthState, verifier, "code", { now: 1_800_000_002,
    fetchImpl: async (url) => String(url) === "https://oauth2.googleapis.com/token"
      ? response({ access_token: "oauth-access", refresh_token: "oauth-refresh-token", scope: "openid email " + colabScope, expires_in: 3600 })
      : response({ sub: "subject", email: "owner@example.com", email_verified: true }) });
}

test("Google Colab MCP client is pinned to the hosted endpoint, allowlists tool names, and bounds response data", async () => {
  const db = database();
  try {
    await connect(db, "owner-1");
    const result = await callGoogleColabMcpTool({ ...env, DB: db }, "owner-1", "get_subscription", {}, {
      fetchImpl: async (url, init) => {
        if (String(url) === "https://oauth2.googleapis.com/token") {
          assert.equal(new URLSearchParams(init.body).get("refresh_token"), "oauth-refresh-token");
          return response({ access_token: "short-lived-access", scope: colabScope, expires_in: 3600 });
        }
        assert.equal(String(url), "https://colaboratory.googleapis.com/mcp");
        assert.equal(init.redirect, "error");
        assert.equal(init.headers.authorization, "Bearer short-lived-access");
        const request = JSON.parse(init.body);
        assert.equal(request.method, "tools/call");
        assert.equal(request.params.name, "get_subscription");
        return response({ jsonrpc: "2.0", id: request.id, result: { content: [{ type: "text", text: "free" }] } });
      },
    });
    assert.deepEqual(result, { content: [{ type: "text", text: "free" }] });
    await assert.rejects(callGoogleColabMcpTool({ ...env, DB: db }, "owner-1", "delete_everything", {}),
      { message: "GOOGLE_COLAB_TOOL_INVALID" });
    await assert.rejects(callGoogleColabMcpTool({ ...env, DB: db }, "owner-1", "create_runtime", {}),
      { message: "GOOGLE_COLAB_TOOL_INVALID" });
    await assert.rejects(callGoogleColabMcpTool({ ...env, DB: db }, "owner-1", "execute_code", {}),
      { message: "GOOGLE_COLAB_TOOL_INVALID" });
    await assert.rejects(callGoogleColabMcpTool({ ...env, DB: db }, "owner-1", "get_subscription", {}, {
      fetchImpl: async (url) => String(url) === "https://oauth2.googleapis.com/token"
        ? response({ access_token: "short-lived-access", scope: colabScope, expires_in: 3600 })
        : new Response("x".repeat(80_000), { headers: { "content-type": "application/json" } }),
    }), { message: "GOOGLE_COLAB_RESPONSE_TOO_LARGE" });
  } finally { db.close(); }
});

test("Colab capability projection reports eligible GPUs without exposing runtime proxy credentials", async () => {
  const db = database();
  try {
    await connect(db, "capability-owner");
    const result = await handleGoogleColabTool("colab_capabilities", { ...env, DB: db }, "capability-owner", {
      fetchImpl: async (url, init) => {
        if (String(url) === "https://oauth2.googleapis.com/token") {
          return response({ access_token: "short-lived-access", scope: colabScope, expires_in: 3600 });
        }
        const request = JSON.parse(init.body);
        const output = request.params.name === "get_subscription" ? { tier: "SUBSCRIPTION_TIER_PRO" }
          : request.params.name === "list_runtime_specs" ? { runtimeSpecs: [
            { key: { variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD" }, eligible: true },
            { key: { variant: "VARIANT_GPU", accelerator: "A100", shape: "SHAPE_STANDARD" }, eligible: false },
          ] }
          : { runtimes: [{ name: "runtimes/owned", runtimeSpec: { key: { variant: "VARIANT_GPU",
            accelerator: "T4", shape: "SHAPE_STANDARD" } },
            connectionInfo: { token: "secret-runtime-token", url: "https://private-runtime.example" } }] };
        return response({ jsonrpc: "2.0", id: request.id, result: { structuredContent: output } });
      },
    });
    assert.equal(result.status, "ok");
    assert.equal(result.machine_state.subscription_tier, "SUBSCRIPTION_TIER_PRO");
    assert.deepEqual(result.machine_state.eligible_gpu_specs, [
      { accelerator: "T4", shape: "SHAPE_STANDARD", eligible: true },
      { accelerator: "A100", shape: "SHAPE_STANDARD", eligible: false },
    ]);
    assert.equal(result.machine_state.active_gpu_runtime_count, 1);
    assert.equal(result.machine_state.execution_lifecycle_enabled, false);
    assert.deepEqual(result.machine_state.cost_terms, { per_run_usd: null, remaining_quota: null,
      semantics: "google_account_subscription_quota_not_quantified_per_run",
      quota_exhaustion_effect: "google_paid_account_reverts_to_free_tier_restrictions",
      compute_unit_balance_available_via_api: false, positive_compute_units_required_for_automation: true,
      positive_compute_units_verified: false, automatic_top_up_available: false,
      paid_fallback_allowed: false });
    assert.deepEqual(result.machine_state.execution_security, { network_egress: "unrestricted",
      private_data_allowed: false, provider_credentials_allowed: false,
      run_owned_runtime_deletion_requires_exact_plan_confirmation: true });
    assert.equal(result.machine_state.account_email_redacted, "o***@example.com");
    assert.equal(JSON.stringify(result).includes("owner@example.com"), false);
    assert.equal(JSON.stringify(result).includes("secret-runtime-token"), false);
    assert.equal(JSON.stringify(result).includes("private-runtime.example"), false);
  } finally { db.close(); }
});

test("Colab capability projection rejects malformed runtime identities and incomplete runtime specs", async () => {
  const db = database();
  try {
    await connect(db, "invalid-capability-owner");
    await assert.rejects(handleGoogleColabTool("colab_capabilities", { ...env, DB: db }, "invalid-capability-owner", {
      fetchImpl: async (url, init) => {
        if (String(url) === "https://oauth2.googleapis.com/token") {
          return response({ access_token: "short-lived-access", scope: colabScope, expires_in: 3600 });
        }
        const request = JSON.parse(init.body);
        const output = request.params.name === "get_subscription" ? { tier: "SUBSCRIPTION_TIER_PRO" }
          : request.params.name === "list_runtime_specs" ? { runtimeSpecs: [
            { key: { variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD" }, eligible: true },
          ] }
          : { runtimes: [{ name: "https://attacker.example/runtimes/x",
            runtimeSpec: { key: { variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD" } } }] };
        return response({ jsonrpc: "2.0", id: request.id, result: { structuredContent: output } });
      },
    }), { message: "GOOGLE_COLAB_RESPONSE_INVALID" });
  } finally { db.close(); }
});

test("Google Colab MCP client selects the matching response from a bounded event stream", async () => {
  const db = database();
  try {
    await connect(db, "stream-owner");
    const result = await callGoogleColabMcpTool({ ...env, DB: db }, "stream-owner", "get_subscription", {}, {
      fetchImpl: async (url, init) => {
        if (String(url) === "https://oauth2.googleapis.com/token") {
          return response({ access_token: "short-lived-access", scope: colabScope, expires_in: 3600 });
        }
        const request = JSON.parse(init.body);
        const payload = { jsonrpc: "2.0", id: request.id, result: { content: [{ type: "text", text: "free" }] } };
        return new Response(`event: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress","params":{}}\n\nevent: message\ndata: ${JSON.stringify(payload)}\n\n`,
          { status: 200, headers: { "content-type": "text/event-stream" } });
      },
    });
    assert.deepEqual(result, { content: [{ type: "text", text: "free" }] });
  } finally { db.close(); }
});
