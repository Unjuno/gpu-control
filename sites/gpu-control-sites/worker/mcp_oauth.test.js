import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";
import worker from "./index.js";
import { authenticateMcpAccessToken, beginMcpOAuthGitHubLogin, completeMcpOAuthGitHubLogin,
  createMcpOAuthConsent, exchangeMcpOAuthToken, mcpAuthorizationServerMetadata,
  mcpProtectedResourceMetadata, registerMcpOAuthClient, revokeMcpOAuthToken } from "./mcp_oauth.js";

const origin = "https://gpu-control.example";
const resource = `${origin}/mcp`;
const callback = "http://127.0.0.1:39281/oauth/callback";
const now = 1_800_000_000;
const verifier = "v".repeat(43);

function b64url(bytes) { return Buffer.from(bytes).toString("base64url"); }
async function challenge(value) {
  return b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}

function database({ currentSchema = false } = {}) {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec("PRAGMA foreign_keys=ON");
  if (currentSchema) {
    for (const migration of readdirSync(new URL("../drizzle/", import.meta.url)).filter((name) => name.endsWith(".sql")).sort()) {
      sqlite.exec(readFileSync(new URL(`../drizzle/${migration}`, import.meta.url), "utf8"));
    }
  } else {
    sqlite.exec(readFileSync(new URL("../drizzle/0035_github_owner_identity.sql", import.meta.url), "utf8"));
    sqlite.exec(readFileSync(new URL("../drizzle/0036_mcp_oauth_clients.sql", import.meta.url), "utf8"));
  }
  return {
    sqlite,
    prepare(sql) {
      return { bind(...values) {
        const statement = sqlite.prepare(sql);
        return { sql, values, first: async () => statement.get(...values), all: async () => ({ results: statement.all(...values) }),
          run: async () => statement.run(...values) };
      } };
    },
    async batch(statements) {
      sqlite.exec("BEGIN");
      try {
        const result = statements.map(({ sql, values }) => {
          const statement = sqlite.prepare(sql);
          if (sql.includes("RETURNING")) return { results: statement.all(...values) };
          return { meta: { changes: Number(statement.run(...values).changes) } };
        });
        sqlite.exec("COMMIT");
        return result;
      } catch (error) { sqlite.exec("ROLLBACK"); throw error; }
    },
  };
}

async function authorizeClientForLinkedOwner(db, client, at) {
  const auth = { response_type: "code", client_id: client.client_id, redirect_uri: callback,
    scope: "experiments:read", state: "client-state", code_challenge: await challenge(verifier),
    code_challenge_method: "S256", resource };
  const consent = await createMcpOAuthConsent(db, auth, origin, at);
  const csrf = (await consent.response.text()).match(/name="csrf" value="([A-Za-z0-9_-]{43})"/)?.[1];
  assert.ok(csrf);
  const login = await beginMcpOAuthGitHubLogin(db, csrf, { GITHUB_APP_ID: "1", GITHUB_APP_SLUG: "gpu-control",
    GITHUB_APP_PRIVATE_KEY: "configured", GITHUB_APP_CLIENT_ID: "github-client",
    GITHUB_APP_CLIENT_SECRET: "x".repeat(20), GITHUB_APP_OAUTH_CALLBACK_URL: `${origin}/github/oauth/callback` }, at);
  const state = new URL(login.authorization_url).searchParams.get("state");
  const completed = await completeMcpOAuthGitHubLogin(db, state, "ghu_abcdefghijklmnop", async () =>
    new Response(JSON.stringify({ id: 1234567, login: "owner" }), { status: 200 }), at + 1);
  const code = new URL(completed.redirect_uri).searchParams.get("code");
  const token = await exchangeMcpOAuthToken(db, new URLSearchParams({ grant_type: "authorization_code",
    client_id: client.client_id, code, redirect_uri: callback, code_verifier: verifier, resource }), origin, at + 2);
  assert.equal(token.status, 200);
  return (await token.json()).access_token;
}

