import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { generateKeyPairSync, createVerify, createHash } from "node:crypto";
import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  beginGithubInstallationOAuth,
  completeGithubInstallationOAuth,
  createGithubAppJwt,
  createGithubInstallationToken,
  createOwnedRepositoryReadToken,
  createGithubInstallationUrl,
  disconnectGithubApp,
  exchangeGithubOAuthCode,
  githubAppOwnerConnectionConfigured,
  githubAppOAuthConfigured,
  githubConnectionStatus,
  listGithubInstallationRepositories,
  listOwnedGithubRepositories,
  verifyGithubInstallation,
} from "./github_app_connection.js";

const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const privatePem = privateKey.export({ type: "pkcs8", format: "pem" });
const env = { GITHUB_APP_ID: "12345", GITHUB_APP_SLUG: "gpu-control-source",
  GITHUB_APP_PRIVATE_KEY: privatePem, GITHUB_APP_CLIENT_ID: "Iv1.client-id",
  GITHUB_APP_CLIENT_SECRET: "github-app-client-secret-for-tests",
  GITHUB_APP_TOKEN_ENCRYPTION_KEY: randomBytes(32).toString("base64url"),
  GITHUB_APP_OAUTH_CALLBACK_URL: "https://gpu-control.example/github/oauth/callback" };
const testTokens = { access_token: "ghu_aaaaaaaaaaaaaaaaaaaa", refresh_token: "ghr_bbbbbbbbbbbbbbbbbbbb",
  access_expires_in: 28_800, refresh_expires_in: 15_897_600 };

function database() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(readFileSync(new URL("../drizzle/0030_github_app_connections.sql", import.meta.url), "utf8"));
  sqlite.exec(readFileSync(new URL("../drizzle/0033_github_installation_user_authorization.sql", import.meta.url), "utf8"));
  sqlite.exec(readFileSync(new URL("../drizzle/0035_github_owner_identity.sql", import.meta.url), "utf8"));
  sqlite.exec(readFileSync(new URL("../drizzle/0041_github_user_repository_scope.sql", import.meta.url), "utf8"));
  sqlite.exec(readFileSync(new URL("../drizzle/0042_github_live_user_authorization.sql", import.meta.url), "utf8"));
  const db = {
    prepare(sql) {
      return { bind(...values) {
        const statement = sqlite.prepare(sql);
        return {
          sql, values,
          run: async () => statement.run(...values),
          first: async () => statement.get(...values),
          all: async () => ({ results: statement.all(...values) }),
        };
      } };
    },
    async batch(statements) {
      sqlite.exec("BEGIN");
      try {
        const results = statements.map(({ sql, values }) => {
          const statement = sqlite.prepare(sql);
          if (sql.includes("RETURNING")) return { results: statement.all(...values) };
          return { meta: { changes: Number(statement.run(...values).changes) } };
        });
        sqlite.exec("COMMIT");
        return results;
      } catch (error) { sqlite.exec("ROLLBACK"); throw error; }
    },
    close: () => sqlite.close(),
  };
  return db;
}

function mockResponse(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json" } });
}

async function seedConnection(db, owner = "site-owner", repositories = [
  { id: "7", repository: "unjuno/model-as-a-paper" },
], now = 2_000_000_000) {
  const intent = await createGithubInstallationUrl(db, owner, env.GITHUB_APP_SLUG, now);
  const state = new URL(intent.authorization_url).searchParams.get("state");
  const authorization = await beginGithubInstallationOAuth(db, state, "98765", {
    id: "98765", account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
    permissions: { contents: "read", metadata: "read" },
  }, env, now + 1);
  const oauthState = new URL(authorization.authorization_url).searchParams.get("state");
  const linked = await completeGithubInstallationOAuth(env, db, oauthState, testTokens, async (url) => {
    const path = new URL(url).pathname;
    if (path === "/user") return mockResponse({ id: 7654321, login: "Unjuno" });
    return mockResponse({ total_count: repositories.length, repositories: repositories.map((item) => ({
      id: Number(item.id), full_name: item.repository,
    })) });
  }, now + 2);
  assert.equal(linked.connected, true);
}

