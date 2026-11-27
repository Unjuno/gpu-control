import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { generateKeyPairSync, createVerify } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  bindGithubInstallation,
  createGithubAppJwt,
  createGithubInstallationToken,
  createGithubInstallationUrl,
  disconnectGithubApp,
  githubConnectionStatus,
  listGithubInstallationRepositories,
  verifyGithubInstallation,
} from "./github_app_connection.js";

const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const privatePem = privateKey.export({ type: "pkcs8", format: "pem" });
const env = { GITHUB_APP_ID: "12345", GITHUB_APP_SLUG: "gpu-control-source",
  GITHUB_APP_PRIVATE_KEY: privatePem };

function database() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(readFileSync(new URL("../drizzle/0030_github_app_connections.sql", import.meta.url), "utf8"));
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

test("install callback binds one owner only after checking selected-repository read-only scope", async () => {
  const db = database();
  try {
    const intent = await createGithubInstallationUrl(db, "site-owner", env.GITHUB_APP_SLUG, 1_800_000_000);
    const state = new URL(intent.authorization_url).searchParams.get("state");
    const linked = await bindGithubInstallation(db, state, "98765", async (id) => ({ id: Number(id),
      account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
      permissions: { contents: "read", metadata: "read" } }), 1_800_000_030);
    assert.deepEqual(linked, { connected: true, account_login: "Unjuno", repository_selection: "selected" });
    assert.deepEqual(await githubConnectionStatus(db, "site-owner"), { connected: true,
      account_login: "Unjuno", repository_selection: "selected", connected_at: 1_800_000_030 });
    await assert.rejects(bindGithubInstallation(db, state, "98765", async () => ({}), 1_800_000_031),
      { message: "GITHUB_INSTALLATION_STATE_REPLAYED" });
    await assert.rejects(disconnectGithubApp(db, "site-owner").then(async () =>
      bindGithubInstallation(db, state, "98765", async () => ({}), 1_800_000_032)),
    { message: "GITHUB_INSTALLATION_STATE_REPLAYED" });
    await disconnectGithubApp(db, "site-owner");
    assert.deepEqual(await githubConnectionStatus(db, "site-owner"), { connected: false });
  } finally { db.close(); }
});

test("installation must be selected, unsuspended and contents-read only", async () => {
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
      await assert.rejects(bindGithubInstallation(db, state, "4", async () => installation, 1_800_000_001),
        { message: "GITHUB_INSTALLATION_SCOPE_INVALID" });
      assert.deepEqual(await githubConnectionStatus(db, "site-owner"), { connected: false });
    }
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
  assert.deepEqual(JSON.parse(request.init.body), { repositories: ["Unjuno/model-as-a-paper"],
    permissions: { contents: "read", metadata: "read" } });
  assert.match(request.init.headers.authorization, /^Bearer [A-Za-z0-9_.-]+$/);
});

test("installation verification and repository listing never return app credentials", async () => {
  const responses = [
    { id: 98765, account: { login: "Unjuno" }, repository_selection: "selected", suspended_at: null,
      permissions: { contents: "read", metadata: "read" } },
    { token: "ghs-list-token", expires_at: new Date(Date.now() + 60_000).toISOString(),
      permissions: { contents: "read", metadata: "read" } },
    { total_count: 1, repositories: [{ full_name: "Unjuno/model-as-a-paper", private: false, default_branch: "main" }] },
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
  assert.deepEqual(repositories, [{ repository: "unjuno/model-as-a-paper", private: false, default_branch: "main" }]);
  assert.equal(seen[0].url, "https://api.github.com/app/installations/98765");
  assert.equal(seen[2].url, "https://api.github.com/installation/repositories?per_page=100&page=1");
  assert.equal(JSON.stringify([installation, repositories]).includes("ghs-"), false);
});