test("Sites HTTP exposes OAuth discovery, public-client registration and owner consent", async () => {
  const db = database();
  const env = { DB: db };
  try {
    const protectedResource = await worker.fetch(new Request(`${origin}/.well-known/oauth-protected-resource`), env);
    assert.equal(protectedResource.status, 200);
    assert.equal((await protectedResource.json()).resource, resource);

    const serverMetadata = await worker.fetch(new Request(`${origin}/.well-known/oauth-authorization-server`), env);
    assert.equal(serverMetadata.status, 200);
    const metadata = await serverMetadata.json();
    assert.equal(metadata.registration_endpoint, `${origin}/oauth/register`);
    assert.equal(metadata.authorization_endpoint, `${origin}/oauth/authorize`);
    assert.equal(metadata.token_endpoint, `${origin}/oauth/token`);

    const registered = await worker.fetch(new Request(`${origin}/oauth/register`, {
      method: "POST",
      headers: { "content-type": "application/json", "cf-connecting-ip": "192.0.2.10" },
      body: JSON.stringify({ client_name: "Example chat client", redirect_uris: [callback] }),
    }), env);
    assert.equal(registered.status, 201);
    const client = await registered.json();

    const authorizationUrl = new URL(`${origin}/oauth/authorize`);
    for (const [key, value] of Object.entries({ response_type: "code", client_id: client.client_id,
      redirect_uri: callback, scope: "experiments:read", state: "client-state",
      code_challenge: await challenge(verifier), code_challenge_method: "S256", resource })) {
      authorizationUrl.searchParams.set(key, value);
    }
    const consent = await worker.fetch(new Request(authorizationUrl), env);
    assert.equal(consent.status, 200);
    assert.match(consent.headers.get("set-cookie"), /__Host-gpu-control-mcp-consent=/);
    assert.match(await consent.text(), /Example chat client/);

    const tokenWithBearerHeader = await worker.fetch(new Request(`${origin}/oauth/token`, {
      method: "POST", headers: { authorization: "Bearer ignored",
        "content-type": "application/x-www-form-urlencoded" },
      body: "grant_type=authorization_code",
    }), env);
    assert.equal(tokenWithBearerHeader.status, 400);
  } finally { db.sqlite.close(); }
});