test("GitHub App JWT uses RS256 and a short bounded lifetime", async () => {
  const token = await createGithubAppJwt(env, 1_800_000_000);
  const [headerPart, payloadPart, signaturePart] = token.split(".");
  const decode = (part) => JSON.parse(Buffer.from(part.replaceAll("-", "+").replaceAll("_", "/"), "base64").toString());
  assert.deepEqual(decode(headerPart), { alg: "RS256", typ: "JWT" });
  assert.deepEqual(decode(payloadPart), { iss: "12345", iat: 1_799_999_940, exp: 1_800_000_540 });
  const verifier = createVerify("RSA-SHA256");
  verifier.update(`${headerPart}.${payloadPart}`);
  verifier.end();
  assert.equal(verifier.verify(publicKey, Buffer.from(signaturePart.replaceAll("-", "+").replaceAll("_", "/"), "base64")), true);
});

test("install callback requires user access to the exact installation before binding", async () => {
  const db = database();
  try {
    const intent = await createGithubInstallationUrl(db, "site-owner", env.GITHUB_APP_SLUG, 1_800_000_000);
    const state = new URL(intent.authorization_url).searchParams.get("state");
    const installation = { id: "98765",
      account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
      permissions: { contents: "read", metadata: "read" } };
    const authorization = await beginGithubInstallationOAuth(db, state, "98765", installation, env, 1_800_000_030);
    const authorizationUrl = new URL(authorization.authorization_url);
    const oauthState = authorizationUrl.searchParams.get("state");
    const verifier = authorization.pkce_cookie.match(/__Host-gpu-control-oauth=[a-f0-9]{64}\.([A-Za-z0-9_-]{43})/)[1];
    assert.equal(authorizationUrl.searchParams.get("client_id"), env.GITHUB_APP_CLIENT_ID);
    assert.equal(authorizationUrl.searchParams.get("redirect_uri"), env.GITHUB_APP_OAUTH_CALLBACK_URL);
    assert.equal(authorizationUrl.searchParams.get("code_challenge_method"), "S256");
    assert.equal(authorizationUrl.searchParams.get("scope"), "offline_access");
    assert.equal(authorizationUrl.searchParams.get("code_challenge"),
      createHash("sha256").update(verifier).digest("base64url"));
    assert.match(authorization.pkce_cookie, /Secure; HttpOnly; SameSite=Lax/);
    assert.deepEqual(await githubConnectionStatus(db, "site-owner"), { connected: false });
    const linked = await completeGithubInstallationOAuth(env, db, oauthState, testTokens, async (url, init) => {
      assert.equal(init.headers.authorization, "Bearer ghu_aaaaaaaaaaaaaaaaaaaa");
      if (String(url) === "https://api.github.com/user") return mockResponse({ id: 7654321, login: "Unjuno" });
      assert.equal(String(url), "https://api.github.com/user/installations/98765/repositories?per_page=25&page=1");
      return mockResponse({ total_count: 1, repositories: [{ id: 7, full_name: "Unjuno/model-as-a-paper" }] });
    }, 1_800_000_031);
    assert.deepEqual(linked, { connected: true, account_login: "Unjuno", repository_selection: "selected" });
    assert.deepEqual(await githubConnectionStatus(db, "site-owner"), { connected: true,
      account_login: "Unjuno", repository_selection: "selected", connected_at: 1_800_000_031 });
    assert.deepEqual({ ...(await db.prepare("SELECT github_user_id, verified_at FROM github_owner_identities WHERE owner_id=?")
      .bind("site-owner").first()) }, { github_user_id: "7654321", verified_at: 1_800_000_031 });
    await assert.rejects(completeGithubInstallationOAuth(env, db, oauthState, testTokens,
      async () => mockResponse({ total_count: 1, repositories: [{}] }), 1_800_000_031),
    { message: "GITHUB_INSTALLATION_STATE_REPLAYED" });
    await assert.rejects(disconnectGithubApp(db, "site-owner").then(async () =>
      completeGithubInstallationOAuth(env, db, oauthState, testTokens, async () => mockResponse({}),
        1_800_000_032)), { message: "GITHUB_INSTALLATION_STATE_REPLAYED" });
    await disconnectGithubApp(db, "site-owner");
    assert.deepEqual(await githubConnectionStatus(db, "site-owner"), { connected: false });
  } finally { db.close(); }
});

