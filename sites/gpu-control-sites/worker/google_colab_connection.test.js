import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { createHash, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  beginGoogleColabOAuth, completeGoogleColabOAuth, createGoogleColabConnectionUrl,
  disconnectGoogleColab, googleColabAccessToken, googleColabConnectionConfigured,
  googleColabConnectionStatus, googleColabOAuthConfigured,
} from "./google_colab_connection.js";

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
  return {
    prepare(sql) { return { bind(...values) {
      const statement = sqlite.prepare(sql);
      return { run: async () => statement.run(...values), first: async () => statement.get(...values),
        all: async () => ({ results: statement.all(...values) }) };
    } }; },
    close: () => sqlite.close(),
  };
}

function response(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json" } });
}

async function begin(db, owner = "chat-owner", now = 1_800_000_000) {
  const link = await createGoogleColabConnectionUrl(db, owner, now);
  const setupState = new URL(link.authorization_url).searchParams.get("state");
  const started = await beginGoogleColabOAuth(db, setupState, env, now + 1);
  const authorization = new URL(started.authorization_url);
  const [cookieName, cookieValue] = started.pkce_cookie.split(";")[0].split("=");
  const [cookieState, verifier] = cookieValue.split(".");
  assert.equal(cookieName, "__Host-gpu-control-colab-oauth");
  assert.equal(authorization.searchParams.get("state"), cookieState);
  assert.equal(authorization.searchParams.get("code_challenge_method"), "S256");
  assert.equal(authorization.searchParams.get("code_challenge"),
    createHash("sha256").update(verifier).digest("base64url"));
  assert.deepEqual(authorization.searchParams.get("scope").split(" ").sort(),
    ["email", "openid", colabScope].sort());
  assert.equal(authorization.searchParams.get("access_type"), "offline");
  return { state: cookieState, verifier, now: now + 2 };
}

test("Google Colab OAuth configuration binds an HTTPS callback and 256-bit token-encryption key", () => {
  assert.equal(googleColabOAuthConfigured(env), true);
  assert.equal(googleColabConnectionConfigured(env), true);
  assert.equal(googleColabOAuthConfigured({ ...env, GOOGLE_COLAB_OAUTH_CALLBACK_URL: "https://evil.example/callback" }), false);
  assert.equal(googleColabConnectionConfigured({ ...env, GOOGLE_COLAB_TOKEN_ENCRYPTION_KEY: "short" }), false);
});

test("connection proves Google identity, encrypts the refresh token, refreshes access, and disconnects owner-only", async () => {
  const db = database();
  const rawRefreshToken = "google-refresh-token-sensitive-test";
  try {
    const flow = await begin(db);
    const linked = await completeGoogleColabOAuth(db, env, flow.state, flow.verifier, "one-time-code", {
      now: flow.now,
      fetchImpl: async (url, init) => {
        if (String(url) === "https://oauth2.googleapis.com/token") {
          assert.equal(init.method, "POST");
          const body = new URLSearchParams(init.body);
          assert.equal(body.get("client_secret"), env.GOOGLE_COLAB_OAUTH_CLIENT_SECRET);
          assert.equal(body.get("code_verifier"), flow.verifier);
          return response({ access_token: "google-access-token", refresh_token: rawRefreshToken,
            expires_in: 3600, scope: "openid email " + colabScope });
        }
        assert.equal(String(url), "https://openidconnect.googleapis.com/v1/userinfo");
        assert.equal(init.headers.authorization, "Bearer google-access-token");
        return response({ sub: "google-subject-1", email: "owner@example.com", email_verified: true });
      },
    });
    assert.deepEqual(linked, { connected: true, account_email: "owner@example.com", connected_at: flow.now });
    const stored = await db.prepare("SELECT * FROM google_colab_accounts WHERE owner_id=?").bind("chat-owner").first();
    assert.notEqual(stored.refresh_token_ciphertext, rawRefreshToken);
    assert.notEqual(stored.refresh_token_ciphertext, Buffer.from(rawRefreshToken).toString("base64url"));
    assert.equal(stored.refresh_token_iv.length, 16);
    assert.deepEqual(await googleColabConnectionStatus(db, "chat-owner"),
      { connected: true, account_email: "owner@example.com", connected_at: flow.now });
    assert.deepEqual(await googleColabConnectionStatus(db, "other-owner"), { connected: false });

    const access = await googleColabAccessToken(db, env, "chat-owner", { fetchImpl: async (url, init) => {
      assert.equal(String(url), "https://oauth2.googleapis.com/token");
      const body = new URLSearchParams(init.body);
      assert.equal(body.get("refresh_token"), rawRefreshToken);
      return response({ access_token: "fresh-short-lived-access-token", refresh_token: "rotated-refresh-token-123",
        expires_in: 3600, scope: colabScope });
    } });
    assert.equal(access.access_token, "fresh-short-lived-access-token");
    assert.equal(access.google_subject_id, "google-subject-1");
    await googleColabAccessToken(db, env, "chat-owner", { fetchImpl: async (url, init) => {
      const body = new URLSearchParams(init.body);
      assert.equal(body.get("refresh_token"), "rotated-refresh-token-123");
      return response({ access_token: "fresh-after-rotation", expires_in: 3600, scope: colabScope });
    } });

    await assert.rejects(googleColabAccessToken(db, env, "other-owner"), { message: "GOOGLE_COLAB_CONNECTION_REQUIRED" });
    const disconnected = await disconnectGoogleColab(db, env, "chat-owner", {
      fetchImpl: async (url, init) => {
        assert.equal(String(url), "https://oauth2.googleapis.com/revoke");
        assert.equal(new URLSearchParams(init.body).get("token"), "rotated-refresh-token-123");
        return new Response(null, { status: 200 });
      },
    });
    assert.deepEqual(disconnected, { disconnected: true, remote_revoked: true });
    assert.deepEqual(await googleColabConnectionStatus(db, "chat-owner"), { connected: false });
  } finally { db.close(); }
});

