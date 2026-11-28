import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
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

function database() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(readFileSync(new URL("../drizzle/0035_github_owner_identity.sql", import.meta.url), "utf8"));
  sqlite.exec(readFileSync(new URL("../drizzle/0036_mcp_oauth_clients.sql", import.meta.url), "utf8"));
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
    const completed = await completeMcpOAuthGitHubLogin(db, githubState, "ghu_abcdefghijklmnop", async () =>
      new Response(JSON.stringify({ id: 1234567, login: "owner" }), { status: 200 }), now + 1);
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