test("GitHub user-scope pagination stays below the bounded response size for 100 repositories", async () => {
  const db = database();
  const intent = await createGithubInstallationUrl(db, "site-owner", env.GITHUB_APP_SLUG, 1_800_000_000);
  const state = new URL(intent.authorization_url).searchParams.get("state");
  const authorization = await beginGithubInstallationOAuth(db, state, "98765", {
    id: "98765", account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
    permissions: { contents: "read", metadata: "read" },
  }, env, 1_800_000_001);
  const oauthState = new URL(authorization.authorization_url).searchParams.get("state");
  const requestedPages = [];
  const linked = await completeGithubInstallationOAuth(env, db, oauthState, testTokens, async (url) => {
    const value = new URL(url);
    if (value.pathname === "/user") return mockResponse({ id: 7654321, login: "Unjuno" });
    const page = Number(value.searchParams.get("page"));
    assert.equal(value.searchParams.get("per_page"), "25");
    requestedPages.push(page);
    const repositories = Array.from({ length: page <= 4 ? 25 : 0 }, (_, index) => ({
      id: (page - 1) * 25 + index + 1,
      full_name: `Unjuno/repository-${(page - 1) * 25 + index}`,
      description: "x".repeat(350),
    }));
    return mockResponse({ total_count: 100, repositories });
  }, 1_800_000_002);
  assert.equal(linked.connected, true);
  assert.deepEqual(requestedPages, [1, 2, 3, 4]);
  const stored = await db.prepare("SELECT user_authorized_repositories_json FROM github_app_installations WHERE owner_id=?")
    .bind("site-owner").first();
  assert.equal(JSON.parse(stored.user_authorized_repositories_json).length, 100);
  db.close();
});

test("a GitHub subject cannot be rebound to another Sites owner or silently switched", async () => {
  const db = database();
  try {
    await db.prepare(`INSERT INTO github_owner_identities (owner_id, github_user_id, verified_at)
      VALUES (?, ?, ?)` ).bind("first-owner", "7654321", 1_800_000_000).run();
    const link = async (owner, identityId, login) => {
      const intent = await createGithubInstallationUrl(db, owner, env.GITHUB_APP_SLUG, 1_800_000_000);
      const state = new URL(intent.authorization_url).searchParams.get("state");
      const authorization = await beginGithubInstallationOAuth(db, state, "98765", {
        id: "98765", account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
        permissions: { contents: "read", metadata: "read" },
      }, env, 1_800_000_001);
      const oauthState = new URL(authorization.authorization_url).searchParams.get("state");
      await completeGithubInstallationOAuth(env, db, oauthState, testTokens, async (url) => {
        return mockResponse(String(url) === "https://api.github.com/user"
          ? { id: identityId, login } : { total_count: 1, repositories: [{ id: 7, full_name: "Unjuno/model-as-a-paper" }] });
      }, 1_800_000_002);
    };
    await assert.rejects(link("second-owner", 7654321, "Unjuno"),
      { message: "GITHUB_IDENTITY_ALREADY_LINKED" });
    await assert.rejects(link("first-owner", 8765432, "OtherUser"),
      { message: "GITHUB_IDENTITY_CHANGE_REQUIRES_RELINK" });
    const identities = await db.prepare("SELECT owner_id, github_user_id FROM github_owner_identities").bind().all();
    assert.deepEqual(identities.results.map((row) => ({ ...row })),
      [{ owner_id: "first-owner", github_user_id: "7654321" }]);
  } finally { db.close(); }
});

