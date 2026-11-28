import assert from "node:assert/strict";
import { generateKeyPairSync, randomBytes } from "node:crypto";
import test from "node:test";
import { createGithubOAuthRoutes } from "./github_oauth_routes.js";

const { privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const privatePem = privateKey.export({ type: "pkcs8", format: "pem" });
const env = {
  DB: { prepare() { return { bind() { return { first: async () => null }; } }; } },
  GITHUB_APP_ID: "12345",
  GITHUB_APP_SLUG: "gpu-control-source",
  GITHUB_APP_PRIVATE_KEY: privatePem,
  GITHUB_APP_CLIENT_ID: "Iv1.client-id",
  GITHUB_APP_CLIENT_SECRET: "github-app-client-secret-for-tests",
  GITHUB_APP_TOKEN_ENCRYPTION_KEY: randomBytes(32).toString("base64url"),
  GITHUB_APP_OAUTH_CALLBACK_URL: "https://gpu-control.example/github/oauth/callback",
};

function htmlPage(title, _content, status = 200) {
  return new Response(title, { status, headers: { "content-type": "text/html", "cache-control": "no-store" } });
}

const routes = createGithubOAuthRoutes({ htmlPage, escapeHtml: (value) => String(value) });

test("GitHub OAuth setup accepts only GET", async () => {
  const response = await routes.setup(new Request("https://gpu-control.example/github/setup", { method: "POST" }), {});
  assert.equal(response.status, 405);
});

test("invalid GitHub callback state is rejected and clears the one-time cookie", async () => {
  const response = await routes.callback(new Request("https://gpu-control.example/github/oauth/callback?state=invalid&code=ignored", {
    headers: { cookie: "__Host-gpu-control-oauth=invalid.verifier" },
  }), env);
  assert.equal(response.status, 400);
  assert.match(response.headers.get("set-cookie") || "", /__Host-gpu-control-oauth=; Max-Age=0/);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
});