test("OAuth state is owner-bound, single-use and invalid scopes never create a connection", async () => {
  const db = database();
  try {
    const flow = await begin(db, "owner-a");
    await assert.rejects(completeGoogleColabOAuth(db, env, flow.state, flow.verifier, "one-time-code", {
      now: flow.now,
      fetchImpl: async () => response({ access_token: "token", refresh_token: "refresh", expires_in: 3600, scope: "openid email" }),
    }), { message: "GOOGLE_COLAB_OAUTH_SCOPE_INVALID" });
    assert.deepEqual(await googleColabConnectionStatus(db, "owner-a"), { connected: false });
    await assert.rejects(completeGoogleColabOAuth(db, env, flow.state, flow.verifier, "one-time-code"),
      { message: "GOOGLE_COLAB_CONNECTION_STATE_REPLAYED" });
    assert.deepEqual(await googleColabConnectionStatus(db, "owner-b"), { connected: false });
  } finally { db.close(); }
});

test("OAuth response parsing is bounded and a connected owner must disconnect before changing Google identity", async () => {
  const db = database();
  try {
    const flow = await begin(db);
    const tokenResponse = (subject) => async (url) => String(url) === "https://oauth2.googleapis.com/token"
      ? response({ access_token: "google-access-token", refresh_token: "google-refresh-token-123",
        expires_in: 3600, scope: "openid email " + colabScope })
      : response({ sub: subject, email: "owner@example.com", email_verified: true });
    await completeGoogleColabOAuth(db, env, flow.state, flow.verifier, "one-time-code", {
      now: flow.now, fetchImpl: tokenResponse("google-subject-1"),
    });

    const second = await begin(db);
    await assert.rejects(completeGoogleColabOAuth(db, env, second.state, second.verifier, "second-code", {
      now: second.now, fetchImpl: tokenResponse("google-subject-2"),
    }), { message: "GOOGLE_COLAB_RECONNECT_REQUIRES_DISCONNECT" });
    assert.equal((await googleColabConnectionStatus(db, "chat-owner")).account_email, "owner@example.com");

    const oversized = await begin(db, "oversized-owner");
    await assert.rejects(completeGoogleColabOAuth(db, env, oversized.state, oversized.verifier, "oversized-code", {
      now: oversized.now, fetchImpl: async () => new Response("x".repeat(20_000), {
        headers: { "content-type": "application/json" },
      }),
    }), { message: "GOOGLE_COLAB_OAUTH_RESPONSE_INVALID" });
    assert.deepEqual(await googleColabConnectionStatus(db, "oversized-owner"), { connected: false });
  } finally { db.close(); }
});