test("installation must be selected, unsuspended and contents-read only before OAuth begins", async () => {
  const db = database();
  try {
    for (const installation of [
      { id: 4, account: { login: "Unjuno" }, repository_selection: "all", permissions: { contents: "read", metadata: "read" } },
      { id: 4, account: { login: "Unjuno" }, repository_selection: "selected", permissions: { contents: "write", metadata: "read" } },
      { id: 4, account: { login: "Unjuno" }, repository_selection: "selected", permissions: { contents: "read", metadata: "read", actions: "write" } },
      { id: 4, account: { login: "Unjuno" }, repository_selection: "selected", permissions: { contents: "read" }, suspended_at: "now" },
    ]) {
      const intent = await createGithubInstallationUrl(db, "site-owner", env.GITHUB_APP_SLUG, 1_800_000_000);
      const state = new URL(intent.authorization_url).searchParams.get("state");
      await assert.rejects(beginGithubInstallationOAuth(db, state, "4", installation, env, 1_800_000_001),
        { message: "GITHUB_INSTALLATION_SCOPE_INVALID" });
      assert.deepEqual(await githubConnectionStatus(db, "site-owner"), { connected: false });
    }
  } finally { db.close(); }
});

test("an unlinked GitHub user cannot bind the setup callback's installation ID", async () => {
  const db = database();
  try {
    const intent = await createGithubInstallationUrl(db, "site-owner", env.GITHUB_APP_SLUG, 1_800_000_000);
    const state = new URL(intent.authorization_url).searchParams.get("state");
    const authorization = await beginGithubInstallationOAuth(db, state, "98765", {
      id: "98765", account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
      permissions: { contents: "read", metadata: "read" },
    }, env, 1_800_000_010);
    const oauthState = new URL(authorization.authorization_url).searchParams.get("state");
    await assert.rejects(completeGithubInstallationOAuth(env, db, oauthState, testTokens,
      async () => mockResponse({ message: "Not Found" }, 404), 1_800_000_020),
    { message: "GITHUB_APP_API_FAILED" });
    assert.deepEqual(await githubConnectionStatus(db, "site-owner"), { connected: false });
    const rows = db.prepare("SELECT consumed_at, completion_nonce FROM github_installation_states WHERE owner_id=?")
      .bind("site-owner");
    const row = await rows.first();
    assert.equal(row.consumed_at, null);
    assert.equal(row.completion_nonce, null);
  } finally { db.close(); }
});

test("malformed GitHub subject identities never consume the setup intent", async () => {
  const db = database();
  try {
    const intent = await createGithubInstallationUrl(db, "site-owner", env.GITHUB_APP_SLUG, 1_800_000_000);
    const state = new URL(intent.authorization_url).searchParams.get("state");
    const authorization = await beginGithubInstallationOAuth(db, state, "98765", {
      id: "98765", account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
      permissions: { contents: "read", metadata: "read" },
    }, env, 1_800_000_010);
    const oauthState = new URL(authorization.authorization_url).searchParams.get("state");
    await assert.rejects(completeGithubInstallationOAuth(env, db, oauthState, testTokens,
      async () => mockResponse({ id: 0, login: "Unjuno" }), 1_800_000_020),
    { message: "GITHUB_USER_IDENTITY_INVALID" });
    const row = await db.prepare(`SELECT consumed_at, completion_nonce FROM github_installation_states
      WHERE owner_id=?`).bind("site-owner").first();
    assert.equal(row.consumed_at, null);
    assert.equal(row.completion_nonce, null);
    assert.equal((await db.prepare("SELECT COUNT(*) AS count FROM github_owner_identities").bind().first()).count, 0);
  } finally { db.close(); }
});