test("independent OAuth MCP clients and ChatGPT share one owner ledger with separate revocable grants", async () => {
  const db = database({ currentSchema: true });
  try {
    db.sqlite.prepare("INSERT INTO github_owner_identities VALUES (?, ?, ?)").run("owner-1", "1234567", now);
    db.sqlite.prepare(`INSERT INTO plans (id, owner_id, idempotency_key, fingerprint, workload, repository,
      source_sha, image_digest, parameters_json, runtime_seconds, max_cost_usd, state, created_at, expires_at, provider)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, 'modal_cpu')`)
      .run("a".repeat(32), "owner-1", "client-neutral-plan", "b".repeat(64), "tiny-stories-inference-v1",
        "owner-1/research", "c".repeat(40), `sha256:${"d".repeat(64)}`, "{}", 30, "0.00", now, now + 300);
    db.sqlite.prepare(`INSERT INTO runs (id, owner_id, plan_id, state, cleanup_state, result_json, created_at, updated_at)
      VALUES (?, ?, ?, 'succeeded', 'confirmed', '{}', ?, ?)`)
      .run("a".repeat(32), "owner-1", "a".repeat(32), now, now + 10);
    db.sqlite.prepare(`INSERT INTO plans (id, owner_id, idempotency_key, fingerprint, workload, repository,
      source_sha, image_digest, parameters_json, runtime_seconds, max_cost_usd, state, created_at, expires_at, provider)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, 'modal_cpu')`)
      .run("e".repeat(32), "owner-2", "other-owner-plan", "f".repeat(64), "tiny-stories-inference-v1",
        "owner-2/research", "1".repeat(40), `sha256:${"2".repeat(64)}`, "{}", 30, "0.00", now, now + 300);
    db.sqlite.prepare(`INSERT INTO runs (id, owner_id, plan_id, state, cleanup_state, result_json, created_at, updated_at)
      VALUES (?, ?, ?, 'succeeded', 'confirmed', '{}', ?, ?)`)
      .run("e".repeat(32), "owner-2", "e".repeat(32), now, now + 10);

    const client = await registerMcpOAuthClient(db, { client_name: "Independent MCP client A", redirect_uris: [callback] }, "192.0.2.55", now);
    const secondClient = await registerMcpOAuthClient(db, { client_name: "Independent MCP client B", redirect_uris: [callback] }, "192.0.2.55", now + 1);
    const accessToken = await authorizeClientForLinkedOwner(db, client, now + 10);
    const secondAccessToken = await authorizeClientForLinkedOwner(db, secondClient, now + 20);
    const env = { DB: db, GPU_CONTROL_ALLOWED_USER_IDS: "owner-1" };
    const rpc = (message, headers = {}) => worker.fetch(new Request(`${origin}/mcp`, {
      method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(message),
    }), env);
    const toolList = { jsonrpc: "2.0", id: 1, method: "tools/list", params: {} };
    const chatTools = await rpc(toolList, { "oai-authenticated-user-id": "owner-1" });
    const externalTools = await rpc(toolList, { authorization: `Bearer ${accessToken}` });
    const secondExternalTools = await rpc(toolList, { authorization: `Bearer ${secondAccessToken}` });
    assert.equal(chatTools.status, 200);
    assert.equal(externalTools.status, 200);
    assert.equal(secondExternalTools.status, 200);
    const chatToolsResult = (await chatTools.json()).result;
    assert.deepEqual((await externalTools.json()).result, chatToolsResult);
    assert.deepEqual((await secondExternalTools.json()).result, chatToolsResult);

    const listRuns = { jsonrpc: "2.0", id: 2, method: "tools/call",
      params: { name: "experiment_list", arguments: {} } };
    const chatRuns = await rpc(listRuns, { "oai-authenticated-user-id": "owner-1" });
    const externalRuns = await rpc(listRuns, { authorization: `Bearer ${accessToken}` });
    const secondExternalRuns = await rpc(listRuns, { authorization: `Bearer ${secondAccessToken}` });
    assert.equal(chatRuns.status, 200);
    assert.equal(externalRuns.status, 200);
    assert.equal(secondExternalRuns.status, 200);
    const chatResult = await chatRuns.json();
    const externalResult = await externalRuns.json();
    const secondExternalResult = await secondExternalRuns.json();
    assert.deepEqual(externalResult.result, chatResult.result);
    assert.deepEqual(secondExternalResult.result, chatResult.result);
    const visibleRuns = JSON.parse(chatResult.result.content[0].text).machine_state.experiments;
    assert.deepEqual(visibleRuns.map((run) => run.run_id), ["a".repeat(32)]);
    assert.ok(!JSON.stringify(externalResult).includes("e".repeat(32)),
      "an authenticated client cannot read a different owner's run");

    await revokeMcpOAuthToken(db, new URLSearchParams({ token: accessToken, client_id: client.client_id }), now + 30);
    assert.equal((await rpc(toolList, { authorization: `Bearer ${accessToken}` })).status, 401,
      "revoking one client's grant removes that access token");
    assert.equal((await rpc(toolList, { authorization: `Bearer ${secondAccessToken}` })).status, 200,
      "revoking one client does not revoke another client's grant for the same owner");
  } finally { db.sqlite.close(); }
});

test("invalid MCP OAuth consent clears its one-time CSRF cookie", async () => {
  const db = database();
  try {
    const response = await worker.fetch(new Request(`${origin}/oauth/authorize`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded", cookie: "__Host-gpu-control-mcp-consent=stale" },
      body: "csrf=forged",
    }), { DB: db });
    assert.equal(response.status, 400);
    assert.match(response.headers.get("set-cookie") || "", /__Host-gpu-control-mcp-consent=; Max-Age=0/);
    assert.equal(response.headers.get("cache-control"), "no-store");
  } finally { db.sqlite.close(); }
});