test("installation token is scoped to one repository and only Contents read", async () => {
  let request;
  const token = await createGithubInstallationToken(env, "98765", "Unjuno/model-as-a-paper", {
    now: 1_800_000_000,
    fetchImpl: async (url, init) => {
      request = { url: String(url), init };
      return mockResponse({ token: "ghs-temporary-token", expires_at: new Date(Date.now() + 60_000).toISOString(),
        permissions: { contents: "read", metadata: "read" },
        repositories: [{ full_name: "Unjuno/model-as-a-paper" }] });
    },
  });
  assert.equal(token.token, "ghs-temporary-token");
  assert.equal(request.url, "https://api.github.com/app/installations/98765/access_tokens");
  assert.deepEqual(JSON.parse(request.init.body), { repositories: ["model-as-a-paper"],
    permissions: { contents: "read", metadata: "read" } });
  assert.match(request.init.headers.authorization, /^Bearer [A-Za-z0-9_.-]+$/);
});

test("owner repository token minting proves the exact repository is selected first", async () => {
  const db = database();
  await seedConnection(db);
  let scopedTokenRequests = 0;
  const fetchImpl = async (url, init) => {
    const parsed = new URL(url);
    const path = parsed.pathname;
    if (path === "/user") return mockResponse({ id: 7654321, login: "Unjuno" });
    if (path === "/user/installations/98765/repositories") return mockResponse({ total_count: 1, repositories: [
      { id: 7, full_name: "Unjuno/model-as-a-paper" },
    ] });
    if (path === "/installation/repositories") {
      return mockResponse({ total_count: 2, repositories: [
        { id: 7, full_name: "Unjuno/model-as-a-paper", private: true, default_branch: "main" },
        { id: 8, full_name: "Unjuno/other-private", private: true, default_branch: "main" },
      ] });
    }
    const body = JSON.parse(init.body);
    if (body.repositories) {
      scopedTokenRequests += 1;
      assert.deepEqual(body, { repositories: ["model-as-a-paper"],
        permissions: { contents: "read", metadata: "read" } });
      return mockResponse({ token: "ghs-owner-scoped", expires_at: new Date(Date.now() + 60_000).toISOString(),
        permissions: { contents: "read", metadata: "read" },
        repositories: [{ full_name: "Unjuno/model-as-a-paper" }] });
    }
    return mockResponse({ token: "ghs-list-only", expires_at: new Date(Date.now() + 60_000).toISOString(),
      permissions: { contents: "read", metadata: "read" } });
  };
  try {
    const token = await createOwnedRepositoryReadToken(env, db, "site-owner", "Unjuno/model-as-a-paper", { fetchImpl });
    assert.equal(token.token, "ghs-owner-scoped");
    await assert.rejects(createOwnedRepositoryReadToken(env, db, "site-owner", "other/private-repo", { fetchImpl }),
      { message: "GITHUB_REPOSITORY_NOT_SELECTED" });
    await assert.rejects(createOwnedRepositoryReadToken(env, db, "site-owner", "Unjuno/other-private", { fetchImpl }),
      { message: "GITHUB_REPOSITORY_NOT_SELECTED" });
    assert.equal(scopedTokenRequests, 1);
    await assert.rejects(createOwnedRepositoryReadToken(env, db, "another-owner", "Unjuno/model-as-a-paper", { fetchImpl }),
      { message: "GITHUB_CONNECTION_REQUIRED" });
  } finally { db.close(); }
});

test("repository listing revalidates the GitHub user's current repository access", async () => {
  const db = database();
  await seedConnection(db, "site-owner", [{ id: "11", repository: "unjuno/allowed" }]);
  let userStillHasAccess = true;
  let scopedTokenRequests = 0;
  const fetchImpl = async (url, init) => {
    const parsed = new URL(url);
    if (parsed.pathname === "/user") return mockResponse({ id: 7654321, login: "Unjuno" });
    if (parsed.pathname === "/user/installations/98765/repositories") return mockResponse(userStillHasAccess
      ? { total_count: 1, repositories: [{ id: 11, full_name: "Unjuno/allowed" }] }
      : { total_count: 0, repositories: [] });
    if (parsed.pathname === "/app/installations/98765/access_tokens") {
      const body = JSON.parse(init.body || "{}");
      if (body.repositories) scopedTokenRequests += 1;
      return mockResponse({ token: body.repositories ? "ghs-scoped" : "ghs-list-only",
        expires_at: new Date(Date.now() + 60_000).toISOString(),
        permissions: { contents: "read", metadata: "read" },
        ...(body.repositories ? { repositories: [{ full_name: "Unjuno/allowed" }] } : {}),
      });
    }
    if (parsed.pathname === "/installation/repositories") return mockResponse({ total_count: 2, repositories: [
      { id: 11, full_name: "Unjuno/allowed", private: true, default_branch: "main" },
      { id: 12, full_name: "Unjuno/not-allowed-to-user", private: true, default_branch: "main" },
    ] });
    throw new Error(`unexpected GitHub request: ${parsed.pathname}`);
  };
  try {
    const repositories = await listOwnedGithubRepositories(env, db, "site-owner", { fetchImpl });
    assert.deepEqual(repositories.map((repo) => repo.repository), ["unjuno/allowed"]);
    const token = await createOwnedRepositoryReadToken(env, db, "site-owner", "Unjuno/allowed", { fetchImpl });
    assert.equal(token.token, "ghs-scoped");
    assert.equal(scopedTokenRequests, 1);
    userStillHasAccess = false;
    assert.deepEqual(await listOwnedGithubRepositories(env, db, "site-owner", { fetchImpl }), []);
    await assert.rejects(createOwnedRepositoryReadToken(env, db, "site-owner", "Unjuno/allowed", { fetchImpl }),
      { message: "GITHUB_REPOSITORY_NOT_SELECTED" });
    assert.equal(scopedTokenRequests, 1);
  } finally { db.close(); }
});

test("expired GitHub user tokens refresh in storage before current repository authorization", async () => {
  const db = database();
  const linkedAt = 2_000_000_000;
  await seedConnection(db, "site-owner", [{ id: "11", repository: "unjuno/allowed" }], linkedAt);
  const refreshedAccess = "ghu_cccccccccccccccccccc";
  const refreshedSecret = "ghr_dddddddddddddddddddd";
  const fetchImpl = async (url, init) => {
    const parsed = new URL(url);
    if (parsed.origin === "https://github.com" && parsed.pathname === "/login/oauth/access_token") {
      const body = new URLSearchParams(init.body);
      assert.equal(body.get("grant_type"), "refresh_token");
      assert.equal(body.get("refresh_token"), testTokens.refresh_token);
      return mockResponse({ access_token: refreshedAccess, refresh_token: refreshedSecret,
        expires_in: 28_800, refresh_token_expires_in: 15_897_600, token_type: "bearer", scope: "" });
    }
    if (parsed.pathname === "/user") {
      assert.equal(init.headers.authorization, `Bearer ${refreshedAccess}`);
      return mockResponse({ id: 7654321, login: "Unjuno" });
    }
    if (parsed.pathname === "/user/installations/98765/repositories") return mockResponse({ total_count: 1,
      repositories: [{ id: 11, full_name: "Unjuno/allowed" }] });
    if (parsed.pathname === "/app/installations/98765/access_tokens") return mockResponse({
      token: "ghs-list-only", expires_at: new Date(Date.now() + 60_000).toISOString(),
      permissions: { contents: "read", metadata: "read" },
    });
    if (parsed.pathname === "/installation/repositories") return mockResponse({ total_count: 1, repositories: [
      { id: 11, full_name: "Unjuno/allowed", private: true, default_branch: "main" },
    ] });
    throw new Error(`unexpected GitHub request: ${parsed.pathname}`);
  };
  try {
    const repositories = await listOwnedGithubRepositories(env, db, "site-owner", {
      fetchImpl, now: linkedAt + testTokens.access_expires_in + 1,
    });
    assert.equal(repositories.length, 1);
    const stored = await db.prepare(`SELECT access_token_ciphertext, refresh_token_ciphertext,
        access_token_expires_at, refresh_token_expires_at FROM github_app_installations WHERE owner_id=?`)
      .bind("site-owner").first();
    assert.notEqual(stored.access_token_ciphertext, "");
    assert.notEqual(stored.refresh_token_ciphertext, "");
    assert.equal(stored.access_token_expires_at, linkedAt + testTokens.access_expires_in + 1 + 28_800);
  } finally { db.close(); }
});