test("MCP OAuth authorizes one linked owner, binds audience, rotates refresh tokens, and revokes replayed families", async () => {
  const db = database();
  try {
    const client = await registerMcpOAuthClient(db, { client_name: "Example MCP client", redirect_uris: [callback] }, "192.0.2.1", now);
    assert.equal(client.token_endpoint_auth_method, "none");
    const metadata = mcpProtectedResourceMetadata(origin);
    assert.equal(metadata.resource, resource);
    assert.deepEqual(mcpAuthorizationServerMetadata(origin).code_challenge_methods_supported, ["S256"]);

    const auth = { response_type: "code", client_id: client.client_id, redirect_uri: callback,
      scope: "experiments:read experiments:execute", state: "client-state", code_challenge: await challenge(verifier),
      code_challenge_method: "S256", resource };
    const consent = await createMcpOAuthConsent(db, auth, origin, now);
    assert.match(consent.response.headers.get("content-security-policy"), /frame-ancestors 'none'/);
    const csrf = (await consent.response.text()).match(/name="csrf" value="([A-Za-z0-9_-]{43})"/)?.[1];
    assert.ok(csrf);
    const login = await beginMcpOAuthGitHubLogin(db, csrf, { GITHUB_APP_ID: "1", GITHUB_APP_SLUG: "gpu-control",
      GITHUB_APP_PRIVATE_KEY: "configured", GITHUB_APP_CLIENT_ID: "github-client",
      GITHUB_APP_CLIENT_SECRET: "x".repeat(20), GITHUB_APP_OAUTH_CALLBACK_URL: `${origin}/github/oauth/callback` }, now);
    const githubUrl = new URL(login.authorization_url);
    const githubState = githubUrl.searchParams.get("state");
    assert.equal(githubUrl.searchParams.get("code_challenge_method"), "S256");

    db.sqlite.exec("INSERT INTO github_owner_identities VALUES ('owner-1','1234567',1)");
    const identityFetch = async () => new Response(JSON.stringify({ id: 1234567, login: "owner" }), { status: 200 });
    await assert.rejects(completeMcpOAuthGitHubLogin(db, githubState, "ghu_abcdefghijklmnop",
      identityFetch, now + 1, (ownerId) => ownerId === "owner-2"), /MCP_OAUTH_OWNER_NOT_ALLOWED/);
    const completed = await completeMcpOAuthGitHubLogin(db, githubState, "ghu_abcdefghijklmnop",
      identityFetch, now + 1, (ownerId) => ownerId === "owner-1");
    const authRedirect = new URL(completed.redirect_uri);
    assert.equal(authRedirect.searchParams.get("state"), "client-state");
    const code = authRedirect.searchParams.get("code");

    const tokenParams = new URLSearchParams({ grant_type: "authorization_code", client_id: client.client_id,
      code, redirect_uri: callback, code_verifier: verifier, resource });
    const tokenResponse = await exchangeMcpOAuthToken(db, tokenParams, origin, now + 2);
    assert.equal(tokenResponse.status, 200);
    const pair = await tokenResponse.json();
    const principal = await authenticateMcpAccessToken(db, pair.access_token, resource, now + 3);
    assert.equal(principal.owner_id, "owner-1");
    assert.deepEqual(principal.scopes, ["experiments:execute", "experiments:read"]);
    assert.equal(await authenticateMcpAccessToken(db, pair.access_token, "https://other.example/mcp", now + 3), null);
    assert.equal(await authenticateMcpAccessToken(db, pair.access_token, resource, now + 903), null);

    const replayCode = await exchangeMcpOAuthToken(db, tokenParams, origin, now + 4);
    assert.equal(replayCode.status, 400);
    const refreshParams = new URLSearchParams({ grant_type: "refresh_token", client_id: client.client_id,
      refresh_token: pair.refresh_token, resource });
    const rotatedResponse = await exchangeMcpOAuthToken(db, refreshParams, origin, now + 5);
    assert.equal(rotatedResponse.status, 200);
    const rotated = await rotatedResponse.json();
    assert.ok(await authenticateMcpAccessToken(db, rotated.access_token, resource, now + 6));

    const replayRefresh = await exchangeMcpOAuthToken(db, refreshParams, origin, now + 7);
    assert.equal(replayRefresh.status, 400);
    assert.equal(await authenticateMcpAccessToken(db, rotated.access_token, resource, now + 8), null);
  } finally { db.sqlite.close(); }
});

test("MCP OAuth rejects unregistered redirects, insecure remote redirects, duplicate parameters, and unlinked GitHub identities", async () => {
  const db = database();
  try {
    await assert.rejects(registerMcpOAuthClient(db, { client_name: "Bad", redirect_uris: ["http://example.com/callback"] }, "192.0.2.2", now),
      /MCP_OAUTH_CLIENT_METADATA_INVALID/);
    const client = await registerMcpOAuthClient(db, { client_name: "Example", redirect_uris: [callback] }, "192.0.2.2", now);
    const base = { response_type: "code", client_id: client.client_id, redirect_uri: callback, state: "state",
      code_challenge: await challenge(verifier), code_challenge_method: "S256", resource };
    await assert.rejects(createMcpOAuthConsent(db, { ...base, redirect_uri: "http://127.0.0.1:39281/other" }, origin, now),
      /MCP_OAUTH_REDIRECT_URI_INVALID/);
    const consent = await createMcpOAuthConsent(db, base, origin, now);
    const csrf = (await consent.response.text()).match(/name="csrf" value="([A-Za-z0-9_-]{43})"/)?.[1];
    const login = await beginMcpOAuthGitHubLogin(db, csrf, { GITHUB_APP_ID: "1", GITHUB_APP_SLUG: "gpu-control",
      GITHUB_APP_PRIVATE_KEY: "configured", GITHUB_APP_CLIENT_ID: "github-client",
      GITHUB_APP_CLIENT_SECRET: "x".repeat(20), GITHUB_APP_OAUTH_CALLBACK_URL: `${origin}/github/oauth/callback` }, now);
    await assert.rejects(completeMcpOAuthGitHubLogin(db, new URL(login.authorization_url).searchParams.get("state"),
      "ghu_abcdefghijklmnop", async () => new Response(JSON.stringify({ id: 7654321, login: "unlinked" }), { status: 200 }), now + 1),
    /MCP_OAUTH_OWNER_LINK_REQUIRED/);

    const duplicate = new URLSearchParams({ grant_type: "refresh_token", client_id: client.client_id,
      refresh_token: "gpc_rt_" + "a".repeat(43), resource });
    duplicate.append("resource", resource);
    assert.equal((await exchangeMcpOAuthToken(db, duplicate, origin, now)).status, 400);
  } finally { db.sqlite.close(); }
});

test("per-IP rejected DCR attempts do not consume the shared registration allowance", async () => {
  const db = database({ currentSchema: true });
  try {
    const metadata = { client_name: "Example", redirect_uris: [callback] };
    for (let attempt = 0; attempt < 10; attempt++) {
      await registerMcpOAuthClient(db, metadata, "192.0.2.80", now + attempt);
    }
    await assert.rejects(registerMcpOAuthClient(db, metadata, "192.0.2.80", now + 10),
      /MCP_OAUTH_REGISTRATION_RATE_LIMITED/);
    await registerMcpOAuthClient(db, metadata, "192.0.2.81", now + 11);

    const globalHash = createHash("sha256")
      .update("gpu-control-mcp-client-registration:global").digest("hex");
    const count = db.sqlite.prepare(`SELECT registration_count FROM mcp_oauth_registration_limits
      WHERE ip_hash=? AND period_day=?`).get(globalHash, new Date(now * 1000).toISOString().slice(0, 10));
    assert.equal(count.registration_count, 11,
      "only successfully registered clients consume the global allowance");
  } finally { db.sqlite.close(); }
});

test("MCP OAuth revocation is client-bound and idempotent", async () => {
  const db = database();
  try {
    const client = await registerMcpOAuthClient(db, { client_name: "Example", redirect_uris: [callback] }, "192.0.2.3", now);
    const token = "gpc_at_" + "z".repeat(43);
    const hash = Buffer.from(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token))).toString("hex");
    db.sqlite.prepare(`INSERT INTO mcp_oauth_tokens VALUES (?, 'access', ?, 'owner-1', 'experiments:read', ?, ?, ?, ?, NULL, NULL, NULL)`)
      .run(hash, client.client_id, resource, "a".repeat(32), now, now + 100);
    await revokeMcpOAuthToken(db, new URLSearchParams({ token, client_id: "gpc_client_" + "a".repeat(32) }), now + 1);
    assert.ok(await authenticateMcpAccessToken(db, token, resource, now + 2));
    await revokeMcpOAuthToken(db, new URLSearchParams({ token, client_id: client.client_id }), now + 3);
    assert.equal(await authenticateMcpAccessToken(db, token, resource, now + 4), null);
  } finally { db.sqlite.close(); }
});