test("GitHub OAuth code exchange keeps the client secret server-side and returns expiring tokens for encrypted storage", async () => {
  assert.equal(githubAppOAuthConfigured(env), true);
  assert.equal(githubAppOwnerConnectionConfigured(env), true);
  assert.equal(githubAppOwnerConnectionConfigured({ ...env, GITHUB_APP_TOKEN_ENCRYPTION_KEY: "short" }), false);
  let request;
  const verifier = "a".repeat(43);
  const token = await exchangeGithubOAuthCode(env, "one-time-code", verifier, { fetchImpl: async (url, init) => {
    request = { url: String(url), init };
    return mockResponse({ access_token: testTokens.access_token, refresh_token: testTokens.refresh_token,
      expires_in: testTokens.access_expires_in, refresh_token_expires_in: testTokens.refresh_expires_in,
      token_type: "bearer", scope: "" });
  } });
  assert.deepEqual(token, testTokens);
  assert.equal(request.url, "https://github.com/login/oauth/access_token");
  const body = new URLSearchParams(request.init.body);
  assert.equal(body.get("client_secret"), env.GITHUB_APP_CLIENT_SECRET);
  assert.equal(body.get("redirect_uri"), env.GITHUB_APP_OAUTH_CALLBACK_URL);
  assert.equal(body.get("code_verifier"), verifier);
});

test("installation verification and repository listing never return app credentials", async () => {
  const responses = [
    { id: 98765, account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
      permissions: { contents: "read", metadata: "read" } },
    { token: "ghs-list-token", expires_at: new Date(Date.now() + 60_000).toISOString(),
      permissions: { contents: "read", metadata: "read" } },
    { total_count: 1, repositories: [{ id: 7, full_name: "Unjuno/model-as-a-paper", private: false, default_branch: "main" }] },
  ];
  const seen = [];
  const fetchImpl = async (url, init) => {
    seen.push({ url: String(url), headers: { ...init.headers }, body: init.body });
    return mockResponse(responses.shift());
  };
  const installation = await verifyGithubInstallation(env, "98765", { now: 1_800_000_000, fetchImpl });
  const repositories = await listGithubInstallationRepositories(env, "98765", { now: 1_800_000_000, fetchImpl });
  assert.deepEqual(installation, { id: "98765", account: { login: "Unjuno" },
    repository_selection: "selected", permissions: { contents: "read", metadata: "read" }, suspended_at: null });
  assert.deepEqual(repositories, [{ id: "7", repository: "unjuno/model-as-a-paper", private: false, default_branch: "main" }]);
  assert.equal(seen[0].url, "https://api.github.com/app/installations/98765");
  assert.equal(seen[2].url, "https://api.github.com/installation/repositories?per_page=25&page=1");
  assert.equal(JSON.stringify([installation, repositories]).includes("ghs-"), false);
});

test("installation repository listing keeps response pages bounded for large accounts", async () => {
  const seen = [];
  const repositories = Array.from({ length: 60 }, (_, index) => ({ id: index + 1,
    full_name: `Unjuno/repo-${index + 1}`, private: true, default_branch: "main",
    description: "d".repeat(350) }));
  const fetchImpl = async (url) => {
    const parsed = new URL(url);
    seen.push(parsed.toString());
    if (parsed.pathname.endsWith("/access_tokens")) return mockResponse({ token: "ghs-list-token",
      expires_at: new Date(Date.now() + 60_000).toISOString(),
      permissions: { contents: "read", metadata: "read" } });
    const page = Number(parsed.searchParams.get("page"));
    const start = (page - 1) * 25;
    return mockResponse({ total_count: repositories.length, repositories: repositories.slice(start, start + 25) });
  };
  const listed = await listGithubInstallationRepositories(env, "98765", { fetchImpl });
  assert.equal(listed.length, 60);
  assert.deepEqual(seen.slice(1).map((url) => new URL(url).search), [
    "?per_page=25&page=1", "?per_page=25&page=2", "?per_page=25&page=3",
  ]);
});
